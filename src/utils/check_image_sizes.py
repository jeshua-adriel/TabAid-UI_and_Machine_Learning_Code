#Commnd to run this util: python src/utils/check_image_sizes.py
from pathlib import Path
import cv2

def show_sizes(folder: str):
    p = Path(folder)
    if not p.exists():
        print(f"[Missing] {folder}")
        return
    imgs = sorted([x for x in p.rglob("*") if x.suffix.lower() in [".png", ".jpg", ".jpeg"]])
    print(f"\n== {folder} ({len(imgs)} images) ==")
    for img_path in imgs[:30]:  # show first 30 to keep it readable
        img = cv2.imread(str(img_path))
        if img is None:
            print(f"  {img_path.name}: unreadable")
            continue
        h, w = img.shape[:2]
        print(f"  {img_path.name}: {w}x{h}")

if __name__ == "__main__":
    show_sizes("src/ml/refs/game2")
    show_sizes("src/ml/refs/game3")
    show_sizes("src/assets/images/guides/game2")
    show_sizes("src/assets/images/guides/game3")
    show_sizes("src/data/game2_submissions")
    show_sizes("src/data/game3_submissions")