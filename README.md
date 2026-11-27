# Estimating flood damage at Lake Kivu

**SDS320 · Simon Rüegg · December 2026**

This project trains a deep-learning model to detect buildings on very high resolution satellite images and uses it to estimate how many buildings were destroyed by the floods and mudflows along the shoreline of Lake Kivu in late spring 2023. Buildings are detected on a pre-event and a post-event image. The two predictions are compared to find destroyed buildings, and the economic damage is estimated from the destroyed building area.

---

## Contents

1. [Project structure](#project-structure)
2. [Installation](#installation)
3. [Data](#data)
4. [Running the notebook](#running-the-notebook)
5. [Workflow](#workflow)
6. [Results](#results)
7. [Limitations](#limitations)
8. [References](#references)

---

## Project structure

```
SDS320/
├── README.md
├── environment.yml
├── notebooks/
│   ├── sds320_project.ipynb      # main notebook
│   └── functions/                # helper functions used in the notebook
│       ├── clip_tifs.py
│       ├── merge_tifs.py
│       └── raster_outline.py
├── data/
│   ├── raw/raster/               # Vantor images (not included, see "Data")
│   ├── processed/                # merged and clipped rasters, training/validation labels
│   ├── training/rgb/             # image and label tiles for training
│   └── validation/rgb/           # predictions on the validation area
├── GIS/                          # hand-drawn layers from QGIS (buildings, AOIs, control points)
├── models/rgb/                   # trained model (best_model.pth, training_history.pth)
└── results/                      # predictions, building status, threshold sensitivity
```

All paths in the notebook are relative (`../data/...`), so the notebook must be started from inside its own folder.

---

## Installation

The project uses a conda environment (tested with Python 3.12 on Windows).

```bash
conda env create -f environment.yml
conda activate sds320
```

Register the environment as a Jupyter kernel (optional):

```bash
python -m ipykernel install --user --name sds320 --display-name "Python (sds320)"
```

To update the environment after changing `environment.yml`:

```bash
conda env update -f environment.yml --prune
```

> **GPU:** training is much faster on a GPU. If you have an NVIDIA GPU, install a CUDA-enabled PyTorch build that matches your driver.

> **GDAL/PROJ on Windows:** the first code cell of the notebook sets `PATH`, `GDAL_DATA` and `PROJ_DATA` to the conda environment. Always run this cell first, otherwise the kernel may crash.

---

## Data

### Satellite images
The images come from **Vantor's Open Data Program**, which provides pre- and post-disaster imagery. A (free) Vantor account is needed to download them. This project uses the **visual (RGB)** images. Multispectral and panchromatic images of the same area and dates are also available.

Place the downloaded files in `data/raw/raster/`:

| File | Event |
|---|---|
| `10300100E57BC400-visual_pre_north.tif` | pre-event |
| `10300100E57BC400-visual_pre_south.tif` | pre-event |
| `1040010084614200-visual_post_north.tif` | post-event |
| `1040010084614200-visual_post_south.tif` | post-event |

### Vector data (`GIS/`)
No reliable building dataset exists for this area (Google's building dataset has low confidence here), so the reference buildings were **digitised by hand in QGIS**.

| File | Content |
|---|---|
| `buildings.gpkg` | hand-drawn reference buildings |
| `aoi_total_area.gpkg` | total area of interest |
| `aoi_training.gpkg` | training area |
| `aoi_validation.gpkg` | validation area (~4 km north of the training area) |
| `control_points.gpkg` | control points to align the pre- and post-event images |

---

## Running the notebook

1. Activate the environment and start Jupyter from the `notebooks/` folder.
2. Run the **set-up cell** (GDAL/PROJ paths) first.
3. Check the **switches** for the long-running steps.

### ⚠️ Switches for long-running steps

Training the model and running the predictions takes a long time. These steps are **skipped by default** and the saved results in `models/` and `results/` are used instead.

The switches are set in the configuration cell at the beginning of the notebook (section 1):

```python
RUN_TRAINING = False         # True → retrain the model
RUN_PREDICTION_PRE = False   # True → predict buildings on the pre-event image
RUN_PREDICTION_POST = False  # True → predict buildings on the post-event image
```

**Before you train the model or run a prediction, set the matching switch to `True`.** If the saved model or results do not exist yet (e.g. on a fresh clone), all three switches must be `True` on the first run.

---

## Workflow

| Section | Step |
|---|---|
| 1. Set up | GDAL/PROJ paths, imports, switches |
| 2. Data | load and merge the north/south tiles of the pre- and post-event images; load reference buildings |
| 3. Data processing | clip rasters to the total AOI, training and validation AOI; split buildings into training and validation set |
| 4. Train the model | rasterise labels, export 256 × 256 px tiles, train a Mask R-CNN instance segmentation model with `geoai.train_instance_segmentation_model()` (50 epochs) |
| 5. Validation | predict on the validation area, compute precision, recall, F1, mean IoU and PQ; post-processing (merge buildings split at tile borders, remove false positives along the lake shore) |
| 6. Apply the model | predict and post-process buildings on the whole pre- and post-event images |
| 7. Analysis | align pre- and post-event predictions (linear shift from control points), classify buildings as *standing* / *destroyed* by overlap threshold, estimate economic damage |

---

## Results

- With an overlap threshold of **1 %**, about **580 buildings** were classified as destroyed, with a total area of about **30,000 m²** (median building size ~45 m²).
- Depending on the building valuation used, the estimated damage to buildings is between **USD 680,000 and USD 3,870,000**:
  - RD Congo Cluster Abris: ~USD 20/m² material cost + 30 % labour and support (likely an underestimate)
  - Global Earthquake Model (OpenQuake): ~USD 130/m² (likely an overestimate, includes urban buildings)

Main output files in `results/`:

| File | Content |
|---|---|
| `prediction_pre.gpkg` / `prediction_post.gpkg` | post-processed building predictions |
| `buildings_overlap.gpkg` | overlap of each pre-event building with post-event buildings |
| `buildings_flood_status.gpkg` | building status (*standing* / *destroyed*) per threshold |
| `threshold_sensitivity.csv` | number and area of destroyed buildings for different thresholds |

---

## Limitations

- The result depends strongly on the chosen overlap threshold.
- Some false positives remain (tile artefacts, objects in the lake, AOI borders); the edge filter also removes a few true positives.
- The post-event prediction area includes the training area.
- Damaged land and infrastructure (roads, water supply, electricity) are not included in the damage estimate.

---

## References

- Vantor Open Data Program – pre- and post-event satellite imagery
- Global Earthquake Model – Exposure model DR Congo: https://docs.openquake.org/global_risk_model/exposure/Africa/Democratic_Republic_of_the_Congo/README.html
- RDC Cluster Abri & AME – Construction locale (Dec 2024): https://s3.eu-west-1.amazonaws.com/sheltercluster.org/public/docs/RDC%20Cluster%20Abri%26AME_Construction%20locale_VFDec2024.pdf
- geoai: https://opengeoai.org