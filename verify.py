#!/usr/bin/env python3
"""Verify screenshot using scikit-image - fast, deterministic checks."""
import sys
import os
import numpy as np
from skimage import io, color, filters

# Thresholds (configurable via env)
BLANK_THRESHOLD = float(os.environ.get("VERIFY_BLANK_THRESHOLD", "10"))
EDGE_THRESHOLD = float(os.environ.get("VERIFY_EDGE_THRESHOLD", "0.01"))

def is_blank(img):
    """Check if image is mostly one color (blank/failed render)."""
    gray = color.rgb2gray(img) if img.ndim == 3 else img
    return np.std(gray) < BLANK_THRESHOLD / 255

def has_ui_elements(img):
    """Check if image has edges (UI elements like buttons, text)."""
    gray = color.rgb2gray(img) if img.ndim == 3 else img
    edges = filters.sobel(gray)
    edge_ratio = np.mean(edges > 0.1)
    return edge_ratio > EDGE_THRESHOLD

def verify(image_path):
    """Verify screenshot is valid. Returns (passed, message)."""
    try:
        img = io.imread(image_path)
    except Exception as e:
        return False, f"Cannot read image: {e}"

    if is_blank(img):
        return False, "Image is blank (failed render)"

    if not has_ui_elements(img):
        return False, "No UI elements detected"

    return True, "Screenshot looks valid"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: verify.py IMAGE", file=sys.stderr)
        sys.exit(1)

    passed, msg = verify(sys.argv[1])
    print(f"{'PASS' if passed else 'FAIL'}: {msg}")
    sys.exit(0 if passed else 1)
