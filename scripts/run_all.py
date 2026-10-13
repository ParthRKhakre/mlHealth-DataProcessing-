"""One command for the whole pipeline:

    python scripts/run_all.py --n 10

Steps: check credentials -> download zips -> extract N subjects per
dataset -> verify the files open -> print a summary table.
A failure in one dataset is logged and the others still run.
"""

import argparse

from download import download_dataset
from extract_subset import extract_subset
from utils import PROJECT_DIR, has_kaggle_credentials, load_config, pick_seed, setup_logging
from verify import verify_dataset

log = setup_logging()


def print_summary(results):
    """Print a simple text table of what was extracted."""
    header = f"{'dataset':<12} {'zip size':>10} {'subjects':>9} {'files':>7}  folder"
    print("\n" + "=" * len(header) + "\nSUMMARY\n" + header + "\n" + "-" * len(header))
    for r in results:
        if r.get("subjects") is None:
            print(f"{r['dataset']:<12} {'-':>10} {'FAILED':>9} {'-':>7}  {r.get('error', '')}")
        else:
            print(f"{r['dataset']:<12} {r['zip_mb']:>7.0f} MB {r['subjects']:>9} "
                  f"{r['files']:>7}  {r['folder'].relative_to(PROJECT_DIR)}")
    print("=" * len(header))


def main():
    cfg = load_config()
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, default=cfg["defaults"]["n_subjects"],
                        help="subjects per dataset (default 10)")
    parser.add_argument("--seed", type=int, default=None,
                        help="random seed for all datasets (overrides config.yaml)")
    parser.add_argument("--skip-download", action="store_true",
                        help="use zips that are already on disk")
    args = parser.parse_args()

    if not args.skip_download and not has_kaggle_credentials():
        log.error("No Kaggle credentials found. Put kaggle.json in ~/.kaggle/ "
                  "(or in the project folder). See README.md.")
        return

    results = []
    for ds in cfg["datasets"]:
        name = ds["name"]
        log.info(f"========== {name} ({ds['slug']}) ==========")
        try:
            if not args.skip_download:
                if download_dataset(ds["slug"], PROJECT_DIR / ds["folder"],
                                    cfg["defaults"].get("download_retries", 3)) is None:
                    results.append({"dataset": name, "error": "download failed"})
                    continue
            summary = extract_subset(ds, args.n, pick_seed(args.seed, ds, cfg))
            if summary is None:
                results.append({"dataset": name, "error": "extraction failed"})
                continue
            verify_dataset(ds, args.n)
            results.append(summary)
        except Exception as e:  # never crash the whole run because of one dataset
            log.exception(f"[{name}] unexpected error")
            results.append({"dataset": name, "error": str(e)})

    print_summary(results)


if __name__ == "__main__":
    main()
