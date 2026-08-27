"""
Crowd density estimation via density-map regression — the standard approach
in crowd counting literature (CSRNet, MCNN, and successors all use this
core idea): instead of detecting/counting individual people (hard in dense
crowds with heavy overlap), predict a per-pixel "density map" where the
SUM over all pixels equals the total head count. Ground truth is built by
placing a small Gaussian at each annotated head position.

This is a lightweight version (fewer channels than full CSRNet) so it
trains reasonably on CPU for prototyping; scale up channels once you're
on a real dataset + GPU.
"""

import torch
import torch.nn as nn


class LightDensityNet(nn.Module):
    def __init__(self):
        super().__init__()

        # Frontend: standard conv feature extractor (VGG-style, no pretrained
        # weights required to get started, though loading pretrained VGG16
        # frontend weights is common practice and improves results a lot —
        # see docs/UPGRADE_NOTES.md for how to swap that in later).
        self.frontend = nn.Sequential(
            nn.Conv2d(3, 32, 3, padding=1), nn.ReLU(inplace=True),
            nn.Conv2d(32, 32, 3, padding=1), nn.ReLU(inplace=True),
            nn.MaxPool2d(2),

            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(inplace=True),
            nn.Conv2d(64, 64, 3, padding=1), nn.ReLU(inplace=True),
            nn.MaxPool2d(2),

            nn.Conv2d(64, 128, 3, padding=1), nn.ReLU(inplace=True),
            nn.Conv2d(128, 128, 3, padding=1), nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
        )

        # Backend: dilated convolutions (CSRNet's key idea) — expands
        # receptive field without further downsampling, preserving spatial
        # resolution needed for accurate density maps.
        self.backend = nn.Sequential(
            nn.Conv2d(128, 128, 3, padding=2, dilation=2), nn.ReLU(inplace=True),
            nn.Conv2d(128, 64, 3, padding=2, dilation=2), nn.ReLU(inplace=True),
            nn.Conv2d(64, 32, 3, padding=2, dilation=2), nn.ReLU(inplace=True),
        )

        self.output_layer = nn.Conv2d(32, 1, kernel_size=1)

    def forward(self, x):
        x = self.frontend(x)
        x = self.backend(x)
        density_map = self.output_layer(x)
        density_map = torch.relu(density_map)  # density can't be negative
        return density_map  # (B, 1, H/8, W/8)


def count_from_density_map(density_map):
    """Sum over spatial dims -> estimated head count per sample. (B,1,H,W) -> (B,)"""
    return density_map.sum(dim=(1, 2, 3))


def density_to_percentage(count, capacity):
    """
    Convert a raw head count into a density RATIO/PERCENTAGE relative to a
    configured 'capacity' (max expected people for the monitored area) —
    this is what item #1 in the request actually asks for, not just a raw
    count. Capacity should be set per-camera/per-site based on the physical
    space being monitored (configs/density.yaml).
    """
    return (count / capacity) * 100.0
