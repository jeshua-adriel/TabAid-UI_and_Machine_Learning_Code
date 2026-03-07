# line_analysis.py (SIMPLE)
import cv2
import numpy as np


def _prep(path):
    img = cv2.imread(path)
    if img is None:
        raise ValueError(f"Cannot read image: {path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    bw = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 31, 5
    )
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=2)
    return bw


def _largest_component(bw):
    n, labels, stats, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
    if n <= 1:
        return None
    areas = stats[1:, cv2.CC_STAT_AREA]
    idx = 1 + int(np.argmax(areas))
    return (labels == idx).astype(np.uint8) * 255


def _fit_angle_and_straightness(mask):
    ys, xs = np.where(mask > 0)
    if len(xs) < 50:
        return None

    pts = np.column_stack([xs.astype(np.float32), ys.astype(np.float32)])
    mean = pts.mean(axis=0)
    centered = pts - mean
    cov = np.cov(centered.T)
    eigvals, eigvecs = np.linalg.eig(cov)

    i = int(np.argmax(eigvals))
    d = eigvecs[:, i]
    d = d / (np.linalg.norm(d) + 1e-8)

    # undirected angle 0..180
    ang = np.degrees(np.arctan2(d[1], d[0]))
    ang = (ang + 180.0) % 180.0

    # straightness 0..1
    straightness = float(np.max(eigvals) / (np.sum(eigvals) + 1e-8))

    return float(ang), straightness


def _angle_diff(a, b):
    diff = abs(a - b) % 180.0
    return float(min(diff, 180.0 - diff))


def analyze_line(reference_img, child_img):
    ref_bw = _largest_component(_prep(reference_img))
    child_bw = _largest_component(_prep(child_img))

    if ref_bw is None or child_bw is None:
        return {"angle_error_deg": 180.0, "straightness": 0.0}

    ref_fit = _fit_angle_and_straightness(ref_bw)
    child_fit = _fit_angle_and_straightness(child_bw)

    if ref_fit is None or child_fit is None:
        return {"angle_error_deg": 180.0, "straightness": 0.0}

    ref_ang, _ = ref_fit
    child_ang, child_straight = child_fit

    return {
        "angle_error_deg": _angle_diff(ref_ang, child_ang),
        "straightness": float(child_straight),
    }