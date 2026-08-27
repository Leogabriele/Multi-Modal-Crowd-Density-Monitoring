"""
Dataset loader: pairs each image with its ground-truth density map, built
on the fly from point annotations via density_map.points_to_density_map.

Expects:
    data/raw/<dataset_name>/
        scene_0000.jpg, scene_0001.jpg, ...
        annotations.json   -> {"scene_0000.jpg": [[x,y], [x,y], ...], ...}

For real datasets, write a conversion script that produces this same
annotations.json format from the dataset's native format (e.g. ShanghaiTech
ships .mat files) — see docs/DATASET_SETUP.md.
"""

import os
import json
import numpy as np
import cv2
from torch.utils.data import Dataset

from .density_map import points_to_density_map


class CrowdDensityDataset(Dataset):
    def __init__(self, root_dir, image_size=256, downsample=8, sigma=4, split="train", val_fraction=0.15):
        self.root_dir = root_dir
        self.image_size = image_size
        self.downsample = downsample
        self.sigma = sigma

        ann_path = os.path.join(root_dir, "annotations.json")
        if not os.path.exists(ann_path):
            raise FileNotFoundError(
                f"Expected annotations file at '{ann_path}'. "
                f"See docs/DATASET_SETUP.md for the expected format."
            )
        with open(ann_path) as f:
            self.annotations = json.load(f)

        all_filenames = sorted(self.annotations.keys())
        n_val = max(1, int(len(all_filenames) * val_fraction))

        if split == "train":
            self.filenames = all_filenames[:-n_val]
        elif split == "val":
            self.filenames = all_filenames[-n_val:]
        else:
            raise ValueError("split must be 'train' or 'val'")

    def __len__(self):
        return len(self.filenames)

    def __getitem__(self, idx):
        fname = self.filenames[idx]
        img_path = os.path.join(self.root_dir, fname)
        img = cv2.imread(img_path)
        if img is None:
            raise IOError(f"Failed to read image: {img_path}")
        orig_h, orig_w = img.shape[:2]

        points = self.annotations[fname]

        # Resize image to a fixed size for batching; scale point coords to match.
        img_resized = cv2.resize(img, (self.image_size, self.image_size))
        scale_x = self.image_size / orig_w
        scale_y = self.image_size / orig_h
        scaled_points = [(x * scale_x, y * scale_y) for (x, y) in points]

        img_resized = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        img_chw = np.transpose(img_resized, (2, 0, 1))  # (C,H,W)

        density_map = points_to_density_map(
            scaled_points,
            image_shape=(self.image_size, self.image_size),
            sigma=self.sigma,
            downsample=self.downsample,
        )
        density_map = density_map[None, :, :]  # (1, H/ds, W/ds)

        return img_chw.astype(np.float32), density_map.astype(np.float32), len(points)
