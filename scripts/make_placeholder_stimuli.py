"""Create six PLACEHOLDER profile images and the stimulus manifest.

These neutral silhouettes are used only for development and testing. Before
data collection they must be replaced by the final licensed synthetic face
images (same file names), after which this script's --manifest-only mode
recomputes the SHA-256 hashes."""
import hashlib
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "static", "stimuli")

PROFILES = [
    ("P1", "Aruzhan", 21, "Third-year student. I like long walks along the Yesil embankment, board games and trying new coffee places."),
    ("P2", "Daniyar", 22, "Into football on weekends and learning to cook. Looking for someone to explore the city with."),
    ("P3", "Madina", 20, "I read a lot, mostly fantasy and history. Weekends are for the cinema or a quiet park."),
    ("P4", "Timur", 23, "Engineering student who enjoys cycling and photography. Always up for a good conversation."),
    ("P5", "Aigerim", 22, "I draw, listen to podcasts and love travelling around Kazakhstan by train."),
    ("P6", "Nurlan", 24, "Gym in the morning, coding in the evening. I'd like to meet someone calm and kind."),
]
BG = ["#c9d6df", "#d8cfc4", "#cfd8c4", "#d6c9df", "#dfd2c9", "#c4d3d8"]


def draw_placeholder(path, bg):
    w, h = 600, 750
    img = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)
    d.ellipse((200, 150, 400, 370), fill="#8a949c")          # head
    d.rounded_rectangle((120, 400, 480, 760), 160, fill="#8a949c")  # shoulders
    try:
        f = ImageFont.truetype("DejaVuSans-Bold.ttf", 28)
    except OSError:
        f = ImageFont.load_default()
    d.text((w / 2, 60), "PLACEHOLDER", fill="#4a5258", font=f, anchor="mm")
    img.save(path, "PNG", optimize=False)


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main(manifest_only=False):
    os.makedirs(OUT, exist_ok=True)
    manifest = []
    for (pid, name, age, bio), bg in zip(PROFILES, BG):
        fname = f"{pid}.png"
        fpath = os.path.join(OUT, fname)
        if not manifest_only:
            draw_placeholder(fpath, bg)
        manifest.append({"profile_id": pid, "display_name": name, "age": age,
                         "bio": bio, "image_file": fname, "image_sha256": sha256(fpath),
                         "placeholder": not manifest_only})
    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    for m in manifest:
        print(m["profile_id"], m["image_file"], m["image_sha256"])


if __name__ == "__main__":
    main(manifest_only="--manifest-only" in sys.argv)
