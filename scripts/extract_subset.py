"""Extract only N subjects (patients) from each dataset ZIP.

The ZIP is never fully extracted: we read its table of contents
(zf.namelist(), which is fast), group the files by subject ID, pick N
subjects, and copy out only their files.

Usage:
    python scripts/extract_subset.py                       # all datasets, N=10
    python scripts/extract_subset.py --n 5 --seed 42       # 5 random subjects
    python scripts/extract_subset.py --only brain_ct --inspect   # just show the zip layout
"""

import argparse
import csv
import random
import re
import shutil
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

from utils import (PROJECT_DIR, image_format, is_image, load_config,
                   read_image, setup_logging)

log = setup_logging()

# Small non-image files (labels, licenses, CSVs) worth copying alongside the subset
INFO_EXTS = (".csv", ".txt", ".xlsx", ".json", ".md")
MAX_INFO_FILE_BYTES = 50 * 1024 * 1024  # skip anything bigger than 50 MB


# ------------------------------------------------------------------
# 1. Look inside the zip
# ------------------------------------------------------------------
def list_zip_files(zf, exclude_regex=""):
    """All real files in the zip (skip folders, macOS junk like __MACOSX/._x,
    and anything matching exclude_regex, e.g. a duplicate copy of the data)."""
    files = []
    for info in zf.infolist():
        name = info.filename
        if info.is_dir() or "__MACOSX" in name or PurePosixPath(name).name.startswith("."):
            continue
        if exclude_regex and re.search(exclude_regex, name):
            continue
        files.append(info)
    return files


def describe_zip(files, name):
    """Print a short summary of how the zip is organised."""
    exts = Counter(PurePosixPath(f.filename).suffix.lower() for f in files)
    # Count files per folder (up to two levels deep) so we can see the structure
    folders = Counter("/".join(f.filename.split("/")[:-1][:2]) or "(top level)" for f in files)
    total_gb = sum(f.file_size for f in files) / 1e9
    log.info(f"[{name}] {len(files)} files, {total_gb:.2f} GB uncompressed")
    log.info(f"[{name}] file types: {dict(exts.most_common(8))}")
    for folder, count in folders.most_common(8):
        log.info(f"[{name}]   {folder}/ ... {count} files")


# ------------------------------------------------------------------
# 2. Group files by subject / patient
# ------------------------------------------------------------------
def group_by_subject(files, subject_regex):
    """Return {subject_id: [ZipInfo, ...]} for every image file.

    If subject_regex is empty, every image is its own "subject"
    (useful for flat X-ray folders without patient IDs)."""
    groups = defaultdict(list)
    pattern = re.compile(subject_regex) if subject_regex else None
    for f in files:
        if not is_image(f.filename):
            continue
        if pattern:
            match = pattern.search(f.filename)
            if not match:
                continue  # file doesn't belong to any subject (e.g. a README image)
            subject = match.group(1)
        else:
            subject = PurePosixPath(f.filename).stem
        groups[subject].append(f)
    return groups


def natural_key(text):
    """Sort "slice2" before "slice10" (plain sorting would put 10 first)."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text)]


def choose_subjects(subject_ids, n, seed=None):
    """First N subjects in sorted order, or a reproducible random N if seed is set."""
    ids = sorted(subject_ids, key=natural_key)
    if seed is None:
        return ids[:n]
    return sorted(random.Random(seed).sample(ids, min(n, len(ids))), key=natural_key)


# ------------------------------------------------------------------
# 3. Extract only the chosen files
# ------------------------------------------------------------------
def common_prefix(files):
    """The top folder shared by every file, so we can drop it from output paths
    (keeps Windows paths short)."""
    parts = [f.filename.split("/")[:-1] for f in files]
    prefix = []
    for level in zip(*parts):
        if len(set(level)) != 1:
            break
        prefix.append(level[0])
    return "/".join(prefix) + "/" if prefix else ""


def extract_member(zf, info, dest_path):
    """Copy ONE file out of the zip. Returns True on success, False if corrupt."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zf.open(info) as src, open(dest_path, "wb") as dst:
            shutil.copyfileobj(src, dst)  # streams; also checks the CRC
        return True
    except (zipfile.BadZipFile, OSError, EOFError) as e:
        log.warning(f"  skipping corrupt file {info.filename}: {e}")
        dest_path.unlink(missing_ok=True)
        return False


def safe_dest(out_dir, rel_path):
    """Build the output path and make sure it stays inside out_dir."""
    dest = (out_dir / rel_path).resolve()
    if out_dir.resolve() not in dest.parents:
        raise ValueError(f"unsafe path in zip: {rel_path}")
    return dest


