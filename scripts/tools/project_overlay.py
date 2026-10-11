#!/usr/bin/env python3
"""project_overlay.py -- project the spec's 3D geometry through a reference camera onto the
reference image, to check camera placement and spec geometry against the reference.

    python3 scripts/tools/project_overlay.py <spec.json> <REF_ID> <out.jpg>
            [--camera JSON_OVERRIDE] [--json out.json] [--rooms all|camera]
    python3 scripts/tools/project_overlay.py <spec.json> --all OUTDIR [--json out.json]

* The image is the reference for REF_ID from references/manifest.json; ids not in the manifest
  (fixture cameras such as FIX01) get a neutral grey 960x540 canvas.
* The camera comes from spec["cameras"] (ref == REF_ID); --camera '{"position":[..],
  "look_at":[..],"horizontal_fov_deg":..,"roll_deg":..}' (or a path to such a JSON file)
  overrides individual fields (or supplies the whole camera when the spec has none).
* Camera math = SCHEMA.md "Camera math" via spec_lib.project / project_segment; segments are
  clipped in camera space at zc = 0.05 (no wrapped lines) and then to the image.
* Drawn on a darkened copy of the reference: room wireframes in cyan (floor-wall lines,
  ceiling-wall lines that follow sloped ceilings, vertical corners, slope break / crease
  lines; the camera's own room bright, other rooms dim), openings in yellow on both wall faces
  with jamb depth lines, dormer recesses in orange, items as 3D boxes (12 edges + a front
  tick) with labels in magenta, lights as white crosses, and a HUD with the camera numbers.
* --json writes projected 2D positions of item centres, opening corners and lights.
* --all OUTDIR writes OUTDIR/<REF>.jpg for every camera in the spec.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spec_lib as S  # noqa: E402

SS = 2
GREY_SIZE = (960, 540)
CYAN, CYAN_DIM = (0, 255, 255), (0, 150, 165)
YELLOW, YELLOW_DIM = (255, 225, 0), (170, 150, 20)
ORANGE = (255, 145, 0)
MAGENTA, MAGENTA_DIM = (255, 40, 255), (175, 70, 175)
WHITE = (255, 255, 255)


def simplify_polyline(P, tol=1e-6):
    """Drop interior points that are collinear (3D) with their neighbours."""
    P = np.asarray(P, float)
    if len(P) <= 2:
        return P
    keep = [0]
    for i in range(1, len(P) - 1):
        a, b, c = P[keep[-1]], P[i], P[i + 1]
        u, v = b - a, c - b
        nu, nv = np.linalg.norm(u), np.linalg.norm(v)
        if nu < 1e-12:
            continue
        if nv < 1e-12 or np.linalg.norm(np.cross(u / nu, v / nv)) > tol:
            keep.append(i)
    keep.append(len(P) - 1)
    return P[keep]


def build_camera(spec: S.Spec, ref: str, override=None) -> dict:
    base = dict(spec.camera(ref) or {})
    if override:
        if isinstance(override, str):
            p = Path(override)
            ov = S.load_json(p) if p.exists() else json.loads(override)
        else:
            ov = dict(override)
        base.update(ov)
    base.setdefault("ref", ref)
    base.setdefault("roll_deg", 0.0)
    missing = [k for k in ("position", "look_at", "horizontal_fov_deg") if k not in base]
    if missing:
        raise ValueError(f"no camera for '{ref}' in the spec and override lacks {missing}")
    if not base.get("room"):
        base["room"] = spec.room_at(base["position"][0], base["position"][1])
    return base


def load_canvas(ref: str, manifest=None):
    """(RGB image, path or None). Grey 960x540 when ``ref`` is not in the manifest."""
    path = S.reference_image_path(ref, manifest)
    if path is None:
        return Image.new("RGB", GREY_SIZE, (128, 128, 128)), None
    return Image.open(path).convert("RGB"), path


class Overlay:
    def __init__(self, spec: S.Spec, cam: dict, img: Image.Image, rooms_mode: str = "all"):
        self.spec, self.cam = spec, cam
        self.W, self.H = img.size
        dark = ImageEnhance.Brightness(img).enhance(0.55)
        self.img = dark.resize((self.W * SS, self.H * SS), Image.LANCZOS).convert("RGBA")
        self.d = ImageDraw.Draw(self.img)
        self.rooms_mode = rooms_mode
        fs = max(10, int(round(self.W / 75)))
        self.font = S.load_font(fs * SS)
        self.font_b = S.load_font(fs * SS, bold=True)
        self.font_s = S.load_font(max(9, fs - 2) * SS)
        self.placed = []
        self.k = S.focal_px(cam, self.W)
        S.camera_basis(cam)  # raises early for degenerate cameras

    # -- primitives
    def seg(self, p0, p1, col, width=1.5):
        s = S.project_segment(p0, p1, self.cam, self.W, self.H)
        if s is None:
            return None
        (u0, v0), (u1, v1) = s
        self.d.line([u0 * SS, v0 * SS, u1 * SS, v1 * SS], fill=col, width=max(1, int(round(width * SS))))
        return s

    def polyline(self, P, col, width=1.5):
        P = simplify_polyline(P)
        for a, b in zip(P[:-1], P[1:]):
            self.seg(a, b, col, width)

    def uv(self, p):
        uv, zc = S.project(np.asarray(p, float), self.cam, self.W, self.H)
        return uv, zc

    def in_frame(self, uv):
        return uv is not None and np.all(np.isfinite(uv)) and 0 <= uv[0] <= self.W and 0 <= uv[1] <= self.H

    def label(self, uv, text, col, font=None, force=False):
        font = font or self.font
        x, y = uv[0] * SS, uv[1] * SS
        for dx, dy in ((0, 0), (0, -14), (0, 14), (40, 0), (-40, 0), (0, -28), (0, 28)):
            c = (x + dx * SS, y + dy * SS)
            box = self.d.textbbox(c, text, font=font, anchor="mm", stroke_width=2 * SS)
            ok = all(box[2] <= b[0] or b[2] <= box[0] or box[3] <= b[1] or b[3] <= box[1] for b in self.placed)
            if ok or force:
                self.placed.append(box)
                self.d.text(c, text, font=font, fill=col, anchor="mm", stroke_width=2 * SS, stroke_fill=(0, 0, 0))
                return True
        return False

    def room_visible(self, rid):
        return self.rooms_mode == "all" or rid == self.cam.get("room")

    # -- layers
    def draw_rooms(self):
        for rid, room in self.spec.rooms.items():
            if not self.room_visible(rid):
                continue
            own = rid == self.cam.get("room")
            col, wd = (CYAN, 2.0) if own else (CYAN_DIM, 1.2)
            try:
                poly = np.asarray(room["polygon"], float)
            except (KeyError, TypeError, ValueError):
                continue
            n = len(poly)
            for i in range(n):
                a, b = poly[i], poly[(i + 1) % n]
                L = float(np.linalg.norm(b - a))
                self.seg([a[0], a[1], 0.0], [b[0], b[1], 0.0], col, wd)
                m = max(2, int(math.ceil(L / 0.05)) + 1)
                t = np.linspace(0, 1, m)[:, None]
                pts = a + t * (b - a)
                z = np.asarray(self.spec.ceiling_z(rid, pts[:, 0], pts[:, 1]))
                self.polyline(np.column_stack([pts, z]), col, wd)
                zc = float(self.spec.ceiling_z(rid, a[0], a[1]))
                self.seg([a[0], a[1], 0.0], [a[0], a[1], zc], col, wd)
            for line in self.spec.ceiling_creases(rid):
                self.polyline(line, col, wd)

    def draw_openings(self, data):
        for w, o in self.spec.openings():
            try:
                sides = self.spec.opening_side_rooms(w, o)
                faces = {sd: S.opening_face_rect(w, o, sd) for sd in ("left", "right")}
            except (KeyError, TypeError, ValueError):
                continue
            rooms = [r for r in (sides["left"], sides["right"]) if r]
            if rooms and not any(self.room_visible(r) for r in rooms):
                continue
            near = self.cam.get("room") in rooms
            col, wd = (YELLOW, 2.0) if near else (YELLOW_DIM, 1.3)
            entry = {"wall": w.get("id"), "type": o.get("type"), "faces": {}}
            for sd, R in faces.items():
                for i in range(4):
                    self.seg(R[i], R[(i + 1) % 4], col, wd)
                uv, zc = S.project(R, self.cam, self.W, self.H)
                entry["faces"][sd] = {
                    "room": sides[sd],
                    "corners_world": R.round(4).tolist(),
                    "corners_px": [None if not np.all(np.isfinite(p)) else [round(float(p[0]), 2), round(float(p[1]), 2)]
                                   for p in uv],
                    "depth": [round(float(z), 4) for z in zc],
                }
            for i in range(4):
                self.seg(faces["left"][i], faces["right"][i], col, max(1.0, wd - 0.8))
            if o.get("type") == "dormer":
                g = self.spec.dormer_geometry(w, o)
                if g:
                    inner, front = g["inner"], g["front"]
                    for i in range(4):
                        self.seg(front[i], front[(i + 1) % 4], ORANGE, wd)
                        self.seg(inner[i], front[i], ORANGE, wd)
                    for line in g["cut_lines"]:
                        self.polyline(line, ORANGE, wd)
                    entry["dormer_front_px"] = [None if not np.all(np.isfinite(p)) else [round(float(p[0]), 2), round(float(p[1]), 2)]
                                                for p in S.project(front, self.cam, self.W, self.H)[0]]
            c = faces[sides["left"] and "left" or "right"].mean(axis=0) if rooms else faces["left"].mean(axis=0)
            if self.cam.get("room") in rooms:
                side = "left" if sides["left"] == self.cam.get("room") else "right"
                c = faces[side].mean(axis=0)
            uv, zc = self.uv(c)
            if zc > S.NEAR_CLIP and self.in_frame(uv):
                self.label(uv, str(o.get("id")), col, self.font_s)
            data["openings"][o.get("id")] = entry

    def draw_items(self, data):
        cam_room = self.cam.get("room")
        items = list(self.spec.items)
        # far first so near labels win placement later? place labels near-first instead
        depth = []
        for it in items:
            try:
                depth.append(float(S.world_to_camera(S.item_center(it), self.cam)[0, 2]))
            except (KeyError, TypeError, ValueError, IndexError):
                depth.append(float("inf"))
        order = np.argsort(depth)
        for idx in order:
            it = items[idx]
            rid = it.get("room")
            if not self.room_visible(rid):
                continue
            try:
                B = S.item_box_corners(it)
            except (KeyError, TypeError, ValueError, IndexError):
                continue
            own = rid == cam_room or cam_room is None
            col, wd = (MAGENTA, 1.8) if own else (MAGENTA_DIM, 1.1)
            segs = [self.seg(B[i], B[j], col, wd) for i, j in S.BOX_EDGES]
            # front tick: from the centre of the front face, 15 cm outward
            z0, z1 = S.item_z_range(it)
            fe = S.item_front_edge(it)
            fc = np.array([*(0.5 * (fe[0] + fe[1])), 0.5 * (z0 + z1)])
            fwd = S.yaw_forward(it.get("yaw_deg", 0))
            self.seg(fc, fc + np.array([fwd[0], fwd[1], 0.0]) * 0.15, col, wd + 0.8)
            ctr = S.item_center(it)
            uv, zc = self.uv(ctr)
            vis = bool(zc > S.NEAR_CLIP and self.in_frame(uv))
            # label anchor: centre, else top/bottom face centre, else mean of the visible edge points
            anchor = uv if vis else None
            if anchor is None:
                for zz in (z1, z0):
                    q, qz = self.uv(np.array([ctr[0], ctr[1], zz]))
                    if qz > S.NEAR_CLIP and self.in_frame(q):
                        anchor = q
                        break
            if anchor is None:
                pts = [p for sg in segs if sg is not None for p in sg
                       if 0 <= p[0] <= self.W and 0 <= p[1] <= self.H]
                if pts:
                    anchor = np.mean(np.array(pts), axis=0)
                    anchor = np.clip(anchor, [20, 10], [self.W - 20, self.H - 10])
            data["items"][it.get("id")] = {
                "room": rid,
                "center_world": [round(float(v), 4) for v in ctr],
                "center_px": None if not np.all(np.isfinite(uv)) else [round(float(uv[0]), 2), round(float(uv[1]), 2)],
                "depth": round(float(zc), 4),
                "in_frame": vis,
                "partly_visible": vis or any(sg is not None and any(0 <= p[0] <= self.W and 0 <= p[1] <= self.H
                                                                    for p in sg) for sg in segs),
            }
            if anchor is not None:
                self.label(anchor, S.short_label(it.get("id", "?")), col, self.font if own else self.font_s)

    def draw_lights(self, data):
        for lt in self.spec.lights:
            try:
                p = np.asarray(lt["position"], float)
            except (KeyError, TypeError, ValueError):
                continue
            uv, zc = self.uv(p)
            vis = bool(zc > S.NEAR_CLIP and self.in_frame(uv))
            data["lights"][lt.get("id")] = {
                "center_px": None if not np.all(np.isfinite(uv)) else [round(float(uv[0]), 2), round(float(uv[1]), 2)],
                "depth": round(float(zc), 4), "in_frame": vis}
            if not vis or not self.room_visible(lt.get("room")):
                continue
            x, y = uv[0] * SS, uv[1] * SS
            r = 8 * SS
            for dx, dy in ((r, 0), (0, r), (0.7 * r, 0.7 * r), (0.7 * r, -0.7 * r)):
                self.d.line([x - dx, y - dy, x + dx, y + dy], fill=(0, 0, 0), width=4 * SS)
            for dx, dy in ((r, 0), (0, r), (0.7 * r, 0.7 * r), (0.7 * r, -0.7 * r)):
                self.d.line([x - dx, y - dy, x + dx, y + dy], fill=WHITE, width=2 * SS)
            self.label((uv[0], uv[1] + 16), S.short_label(lt.get("id", "")), WHITE, self.font_s)

    def hud(self, ref, img_path):
        c = self.cam
        P, T = c["position"], c["look_at"]
        lines = [
            (f"{ref}  room={c.get('room')}  {self.W}x{self.H}" + ("" if img_path else "  (grey canvas)"), WHITE),
            (f"pos ({P[0]:.2f}, {P[1]:.2f}, {P[2]:.2f})  look_at ({T[0]:.2f}, {T[1]:.2f}, {T[2]:.2f})", WHITE),
            (f"hfov {float(c['horizontal_fov_deg']):.1f}°  roll {float(c.get('roll_deg', 0) or 0):.1f}°  "
             f"k={self.k:.1f}px  vfov {S.vertical_fov_deg(c, self.W, self.H):.1f}°", WHITE),
        ]
        x, y = 6 * SS, (self.H - 6) * SS
        hts = []
        for t, _ in lines:
            b = self.d.textbbox((0, 0), t, font=self.font_s)
            hts.append(b[3] - b[1] + 4 * SS)
        legend = [("rooms", CYAN), ("openings", YELLOW), ("dormer", ORANGE), ("items", MAGENTA), ("lights", WHITE)]
        total = sum(hts) + hts[0]
        wmax = max(self.d.textbbox((0, 0), t, font=self.font_s)[2] for t, _ in lines)
        lay = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
        ImageDraw.Draw(lay).rectangle([0, y - total - 6 * SS, x + wmax + 8 * SS, self.H * SS], fill=(0, 0, 0, 150))
        self.img.alpha_composite(lay)
        self.d = ImageDraw.Draw(self.img)
        yy = y - total
        for (t, col), h in zip(lines, hts):
            self.d.text((x, yy), t, font=self.font_s, fill=col)
            yy += h
        xx = x
        for t, col in legend:
            self.d.text((xx, yy), t, font=self.font_s, fill=col)
            xx += self.d.textbbox((0, 0), t + "   ", font=self.font_s)[2]

    def render(self, ref, img_path):
        data = {"ref": ref, "image": str(img_path) if img_path else None, "size": [self.W, self.H],
                "camera": {k: self.cam.get(k) for k in ("room", "position", "look_at", "horizontal_fov_deg", "roll_deg")},
                "focal_px": round(self.k, 4), "items": {}, "openings": {}, "lights": {}}
        self.draw_rooms()
        self.draw_openings(data)
        self.draw_items(data)
        self.draw_lights(data)
        self.hud(ref, img_path)
        out = self.img.resize((self.W, self.H), Image.LANCZOS).convert("RGB")
        return out, data


def make_overlay(spec, ref, out_path, camera_override=None, rooms_mode="all", manifest=None):
    if not isinstance(spec, S.Spec):
        spec = S.Spec(spec)
    cam = build_camera(spec, ref, camera_override)
    img, img_path = load_canvas(ref, manifest)
    out, data = Overlay(spec, cam, img, rooms_mode).render(ref, img_path)
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        out.save(out_path, quality=92)
    return out, data


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("ref", nargs="?", help="reference / camera id (e.g. MOOD03, FIX01)")
    ap.add_argument("out", nargs="?", help="output .jpg")
    ap.add_argument("--camera", help="JSON camera override (string or path to a .json file)")
    ap.add_argument("--all", dest="all_dir", help="write an overlay for every spec camera into this directory")
    ap.add_argument("--json", dest="json_out", help="write projected 2D positions as JSON")
    ap.add_argument("--rooms", choices=("all", "camera"), default="all",
                    help="draw every room (default; non-camera rooms dimmed) or only the camera's room")
    a = ap.parse_args(argv)
    spec = S.load_spec(a.spec)
    results = {}
    if a.all_dir:
        if not spec.cameras:
            print("spec has no cameras", file=sys.stderr)
            return 2
        for c in spec.cameras:
            ref = c.get("ref")
            out = Path(a.all_dir) / f"{ref}.jpg"
            _, data = make_overlay(spec, ref, out, None, a.rooms)
            results[ref] = data
            print(f"wrote {out}")
    if a.ref:
        if not a.out:
            ap.error("out.jpg is required with REF_ID")
        try:
            _, data = make_overlay(spec, a.ref, a.out, a.camera, a.rooms)
        except ValueError as ex:
            print(f"error: {ex}", file=sys.stderr)
            return 2
        results[a.ref] = data
        print(f"wrote {a.out}")
    if not a.ref and not a.all_dir:
        ap.error("give REF_ID OUT.jpg and/or --all OUTDIR")
    if a.json_out:
        Path(a.json_out).parent.mkdir(parents=True, exist_ok=True)
        payload = results[a.ref] if (a.ref and not a.all_dir) else results
        with open(a.json_out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        print(f"wrote {a.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
