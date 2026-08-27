# Results Log — Crowd Density Module

## Pipeline verification (synthetic smoke-test data)

- Density map generation: verified sum-preservation property exactly
  (density map sum matches annotated point count to within 1e-5, including
  edge cases: empty scene, points at image borders).
- Model forward pass: verified correct output shape (256x256 input ->
  32x32 density map, matching the 3x max-pool /8 downsampling).
- Training: loss decreased steadily over 15 epochs (MSE: 0.0266 -> 0.0069).
- Validation count MAE: dropped from 67.4 (epoch 1, untrained) to ~3-10
  people by epoch 13-15 (fluctuates due to tiny 9-image validation set —
  expected noise at this scale, not a bug).
- Live-feed inference loop (tested on a static held-out frame, since this
  sandbox has no camera): produced a sensible heatmap concentrated on the
  actual crowd cluster, with correct count/percentage text overlay.

**Single held-out test frame result:** true count 40, predicted 23.6
(~40% underestimate). This is a real, honestly-reported result — expected
given only 51 tiny synthetic training images and a quick 15-epoch run, not
a bug in the pipeline. Do not treat this number as representative of the
method's real-world capability.

## Real dataset results

*(Not yet run — fill in here once you've trained on ShanghaiTech or another
real dataset per docs/DATASET_SETUP.md.)*

| Dataset | Epochs | Val Count MAE | Notes |
|---|---|---|---|
| — | — | — | — |

## Known limitations of the current implementation

1. **Frontend has no pretrained weights.** Real CSRNet implementations
   initialize their VGG16 frontend with ImageNet-pretrained weights, which
   meaningfully improves accuracy on real photos. This lightweight version
   trains from scratch — fine for the synthetic smoke test, but consider
   adding pretrained weights before reporting real-dataset numbers (see
   `docs/UPGRADE_NOTES.md` — TODO, not yet written; ask when you get here).
2. **Fixed Gaussian sigma.** Literature often uses adaptive sigma (denser
   crowds -> smaller sigma per person) for better accuracy; this version
   uses one fixed sigma for simplicity.
3. **No temporal smoothing on the live feed.** Each frame is scored
   independently, so the displayed count may jitter frame-to-frame. Worth
   adding a rolling average if the live display feels too jumpy.
