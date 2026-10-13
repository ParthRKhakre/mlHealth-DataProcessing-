"""Small helpers shared by all scripts: paths, config loading, logging."""

import logging
import os
from pathlib import Path

import yaml

# Folder layout:  project/scripts/utils.py  ->  PROJECT_DIR = project/
SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPTS_DIR.parent
LOGS_DIR = PROJECT_DIR / "logs"
CONFIG_PATH = SCRIPTS_DIR / "config.yaml"

# File extensions we treat as medical images
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".dcm", ".nii", ".nii.gz", ".mhd")


def load_config(path=CONFIG_PATH):
    """Read config.yaml and return it as a Python dict."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def setup_logging(name="pipeline"):
    """Log to the screen AND to logs/run.log."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOGS_DIR / "run.log", encoding="utf-8"),
        ],
    )
    return logging.getLogger(name)


def use_project_kaggle_json():
    """If kaggle.json sits in the project folder (and not in ~/.kaggle),
    tell the Kaggle tool to look there via KAGGLE_CONFIG_DIR."""
    home_json = Path.home() / ".kaggle" / "kaggle.json"
    project_json = PROJECT_DIR / "kaggle.json"
    if not home_json.exists() and project_json.exists():
        os.environ.setdefault("KAGGLE_CONFIG_DIR", str(PROJECT_DIR))


def has_kaggle_credentials():
    """True if any supported form of Kaggle credentials is available."""
    use_project_kaggle_json()
    config_dir = Path(os.environ.get("KAGGLE_CONFIG_DIR", Path.home() / ".kaggle"))
    return (
        (config_dir / "kaggle.json").exists()
        or (config_dir / "access_token").exists()
        or ("KAGGLE_USERNAME" in os.environ and "KAGGLE_KEY" in os.environ)
        or "KAGGLE_API_TOKEN" in os.environ
    )


def pick_seed(cli_seed, ds, cfg):
    """Which seed to use for one dataset: --seed on the command line wins,
    then a "seed" set on that dataset in config.yaml, then defaults.seed."""
    if cli_seed is not None:
        return cli_seed
    return ds.get("seed", cfg["defaults"].get("seed"))


def is_image(path):
    """True if the path ends with one of our image extensions."""
    return path.lower().endswith(IMAGE_EXTS)


def image_format(path):
    """Return a short format name such as 'PNG', 'JPEG', 'DICOM', 'NIfTI'."""
    p = path.lower()
    if p.endswith((".nii", ".nii.gz")):
        return "NIfTI"
    if p.endswith(".dcm"):
        return "DICOM"
    if p.endswith((".jpg", ".jpeg")):
        return "JPEG"
    if p.endswith(".png"):
        return "PNG"
    if p.endswith(".mhd"):
        return "MetaImage"
    return Path(p).suffix.upper().lstrip(".")


def read_image(path):
    """Open one medical image file and return it as a numpy array.
    Supports NIfTI (.nii/.nii.gz), DICOM (.dcm) and normal images (.png/.jpg).
    Raises an exception if the file cannot be read."""
    import numpy as np

    fmt = image_format(str(path))
    if fmt == "NIfTI":
        import nibabel as nib
        return np.asarray(nib.load(str(path)).dataobj)
    if fmt == "DICOM":
        import pydicom
        return pydicom.dcmread(str(path)).pixel_array
    if fmt in ("PNG", "JPEG"):
        from PIL import Image
        with Image.open(path) as img:
            return np.array(img)
    raise ValueError(f"Don't know how to read {fmt} files: {path}")
