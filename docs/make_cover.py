"""Textless cover: two agents, a sealed envelope passing through an IAM gate.

    python3 docs/make_cover.py

Writes docs/devto-cover.<hash>.jpg (1376x578) and docs/builder-cover.<hash>.jpg
(1200x675), drawn at 2x and downsampled, named by a hash of their bytes.
"""

from __future__ import annotations

import hashlib
import io
import pathlib

from PIL import Image, ImageDraw

OUT = pathlib.Path(__file__).resolve().parent
SURFACE = (26, 26, 25)
PAPER = (236, 233, 222)
RULE = (58, 58, 55)
MUTED = (128, 127, 120)
BLUE = (57, 135, 229)
ORANGE = (217, 89, 38)


def agent(d, cx, cy, r, colour):
    """A round robot head: body, antenna, two eyes."""
    d.line([(cx, cy - r), (cx, cy - r * 1.45)], fill=colour, width=int(r * 0.12))
    d.ellipse([cx - r * 0.16, cy - r * 1.62, cx + r * 0.16, cy - r * 1.3], fill=colour)
    d.rounded_rectangle(
        [cx - r, cy - r, cx + r, cy + r], radius=int(r * 0.45), fill=colour
    )
    for ex in (-0.38, 0.38):
        d.ellipse(
            [
                cx + ex * r - r * 0.17,
                cy - r * 0.25,
                cx + ex * r + r * 0.17,
                cy + r * 0.09,
            ],
            fill=SURFACE,
        )
    d.rounded_rectangle(
        [cx - r * 0.4, cy + r * 0.38, cx + r * 0.4, cy + r * 0.5],
        radius=int(r * 0.06),
        fill=SURFACE,
    )


def gate(d, cx, cy, w, h):
    """An arched gate with a keyhole."""
    t = int(w * 0.16)
    d.rounded_rectangle(
        [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2],
        radius=int(w / 2),
        outline=PAPER,
        width=t,
    )
    kr = w * 0.13
    ky = cy - h * 0.08
    d.ellipse([cx - kr, ky - kr, cx + kr, ky + kr], fill=PAPER)
    d.polygon(
        [
            (cx - kr * 0.55, ky),
            (cx + kr * 0.55, ky),
            (cx + kr * 0.9, ky + kr * 2.6),
            (cx - kr * 0.9, ky + kr * 2.6),
        ],
        fill=PAPER,
    )


def envelope(d, cx, cy, w):
    h = w * 0.64
    box = [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]
    d.rounded_rectangle(box, radius=int(w * 0.05), fill=PAPER)
    lw = max(2, int(w * 0.035))
    d.line(
        [(box[0], box[1]), (cx, cy + h * 0.08), (box[2], box[1])], fill=MUTED, width=lw
    )
    sr = w * 0.15
    sy = cy + h * 0.08
    d.ellipse([cx - sr, sy - sr, cx + sr, sy + sr], fill=ORANGE)
    d.ellipse(
        [cx - sr * 0.5, sy - sr * 0.5, cx + sr * 0.5, sy + sr * 0.5],
        outline=SURFACE,
        width=max(2, int(sr * 0.18)),
    )


def draw(width, height):
    s = 2
    W, H = width * s, height * s
    img = Image.new("RGB", (W, H), SURFACE)
    d = ImageDraw.Draw(img)
    cy = H * 0.54
    u = min(H, W / 2.381)  # size everything from the 2.381:1 band
    r = u * 0.17
    gw, gh = u * 0.34, u * 0.62
    lx, rx, gx = W / 2 - u * 0.95, W / 2 + u * 0.95, W / 2
    left_edge, gate_edge = lx + r, gx - gw / 2
    for i in range(1, 30):
        x = lx + r * 1.3 + (rx - lx - r * 2.6) * i / 30
        if abs(x - gx) < gw / 2:
            continue
        dot = u * 0.011
        d.ellipse([x - dot, cy - dot, x + dot, cy + dot], fill=RULE)
    agent(d, lx, cy, r, BLUE)
    agent(d, rx, cy, r, ORANGE)
    gate(d, gx, cy, gw, gh)
    gap = gate_edge - left_edge
    envelope(d, left_edge + gap / 2, cy, min(u * 0.3, gap * 0.7))
    return img.resize((width, height), Image.LANCZOS)


def save(img, stem):
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92, optimize=True)
    data = buf.getvalue()
    name = f"{stem}.{hashlib.sha256(data).hexdigest()[:8]}.jpg"
    (OUT / name).write_bytes(data)
    print(f"wrote docs/{name}  {img.size[0]}x{img.size[1]}  {len(data) // 1024} KB")


if __name__ == "__main__":
    save(draw(1376, 578), "devto-cover")
    save(draw(1200, 675), "builder-cover")
