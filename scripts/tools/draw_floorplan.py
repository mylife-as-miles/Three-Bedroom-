#!/usr/bin/env python3
"""draw_floorplan.py -- architectural plan drawing of an apartment_spec.json (schema v2).

    python3 scripts/tools/draw_floorplan.py <spec.json> <out.png> [--scale 120]

Draws: rooms (light fill, name, id, area, ceiling), walls as solid polygons (exterior darkest,
party brown, interior grey), doors (leaf + swing arc), doorways (gap + casing ticks + dashed
head), windows (triple lines), dormers (dashed outward recess), roof windows (dashed, projected
onto the slope), sloped-ceiling zones (hatched, knee line + line where the slope reaches the
flat height), items (rotated rectangles, thick front edge + tick, short labels), lights,
cameras (dot + FOV wedge + ref), spawn, 1 m grid, scale bar, north arrow (+Y), title, legend.
Plan up = +Y (north), right = +X (east). Rendered 2x and downsampled for anti-aliasing.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spec_lib as S  # noqa: E402

SS = 2  # supersampling factor

ROOM_FILLS = {
    "bedroom_1": (205, 233, 232), "bedroom_2": (244, 214, 210), "bedroom_3": (246, 232, 204),
    "kitchen": (236, 238, 206), "bathroom": (214, 228, 246), "hall": (222, 233, 214),
    "living_placeholder": (232, 232, 232),
}
GENERIC_FILLS = [(230, 222, 240), (240, 228, 214), (214, 236, 240), (236, 214, 230)]
WALL_COL = {"exterior": (38, 38, 38), "party": (92, 70, 52), "interior": (112, 112, 112)}
CAT_COL = {"furniture": (139, 90, 43), "appliance": (46, 109, 164), "fixture": (32, 128, 128),
           "decor": (142, 68, 173), "prop": (176, 58, 122), "light_fixture": (204, 122, 0)}
WIN_COL = (31, 78, 121)
GLASS = (214, 234, 250)
HATCH_COL = (150, 110, 50)
CAM_COL = (192, 57, 43)
SPAWN_COL = (30, 150, 80)
LIGHT_COL = (214, 137, 16)
GRID_COL = (226, 226, 226)
TEXT_COL = (25, 25, 25)


class Plan:
    def __init__(self, spec: S.Spec, scale: float):
        self.spec = spec
        self.s = float(scale)
        xmin, ymin, xmax, ymax = spec.bounds()
        pad = 0.6
        self.xmin, self.ymin = math.floor(xmin - pad), math.floor(ymin - pad)
        self.xmax, self.ymax = math.ceil(xmax + pad), math.ceil(ymax + pad)
        self.ml, self.mr, self.mt = 60, 60, 92
        plan_w = (self.xmax - self.xmin) * self.s
        self.W = int(max(plan_w + self.ml + self.mr, 1000))
        self.ml = int((self.W - plan_w) / 2)
        self.legend_h = 118
        self.H = int((self.ymax - self.ymin) * self.s + self.mt + 40 + self.legend_h)
        self.img = Image.new("RGBA", (self.W * SS, self.H * SS), (255, 255, 255, 255))
        self.d = ImageDraw.Draw(self.img)
        self.placed = []  # label boxes (supersampled px)
        self.f = {k: S.load_font(v * SS, bold=b) for k, (v, b) in {
            "title": (20, True), "sub": (11, False), "room": (14, True), "roominfo": (11, False),
            "item": (10, False), "small": (9, False), "smallb": (10, True), "legend": (11, False)}.items()}

    # -- transforms
    def P(self, x, y):
        return ((self.ml + (x - self.xmin) * self.s) * SS, (self.mt + (self.ymax - y) * self.s) * SS)

    def PP(self, pts):
        return [self.P(float(p[0]), float(p[1])) for p in pts]

    def w(self, px):
        return max(1, int(round(px * SS)))

    # -- primitives
    def layer(self):
        return Image.new("RGBA", self.img.size, (0, 0, 0, 0))

    def composite(self, lay):
        self.img.alpha_composite(lay)
        self.d = ImageDraw.Draw(self.img)

    def line(self, pts, col, width=1.0, d=None):
        (d or self.d).line(self.PP(pts), fill=col, width=self.w(width), joint="curve")

    def dashed(self, a, b, col, width=1.0, dash=0.10, gap=0.06, d=None):
        a, b = np.asarray(a, float), np.asarray(b, float)
        L = float(np.linalg.norm(b - a))
        if L < 1e-9:
            return
        u = (b - a) / L
        t = 0.0
        while t < L:
            t1 = min(L, t + dash)
            self.line([a + u * t, a + u * t1], col, width, d)
            t = t1 + gap

    def dashdot(self, a, b, col, width=1.0):
        a, b = np.asarray(a, float), np.asarray(b, float)
        L = float(np.linalg.norm(b - a))
        if L < 1e-9:
            return
        u = (b - a) / L
        t = 0.0
        while t < L:
            self.line([a + u * t, a + u * min(L, t + 0.18)], col, width)
            t += 0.24
            if t < L:
                self.line([a + u * t, a + u * min(L, t + 0.02)], col, width)
            t += 0.06

    def text(self, xy, s, font, col=TEXT_COL, anchor="mm", halo=True):
        kw = {"stroke_width": 2 * SS, "stroke_fill": (255, 255, 255)} if halo else {}
        self.d.text(xy, s, font=font, fill=col, anchor=anchor, **kw)

    def text_box(self, xy, s, font, anchor="mm"):
        return self.d.textbbox(xy, s, font=font, anchor=anchor, stroke_width=2 * SS)

    def free(self, box):
        x0, y0, x1, y1 = box
        if x0 < 0 or y0 < 0 or x1 > self.img.size[0] or y1 > self.img.size[1]:
            return False
        for b in self.placed:
            if not (x1 <= b[0] or b[2] <= x0 or y1 <= b[1] or b[3] <= y0):
                return False
        return True

    def place_label(self, cands, s, font, col, force=True):
        """cands: list of supersampled pixel points (centre anchors). First free wins."""
        for c in cands:
            box = self.text_box(c, s, font)
            if self.free(box):
                self.placed.append(box)
                self.text(c, s, font, col)
                return True
        if force and cands:
            box = self.text_box(cands[0], s, font)
            self.placed.append(box)
            self.text(cands[0], s, font, col)
            return True
        return False

    # ------------------------------------------------------------------------------------
    def draw_grid(self):
        for x in range(self.xmin, self.xmax + 1):
            self.line([(x, self.ymin), (x, self.ymax)], GRID_COL, 1)
            px, py = self.P(x, self.ymax)
            self.text((px, py - 8 * SS), f"{x}", self.f["small"], (140, 140, 140), halo=False)
        for y in range(self.ymin, self.ymax + 1):
            self.line([(self.xmin, y), (self.xmax, y)], GRID_COL, 1)
            px, py = self.P(self.xmin, y)
            self.text((px - 10 * SS, py), f"{y}", self.f["small"], (140, 140, 140), halo=False)

    def draw_rooms(self):
        lay = self.layer()
        ld = ImageDraw.Draw(lay)
        for k, (rid, r) in enumerate(self.spec.rooms.items()):
            col = ROOM_FILLS.get(rid, GENERIC_FILLS[k % len(GENERIC_FILLS)])
            ld.polygon(self.PP(r["polygon"]), fill=col + (255,))
        self.composite(lay)
        # placeholder diagonal hatch
        for rid, r in self.spec.rooms.items():
            if r.get("placeholder"):
                self.hatch(np.asarray(r["polygon"], float), (190, 190, 190), spacing=0.25, angle=-45, width=1)

    def hatch(self, poly, col, spacing=0.12, angle=45, width=1, alpha=255):
        mask = Image.new("L", self.img.size, 0)
        ImageDraw.Draw(mask).polygon(self.PP(poly), fill=alpha)
        lay = self.layer()
        ld = ImageDraw.Draw(lay)
        lo, hi = poly.min(axis=0), poly.max(axis=0)
        c = 0.5 * (lo + hi)
        R = float(np.linalg.norm(hi - lo)) / 2 + 0.1
        t = math.radians(angle)
        u = np.array([math.cos(t), math.sin(t)])
        n = np.array([-u[1], u[0]])
        k = -R
        # align to a global pattern so adjacent zones join seamlessly
        k = math.floor((float(c @ n) - R) / spacing) * spacing - float(c @ n)
        while k <= R:
            p = c + n * k
            ld.line(self.PP([p - u * R, p + u * R]), fill=col + (255,), width=self.w(width))
            k += spacing
        empty = Image.new("RGBA", self.img.size, (0, 0, 0, 0))
        self.composite(Image.composite(lay, empty, mask))

    # -- walls --------------------------------------------------------------------------
    def wall_end_ext(self, w):
        a, b, d, nl, L = S.wall_frame(w)
        ext = [0.0, 0.0]
        for k, E in enumerate((a, b)):
            for o in self.spec.walls.values():
                if o is w:
                    continue
                try:
                    oa, ob, od, _, _ = S.wall_frame(o)
                except (KeyError, TypeError, ValueError):
                    continue
                if min(np.linalg.norm(oa - E), np.linalg.norm(ob - E)) > 0.01:
                    continue
                if abs(d[0] * od[1] - d[1] * od[0]) < 0.1:
                    continue
                ext[k] = max(ext[k], 0.5 * float(o["thickness"]))
        return ext

    def draw_walls(self):
        order = {"interior": 0, "party": 1, "exterior": 2}
        for w in sorted(self.spec.walls.values(), key=lambda w: order.get(w.get("kind"), 0)):
            try:
                L = S.wall_length(w)
            except (KeyError, TypeError, ValueError):
                continue
            col = WALL_COL.get(w.get("kind"), WALL_COL["interior"])
            e0, e1 = self.wall_end_ext(w)
            cuts = sorted(S.opening_span(o) for o in w.get("openings") or [])
            cur = -e0
            pieces = []
            for s0, s1 in cuts:
                if s0 > cur:
                    pieces.append((cur, s0))
                cur = max(cur, s1)
            if L + e1 > cur:
                pieces.append((cur, L + e1))
            for p0, p1 in pieces:
                self.d.polygon(self.PP(S.wall_body_polygon(w, p0, p1)), fill=col)

    def draw_openings(self):
        for w in self.spec.walls.values():
            for o in w.get("openings") or []:
                try:
                    self.draw_opening(w, o)
                except (KeyError, TypeError, ValueError):
                    continue

    def draw_opening(self, w, o):
        t = o.get("type")
        s0, s1 = S.opening_span(o)
        a, b, d, nl, L = S.wall_frame(w)
        h = 0.5 * float(w["thickness"])
        sides = self.spec.opening_side_rooms(w, o)
        dark = (20, 20, 20)
        # threshold / sill infill so the gap reads as an opening, not a missing wall
        if t in ("window", "dormer", "roof_window"):
            self.d.polygon(self.PP(S.wall_body_polygon(w, s0, s1)), fill=GLASS)
            for off in (-h, 0.0, h):
                self.line([a + d * s0 + nl * off, a + d * s1 + nl * off], WIN_COL, 1.4)
            for s in (s0, s1):
                self.line([a + d * s + nl * h, a + d * s - nl * h], WIN_COL, 1.4)
        if t == "dormer":
            g = self.spec.dormer_geometry(w, o)
            if g:
                fr = g["front"][:, :2]
                inner = g["inner"][:, :2]
                lay = self.layer()
                ImageDraw.Draw(lay).polygon(self.PP([inner[0], inner[1], fr[1], fr[0]]), fill=GLASS + (150,))
                self.composite(lay)
                self.dashed(inner[0], fr[0], WIN_COL, 1.6)
                self.dashed(inner[1], fr[1], WIN_COL, 1.6)
                self.dashed(fr[0], fr[1], WIN_COL, 1.6)
                m = 0.5 * (fr[0] + fr[1])
                outdir = (fr[0] - inner[0]) / max(1e-9, np.linalg.norm(fr[0] - inner[0]))
                self.place_label([self.P(*(m + outdir * 0.14)), self.P(*(m - outdir * 0.3))],
                                 f"dormer d={g['depth']:.2f}", self.f["small"], WIN_COL)
        if t == "roof_window":
            rid = sides["left"] or sides["right"]
            side = "left" if sides["left"] else "right"
            if rid in self.spec.rooms:
                f = S.wall_face(w, side)
                z0, z1 = S.opening_z(o)
                d0, d1 = 0.0, float((o.get("details") or {}).get("depth", 0.9))
                for _, sl, _ in self.spec.ceiling_planes(rid)[1:]:
                    if sl.get("wall") == w.get("id"):
                        tp = math.tan(math.radians(float(sl["pitch_deg"])))
                        d0 = max(0.0, (z0 - float(sl["knee_height"])) / tp)
                        d1 = max(d0 + 0.05, (z1 - float(sl["knee_height"])) / tp)
                p = [S.wall_point(w, s0, side) + f["normal"] * d0, S.wall_point(w, s1, side) + f["normal"] * d0,
                     S.wall_point(w, s1, side) + f["normal"] * d1, S.wall_point(w, s0, side) + f["normal"] * d1]
                for i in range(4):
                    self.dashed(p[i], p[(i + 1) % 4], WIN_COL, 1.6)
        if t == "doorway":
            for s in (s0, s1):
                self.line([a + d * s + nl * (h + 0.06), a + d * s - nl * (h + 0.06)], dark, 2.2)
            for off in (-h, h):
                self.dashed(a + d * s0 + nl * off, a + d * s1 + nl * off, (90, 90, 90), 1.0, dash=0.06, gap=0.05)
        if t in ("door", "louvered_pair"):
            si = o.get("swing_into")
            side = None
            for sd in ("left", "right"):
                if sides[sd] is not None and sides[sd] == si:
                    side = sd
            if side is None:  # swing toward a non-room side (should not happen) -> left
                side = "left" if si == sides["left"] or sides["right"] is None else "right"
            for s in (s0, s1):
                self.line([a + d * s + nl * h, a + d * s - nl * h], dark, 1.2)
            for lf in S.door_leaves(w, o, side):
                hgt, op, cl = lf["hinge"], lf["open_tip"], lf["closed_tip"]
                u = (op - hgt) / max(1e-9, lf["radius"])
                v = (cl - hgt) / max(1e-9, lf["radius"])
                tk = 0.035
                leaf = [hgt, op, op + v * tk, hgt + v * tk]
                self.d.polygon(self.PP(leaf), fill=(255, 255, 255), outline=dark, width=self.w(1.6))
                if o.get("type") == "louvered_pair" or o.get("leaf") == "louvered_pair":
                    n_l = max(2, int(lf["radius"] / 0.06))
                    for i in range(1, n_l):
                        q = hgt + u * (lf["radius"] * i / n_l)
                        self.line([q, q + v * tk], dark, 0.8)
                arc = [hgt + lf["radius"] * (math.cos(th) * v + math.sin(th) * u)
                       for th in np.linspace(0, math.pi / 2, 24)]
                self.line(arc, (90, 90, 90), 1.0)
        if t == "sliding_door":
            side = "left" if sides["left"] else "right"
            if o.get("swing_into") in (sides["left"], sides["right"]):
                side = "left" if o.get("swing_into") == sides["left"] else "right"
            f = S.wall_face(w, side)
            off = f["normal"] * 0.03
            p0, p1 = a + d * s0 + f["normal"] * h + off, a + d * s1 + f["normal"] * h + off
            q0, q1 = p0 + d * (s1 - s0) * 0.5, p1 + d * (s1 - s0) * 0.5
            self.d.polygon(self.PP([q0, q1, q1 + f["normal"] * 0.035, q0 + f["normal"] * 0.035]),
                           fill=(255, 255, 255), outline=dark, width=self.w(1.4))
            self.dashed(p0, p1, dark, 1.0)
            mid = 0.5 * (q0 + q1) + f["normal"] * 0.12
            self.line([mid - d * 0.2, mid + d * 0.2], dark, 1.2)
            self.line([mid + d * 0.2, mid + d * 0.13 + f["normal"] * 0.05], dark, 1.2)
        # opening id label (outside the wall on the first side without a room, else left)
        side = "right" if sides["right"] is None and sides["left"] is not None else "left"
        if t == "dormer":
            side = "left" if sides["left"] is not None else "right"
        f = S.wall_face(w, side)
        m = a + d * (0.5 * (s0 + s1))
        lab = str(o.get("id", ""))
        gap = h + 0.13
        self.place_label([self.P(*(m + f["normal"] * gap)), self.P(*(m - f["normal"] * gap)),
                          self.P(*(m + f["normal"] * (gap + 0.15))), self.P(*(m - f["normal"] * (gap + 0.15)))],
                         lab, self.f["small"], (95, 95, 95), force=False)

    # -- items, lights, cameras -----------------------------------------------------------
    def draw_items(self):
        items = sorted(self.spec.items, key=lambda i: (S.item_z_range(i)[1] > 0.03, S.item_z_range(i)[0]))
        lay = self.layer()
        ld = ImageDraw.Draw(lay)
        for it in items:
            try:
                fp = S.item_footprint(it)
            except (KeyError, TypeError, ValueError, IndexError):
                continue
            col = CAT_COL.get(it.get("category"), (80, 80, 80))
            z0, z1 = S.item_z_range(it)
            alpha = 25 if (z1 - z0) <= 0.03 else (0 if z0 >= 1.0 else 70)
            if alpha:
                ld.polygon(self.PP(fp), fill=col + (alpha,))
        self.composite(lay)
        for it in items:
            try:
                fp = S.item_footprint(it)
            except (KeyError, TypeError, ValueError, IndexError):
                continue
            col = CAT_COL.get(it.get("category"), (80, 80, 80))
            z0, z1 = S.item_z_range(it)
            if (z1 - z0) <= 0.03 or z0 >= 1.0:
                for i in range(4):
                    self.dashed(fp[i], fp[(i + 1) % 4], col, 1.2, dash=0.07, gap=0.05)
            else:
                self.line(list(fp) + [fp[0]], col, 1.4)
            # front edge + tick
            self.line([fp[2], fp[3]], col, 3.2)
            m = 0.5 * (fp[2] + fp[3])
            _, ey = S.yaw_axes(it.get("yaw_deg", 0))
            self.line([m, m + ey * 0.10], col, 2.0)

    def item_labels(self):
        for it in self.spec.items:
            try:
                fp = S.item_footprint(it)
            except (KeyError, TypeError, ValueError, IndexError):
                continue
            col = tuple(int(c * 0.75) for c in CAT_COL.get(it.get("category"), (80, 80, 80)))
            c = fp.mean(axis=0)
            ex, ey = S.yaw_axes(it.get("yaw_deg", 0))
            w, dd = float(it["dimensions"][0]), float(it["dimensions"][1])
            r = 0.5 * max(w, dd) + 0.12
            cands = [self.P(*c)] + [self.P(*(c + v)) for v in
                                    (np.array([0, -0.5 * dd - 0.12]), np.array([0, 0.5 * dd + 0.12]),
                                     np.array([r, 0]), np.array([-r, 0]), np.array([0, -r]), np.array([0, r]),
                                     np.array([r, r]), np.array([-r, -r]), np.array([r, -r]), np.array([-r, r]))]
            self.place_label(cands, S.short_label(it.get("id", "?")), self.f["item"], col)

    def draw_lights(self):
        for lt in self.spec.lights:
            try:
                p = np.asarray(lt["position"], float)
            except (KeyError, TypeError, ValueError):
                continue
            px, py = self.P(p[0], p[1])
            r = 0.09 * self.s * SS
            self.d.ellipse([px - r, py - r, px + r, py + r], outline=LIGHT_COL, width=self.w(1.8), fill=(255, 248, 225))
            k = r * 0.7
            self.d.line([px - k, py - k, px + k, py + k], fill=LIGHT_COL, width=self.w(1.6))
            self.d.line([px - k, py + k, px + k, py - k], fill=LIGHT_COL, width=self.w(1.6))

    def light_labels(self):
        for lt in self.spec.lights:
            try:
                p = np.asarray(lt["position"], float)
            except (KeyError, TypeError, ValueError):
                continue
            lab = f"{S.short_label(lt.get('id', ''))} z{p[2]:.2f}"
            self.place_label([self.P(p[0], p[1] - 0.2), self.P(p[0], p[1] + 0.2), self.P(p[0] + 0.5, p[1]),
                              self.P(p[0] - 0.5, p[1])], lab, self.f["small"], (160, 95, 0), force=False)

    def draw_cameras(self):
        lay = self.layer()
        ld = ImageDraw.Draw(lay)
        R = 1.1
        wedges = []
        for cam in self.spec.cameras:
            try:
                P = np.asarray(cam["position"], float)
                T = np.asarray(cam["look_at"], float)
                hf = math.radians(float(cam["horizontal_fov_deg"]))
            except (KeyError, TypeError, ValueError):
                continue
            v = T[:2] - P[:2]
            if np.linalg.norm(v) < 1e-6:
                continue
            ang = math.atan2(v[1], v[0])
            pts = [P[:2]] + [P[:2] + R * np.array([math.cos(a), math.sin(a)])
                             for a in np.linspace(ang - hf / 2, ang + hf / 2, 24)]
            ld.polygon(self.PP(pts), fill=CAM_COL + (38,))
            wedges.append((cam, P, T, pts))
        self.composite(lay)
        for cam, P, T, pts in wedges:
            self.line(pts + [pts[0]], CAM_COL, 1.2)
            self.dashed(P[:2], T[:2], CAM_COL, 0.8, dash=0.05, gap=0.05)
            tx, ty = self.P(T[0], T[1])
            k = 4 * SS
            self.d.line([tx - k, ty - k, tx + k, ty + k], fill=CAM_COL, width=self.w(1.2))
            self.d.line([tx - k, ty + k, tx + k, ty - k], fill=CAM_COL, width=self.w(1.2))
            px, py = self.P(P[0], P[1])
            r = 4.5 * SS
            self.d.ellipse([px - r, py - r, px + r, py + r], fill=CAM_COL, outline=(255, 255, 255), width=SS)

    def camera_labels(self):
        for cam in self.spec.cameras:
            try:
                P = np.asarray(cam["position"], float)
                T = np.asarray(cam["look_at"], float)
            except (KeyError, TypeError, ValueError):
                continue
            v = T[:2] - P[:2]
            v = v / max(1e-9, np.linalg.norm(v))
            lab = f"{cam.get('ref', '?')} (z{P[2]:.2f}, {float(cam.get('horizontal_fov_deg', 0)):g}°)"
            self.place_label([self.P(*(P[:2] - v * 0.25)), self.P(*(P[:2] - v * 0.25 + np.array([0, -0.18]))),
                              self.P(*(P[:2] + np.array([0, 0.2]))), self.P(*(P[:2] + np.array([0, -0.2])))],
                             lab, self.f["smallb"], CAM_COL)

    def draw_spawn(self):
        sp = self.spec.spawn
        if not isinstance(sp, dict):
            return
        try:
            p = np.asarray(sp["position"], float)[:2]
        except (KeyError, TypeError, ValueError):
            return
        fwd = S.yaw_forward(sp.get("yaw_deg", 0))
        px, py = self.P(*p)
        r = 0.17 * self.s * SS
        self.d.ellipse([px - r, py - r, px + r, py + r], outline=SPAWN_COL, width=self.w(2.4), fill=(225, 245, 230))
        tip = p + fwd * 0.42
        side = np.array([-fwd[1], fwd[0]])
        self.line([p, tip], SPAWN_COL, 2.4)
        self.d.polygon(self.PP([tip + fwd * 0.04, tip - fwd * 0.1 + side * 0.07, tip - fwd * 0.1 - side * 0.07]),
                       fill=SPAWN_COL)
        self.place_label([self.P(*(p - fwd * 0.33)), self.P(*(p + side * 0.45)), self.P(*(p - side * 0.45))],
                         "SPAWN", self.f["smallb"], SPAWN_COL)

    def room_labels(self):
        for rid, r in self.spec.rooms.items():
            try:
                poly = np.asarray(r["polygon"], float)
            except (KeyError, TypeError, ValueError):
                continue
            pt = self.label_point(rid, poly)
            area = S.polygon_area(poly)
            ceil = r.get("ceiling") or {}
            if ceil.get("type") == "sloped":
                ks = ", ".join(f"{float(s['knee_height']):.2f}" for s in ceil.get("slopes", []))
                cinfo = f"sloped ceiling {float(ceil.get('height', 0)):.2f} (knee {ks})"
            else:
                cinfo = f"flat ceiling {float(ceil.get('height', 0)):.2f}"
            lines = [(r.get("name", rid), self.f["room"], TEXT_COL),
                     (f"{rid}  ·  {area:.2f} m²", self.f["roominfo"], (60, 60, 60)),
                     (cinfo, self.f["roominfo"], (60, 60, 60))]
            if r.get("placeholder"):
                lines.append(("PLACEHOLDER (no furnishing)", self.f["smallb"], (120, 120, 120)))
            px, py = self.P(*pt)
            hts = [self.d.textbbox((0, 0), t, font=f)[3] - self.d.textbbox((0, 0), t, font=f)[1] + 4 * SS
                   for t, f, _ in lines]
            y = py - sum(hts) / 2
            for (t, f, c), hh in zip(lines, hts):
                box = self.text_box((px, y + hh / 2), t, f)
                self.placed.append(box)
                self.text((px, y + hh / 2), t, f, c)
                y += hh

    def label_point(self, rid, poly):
        lo, hi = poly.min(axis=0), poly.max(axis=0)
        X, Y = np.meshgrid(np.linspace(lo[0], hi[0], 40), np.linspace(lo[1], hi[1], 40))
        Q = np.column_stack([X.ravel(), Y.ravel()])
        Q = Q[S.points_in_polygon(Q, poly)]
        if not len(Q):
            return S.polygon_centroid(poly)
        score = S.distance_to_boundary(Q, poly)
        # keep clear of furniture: penalise points inside/near item footprints
        for it in self.spec.items_in_room(rid):
            try:
                z0, z1 = S.item_z_range(it)
                if z1 - z0 <= 0.03:
                    continue
                fp = S.item_footprint(it)
            except (KeyError, TypeError, ValueError, IndexError):
                continue
            score = np.minimum(score, -S.polygon_signed_distance(Q, fp))  # <0 inside the footprint
        for lt in self.spec.lights:
            if lt.get("room") == rid:
                try:
                    lp = np.asarray(lt["position"], float)[:2]
                except (KeyError, TypeError, ValueError):
                    continue
                score = np.minimum(score, np.linalg.norm(Q - lp, axis=1) - 0.15)
        c = S.polygon_centroid(poly)
        score = score - 0.04 * np.linalg.norm(Q - c, axis=1)
        return Q[int(np.argmax(score))]

    # -- furniture of the sheet -----------------------------------------------------------
    def draw_frame(self, spec_path):
        W = self.img.size[0]
        self.text((20 * SS, 26 * SS), f"{self.spec.name} — floor plan", self.f["title"], TEXT_COL, anchor="lm",
                  halo=False)
        sub = (f"schema v{self.spec.data.get('schema_version', '?')} · {Path(spec_path).name} · "
               f"1 m grid · {self.s:g} px/m · +X east, +Y north · "
               f"{len(self.spec.rooms)} rooms, {len(self.spec.walls)} walls, {len(self.spec.items)} items, "
               f"{len(self.spec.cameras)} cameras")
        self.text((20 * SS, 50 * SS), sub, self.f["sub"], (90, 90, 90), anchor="lm", halo=False)
        # north arrow (+Y)
        cx, cy = W - 50 * SS, 46 * SS
        self.d.polygon([(cx, cy - 26 * SS), (cx - 10 * SS, cy + 8 * SS), (cx, cy), (cx + 10 * SS, cy + 8 * SS)],
                       fill=(30, 30, 30))
        self.text((cx, cy - 36 * SS), "N (+Y)", self.f["smallb"], TEXT_COL, halo=False)
        # scale bar
        y0 = (self.H - self.legend_h + 18) * SS
        x0 = 30 * SS
        seg = self.s * SS
        for i in range(5):
            self.d.rectangle([x0 + i * seg, y0, x0 + (i + 1) * seg, y0 + 8 * SS],
                             fill=(30, 30, 30) if i % 2 == 0 else (255, 255, 255), outline=(30, 30, 30), width=SS)
            self.text((x0 + i * seg, y0 + 18 * SS), f"{i}", self.f["small"], TEXT_COL, halo=False)
        self.text((x0 + 5 * seg, y0 + 18 * SS), "5 m", self.f["small"], TEXT_COL, halo=False)
        self.draw_legend(x0 + 5 * seg + 50 * SS, y0 - 6 * SS)

    def draw_legend(self, x, y):
        W = self.img.size[0]
        entries = [
            ("ext", "exterior wall"), ("party", "party wall"), ("int", "interior wall"), ("door", "door + swing"),
            ("doorway", "doorway"), ("window", "window"), ("dormer", "dormer (dashed)"),
            ("slope", "sloped ceiling"), ("item", "item (thick = front)"), ("light", "light"),
            ("cam", "camera + FOV"), ("spawn", "spawn"),
        ]
        col_w = 150 * SS
        row_h = 22 * SS
        cols = max(1, int((W - x - 20 * SS) // col_w))
        for k, (sym, lab) in enumerate(entries):
            cx = x + (k % cols) * col_w
            cy = y + (k // cols) * row_h
            g = (cx, cy - 6 * SS, cx + 28 * SS, cy + 6 * SS)
            if sym in ("ext", "party", "int"):
                self.d.rectangle(g, fill=WALL_COL[{"ext": "exterior", "party": "party", "int": "interior"}[sym]])
            elif sym == "door":
                self.d.line([g[0], g[3], g[0], g[1] - 8 * SS], fill=(20, 20, 20), width=2 * SS)
                self.d.arc([g[0] - 20 * SS, g[1] - 8 * SS, g[0] + 20 * SS, g[3] + 26 * SS], 270, 360,
                           fill=(90, 90, 90), width=SS)
            elif sym == "doorway":
                self.d.rectangle((g[0], g[1], g[0] + 7 * SS, g[3]), fill=WALL_COL["interior"])
                self.d.rectangle((g[2] - 7 * SS, g[1], g[2], g[3]), fill=WALL_COL["interior"])
                for xx in (g[0] + 7 * SS, g[2] - 7 * SS):
                    self.d.line([xx, g[1] - 3 * SS, xx, g[3] + 3 * SS], fill=(20, 20, 20), width=2 * SS)
            elif sym == "window":
                self.d.rectangle(g, fill=GLASS)
                for yy in (g[1], (g[1] + g[3]) / 2, g[3]):
                    self.d.line([g[0], yy, g[2], yy], fill=WIN_COL, width=SS)
            elif sym == "dormer":
                for i in range(0, 28, 6):
                    self.d.line([g[0] + i * SS, g[1], g[0] + (i + 3) * SS, g[1]], fill=WIN_COL, width=SS)
                    self.d.line([g[0] + i * SS, g[3], g[0] + (i + 3) * SS, g[3]], fill=WIN_COL, width=SS)
            elif sym == "slope":
                for i in range(-12, 28, 5):
                    self.d.line([g[0] + max(0, i) * SS, g[3] - max(0, -i) * SS,
                                 g[0] + min(28, i + 12) * SS, g[3] - min(12, 28 - i + 0) * SS + 0],
                                fill=HATCH_COL, width=SS)
            elif sym == "item":
                self.d.rectangle(g, outline=CAT_COL["furniture"], width=SS, fill=(225, 210, 195))
                self.d.line([g[0], g[1], g[2], g[1]], fill=CAT_COL["furniture"], width=3 * SS)
            elif sym == "light":
                r = 6 * SS
                c = ((g[0] + g[2]) / 2, (g[1] + g[3]) / 2)
                self.d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], outline=LIGHT_COL, width=2 * SS)
                self.d.line([c[0] - 4 * SS, c[1] - 4 * SS, c[0] + 4 * SS, c[1] + 4 * SS], fill=LIGHT_COL, width=SS)
                self.d.line([c[0] - 4 * SS, c[1] + 4 * SS, c[0] + 4 * SS, c[1] - 4 * SS], fill=LIGHT_COL, width=SS)
            elif sym == "cam":
                self.d.polygon([(g[0], (g[1] + g[3]) / 2), (g[2], g[1] - 3 * SS), (g[2], g[3] + 3 * SS)],
                               fill=(240, 205, 200), outline=CAM_COL)
                self.d.ellipse([g[0] - 4 * SS, (g[1] + g[3]) / 2 - 4 * SS, g[0] + 4 * SS, (g[1] + g[3]) / 2 + 4 * SS],
                               fill=CAM_COL)
            elif sym == "spawn":
                c = (g[0] + 8 * SS, (g[1] + g[3]) / 2)
                self.d.ellipse([c[0] - 7 * SS, c[1] - 7 * SS, c[0] + 7 * SS, c[1] + 7 * SS], outline=SPAWN_COL,
                               width=2 * SS)
                self.d.line([c[0], c[1], c[0] + 18 * SS, c[1]], fill=SPAWN_COL, width=2 * SS)
            self.text((cx + 36 * SS, cy), lab, self.f["legend"], TEXT_COL, anchor="lm", halo=False)

    def render(self, spec_path):
        self.draw_grid()
        self.draw_rooms()
        for rid in self.spec.rooms:
            for s, face, D, zone in self.spec.slope_zone_polygons(rid):
                self.hatch(zone, HATCH_COL, spacing=0.12, angle=45, width=1, alpha=110)
        self.draw_items()
        self.draw_walls()
        self.draw_openings()
        self.draw_lights()
        self.draw_cameras()
        self.draw_spawn()
        self.room_labels()
        self.slope_lines()
        self.camera_labels()
        self.item_labels()
        self.light_labels()
        self.draw_frame(spec_path)
        out = self.img.resize((self.W, self.H), Image.LANCZOS).convert("RGB")
        return out

    def slope_lines(self):
        for rid, r in self.spec.rooms.items():
            poly = np.asarray(r["polygon"], float)
            for s, face, D, zone in self.spec.slope_zone_polygons(rid):
                n, dvec = face["normal"], face["dir"]
                for off, kind in ((0.035, "knee"), (D, "flat")):
                    p0 = face["a"] + n * off
                    segs = S.clip_line_to_polygon(p0, dvec, poly)
                    for t0, t1 in segs:
                        a, b = p0 + dvec * t0, p0 + dvec * t1
                        if kind == "knee":
                            self.dashdot(a, b, HATCH_COL, 1.6)
                        else:
                            self.dashed(a, b, HATCH_COL, 1.6, dash=0.16, gap=0.08)
                    if not segs:
                        continue
                    t0, t1 = max(segs, key=lambda q: q[1] - q[0])
                    m = p0 + dvec * (0.5 * (t0 + t1))
                    if kind == "knee":
                        lab = f"knee {float(s['knee_height']):.2f} m · pitch {float(s['pitch_deg']):g}°"
                        pos = m + n * 0.15
                    else:
                        lab = f"slope reaches {self.spec.ceiling_height(rid):.2f} m ({D:.2f} m from wall)"
                        pos = m - n * 0.13
                    cands = [pos + dvec * k for k in (0, 0.9, -0.9, 1.6, -1.6)]
                    self.place_label([self.P(*c) for c in cands], lab, self.f["small"], (120, 85, 30))


def draw_floorplan(spec, out_path, scale=120.0, spec_path="spec.json"):
    if not isinstance(spec, S.Spec):
        spec = S.Spec(spec)
    img = Plan(spec, scale).render(spec_path)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return img


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("out")
    ap.add_argument("--scale", type=float, default=120.0, help="pixels per metre (default 120)")
    a = ap.parse_args(argv)
    spec = S.load_spec(a.spec)
    img = draw_floorplan(spec, a.out, a.scale, a.spec)
    print(f"wrote {a.out} ({img.size[0]}x{img.size[1]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
