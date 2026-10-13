"""Check that the extracted files can actually be opened, and save one
preview image per dataset into logs/.

Usage:
    python scripts/verify.py --n 10
"""

import argparse
import csv
import re
from pathlib import Path

import numpy as np
from PIL import Image

from utils import LOGS_DIR, PROJECT_DIR, image_format, load_config, read_image, setup_logging

log = setup_logging()


def to_uint8(array):
    """Scale any image to 0-255 so it can be saved as a PNG preview."""
    a = array.astype(np.float32)
    lo, hi = np.percentile(a, 1), np.percentile(a, 99)
    if hi <= lo:
        hi = lo + 1
    return (np.clip((a - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)


def to_2d(array):
    """Pick something viewable: the middle slice of a 3D volume, or the image itself."""
    if array.ndim == 3 and array.shape[-1] in (3, 4):  # RGB(A) photo-style image
        return array[..., :3]
    if array.ndim == 3:  # CT volume: take the middle slice along the last axis
        return np.rot90(array[:, :, array.shape[2] // 2])
    return array


def pick_samples(subset_dir, slice_regex="", k=3):
    """A few files from the subset. The first one is the middle slice of the
    first subject (used for the preview); then one file of each format."""
    with open(subset_dir / "metadata.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    all_files = [subset_dir / p for r in rows for p in r["file_paths"].split(";") if p]

    first = [subset_dir / p for p in rows[0]["file_paths"].split(";") if p]
    slices = [p for p in first if re.search(slice_regex, p.as_posix())] if slice_regex else first
    samples = [slices[len(slices) // 2]] if slices else []
    seen_formats = {image_format(str(p)) for p in samples}
    for f in all_files:  # first: one file of every format
        if image_format(str(f)) not in seen_formats:
            samples.append(f)
            seen_formats.add(image_format(str(f)))
    for f in all_files:  # then: fill up to k files
        if len(samples) >= k:
            break
        if f not in samples:
            samples.append(f)
    return samples


def verify_dataset(ds, n):
    """Open a few files of one dataset; save a preview. Returns # of readable files."""
    subset_dir = PROJECT_DIR / ds["folder"] / f"subset_{n}"
    if not (subset_dir / "metadata.csv").exists():
        log.error(f"[{ds['name']}] no subset found at {subset_dir}")
        return 0

    ok, preview_saved = 0, False
    for path in pick_samples(subset_dir, ds.get("slice_regex", "")):
        try:
            arr = read_image(path)
        except Exception as e:
            log.warning(f"[{ds['name']}] cannot read {path.name}: {e}")
            continue
        ok += 1
        log.info(f"[{ds['name']}] {image_format(str(path)):6} {path.relative_to(subset_dir)}"
                 f"  shape={arr.shape} dtype={arr.dtype} min={arr.min()} max={arr.max()}")
        if not preview_saved:
            out = LOGS_DIR / f"{ds['name']}_preview.png"
            Image.fromarray(to_uint8(to_2d(arr))).save(out)
            log.info(f"[{ds['name']}] preview saved -> {out}")
            preview_saved = True
    return ok


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    cfg = load_config()
    parser.add_argument("--n", type=int, default=cfg["defaults"]["n_subjects"])
    args = parser.parse_args()
    for ds in cfg["datasets"]:
        verify_dataset(ds, args.n)


if __name__ == "__main__":
    main()
