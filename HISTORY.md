# Project history

A record of what was done, what was decided and why, and what is still open,
so work can pick up where it stopped.

## Current state (13 October 2026)

- The pipeline works end to end: `python scripts/run_all.py --n 10` downloads,
  extracts and verifies all three datasets and reproduces the submitted subsets.
- The three zips are downloaded (3.3 GB) and the `subset_10/` folders are extracted (about 460 MB).
  Both are kept on disk only; `.gitignore` excludes them.
- A 2-page internship report was written: `../Internship_Report.docx` and `.pdf`.
  It is outside this repo on purpose.
- `kaggle.json` sits in this `project/` folder. It is git-ignored. Never commit it.

## Timeline

| Date | What happened |
|---|---|
| 2026-10-12 | Created the empty `mlHealth Data Processing` folder. |
| 2026-10-13 | Created the folder structure, installed packages, set up Kaggle credentials. |
| 2026-10-13 | Searched Kaggle and chose the three datasets (see below). |
| 2026-10-13 | Wrote `download.py`, `extract_subset.py`, `verify.py`, `run_all.py`, `utils.py`, `config.yaml` and the README. |
| 2026-10-13 | Downloaded all three zips and extracted 10 patients per dataset. |
| 2026-10-13 | Pushed to GitHub (commit `55fb99b`). |
| 2026-10-13 | Gave the X-ray dataset its own seed (42) so `run_all.py` reproduces the submitted subset (commit `8f1600f`). |
| 2026-10-13 | Wrote the 2-page internship report (Word and PDF). |

## Datasets chosen and why

| Folder | Kaggle slug | Why |
|---|---|---|
| brain_ct | `vbookshelf/computed-tomography-ct-images` | PhysioNet CT-ICH, 82 patients in per-patient folders, CC BY 4.0, small (95 MB). |
| chest_ct | `maedemaftouni/covid19-ct-scan-lesion-segmentation-dataset` | 71 patients; the patient ID is in each file name, so slices group by patient. |
| chest_xray | `paultimothymooney/chest-xray-pneumonia` | The most used chest X-ray dataset; patient IDs are in the file names. |

Rejected: `mohamedhanyyy/chest-ctscan-images` (no patient IDs),
`fanbyprinciple/luna-lung-cancer-dataset` (masks only, no CT scans),
`ozguraslank/brain-stroke-ct-dataset` (no patient grouping),
`nih-chest-xrays/sample` (4.5 GB, twice the size).

## Decisions and problems found

- **Never extract a full zip.** Files are listed with `zipfile` and only the chosen patients' files are copied out.
- **Patient IDs come from a regex per dataset** (`subject_regex` in `config.yaml`).
- **X-ray zip has a duplicate copy** of every image under `chest_xray/chest_xray/`, so it is skipped with `exclude_regex`.
- **Brain CT has three file types per patient:** brain-window slices, bone-window copies and `_HGE_Seg` masks.
  Only `brain/N.jpg` counts as a slice (`slice_regex`). Chest CT counts only `frames/`, not `masks/`.
- **The Kaggle copy of CT-ICH has JPGs only**, with no NIfTI files. The code can still read DICOM and NIfTI for other datasets.
- **X-ray class balance:** sorted IDs put all NORMAL (`IM-...`) before PNEUMONIA (`person...`), so the first 10 were all NORMAL.
  Fixed by `seed: 42` for chest_xray, which gives 7 NORMAL and 3 PNEUMONIA patients.
- **Seed rules:** `--seed` on the command line wins, then a dataset's own `seed`, then `defaults.seed` (null means the first N).

## Submitted results

| Dataset | Patients | Files | Slices per patient | Image size |
|---|---|---|---|---|
| brain_ct | 049 to 058 | 693 | 26 to 35 | 650×650 uint8 JPEG |
| chest_ct | bjorke, Jun_coronacases_case1 to case9 | 2,520 | 70 to 216 | 512×512×3 uint8 PNG |
| chest_xray | IM-0187, IM-0570, IM-0618, IM-0747, NORMAL2-IM-0623/0804/0950, person1309, person1761, person1823 | 13 | 1 to 3 | 217×467 to 1893×2292 uint8 JPEG |

## Open items and ideas

- [ ] Check X-ray `person1761`: it is much smaller (217×467) and in color, unlike the others.
- [ ] Optional: a class-balanced X-ray pick (for example 5 NORMAL and 5 PNEUMONIA).
- [ ] Confirm the author name in the report ("Parth R. Khakre" was guessed from the GitHub username).
- [ ] An unfinished online draft of the report exists on claude.ai and can be deleted if not needed.
- Next research steps could be preprocessing (resizing, windowing, normalising) or a first baseline model on these subsets.
