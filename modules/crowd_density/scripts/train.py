"""
Academic-Grade Training & Evaluation Pipeline for Crowd Density Estimation.

Includes:
- GPU (CUDA) Tensor Acceleration for RTX 2050
- Dual Academic Evaluation Metrics: MAE (Mean Absolute Error) and RMSE (Root Mean Squared Error)
- Automatic Best-Checkpoint Saving & Learning Rate Scheduling
- Model Complexity Profiling (Parameters, Memory, Inference Latency) for PhD Research Portfolio

Usage:
    python scripts/train.py --config configs/default.yaml
"""
import sys, os
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
import argparse
import yaml
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from tqdm import tqdm

from src.dataset import CrowdDensityDataset
from src.model import LightDensityNet, count_from_density_map


def evaluate_metrics(model, loader, device):
    """Computes academic benchmark metrics: Count MAE and Count RMSE."""
    model.eval()
    abs_errors = []
    sq_errors = []
    with torch.no_grad():
        for imgs, density_maps, true_counts in loader:
            imgs = imgs.to(device)
            pred_maps = model(imgs)
            pred_counts = count_from_density_map(pred_maps).cpu().numpy()
            true_counts = true_counts.numpy()
            
            diff = pred_counts - true_counts
            abs_errors.extend(np.abs(diff).tolist())
            sq_errors.extend((diff ** 2).tolist())
            
    model.train()
    mae = float(np.mean(abs_errors)) if abs_errors else float("nan")
    rmse = float(np.sqrt(np.mean(sq_errors))) if sq_errors else float("nan")
    return mae, rmse


def train(cfg):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("\n" + "=" * 65)
    print(f"🚀 Training Density Estimation CNN on: {device.type.upper()}")
    if device.type == "cuda":
        print(f"   • GPU Device:  {torch.cuda.get_device_name(0)}")
        print(f"   • VRAM:        {torch.cuda.get_device_properties(0).total_memory / (1024**3):.2f} GB")
    print("=" * 65)

    data_root = os.path.join(cfg["data"]["raw_dir"], cfg["data"]["dataset"])
    if not os.path.exists(data_root):
        raise FileNotFoundError(
            f"Dataset directory '{data_root}' not found. "
            f"Please run setup_shanghaitech.py first or verify configs/default.yaml."
        )

    train_ds = CrowdDensityDataset(
        data_root, image_size=cfg["data"]["image_size"],
        downsample=cfg["data"]["downsample"], sigma=cfg["data"]["sigma"], split="train",
    )
    val_ds = CrowdDensityDataset(
        data_root, image_size=cfg["data"]["image_size"],
        downsample=cfg["data"]["downsample"], sigma=cfg["data"]["sigma"], split="val",
    )
    
    use_pin_memory = (device.type == "cuda")
    train_loader = DataLoader(
        train_ds, batch_size=cfg["model"]["batch_size"], 
        shuffle=True, pin_memory=use_pin_memory, drop_last=False
    )
    val_loader = DataLoader(
        val_ds, batch_size=cfg["model"]["batch_size"], 
        shuffle=False, pin_memory=use_pin_memory
    )
    print(f"📊 Dataset Split: {len(train_ds)} Train Samples | {len(val_ds)} Validation Samples")

    model = LightDensityNet().to(device)
    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"🧠 Model Architecture: LightDensityNet | Trainable Parameters: {total_params:,}")

    optimizer = torch.optim.AdamW(
        model.parameters(), 
        lr=cfg["model"]["learning_rate"], 
        weight_decay=1e-4
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', factor=0.5, patience=3, verbose=True
    )
    criterion = nn.MSELoss()

    epochs = cfg["model"]["epochs"]
    best_mae = float("inf")
    best_rmse = float("inf")
    os.makedirs("models", exist_ok=True)
    best_save_path = os.path.join("models", f"best_density_{cfg['data']['dataset']}.pt")
    latest_save_path = os.path.join("models", f"density_{cfg['data']['dataset']}.pt")

    start_training_time = time.time()

    for epoch in range(1, epochs + 1):
        model.train()
        epoch_loss = 0.0
        n_batches = 0

        for imgs, density_maps, _ in tqdm(train_loader, desc=f"Epoch {epoch:02d}/{epochs:02d}", leave=False):
            imgs = imgs.to(device, non_blocking=True)
            density_maps = density_maps.to(device, non_blocking=True)
            
            optimizer.zero_grad()
            pred_maps = model(imgs)
            loss = criterion(pred_maps, density_maps)
            loss.backward()
            optimizer.step()
            
            epoch_loss += loss.item()
            n_batches += 1

        avg_loss = epoch_loss / max(n_batches, 1)
        val_mae, val_rmse = evaluate_metrics(model, val_loader, device)
        scheduler.step(val_mae)

        is_best = val_mae < best_mae
        if is_best:
            best_mae = val_mae
            best_rmse = val_rmse
            torch.save(model.state_dict(), best_save_path)
            status_str = f"⭐ [BEST MODEL SAVED -> MAE: {val_mae:.2f}]"
        else:
            status_str = ""

        print(f"Epoch {epoch:02d}/{epochs:02d} | Train MSE: {avg_loss:.6f} | Val MAE: {val_mae:.2f} | Val RMSE: {val_rmse:.2f} {status_str}")

    torch.save(model.state_dict(), latest_save_path)
    total_time = time.time() - start_training_time

    # Compute Benchmark Inference Latency
    model.eval()
    dummy_input = torch.randn(1, 3, cfg["data"]["image_size"], cfg["data"]["image_size"]).to(device)
    # Warmup
    for _ in range(10):
        _ = model(dummy_input)
    if device.type == "cuda":
        torch.cuda.synchronize()
    t0 = time.time()
    for _ in range(50):
        _ = model(dummy_input)
    if device.type == "cuda":
        torch.cuda.synchronize()
    latency_ms = ((time.time() - t0) / 50) * 1000.0

    print("\n" + "=" * 65)
    print("🎓 ACADEMIC BENCHMARK SUMMARY (For Research Paper / CV)")
    print("=" * 65)
    print(f"   • Total Training Time:        {total_time / 60.0:.2f} minutes")
    print(f"   • Best Validation MAE:        {best_mae:.2f}")
    print(f"   • Best Validation RMSE:       {best_rmse:.2f}")
    print(f"   • Inference Latency (Batch 1):{latency_ms:.2f} ms (~{1000.0/latency_ms:.1f} FPS)")
    print(f"   • Model Size:                 {total_params * 4 / (1024**2):.2f} MB ({total_params:,} params)")
    print(f"   • Saved Checkpoint:           {best_save_path}")
    print("=" * 65 + "\n")
    return model


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/default.yaml")
    args = parser.parse_args()
    cfg = yaml.safe_load(open(args.config))
    train(cfg)
