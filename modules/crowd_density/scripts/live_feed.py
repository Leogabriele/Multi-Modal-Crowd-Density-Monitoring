"""
Run crowd density estimation on a LIVE camera feed (webcam or connected
capture device) with a real-time on-screen overlay showing:
  - Estimated head count
  - Density percentage (count / configured capacity)
  - A heatmap overlay showing WHERE the density is concentrated

Usage:
    python3 scripts/live_feed.py --config configs/default.yaml --checkpoint models/density_synthetic_density.pt

Press 'q' to quit.

NOTE: cv2.VideoCapture(0) opens the default system webcam. If you're using
your capture card (for a DSLR or other external camera source), it usually
also shows up as a numbered device — try --camera 1, --camera 2, etc. if 0
doesn't work. On Windows, you may need --backend dshow.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import argparse
import yaml
import numpy as np
import cv2
import torch

from src.model import LightDensityNet, count_from_density_map, density_to_percentage
from src.density_map import density_map_to_display


def run_live_feed(cfg, checkpoint_path, camera_index=0, backend=None):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    model = LightDensityNet().to(device)
    model.load_state_dict(torch.load(checkpoint_path, map_location=device))
    model.eval()

    image_size = cfg["data"]["image_size"]
    capacity = cfg["density"]["capacity"]

    cap_backend = getattr(cv2, f"CAP_{backend.upper()}") if backend else cv2.CAP_ANY
    cap = cv2.VideoCapture(camera_index, cap_backend)
    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open camera index {camera_index}. Try a different "
            f"--camera index, or check the device is connected and not in "
            f"use by another application."
        )

    print("Live feed started. Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to read frame from camera — stopping.")
            break

        orig_h, orig_w = frame.shape[:2]

        # Preprocess: resize to model input size, normalize
        resized = cv2.resize(frame, (image_size, image_size))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        tensor = torch.from_numpy(np.transpose(rgb, (2, 0, 1))).unsqueeze(0).to(device)

        with torch.no_grad():
            density_map = model(tensor)
            count = count_from_density_map(density_map).item()
            pct = density_to_percentage(torch.tensor([count]), capacity).item()

        # Build heatmap overlay
        dm_np = density_map[0, 0].cpu().numpy()
        heatmap = density_map_to_display(dm_np)
        heatmap_resized = cv2.resize(heatmap, (orig_w, orig_h))
        overlay = cv2.addWeighted(frame, 0.7, heatmap_resized, 0.3, 0)

        # Text overlay
        label = f"Count: {count:.1f}  |  Density: {pct:.1f}% (capacity={capacity})"
        cv2.rectangle(overlay, (0, 0), (orig_w, 40), (0, 0, 0), -1)
        cv2.putText(overlay, label, (10, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # Simple color-coded alert bar based on density percentage
        if pct >= 90:
            bar_color = (0, 0, 255)   # red — near/over capacity
        elif pct >= 60:
            bar_color = (0, 165, 255)  # orange — getting busy
        else:
            bar_color = (0, 200, 0)   # green — normal
        cv2.rectangle(overlay, (0, orig_h - 8), (int(orig_w * min(pct, 100) / 100), orig_h), bar_color, -1)

        cv2.imshow("Crowd Density — Live", overlay)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--camera", type=int, default=0, help="Camera device index")
    parser.add_argument("--backend", default=None, help="e.g. 'dshow' on Windows if default backend fails")
    args = parser.parse_args()

    cfg = yaml.safe_load(open(args.config))
    run_live_feed(cfg, args.checkpoint, camera_index=args.camera, backend=args.backend)
