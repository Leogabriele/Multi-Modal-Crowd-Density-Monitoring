"""
Dataset Setup & Conversion Utility for ShanghaiTech Crowd Counting Dataset.

Converts ShanghaiTech Part A and Part B native MATLAB .mat annotations
(image_info coordinates) into standard annotations.json format expected by
the crowd density training pipeline.

Usage:
    python scripts/setup_shanghaitech.py --input-dir /path/to/extracted/part_B --output-dir data/raw/shanghaitech_part_b
"""

import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import glob
import json
import shutil
import argparse
import numpy as np
import scipy.io as sio

def convert_mat_to_points(mat_path):
    """Extract (x, y) head coordinate points from ShanghaiTech .mat ground truth file."""
    try:
        mat = sio.loadmat(mat_path)
        # ShanghaiTech standard structure: image_info[0,0][0,0][0] contains (N, 2) array of [x, y]
        if "image_info" in mat:
            points = mat["image_info"][0, 0][0, 0][0]
        elif "annPoints" in mat:
            points = mat["annPoints"]
        elif "point" in mat:
            points = mat["point"]
        else:
            for k in mat.keys():
                if not k.startswith("__") and isinstance(mat[k], np.ndarray) and mat[k].ndim == 2 and mat[k].shape[1] == 2:
                    points = mat[k]
                    break
            else:
                points = np.zeros((0, 2), dtype=np.float32)

        points = np.asarray(points, dtype=np.float32)
        if points.ndim == 2 and points.shape[1] == 2:
            return points.tolist()
        return []
    except Exception as e:
        print(f"⚠️ Warning reading {mat_path}: {e}")
        return []

def setup_shanghaitech(input_dir, output_dir, copy_images=True):
    """
    Process train_data and test_data directories in ShanghaiTech Part A/B:
    1. Extracts images
    2. Converts GT_IMG_*.mat to annotations.json
    3. Outputs clean dataset ready for training.
    """
    os.makedirs(output_dir, exist_ok=True)
    annotations = {}
    total_heads = 0
    img_count = 0

    subdirs = [
        os.path.join(input_dir, "train_data"),
        os.path.join(input_dir, "test_data"),
        input_dir
    ]

    found_mats = []
    for sdir in subdirs:
        if os.path.exists(sdir):
            found_mats.extend(glob.glob(os.path.join(sdir, "**", "GT_*.mat"), recursive=True))
            found_mats.extend(glob.glob(os.path.join(sdir, "**", "*.mat"), recursive=True))

    found_mats = sorted(list(set(found_mats)))
    print(f"🔍 Found {len(found_mats)} ground-truth .mat files in '{input_dir}'")

    if not found_mats:
        print(f"❌ No .mat files found in '{input_dir}'.")
        print("Expected structure: part_B/train_data/ground-truth/GT_IMG_1.mat, part_B/train_data/images/IMG_1.jpg")
        return False

    for mat_path in found_mats:
        points = convert_mat_to_points(mat_path)
        base_name = os.path.basename(mat_path)
        img_name = base_name.replace("GT_", "").replace(".mat", ".jpg")
        
        img_candidates = glob.glob(os.path.join(input_dir, "**", img_name), recursive=True)
        if not img_candidates:
            img_candidates = glob.glob(os.path.join(input_dir, "**", img_name.replace(".jpg", ".png")), recursive=True)

        if img_candidates:
            src_img = img_candidates[0]
            dst_img = os.path.join(output_dir, img_name)
            
            if copy_images and os.path.abspath(src_img) != os.path.abspath(dst_img):
                shutil.copyfile(src_img, dst_img)

            annotations[img_name] = points
            total_heads += len(points)
            img_count += 1

    ann_out_path = os.path.join(output_dir, "annotations.json")
    with open(ann_out_path, "w") as f:
        json.dump(annotations, f, indent=2)

    print("\n" + "=" * 60)
    print("✅ ShanghaiTech Dataset Processing Complete!")
    print(f"   • Total Processed Images:      {img_count}")
    print(f"   • Total Ground-Truth Heads:    {total_heads}")
    print(f"   • Avg Heads per Image:         {total_heads / max(img_count, 1):.1f}")
    print(f"   • Annotations Saved To:        {ann_out_path}")
    print("=" * 60)
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Setup ShanghaiTech Dataset for Crowd Counting")
    parser.add_argument("--input-dir", required=True, help="Path to raw unzipped ShanghaiTech directory")
    parser.add_argument("--output-dir", default="data/raw/shanghaitech_part_b", help="Target output folder")
    parser.add_argument("--no-copy", action="store_true", help="Do not copy images, only generate annotations")
    args = parser.parse_args()

    setup_shanghaitech(args.input_dir, args.output_dir, copy_images=not args.no_copy)
