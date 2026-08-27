"""
Generates synthetic "crowd scene" images with KNOWN head positions, purely
to test the density estimation pipeline end-to-end before using a real
dataset (ShanghaiTech etc — see docs/DATASET_SETUP.md).

Each synthetic person = a small circle (crude head proxy). Real training
will use actual photos + real head annotations; this is plumbing-test data
only, same philosophy as the crowd-anomaly project's synthetic demo.
"""

import os
import json
import numpy as np
import cv2

OUT_DIR = "data/raw/synthetic_density"
IMG_SIZE = 256
N_IMAGES = 60


def make_scene(n_people, seed=None):
    rng = np.random.default_rng(seed)
    img = np.full((IMG_SIZE, IMG_SIZE, 3), 40, dtype=np.uint8)  # dark background

    points = []
    # Randomly decide: sparse-scattered vs. clustered (both should exist in
    # training data, since real crowds have both patterns)
    if rng.random() < 0.5 and n_people > 3:
        # clustered
        cluster_center = rng.uniform(40, IMG_SIZE - 40, size=2)
        for _ in range(n_people):
            offset = rng.normal(0, 20, size=2)
            x, y = np.clip(cluster_center + offset, 5, IMG_SIZE - 5)
            points.append((float(x), float(y)))
    else:
        # scattered
        for _ in range(n_people):
            x, y = rng.uniform(5, IMG_SIZE - 5, size=2)
            points.append((float(x), float(y)))

    for (x, y) in points:
        radius = rng.integers(3, 6)
        color = tuple(int(c) for c in rng.integers(150, 230, size=3))
        cv2.circle(img, (int(x), int(y)), int(radius), color, -1)

    return img, points


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    annotations = {}

    rng = np.random.default_rng(42)
    for i in range(N_IMAGES):
        n_people = int(rng.integers(0, 60))  # wide range, including near-empty
        img, points = make_scene(n_people, seed=1000 + i)

        fname = f"scene_{i:04d}.jpg"
        cv2.imwrite(os.path.join(OUT_DIR, fname), img)
        annotations[fname] = points

    with open(os.path.join(OUT_DIR, "annotations.json"), "w") as f:
        json.dump(annotations, f)

    counts = [len(v) for v in annotations.values()]
    print(f"Generated {N_IMAGES} synthetic scenes in {OUT_DIR}")
    print(f"Head count range: {min(counts)} - {max(counts)}, mean: {np.mean(counts):.1f}")


if __name__ == "__main__":
    main()