# ------------------------------------------------------------------
# 4. Metadata
# ------------------------------------------------------------------
def describe_subject(paths, slice_regex=""):
    """Return (n_slices, image_size, formats) for one subject's files.
    slice_regex (optional) decides which 2D files count as slices,
    so masks or duplicate windows are not counted twice."""
    formats = sorted({image_format(str(p)) for p in paths})
    volumes = [p for p in paths if image_format(str(p)) == "NIfTI"]
    slices_2d = [p for p in paths if image_format(str(p)) in ("PNG", "JPEG", "DICOM")]
    if slice_regex:
        slices_2d = [p for p in slices_2d if re.search(slice_regex, p.as_posix())]

    # Prefer a 3D volume (its depth = number of slices); else count 2D files
    sample = volumes[0] if volumes else (slices_2d[0] if slices_2d else None)
    image_size, n_slices = "", len(slices_2d)
    if sample is not None:
        try:
            shape = read_image(sample).shape
            image_size = "x".join(str(s) for s in shape)
            if volumes and len(shape) == 3:
                n_slices = shape[2]
        except Exception as e:  # unreadable file: record it but keep going
            log.warning(f"  could not read {sample.name}: {e}")
            image_size = "unreadable"
    return n_slices, image_size, "+".join(formats)


# ------------------------------------------------------------------
# Main routine for one dataset
# ------------------------------------------------------------------
def extract_subset(ds, n=10, seed=None, inspect_only=False):
    """Extract N subjects of one dataset. Returns a summary dict (or None)."""
    name = ds["name"]
    folder = PROJECT_DIR / ds["folder"]
    zips = sorted(folder.glob("*.zip"))
    if not zips:
        log.error(f"[{name}] no zip found in {folder} - run download first")
        return None
    zip_path = zips[0]

    try:
        zf = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile:
        log.error(f"[{name}] {zip_path.name} is not a valid zip - delete it and re-download")
        return None

    with zf:
        files = list_zip_files(zf, ds.get("exclude_regex", ""))
        describe_zip(files, name)
        groups = group_by_subject(files, ds.get("subject_regex", ""))
        log.info(f"[{name}] found {len(groups)} subjects")
        if inspect_only or not groups:
            if not groups:
                log.error(f"[{name}] no files matched subject_regex - check config.yaml")
            return None

        chosen = choose_subjects(groups.keys(), n, seed)
        log.info(f"[{name}] extracting {len(chosen)} subjects: {', '.join(chosen)}")

        out_dir = folder / f"subset_{n}"
        if out_dir.exists():
            shutil.rmtree(out_dir)  # start clean so old runs don't mix in
        out_dir.mkdir(parents=True)

        prefix = common_prefix(files)
        rows, n_files = [], 0
        for subject in chosen:
            # Each subject gets its own folder, so all of its slices stay together
            saved = []
            for info in sorted(groups[subject], key=lambda f: natural_key(f.filename)):
                rel = info.filename[len(prefix):]
                # ".../Patients_CT/049/bone/1.jpg" -> "049/bone/1.jpg" (no repeated ID)
                if f"/{subject}/" in "/" + rel:
                    rel = ("/" + rel).split(f"/{subject}/", 1)[1]
                dest = safe_dest(out_dir, Path(subject) / rel)
                if extract_member(zf, info, dest):
                    saved.append(dest)
            n_files += len(saved)
            n_slices, size, fmt = describe_subject(saved, ds.get("slice_regex", ""))
            rows.append({
                "subject_id": subject,
                "n_files": len(saved),
                "n_slices": n_slices,
                "image_size": size,
                "format": fmt,
                "file_paths": ";".join(p.relative_to(out_dir).as_posix() for p in saved),
            })
            log.info(f"  {subject}: {len(saved)} files, {n_slices} slices, size {size}")

        # Copy small dataset-level files (labels, license) into _dataset_info/
        for info in files:
            if info.filename.lower().endswith(INFO_EXTS) and info.file_size <= MAX_INFO_FILE_BYTES:
                rel = info.filename[len(prefix):]
                extract_member(zf, info, safe_dest(out_dir, Path("_dataset_info") / rel))

    csv_path = out_dir / "metadata.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    log.info(f"[{name}] wrote {csv_path}")

    return {
        "dataset": name,
        "zip_mb": zip_path.stat().st_size / 1e6,
        "subjects": len(rows),
        "files": n_files,
        "folder": out_dir,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    cfg = load_config()
    parser.add_argument("--n", type=int, default=cfg["defaults"]["n_subjects"],
                        help="number of subjects per dataset (default 10)")
    parser.add_argument("--seed", type=int, default=cfg["defaults"].get("seed"),
                        help="random seed; if omitted, the first N subjects (sorted) are used")
    parser.add_argument("--only", help="process just this dataset name")
    parser.add_argument("--inspect", action="store_true",
                        help="only print the zip layout and subject count")
    args = parser.parse_args()

    for ds in cfg["datasets"]:
        if args.only and ds["name"] != args.only:
            continue
        try:
            extract_subset(ds, args.n, args.seed, args.inspect)
        except Exception:
            log.exception(f"[{ds['name']}] failed - continuing with the next dataset")


if __name__ == "__main__":
    main()
