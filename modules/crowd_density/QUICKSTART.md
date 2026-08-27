# Quickstart — Crowd Density Module

## 1. Setup

```bash
cd urban-monitoring-system/modules/crowd_density
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt --break-system-packages
```

## 2. Smoke test (synthetic data, verifies everything runs on your machine)

```bash
python3 scripts/make_synthetic_data.py
python3 scripts/train.py --config configs/default.yaml
```

**Honest expectation:** with only ~50 tiny synthetic training images and 15
quick epochs, count predictions will be noticeably off (in our test run:
predicted 23.6 vs. true 40 on a held-out image — see docs/RESULTS_LOG.md).
This confirms the pipeline works correctly, not that it's accurate yet.
Accuracy comes from real data + more training (see step 4).

## 3. Try it on your live camera RIGHT NOW (using the smoke-test model)

```bash
python3 scripts/live_feed.py --config configs/default.yaml --checkpoint models/density_synthetic_density.pt
```
Press `q` to quit. You'll see your webcam feed with a density heatmap
overlay and a count/percentage readout — but remember, this checkpoint was
trained on tiny synthetic dot-images, so real-world accuracy will be poor
until you train on real data (step 4). This step is mainly to confirm your
camera + the live inference loop work together on your machine.

**If the camera doesn't open:** try `--camera 1` or `--camera 2` (device
index), and on Windows try adding `--backend dshow`.

**Before pointing this at any real people:** read `docs/ETHICS.md` (in the
project root, one level up) — even a "just testing" live feed pointed at a
real space should follow those guidelines.

## 4. Train on real data for real accuracy

Follow `docs/DATASET_SETUP.md` to get ShanghaiTech or another real crowd
counting dataset, convert it to this module's format, then:

```bash
python3 scripts/train.py --config configs/default.yaml   # after updating dataset name in the config
python3 scripts/live_feed.py --config configs/default.yaml --checkpoint models/density_<your_dataset>.pt
```

## 5. Tuning the density percentage for your actual space

Edit `configs/default.yaml`'s `density.capacity` value — set it to
whatever head count you consider "100% full" for the specific space your
camera monitors. The percentage shown is just `count / capacity * 100`.

## What's next

This module is done. Bring it back when you want to build the next one
(vehicle classification, stray animal detection, etc.) — we'll build each
the same way: model, synthetic pipeline test, real dataset integration,
live feed script.
