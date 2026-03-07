# src/ml/inference.py
import os
import torch
from PIL import Image
import torchvision.transforms as T

from ml.model import EmbeddingNet, SiameseNet, euclidean_dist


# --------------------------------------------------
# Image preprocessing (MUST MATCH TRAINING)
# --------------------------------------------------
def load_and_preprocess(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Image not found: {path}")

    transform = T.Compose([
        T.Resize((128, 128)),
        T.ToTensor(),
        T.Normalize(mean=[0.5, 0.5, 0.5],
                    std=[0.5, 0.5, 0.5]),
    ])

    img = Image.open(path).convert("RGB")
    return transform(img).unsqueeze(0)  # (1,3,128,128)


# --------------------------------------------------
# One-shot similarity (loads model each call)
# --------------------------------------------------
def compute_similarity(img1_path: str, img2_path: str, model_path: str):
    """
    Returns (similarity_0_1, distance_float)
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"

    embedding_net = EmbeddingNet()
    model = SiameseNet(embedding_net).to(device)

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found: {model_path}")

    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval()

    img1 = load_and_preprocess(img1_path).to(device)
    img2 = load_and_preprocess(img2_path).to(device)

    with torch.no_grad():
        emb1, emb2 = model(img1, img2)
        dist = euclidean_dist(emb1, emb2)
        similarity = torch.exp(-dist).item()  # 0..1
        distance = dist.item()

    return float(similarity), float(distance)


# --------------------------------------------------
# Load-once inferencer (recommended for games)
# --------------------------------------------------
class SiameseInferencer:
    """
    Loads the model once, then compute similarity repeatedly fast.
    Optionally caches reference embeddings.
    """
    def __init__(self, model_path: str):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        embedding_net = EmbeddingNet()
        self.model = SiameseNet(embedding_net).to(self.device)

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found: {model_path}")

        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.eval()

        self.transform = T.Compose([
            T.Resize((128, 128)),
            T.ToTensor(),
            T.Normalize(mean=[0.5, 0.5, 0.5],
                        std=[0.5, 0.5, 0.5]),
        ])

        self._ref_cache = {}  # ref_path -> embedding tensor

    def _load(self, path: str):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Image not found: {path}")
        img = Image.open(path).convert("RGB")
        x = self.transform(img).unsqueeze(0).to(self.device)
        return x

    @torch.no_grad()
    def _embed(self, x):
        return self.model.embedding_net(x)

    @torch.no_grad()
    def similarity(self, ref_path: str, child_path: str):
        """
        Returns (similarity_0_1, distance_float)
        """
        if ref_path not in self._ref_cache:
            ref_t = self._load(ref_path)
            self._ref_cache[ref_path] = self._embed(ref_t)

        ref_emb = self._ref_cache[ref_path]

        child_t = self._load(child_path)
        child_emb = self._embed(child_t)

        dist = euclidean_dist(ref_emb, child_emb)
        sim = torch.exp(-dist).item()

        return float(sim), float(dist.item())


# --------------------------------------------------
# Activity evaluation (optional hooks)
# --------------------------------------------------
def combine_scores(similarity: float, details: dict, activity: str) -> float:
    """
    similarity: 0..1
    returns score: 0..100
    """
    if activity == "shading":
        nn_score = similarity * 100.0  # 0..100

        coverage = float(details.get("color_coverage", 0.0))  # 0..1
        coverage_score = coverage * 100.0

        base = 0.60 * nn_score + 0.40 * coverage_score

        overflow = float(details.get("overflow_penalty", 0.0))  # 0..1
        overflow_factor = 1.0 - 0.50 * overflow
        overflow_factor = max(0.0, min(1.0, overflow_factor))

        score = base * overflow_factor
        return max(0.0, min(100.0, score))

    elif activity == "line":
        nn_score = similarity * 100.0

        angle_err = float(details.get("angle_error_deg", 180.0))
        if angle_err <= 5:
            penalty = 1.00
        elif angle_err <= 12:
            penalty = 0.85
        elif angle_err <= 20:
            penalty = 0.65
        else:
            penalty = 0.40

        score = nn_score * penalty
        return max(0.0, min(100.0, score))

    else:
        # fallback: pure similarity
        return max(0.0, min(100.0, similarity * 100.0))


def evaluate_activity(
    activity_type: str,
    reference_img: str,
    child_img: str,
    model_path: str = "ml/outputs/checkpoints/siamese.pth",
) -> tuple[float, dict]:
    """
    Returns (final_score_0_100, details_dict)
    """
    similarity, _dist = compute_similarity(reference_img, child_img, model_path)

    details = {}
    if activity_type == "shading":
        # optional: if you have this file
        from ml.shading_analysis import analyze_shading
        details = analyze_shading(reference_img, child_img)

    elif activity_type == "line":
        # optional: if you have this file
        from ml.line_analysis import analyze_line
        details = analyze_line(reference_img, child_img)

    else:
        raise ValueError("Unknown activity type. Use 'line' or 'shading'.")

    final_score = combine_scores(similarity, details, activity_type)
    return float(final_score), details


# --------------------------------------------------
# Manual test
# --------------------------------------------------
if __name__ == "_main_":
    # Example (edit paths to your real ones)
    score, details = evaluate_activity(
        activity_type="line",
        reference_img="ml/refs/game2/ref1.png",
        child_img="data/game2_submissions/user_1/step1_test.png",
        model_path="ml/outputs/checkpoints/siamese.pth",
    )
    print("Final Score:", score)
    print("Details:", details)