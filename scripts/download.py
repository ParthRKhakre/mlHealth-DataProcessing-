"""Download each Kaggle dataset as a ZIP into its own folder (no unzipping).

Usage:
    python scripts/download.py                 # all datasets in config.yaml
    python scripts/download.py --only brain_ct # just one
"""

import argparse
import shutil
import subprocess
import time
import zipfile
from pathlib import Path

from utils import PROJECT_DIR, has_kaggle_credentials, load_config, setup_logging

log = setup_logging()


def find_zip(folder):
    """Return the .zip file in a folder (Kaggle names it after the dataset)."""
    zips = sorted(Path(folder).glob("*.zip"))
    return zips[0] if zips else None


def zip_is_ok(zip_path):
    """Quick check: can we open the zip and read its table of contents?
    (This does NOT read/extract the file data, so it is fast.)"""
    try:
        with zipfile.ZipFile(zip_path) as zf:
            return len(zf.namelist()) > 0
    except (zipfile.BadZipFile, OSError):
        return False


def download_dataset(slug, folder, retries=3):
    """Run `kaggle datasets download -d <slug> -p <folder>` with retries.
    Returns the path of the downloaded zip, or None on failure."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    existing = find_zip(folder)
    if existing and zip_is_ok(existing):
        log.info(f"[{slug}] already downloaded: {existing.name} - skipping")
        return existing

    kaggle_exe = shutil.which("kaggle")
    if kaggle_exe is None:
        log.error("The 'kaggle' command was not found. Run: pip install kaggle")
        return None

    cmd = [kaggle_exe, "datasets", "download", "-d", slug, "-p", str(folder)]
    for attempt in range(1, retries + 1):
        log.info(f"[{slug}] download attempt {attempt}/{retries}: {' '.join(cmd[1:])}")
        result = subprocess.run(cmd)  # progress bar is shown live
        zip_path = find_zip(folder)
        if result.returncode == 0 and zip_path and zip_is_ok(zip_path):
            size_mb = zip_path.stat().st_size / 1e6
            log.info(f"[{slug}] OK -> {zip_path} ({size_mb:.1f} MB)")
            return zip_path

        log.warning(f"[{slug}] download failed (exit code {result.returncode})")
        partial = zip_path and Path(str(zip_path) + ".kaggle-partial").exists()
        if zip_path and not partial and not zip_is_ok(zip_path):
            # Broken and not resumable -> delete so the next attempt starts fresh.
            # (If a .kaggle-partial marker exists, Kaggle will resume instead.)
            log.warning(f"[{slug}] removing broken zip {zip_path.name}")
            zip_path.unlink(missing_ok=True)
        time.sleep(5 * attempt)  # wait a bit longer after each failure

    log.error(f"[{slug}] giving up after {retries} attempts")
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="download just this dataset name (e.g. brain_ct)")
    args = parser.parse_args()

    if not has_kaggle_credentials():
        log.error("No Kaggle credentials found. See README.md > 'Kaggle API token'.")
        return

    cfg = load_config()
    retries = cfg["defaults"].get("download_retries", 3)
    for ds in cfg["datasets"]:
        if args.only and ds["name"] != args.only:
            continue
        download_dataset(ds["slug"], PROJECT_DIR / ds["folder"], retries)


if __name__ == "__main__":
    main()
