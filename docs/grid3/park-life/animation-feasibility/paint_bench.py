"""Throughput of layered-sprite scene painting with QPainter (raster), 1920x1080 target."""
import math, random, sys, time
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPixmap, QRadialGradient, QTransform

app = QGuiApplication(sys.argv)
W, H = 1920, 1080
SW, SH = 1400, 1050

def noisy(w, h, alpha):
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    rnd = random.Random(w * h)
    for _ in range(60):
        c = QColor(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256), 255 if not alpha else rnd.randrange(120, 256))
        g = QRadialGradient(rnd.uniform(0, w), rnd.uniform(0, h), rnd.uniform(10, max(w, h) / 3))
        g.setColorAt(0, c); g.setColorAt(1, QColor(c.red(), c.green(), c.blue(), 0))
        p.setBrush(g); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(0, 0, w, h))
    p.end()
    return img

bg = QPixmap.fromImage(noisy(SW, SH, False))
layers = [QPixmap.fromImage(noisy(rw, rh, True)) for rw, rh in
          [(420, 500), (300, 220), (160, 220), (400, 470), (560, 150), (450, 260), (280, 270), (150, 200), (330, 260), (200, 150)]]
bubble = QPixmap.fromImage(noisy(60, 60, True))
# Rainbow hue cycle: 12 precomputed tinted variants (no per-frame pixel work)
rain = noisy(450, 260, True)
rain_variants = []
for k in range(12):
    v = QImage(rain); pp = QPainter(v)
    pp.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceAtop)
    pp.fillRect(v.rect(), QColor.fromHsv(k * 30, 200, 255, 90)); pp.end()
    rain_variants.append(QPixmap.fromImage(v))

target = QImage(W, H, QImage.Format.Format_ARGB32_Premultiplied)

def frame(t, smooth, all_active):
    p = QPainter(target)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, smooth)
    p.fillRect(target.rect(), QColor("#101418"))
    ox, oy = (W - SW) / 2, (H - SH) / 2
    p.drawPixmap(int(ox), int(oy), bg)
    for i, pm in enumerate(layers):
        p.save()
        active = all_active or i == 0
        x = ox + 80 * i + (200 * math.sin(t) if active else 0)
        y = oy + 60 * i
        p.translate(x + pm.width() / 2, y)
        if active:
            p.rotate(12 * math.sin(t * 6))
            p.scale(1 + 0.03 * math.sin(t * 3), 1 + 0.03 * math.sin(t * 3))
        p.drawPixmap(QPointF(-pm.width() / 2, 0), pm)
        p.restore()
    if all_active:
        for b in range(10):
            p.setOpacity(0.5 + 0.5 * math.sin(t + b))
            p.drawPixmap(QPointF(ox + 700 + 30 * b - 100 * t % 300, oy + 900 - (t * 120 + b * 40) % 700), bubble)
        p.setOpacity(1.0)
        p.drawPixmap(int(ox + 600), int(oy + 120), rain_variants[int(t * 12) % 12])
    # 8 buttons + cursor ring approximation
    for k in range(8):
        p.setBrush(QColor(40, 100, 160)); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(10 if k < 4 else W - 250, 20 + 260 * (k % 4), 240, 240), 24, 24)
    p.end()

for smooth in (False, True):
    for all_active in (False, True):
        for _ in range(5):
            frame(0, smooth, all_active)
        n = 200
        t0 = time.perf_counter()
        for i in range(n):
            frame(i / 60, smooth, all_active)
        ms = (time.perf_counter() - t0) * 1000 / n
        print(f"smooth={smooth} all_layers_animating={all_active}: {ms:.2f} ms/frame ({1000/ms:.0f} fps max)")
