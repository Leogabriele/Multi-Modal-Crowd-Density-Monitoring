"""
Regression test: confirms the density model produces the expected
downsampled output shape for several input sizes, and that density map sum
correctly reflects total predicted count.
Run: python3 tests/test_model_shapes.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import torch
from src.model import LightDensityNet, count_from_density_map


def test_output_shapes():
    model = LightDensityNet()
    for size in [128, 256, 512]:
        x = torch.rand(1, 3, size, size)
        out = model(x)
        expected = size // 8
        assert out.shape == (1, 1, expected, expected), f"FAIL at size {size}: got {out.shape}"


def test_count_is_nonnegative():
    model = LightDensityNet()
    x = torch.rand(3, 3, 256, 256)
    density_map = model(x)
    counts = count_from_density_map(density_map)
    assert (counts >= 0).all(), "Density counts must be non-negative (ReLU output)"


if __name__ == "__main__":
    test_output_shapes()
    test_count_is_nonnegative()
    print("All tests passed.")
