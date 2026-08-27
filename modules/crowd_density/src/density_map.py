"""
Convert point annotations (x, y head positions) into a ground-truth density
map by placing a Gaussian at each point — the standard label format used
across the crowd-counting literature (MCNN, CSRNet, and successors all use
this). The density map's total sum equals the number of annotated points,
by construction.

For real datasets (e.g. ShanghaiTech), annotations are usually provided as
.mat files with (x,y) head-center coordinates per image — see
docs/DATASET_SETUP.md for how to convert those into the format this module
expects.
"""

import numpy as np
import cv2


def points_to_density_map(points, image_shape, sigma=4, downsample=8):
    """
    points: list of (x, y) head positions in ORIGINAL image pixel coordinates
    image_shape: (H, W) of the original image
    sigma: Gaussian spread (larger = smoother/more spread-out density) —
        literature often uses adaptive sigma based on local crowd density,
        but a fixed sigma is a reasonable starting point.
    downsample: the model's output is downsampled vs. input (this model:
        /8, due to 3 max-pool layers) — the density map should be built at
        that same resolution so ground truth matches model output shape.

    Returns: density map at (H/downsample, W/downsample), where sum(map) ==
        len(points) (up to small numerical Gaussian-truncation error).
    """
    H, W = image_shape
    out_h, out_w = H // downsample, W // downsample
    density_map = np.zeros((out_h, out_w), dtype=np.float32)

    if len(points) == 0:
        return density_map

    for (x, y) in points:
        # scale point coords into the downsampled map's coordinate space
        dx, dy = x / downsample, y / downsample
        if 0 <= dx < out_w and 0 <= dy < out_h:
            density_map[int(dy), int(dx)] += 1.0

    # Blur the point-impulses into Gaussians. Using a fixed sigma in the
    # downsampled space (so it's already scaled appropriately).
    density_map = cv2.GaussianBlur(density_map, (0, 0), sigmaX=sigma / downsample if sigma / downsample >= 0.5 else 0.5)

    # Renormalize so the sum is preserved exactly at len(points) — Gaussian
    # blur near image borders can leak mass outside and change the sum
    # slightly; this keeps the "sum = count" property exact, which matters
    # for training (the model is supervised to match this sum).
    current_sum = density_map.sum()
    if current_sum > 1e-6:
        density_map *= (len(points) / current_sum)

    return density_map


def density_map_to_display(density_map, colormap=cv2.COLORMAP_JET):
    """Normalize a density map to a 0-255 heatmap image for visualization/overlay."""
    dm = density_map.copy()
    if dm.max() > 0:
        dm = dm / dm.max()
    dm_uint8 = (dm * 255).astype(np.uint8)
    heatmap = cv2.applyColorMap(dm_uint8, colormap)
    return heatmap
