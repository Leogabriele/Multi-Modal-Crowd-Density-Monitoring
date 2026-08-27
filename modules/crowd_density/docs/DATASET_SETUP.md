# Dataset Setup — Crowd Density Module

## Recommended real dataset: ShanghaiTech Campus (crowd counting)

- Search "ShanghaiTech crowd counting dataset" — hosted via the original
  authors' links (paper: Zhang et al., CVPR 2016, "Single-Image Crowd
  Counting via Multi-Column CNN").
- Comes with Part A (dense crowds) and Part B (sparser street scenes) —
  Part B is a gentler starting point.
- Annotations are provided as `.mat` files with head-position points per
  image (exactly the format this module's `points_to_density_map` expects
  conceptually — you just need to convert `.mat` -> the `annotations.json`
  format this module reads).

## Other options
- **UCF-QNRF** — larger, denser crowds, harder.
- **Mall Dataset** — smaller, indoor mall scenes, good easy second dataset.

## Converting to this module's format

This module expects:
```
data/raw/<dataset_name>/
    scene_0000.jpg, scene_0001.jpg, ...
    annotations.json   -> {"scene_0000.jpg": [[x1,y1],[x2,y2],...], ...}
```

For ShanghaiTech's `.mat` files, a conversion script looks roughly like:
```python
import scipy.io as sio
import json, glob, os

annotations = {}
for mat_path in glob.glob("GT_*.mat"):
    mat = sio.loadmat(mat_path)
    points = mat["image_info"][0,0][0,0][0]  # shape (N, 2) — check your version's exact structure
    img_name = os.path.basename(mat_path).replace("GT_", "").replace(".mat", ".jpg")
    annotations[img_name] = points.tolist()

json.dump(annotations, open("annotations.json", "w"))
```
(Exact `.mat` structure varies slightly by dataset release — inspect with
`scipy.io.loadmat` and adjust indexing accordingly; happy to help once you
have a real file to look at.)

## After downloading and converting

```bash
python3 -c "
from src.dataset import CrowdDensityDataset
ds = CrowdDensityDataset('data/raw/shanghaitech_partB', split='train')
print('Loaded', len(ds), 'images')
"
```

Then update `configs/default.yaml`'s `data.dataset` field and re-run
`scripts/train.py`.
