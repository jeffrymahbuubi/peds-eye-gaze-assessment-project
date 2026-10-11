"""Cut object layers out of a scene picture by its difference from the empty background.

Used for the Choice-making park art (SPEC-scene-cause-effect-task.md 4.7, step 6): the approved
style anchor shows every object; an edit of it with the objects removed is the background. Where
the two differ is the object. The difference mask is split into connected pieces; the pieces of
the object (see ``object_mask``) are cut out of the scene picture with a 1 px soft edge. The
result keeps the anchor's exact style and position; nothing is redrawn.

Usage (one layer):
    python tools/layer_extract.py <scene.png> <background.png> <out.png> x0 y0 x1 y1
        [--fill] [--any] [--exclude X0 Y0 X1 Y1]... [--threshold T] [--min-area N]
The box is in pixels of <scene.png>; the background is scaled to the scene's size first. Prints the
cut-out's bounding box in pixels and in scene fractions (for scene.yaml).
"""

import argparse

import cv2
import numpy as np

THRESHOLD = 40  # max channel difference that counts as "object"


def load_rgba(path: str) -> np.ndarray:
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise SystemExit(f"cannot read {path}")
    if img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    return img


def components(scene: np.ndarray, background: np.ndarray, threshold: int) -> tuple[int, np.ndarray, np.ndarray, np.ndarray]:
    """Connected pieces of the whole difference mask: (count, labels, stats, centroids)."""
    diff = np.abs(scene[..., :3].astype(np.int16) - background[..., :3].astype(np.int16)).max(axis=2)
    mask = (diff > threshold).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    return cv2.connectedComponentsWithStats(mask, connectivity=8)


def fill_holes(mask: np.ndarray) -> np.ndarray:
    """Fill enclosed holes (for objects whose colour is close to the sky or grass, e.g. a cloud).
    Not for objects that enclose background (a swing frame, a wheel)."""
    pad = cv2.copyMakeBorder(mask, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
    flood = pad.copy()
    cv2.floodFill(flood, np.zeros((pad.shape[0] + 2, pad.shape[1] + 2), np.uint8), (0, 0), 255)
    return (pad | cv2.bitwise_not(flood))[1:-1, 1:-1]


def object_mask(
    scene: np.ndarray,
    background: np.ndarray,
    box: tuple[int, int, int, int],
    *,
    min_area: int = 30,
    threshold: int = THRESHOLD,
    fill: bool = False,
    any_piece: bool = False,
    exclude: tuple[tuple[int, int, int, int], ...] = (),
) -> np.ndarray:
    """Binary mask (uint8 0/255, full scene size) of the object in ``box``.

    By default a piece belongs to the box holding its centroid, so a neighbour reaching into the box
    is not taken; ``any_piece`` takes every piece overlapping the box instead (for an object joined
    to a neighbour, e.g. by a ground shadow). The result is clipped to the box, ``exclude``
    rectangles are cleared, then holes are filled if ``fill``."""
    x0, y0, x1, y1 = box
    count, labels, stats, centroids = components(scene, background, threshold)
    keep = np.zeros(labels.shape, np.uint8)
    inside = labels[y0:y1, x0:x1]
    for i in range(1, count):
        if stats[i, cv2.CC_STAT_AREA] < min_area:
            continue
        cx, cy = centroids[i]
        if (any_piece and (inside == i).any()) or (x0 <= cx < x1 and y0 <= cy < y1):
            keep[labels == i] = 255
    clipped = np.zeros_like(keep)
    clipped[y0:y1, x0:x1] = keep[y0:y1, x0:x1]
    for ex0, ey0, ex1, ey1 in exclude:
        clipped[ey0:ey1, ex0:ex1] = 0
    return fill_holes(clipped) if fill else clipped


def cut(scene: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """RGBA cut-out cropped to the mask, with a 1 px soft edge; and its pixel bbox (x0, y0, x1, y1)."""
    soft = cv2.GaussianBlur(cv2.dilate(mask, np.ones((3, 3), np.uint8)), (3, 3), 0)
    ys, xs = np.nonzero(soft)
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
    out = scene[y0:y1, x0:x1].copy()
    out[..., 3] = soft[y0:y1, x0:x1]
    return out, (x0, y0, x1, y1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("background")
    ap.add_argument("out")
    ap.add_argument("box", nargs=4, type=int)
    ap.add_argument("--min-area", type=int, default=30)
    ap.add_argument("--threshold", type=int, default=THRESHOLD)
    ap.add_argument("--fill", action="store_true", help="fill enclosed holes")
    ap.add_argument("--any", action="store_true", help="take every piece overlapping the box")
    ap.add_argument("--exclude", type=int, nargs=4, action="append", default=[], metavar=("X0", "Y0", "X1", "Y1"))
    a = ap.parse_args()
    scene = load_rgba(a.scene)
    h, w = scene.shape[:2]
    background = cv2.resize(load_rgba(a.background), (w, h), interpolation=cv2.INTER_AREA)
    mask = object_mask(
        scene, background, tuple(a.box), min_area=a.min_area, threshold=a.threshold, fill=a.fill,
        any_piece=a.any, exclude=tuple(tuple(e) for e in a.exclude),
    )
    if not mask.any():
        raise SystemExit("no object found in the box")
    out, (x0, y0, x1, y1) = cut(scene, mask)
    cv2.imwrite(a.out, out)
    print(f"bbox_px {x0} {y0} {x1} {y1}  box {x0 / w:.4f} {y0 / h:.4f} {x1 / w:.4f} {y1 / h:.4f}")


if __name__ == "__main__":
    main()
