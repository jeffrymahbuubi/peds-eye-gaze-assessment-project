"""Build every layer of the Choice-making park scene from the approved art (SPEC 4.7, step 6).

Inputs (configs/assets/scenes/park/): ``reference/style_anchor.png`` (the approved full scene,
1200 x 896) and ``background.png`` (the anchor edited with the objects removed, same framing).
Everything else is derived here, deterministically, so the layers can be rebuilt and checked:

* each object is cut out of the anchor by its difference from the background
  (``tools/layer_extract.py``); moving parts are split (seesaw plank / base, swing seat / frame,
  5 balloons / strings, 7 apples / bare tree), the tree's apple holes are filled from the leaves;
* the ground shadows the background edit removed become one shadow layer (anchor = bg x (1 - a)),
  outside every object layer (an object is darker than grass too, and would leave a ghost);
* the rainbow's tinted copies (N4) and each character's eyes-closed patch (N3, N6: only pixels
  inside the eye box change) are made from the art itself;
* ``buttons/<object>.png`` are the whole objects, for the button pictures;
* the bubble boy's blowing pose (the only redrawn picture, ``reference/bubbles_blowing_raw.png``,
  on a green key) is keyed with ``tools/chroma_key.py`` and fitted to the idle layer's box.

Coordinates below are anchor pixels. Writes the PNGs and prints every layer's box (scene
fractions), pivots and blink spots as JSON for scene.yaml.

Usage: python tools/build_park_scene.py [scene_folder]
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from layer_extract import cut, load_rgba, object_mask  # noqa: E402

W, H = 1200, 896

# Object boxes in anchor px and the extraction options that separate them cleanly.
OBJECTS = {
    "apples": ((15, 25, 435, 560), {"fill": True}),
    "cloud": ((455, 25, 775, 195), {"fill": True}),
    "balloons": ((925, 45, 1165, 490), {}),
    "rainbow": ((565, 210, 950, 400), {"fill": True}),
    "bike": ((380, 365, 615, 660), {}),
    "seesaw": ((720, 395, 1160, 690), {"exclude": ((600, 625, 800, 900),)}),
    "swing": ((40, 550, 395, 880), {}),
    "bubbles": ((610, 622, 800, 880), {"any_piece": True, "exclude": ((766, 630, 800, 660),)}),
}
APPLE_BOXES = (  # one per apple, top to bottom
    (214, 78, 261, 135), (106, 137, 154, 192), (311, 148, 357, 203), (207, 180, 254, 235),
    (47, 200, 94, 255), (96, 275, 143, 330), (318, 265, 365, 321),
)
SEESAW_BASE = np.array([(928, 571), (952, 571), (961, 585), (977, 653), (901, 653), (917, 585)], np.int32)
SEESAW_PIVOT = (940, 594)
SWING_SEAT = np.array([  # follows the right leg's inner edge; takes the seat end that lies over the leg
    (163, 581), (281, 579), (284, 700), (285, 767), (292, 767), (292, 791), (282, 791), (279, 812),
    (275, 824), (268, 832), (158, 832), (148, 760), (150, 700),
], np.int32)
SWING_LEG_HIDDEN = (283, 765, 295, 794)  # leg behind the seat end: filled from the leg around it
SWING_PIVOT = (221, 577)
# Balloon hues (OpenCV H, 0-179), front to back: a front balloon claims its outline first.
BALLOONS = (("red", (0, 8, 172, 179)), ("yellow", (19, 34)), ("orange", (9, 18)), ("blue", (90, 112)), ("purple", (135, 171)))
POP_ORDER = ("purple", "blue", "orange", "yellow", "red")  # back to front: a popped one shows sky
EYES = {  # character: (layer, left pupil, right pupil)
    "bike_rider": ("bike", (478.6, 429.7), (505.3, 427.0)),
    "seesaw_girl": ("seesaw_plank", (787.2, 457.9), (812.5, 457.5)),
    "seesaw_boy": ("seesaw_plank", (1100.7, 507.8), (1125.4, 514.1)),
    "swing_girl": ("swing_seat", (212.1, 678.2), (239.2, 674.5)),
    "bubbles_boy": ("bubbles_child", (705.6, 677.6), (735.1, 681.2)),
}


def frac_box(b: tuple[int, int, int, int]) -> list[float]:
    return [round(b[0] / W, 4), round(b[1] / H, 4), round(b[2] / W, 4), round(b[3] / H, 4)]


def frac_pt(p: tuple[float, float]) -> list[float]:
    return [round(p[0] / W, 4), round(p[1] / H, 4)]


def not_green(img: np.ndarray) -> np.ndarray:
    """True where a pixel is not grass-green (drops the grass halo and old shadow chunks)."""
    b, g, r = (img[..., i].astype(np.int16) for i in range(3))
    return ~((g > r + 15) & (g > b + 15))


def polygon_mask(poly: np.ndarray) -> np.ndarray:
    m = np.zeros((H, W), np.uint8)
    cv2.fillPoly(m, [poly], 255)
    return m


class Builder:
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self.anchor = load_rgba(str(folder / "reference" / "style_anchor.png"))
        self.bg = cv2.resize(load_rgba(str(folder / "background.png")), (W, H), interpolation=cv2.INTER_AREA)
        self.layers: dict[str, list[float]] = {}
        self.occupied = np.zeros((H, W), np.uint8)  # every object layer's pixels: no shadow there

    def save(self, rel: str, mask: np.ndarray, source: np.ndarray | None = None) -> list[float]:
        img, bbox = cut(self.anchor if source is None else source, mask)
        if rel.startswith("objects/"):
            self.occupied |= mask
        path = self.folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), img)
        self.layers[rel] = frac_box(bbox)
        return self.layers[rel]

    def mask(self, name: str) -> np.ndarray:
        box, opts = OBJECTS[name]
        return object_mask(self.anchor, self.bg, box, **opts)

    def build(self) -> dict:
        out: dict = {"pivots": {}, "blink": {}}
        masks = {name: self.mask(name) for name in OBJECTS}
        for name, m in masks.items():
            self.save(f"buttons/{name}.png", m)
        for name in ("cloud", "rainbow", "bike"):
            self.save(f"objects/{name}.png", masks[name])
        self._bubbles(masks["bubbles"])
        self._seesaw(masks["seesaw"], out)
        self._swing(masks["swing"], out)
        self._balloons(masks["balloons"])
        self._apples(masks["apples"])
        self._rainbow_tints(masks["rainbow"])
        self._shadows()
        self._blinks(out)
        out["layers"] = self.layers
        return out

    def _bubbles(self, m: np.ndarray) -> None:
        self.save("objects/bubbles_child.png", m & (not_green(self.anchor) * 255).astype(np.uint8))
        raw = self.folder / "reference" / "bubbles_blowing_raw.png"
        if raw.is_file():  # the one redraw: the blowing pose, keyed and fitted to the idle layer's box
            from chroma_key import key_out

            keyed = self.folder / "objects" / "bubbles_child_blowing.png"
            key_out(str(raw), str(keyed), str(self.folder / "reference" / "_preview.png"))
            (self.folder / "reference" / "_preview.png").unlink()
            idle = cv2.imread(str(self.folder / "objects" / "bubbles_child.png"), cv2.IMREAD_UNCHANGED)
            blow = cv2.imread(str(keyed), cv2.IMREAD_UNCHANGED)
            cv2.imwrite(str(keyed), cv2.resize(blow, (idle.shape[1], idle.shape[0]), interpolation=cv2.INTER_AREA))
            self.layers["objects/bubbles_child_blowing.png"] = self.layers["objects/bubbles_child.png"]

    def _seesaw(self, m: np.ndarray, out: dict) -> None:
        m = m & (not_green(self.anchor) * 255).astype(np.uint8)
        hsv = cv2.cvtColor(self.anchor[..., :3], cv2.COLOR_BGR2HSV)
        wood = ((hsv[..., 0] >= 5) & (hsv[..., 0] <= 30) & (hsv[..., 1] > 60)).astype(np.uint8) * 255
        base = m & polygon_mask(SEESAW_BASE) & ~wood
        base = cv2.morphologyEx(base, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        self.save("objects/seesaw_base.png", base)
        plank_img, plank = self._plank_behind_base(m & ~base)
        self.save("objects/seesaw_plank.png", plank, source=plank_img)
        out["pivots"]["seesaw_plank"] = frac_pt(SEESAW_PIVOT)

    def _plank_behind_base(self, plank: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Rebuild the plank section hidden behind the base, so no notch shows when it tilts: each
        column between two reference columns either side of the base is the left column's plank
        profile, moved along the line joining the plank's centre at both columns."""
        img, plank = self.anchor.copy(), plank.copy()
        xl, xr = 896, 984

        def span(x: int) -> tuple[int, int]:
            ys = np.nonzero(plank[560:640, x])[0] + 560
            return int(ys.min()), int(ys.max())

        (lt, lb), (rt, rb) = span(xl), span(xr)
        column = self.anchor[lt:lb + 1, xl].copy()
        for x in range(xl + 1, xr):
            f = (x - xl) / (xr - xl)
            top = int(round(lt + f * (rt - lt)))
            height = int(round((lb - lt) + f * ((rb - rt) - (lb - lt)))) + 1
            col = cv2.resize(column[:, None, :], (1, height), interpolation=cv2.INTER_LINEAR)[:, 0, :]
            hidden = plank[top:top + height, x] == 0
            img[top:top + height, x][hidden] = col[hidden]
            plank[top:top + height, x] = 255
        return img, plank

    def _swing(self, m: np.ndarray, out: dict) -> None:
        m = m & (not_green(self.anchor) * 255).astype(np.uint8)
        seat = m & polygon_mask(SWING_SEAT)
        self.save("objects/swing_seat.png", seat)
        x0, y0, x1, y1 = SWING_LEG_HIDDEN
        hidden = np.zeros((H, W), np.uint8)
        hidden[y0:y1, x0:x1] = seat[y0:y1, x0:x1]
        frame_img = self.anchor.copy()
        frame_img[..., :3] = cv2.inpaint(self.anchor[..., :3], hidden, 4, cv2.INPAINT_TELEA)
        self.save("objects/swing_frame.png", (m & ~seat) | hidden, source=frame_img)
        out["pivots"]["swing_seat"] = frac_pt(SWING_PIVOT)

    def _balloons(self, m: np.ndarray) -> None:
        hsv = cv2.cvtColor(self.anchor[..., :3], cv2.COLOR_BGR2HSV)
        h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
        coloured = (s > 60) & (v > 100) & (m > 0)
        coloured[265:] = False  # balloons and knots only; below are the strings
        claimed = np.zeros((H, W), np.uint8)
        for colour, ranges in BALLOONS:
            hue = np.zeros((H, W), bool)
            for lo, hi in zip(ranges[0::2], ranges[1::2], strict=True):
                hue |= (h >= lo) & (h <= hi)
            own = (coloured & hue).astype(np.uint8) * 255
            own = cv2.morphologyEx(own, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
            # Take the outline too: only dark or uncoloured pixels next to the balloon, never another hue.
            rim = ((v < 110) | (s <= 60)).astype(np.uint8) * 255
            own = (own | (cv2.dilate(own, np.ones((7, 7), np.uint8)) & rim)) & m & ~claimed
            count, labels, stats, _ = cv2.connectedComponentsWithStats(own, connectivity=8)
            for i in range(1, count):
                if stats[i, cv2.CC_STAT_AREA] < 150:  # a stray knot or speck of another balloon
                    own[labels == i] = 0
            claimed |= own
            self.save(f"objects/balloon_{POP_ORDER.index(colour) + 1}.png", own)
        strings = m & ~claimed
        count, labels, stats, _ = cv2.connectedComponentsWithStats(strings, connectivity=8)
        for i in range(1, count):
            if stats[i, cv2.CC_STAT_AREA] < 40:  # outline crumbs of popped balloons
                strings[labels == i] = 0
        self.save("objects/balloons_strings.png", strings)

    def _apples(self, m: np.ndarray) -> None:
        green = ~not_green(self.anchor)
        holes = np.zeros((H, W), np.uint8)
        for i, (x0, y0, x1, y1) in enumerate(APPLE_BOXES, start=1):
            apple = np.zeros((H, W), np.uint8)
            apple[y0:y1, x0:x1] = ((~green[y0:y1, x0:x1]) & (m[y0:y1, x0:x1] > 0)).astype(np.uint8) * 255
            apple = cv2.morphologyEx(apple, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
            self.save(f"objects/apple_{i}.png", cv2.erode(apple, np.ones((3, 3), np.uint8)))  # no leaf fringe
            holes |= cv2.dilate(apple, np.ones((5, 5), np.uint8))
        tree = self.anchor.copy()
        tree[..., :3] = cv2.inpaint(self.anchor[..., :3], holes, 6, cv2.INPAINT_TELEA)
        self.save("objects/apples_tree.png", m, source=tree)

    def _rainbow_tints(self, m: np.ndarray) -> None:
        hsv = cv2.cvtColor(self.anchor[..., :3], cv2.COLOR_BGR2HSV).astype(np.int16)
        bright = self.anchor.copy()
        bright[..., :3] = (self.anchor[..., :3].astype(np.float32) * 0.45 + 255 * 0.55).astype(np.uint8)
        shifted = hsv.copy()
        shifted[..., 0] = (shifted[..., 0] + 30) % 180
        turned = self.anchor.copy()
        turned[..., :3] = cv2.cvtColor(shifted.astype(np.uint8), cv2.COLOR_HSV2BGR)
        self.save("objects/rainbow_tint_1.png", m, source=bright)  # a white shimmer
        self.save("objects/rainbow_tint_2.png", m, source=turned)  # colours turned 60 deg

    def _shadows(self) -> None:
        anc = self.anchor[..., :3].astype(np.float32)
        bg = self.bg[..., :3].astype(np.float32)
        a = 1 - np.clip((anc / np.maximum(bg, 1)).mean(axis=2), 0, 1)
        a[:450] = 0  # grass only (horizon at y ~ 448)
        a[a < 0.06] = 0
        a[360:650, 380:610] = 0  # the bike rides away: no shadow left behind
        a[cv2.dilate(self.occupied, np.ones((5, 5), np.uint8)) > 0] = 0  # objects are not shadows
        a = cv2.GaussianBlur(a, (5, 5), 0)
        rgba = np.zeros((H, W, 4), np.uint8)
        rgba[..., 3] = (np.clip(a, 0, 1) * 255).astype(np.uint8)
        path = self.folder / "layers" / "shadows.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), rgba)
        self.layers["layers/shadows.png"] = [0.0, 0.0, 1.0, 1.0]

    def _blinks(self, out: dict) -> None:
        """Eyes-closed patch per character: the pupils painted over with the face's own skin colour
        and a lash line in the outline colour; only pixels inside the eye box differ."""
        for spot, (layer, left, right) in EYES.items():
            # A margin wide enough that the anti-aliased lids never reach the patch's edge.
            x0, y0 = int(min(left[0], right[0]) - 10), int(min(left[1], right[1]) - 10)
            x1, y1 = int(max(left[0], right[0]) + 11), int(max(left[1], right[1]) + 11)
            patch = self.anchor[y0:y1, x0:x1].copy()
            ink = tuple(int(c) for c in patch[..., :3].reshape(-1, 3)[patch[..., :3].sum(axis=2).argmin()])
            for cx, cy in (left, right):
                px, py = cx - x0, cy - y0
                ring = [patch[int(py + dy), int(px + dx), :3] for dx, dy in ((0, 7), (-6, 4), (6, 4), (-7, 0), (7, 0))
                        if 0 <= int(py + dy) < patch.shape[0] and 0 <= int(px + dx) < patch.shape[1]]
                skin = tuple(int(c) for c in np.median(np.array(ring), axis=0))
                cv2.ellipse(patch, (int(round(px)), int(round(py))), (4, 5), 0, 0, 360, (*skin, 255), -1, cv2.LINE_AA)
                cv2.ellipse(patch, (int(round(px)), int(round(py - 1))), (4, 3), 0, 10, 170, (*ink, 255), 2, cv2.LINE_AA)
            patch[..., 3] = 255
            path = self.folder / "blink" / f"{spot}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(path), patch)
            mid = ((left[0] + right[0]) / 2, (left[1] + right[1]) / 2)
            out["blink"][spot] = {"layer": layer, "xy": frac_pt(mid), "box": frac_box((x0, y0, x1, y1)),
                                  "r": round(abs(right[0] - left[0]) / 2 / W, 4), "image": f"blink/{spot}.png"}


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "configs" / "assets" / "scenes" / "park"
    print(json.dumps(Builder(folder).build(), indent=1))


if __name__ == "__main__":
    main()
