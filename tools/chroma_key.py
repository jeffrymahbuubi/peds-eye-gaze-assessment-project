"""Remove a flat green key colour from an AI-generated object picture.

Used for the Choice-making scene art (SPEC-scene-cause-effect-task.md 4.7, step 2 pipeline):
the image tool cannot return a transparent PNG, so each object is drawn alone on flat
#00FF00 and keyed out here. Output is cropped to the object; a preview on a checkerboard
and on a dark colour is written next to it for the user's approval.

Usage: python tools/chroma_key.py <in.png> <out.png> <preview.png>
"""

import sys

import numpy as np
from PySide6.QtGui import QColor, QImage, QPainter

# Greenness d = G - max(R, B): d <= LOW keeps the pixel, d >= LOW + RAMP removes it.
LOW, RAMP = 60.0, 100.0


def key_out(src: str, out: str, preview: str) -> tuple[int, int, int, int]:
    im = QImage(src).convertToFormat(QImage.Format.Format_RGBA8888)
    w, h = im.width(), im.height()
    raw = np.frombuffer(im.constBits(), np.uint8).reshape(h, im.bytesPerLine())
    a = raw[:, : w * 4].reshape(h, w, 4).astype(np.float32)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    rb = np.maximum(r, b)
    d = g - rb
    alpha = np.clip(1 - (d - LOW) / RAMP, 0, 1)
    # Despill: on edge pixels with a green tint, clamp G to max(R, B).
    a[..., 1] = np.where((alpha < 1) & (d > 0), rb, g)
    a[..., 3] = alpha * 255
    ys, xs = np.nonzero(alpha > 0.05)
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    crop = np.ascontiguousarray(a[y0 : y1 + 1, x0 : x1 + 1].astype(np.uint8))
    ch, cw = crop.shape[:2]
    oi = QImage(crop.data, cw, ch, cw * 4, QImage.Format.Format_RGBA8888).copy()
    oi.save(out)

    pv = QImage(cw * 2 + 20, ch, QImage.Format.Format_RGBA8888)
    pv.fill(QColor("#ffffff"))
    p = QPainter(pv)
    for yy in range(0, ch, 16):
        for xx in range(0, cw, 16):
            if (xx // 16 + yy // 16) % 2:
                p.fillRect(xx, yy, 16, 16, QColor("#cccccc"))
    p.fillRect(cw + 20, 0, cw, ch, QColor("#2b3a55"))
    p.drawImage(0, 0, oi)
    p.drawImage(cw + 20, 0, oi)
    p.end()
    pv.save(preview)
    return x0, y0, x1, y1


if __name__ == "__main__":
    print("bbox", key_out(*sys.argv[1:4]))
