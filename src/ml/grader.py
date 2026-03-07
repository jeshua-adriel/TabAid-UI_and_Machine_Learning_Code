# src/ml/grader.py
from __future__ import annotations

import os
import hashlib
from typing import Dict, Tuple

import torch
import torchvision.transforms as T
from PIL import Image

import cv2
import numpy as np

from utils.platform_config import get_config
from ml.model import EmbeddingNet, SiameseNet, euclidean_dist
from ml.line_analysis import analyze_line
from ml.shading_analysis import analyze_shading


CFG = get_config()


def _ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)


def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8", errors="ignore")).hexdigest()


def normalize_image_to_target(src_path: str, dst_path: str, target_w: int, target_h: int):
    """
    Read image, composite alpha onto white if needed, preserve aspect ratio,
    letterbox-pad to target_w x target_h, save as 3-channel BGR PNG.
    """
    img = cv2.imread(src_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Cannot read image: {src_path}")

    # Alpha -> composite onto white
    if len(img.shape) == 3 and img.shape[2] == 4:
        bgr = img[:, :, :3].astype(np.float32)
        a = img[:, :, 3:4].astype(np.float32) / 255.0
        white = np.ones_like(bgr, dtype=np.float32) * 255.0
        bgr = bgr * a + white * (1.0 - a)
        img = bgr.astype(np.uint8)

    # Gray -> BGR
    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    h, w = img.shape[:2]
    scale = min(target_w / float(w), target_h / float(h))
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))

    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    canvas = np.full((target_h, target_w, 3), 255, dtype=np.uint8)

    x0 = (target_w - new_w) // 2
    y0 = (target_h - new_h) // 2
    canvas[y0:y0 + new_h, x0:x0 + new_w] = resized

    ok = cv2.imwrite(dst_path, canvas)
    if not ok:
        raise ValueError(f"Failed to write normalized image: {dst_path}")


