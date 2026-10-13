# Medical imaging subsets (Brain CT, Chest CT, Chest X-ray)

This project downloads three Kaggle datasets as ZIP files and extracts only a
small number of **subjects (patients)** from each, which by default is 10.
The full ZIPs are never extracted. The scripts read each ZIP's table of
contents and copy out only the files they need.

## Folder structure

```
project/
  brain_ct/
    computed-tomography-ct-images.zip      <- downloaded zip (kept as-is)
    subset_10/
      049/brain/1.jpg ... 049/bone/1.jpg   <- one folder per patient, all slices together
      050/ ...
      _dataset_info/                       <- labels, license, README from the zip
      metadata.csv                         <- one row per patient
  chest_ct/      (same layout)
  chest_xray/    (same layout)
  scripts/
    config.yaml          <- which datasets to use and how to find patient IDs
    run_all.py           <- ONE command that runs everything
    download.py          <- step 1: download zips (with retries)
    extract_subset.py    <- step 2: extract N subjects per dataset
    verify.py            <- step 3: open some files, save previews
    utils.py             <- shared helpers (paths, logging, image reading)
  logs/
    run.log              <- everything that happened
    <dataset>_preview.png
  kaggle.json            <- your API key (secret! do not share)
```

## Datasets used

| Folder | Kaggle dataset | What it is | Subject ID comes from |
|---|---|---|---|
| brain_ct | `vbookshelf/computed-tomography-ct-images` | PhysioNet CT-ICH: 82 head CT scans as JPG slices (brain and bone windows) plus hemorrhage masks. CC BY 4.0. | Patient folder `Patients_CT/049/` |
| chest_ct | `maedemaftouni/covid19-ct-scan-lesion-segmentation-dataset` | COVID-19 lung CT slices (PNG) plus lesion masks | File name `<case>_<slice>.png` |
| chest_xray | `paultimothymooney/chest-xray-pneumonia` | Pediatric chest X-rays, NORMAL and PNEUMONIA (JPEG) | File name `person1_...` / `IM-0115-...` |

## Setup (once)

```bash
pip install kaggle tqdm pydicom nibabel pillow pandas pyyaml numpy
```

**Kaggle API token:** on kaggle.com, go to your profile picture, then
**Settings**, then **API**, then **Create New Token**. This downloads
`kaggle.json`. Put that file in `C:\Users\<you>\.kaggle\kaggle.json`, or in this
`project/` folder. The scripts find it in either place.

## Run everything

```bash
cd project
python scripts/run_all.py --n 10
```

At the end it prints a summary table (dataset, zip size, subjects, files, folder).
If the zips are already downloaded, they are not downloaded again.

### Useful options

```bash
python scripts/run_all.py --n 5                  # 5 subjects per dataset
python scripts/run_all.py --n 10 --seed 42       # random (but repeatable) 10 subjects
python scripts/run_all.py --skip-download        # use zips already on disk

python scripts/extract_subset.py --only chest_ct --inspect   # just show what is inside a zip
python scripts/verify.py --n 10                               # re-check the extracted files
```

By default the **first** N subjects are taken, sorted by ID. Add `--seed <number>`
to take a random sample instead. The same seed always gives the same subjects.
For the X-rays, sorted IDs put all NORMAL patients (`IM-...`) before PNEUMONIA
patients (`person...`), so use `--seed` if you want both classes.

## Changing the datasets

Edit `scripts/config.yaml`:

- `slug`: the Kaggle dataset ID, which is the part of the URL after `kaggle.com/datasets/`.
- `subject_regex`: a regular expression that finds the patient ID in each file
  path inside the zip. The first `( ... )` group is the ID. Set it to `""` if the
  dataset has no patient IDs; then every image counts as one subject.
- `slice_regex` (optional): which files count as slices in `metadata.csv`, so
  that masks and extra windows are not counted.
- `exclude_regex` (optional): paths inside the zip to ignore. The X-ray zip
  contains a duplicate copy of every image under `chest_xray/chest_xray/`.

Tip: run `python scripts/extract_subset.py --only <name> --inspect` to see the
zip's folders and how many subjects your regex finds before extracting.

## metadata.csv columns

| column | meaning |
|---|---|
| subject_id | patient / subject ID |
| n_files | all files extracted for this subject (slices, masks, other windows) |
| n_slices | number of image slices (see `slice_regex`); for X-rays, number of images |
| image_size | shape of one image, e.g. `650x650` (`HxW`, or `HxWxC` for color) |
| format | JPEG / PNG / DICOM / NIfTI |
| file_paths | `;`-separated paths, relative to the `subset_N/` folder |

## Notes

- Downloads retry up to 3 times (set `download_retries` in `config.yaml`).
  An interrupted download resumes where it stopped.
- Corrupt files inside a zip are skipped and logged. If one dataset fails, the
  others still run.
- Running again with the same N replaces the old `subset_N/` folder.
- Check each dataset's license on its Kaggle page before you publish results.
