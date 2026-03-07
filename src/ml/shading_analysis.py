# src/ml/shading_analysis.py
import cv2
import numpy as np


def analyze_shading(ref_path: str, child_path: str) -> dict:
    """
    Returns:
      whitespace_penalty: 0..1 (missed shading inside reference)
      overflow_penalty:   0..1 (shading outside reference)
      color_coverage:     0..1 (how much of ref region was covered)
    """
    ref = cv2.imread(ref_path)
    child = cv2.imread(child_path)

    if ref is None or child is None:
        return {
            "whitespace_penalty": 1.0,
            "overflow_penalty": 1.0,
            "color_coverage": 0.0,
        }

    ref_gray = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY)
    child_gray = cv2.cvtColor(child, cv2.COLOR_BGR2GRAY)

    # Mask shaded area (non-white)
    _, ref_mask = cv2.threshold(ref_gray, 240, 255, cv2.THRESH_BINARY_INV)
    _, child_mask = cv2.threshold(child_gray, 240, 255, cv2.THRESH_BINARY_INV)

    ref_area = int(np.sum(ref_mask > 0))
    child_area = int(np.sum(child_mask > 0))

    if ref_area == 0:
        return {
            "whitespace_penalty": 0.0,
            "overflow_penalty": 0.0,
            "color_coverage": 0.0,
        }

    # Missed shading INSIDE reference
    missed = cv2.bitwise_and(ref_mask, cv2.bitwise_not(child_mask))
    missed_area = int(np.sum(missed > 0))
    whitespace_ratio = missed_area / ref_area

    color_coverage = 1.0 - whitespace_ratio
    color_coverage = float(np.clip(color_coverage, 0.0, 1.0))

    # Overflow shading OUTSIDE reference
    if child_area == 0:
        overflow_ratio = 0.0
    else:
        overflow = cv2.bitwise_and(child_mask, cv2.bitwise_not(ref_mask))
        overflow_area = int(np.sum(overflow > 0))
        overflow_ratio = overflow_area / child_area

    return {
        "whitespace_penalty": float(whitespace_ratio),
        "overflow_penalty": float(overflow_ratio),
        "color_coverage": float(color_coverage),
    }