class SiameseGrader:
    """
    Loads Siamese model once and grades (ref vs child).
    Caches reference embeddings to speed up multi-step grading.

    Supports:
      - grade(ref, child) -> (score_0_100, similarity_0_1)   [Siamese only]
      - grade_activity(activity_type, ref, child) -> (final_score_0_100, similarity_0_1, details_dict)
        where activity_type in: "line", "dots", "shading"
    """

    def __init__(self, model_path: str):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        embedding_net = EmbeddingNet()
        self.model = SiameseNet(embedding_net).to(self.device)

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found: {model_path}")

        state = torch.load(model_path, map_location=self.device)
        self.model.load_state_dict(state)
        self.model.eval()

        # MUST match training preprocessing
        self.transform = T.Compose([
            T.Resize((128, 128)),
            T.ToTensor(),
            T.Normalize(mean=[0.5, 0.5, 0.5],
                        std=[0.5, 0.5, 0.5]),
        ])

        self._ref_cache: Dict[str, torch.Tensor] = {}  # normalized_ref_path -> embedding tensor

        # Normalization cache folder (inside src/ml/)
        self._norm_dir = str(CFG.PATHS.ML_DIR / "_cache_norm")
        _ensure_dir(self._norm_dir)

        # Target export/grading resolution (defaults to 1152x648)
        self._export_w = int(getattr(CFG, "EXPORT_W", 1152))
        self._export_h = int(getattr(CFG, "EXPORT_H", 648))

    def _norm_pair(self, ref_path: str, child_path: str) -> tuple[str, str]:
        """
        Normalize ref and child to the same target size into cached files.
        Regenerates cached normalized files if the source file changed.
        """
        k_ref = _sha1(f"ref|{ref_path}|{self._export_w}x{self._export_h}")
        k_child = _sha1(f"child|{child_path}|{self._export_w}x{self._export_h}")

        nref = os.path.join(self._norm_dir, f"{k_ref}.png")
        nchild = os.path.join(self._norm_dir, f"{k_child}.png")

        def needs_regen(src: str, dst: str) -> bool:
            if not os.path.exists(dst):
                return True
            try:
                return os.path.getmtime(src) > os.path.getmtime(dst)
            except Exception:
                return True

        # ✅ reference: regenerate if ref image was updated
        if needs_regen(ref_path, nref):
            normalize_image_to_target(ref_path, nref, self._export_w, self._export_h)
            # also clear cached embedding for this ref
            if nref in self._ref_cache:
                del self._ref_cache[nref]

        # ✅ child: always regenerate (safe, and each child export is new anyway)
        normalize_image_to_target(child_path, nchild, self._export_w, self._export_h)

        return nref, nchild

    def _load_img(self, path: str) -> torch.Tensor:
        if not os.path.exists(path):
            raise FileNotFoundError(f"Image not found: {path}")
        img = Image.open(path).convert("RGB")
        x = self.transform(img).unsqueeze(0).to(self.device)
        return x

    @torch.no_grad()
    def _embed(self, img_tensor: torch.Tensor) -> torch.Tensor:
        return self.model.embedding_net(img_tensor)

    @torch.no_grad()
    def _similarity(self, ref_path: str, child_path: str) -> float:
        """
        Returns similarity 0..1 using exp(-euclidean_distance).
        Uses normalized cached images to ensure consistent grading.
        """
        norm_ref, norm_child = self._norm_pair(ref_path, child_path)
        print("NORM_REF:", norm_ref)
        print("NORM_CHILD:", norm_child)
        
        import os, time
        print("REF mtime:", time.ctime(os.path.getmtime(ref_path)))
        print("NORM_REF mtime:", time.ctime(os.path.getmtime(norm_ref)))

        # cache ref embedding (huge speedup across steps)
        if norm_ref not in self._ref_cache:
            ref_t = self._load_img(norm_ref)
            self._ref_cache[norm_ref] = self._embed(ref_t)

        ref_emb = self._ref_cache[norm_ref]
        child_t = self._load_img(norm_child)
        child_emb = self._embed(child_t)

        dist = euclidean_dist(ref_emb, child_emb)     # tensor shape [1]
        similarity = torch.exp(-dist).item()          # float 0..1
        print("DIST:", float(dist.item()), "SIM:", float(similarity))
        return float(similarity)

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------
    @torch.no_grad()
    def grade(self, ref_path: str, child_path: str) -> Tuple[int, float]:
        similarity = self._similarity(ref_path, child_path)
        score = int(max(0, min(100, round(similarity * 100))))
        return score, similarity

    def grade_activity(
        self,
        activity_type: str,
        ref_path: str,
        child_path: str
    ) -> Tuple[int, float, dict]:
        """
        Siamese + OpenCV post-analysis.
        Returns:
          final_score_0_100, similarity_0_1, details_dict
        """
        activity_type = (activity_type or "").strip().lower()

        # Always grade with normalized images
        norm_ref, norm_child = self._norm_pair(ref_path, child_path)
        similarity = self._similarity(ref_path, child_path)

        if activity_type == "shading":
            details = analyze_shading(norm_ref, norm_child)
            final = self._combine_scores(similarity, details, "shading")

        elif activity_type in ("line", "dots"):
            details = analyze_line(norm_ref, norm_child)
            print("DETAILS:", details)
            final = self._combine_scores(similarity, details, "line")

        else:
            raise ValueError(f"Unknown activity type: {activity_type}")

        final_int = int(max(0, min(100, round(float(final)))))
        return final_int, float(similarity), details

    # --------------------------------------------------
    # Score combination
    # --------------------------------------------------
    def _combine_scores(self, similarity: float, details: dict, activity: str) -> float:
        if activity == "shading":
            nn_score = float(similarity) * 100.0

            coverage = float(details.get("color_coverage", 0.0))  # 0..1
            coverage_score = coverage * 100.0

            # Weighted blend: 60% NN + 40% coverage
            base = 0.60 * nn_score + 0.40 * coverage_score

            # Overflow penalty (0..1). Max 50% reduction.
            overflow = float(details.get("overflow_penalty", 0.0))
            overflow_factor = 1.0 - 0.50 * overflow
            overflow_factor = max(0.0, min(1.0, overflow_factor))

            score = base * overflow_factor
            return max(0.0, min(100.0, score))

        if activity == "line":
            nn_score = float(similarity) * 100.0
            angle_err = float(details.get("angle_error_deg", 180.0))
            straight = float(details.get("straightness", 0.0))  # from line_analysis

            # angle penalty
            if angle_err <= 5:
                penalty = 1.00
            elif angle_err <= 12:
                penalty = 0.85
            elif angle_err <= 20:
                penalty = 0.65
            else:
                penalty = 0.40

            # straightness factor (0.5–1.0 so it doesn't over-penalize)
            straight_factor = max(0.5, min(1.0, straight))

            score = nn_score * penalty * straight_factor
            return max(0.0, min(100.0, score))

        return max(0.0, min(100.0, float(similarity) * 100.0))