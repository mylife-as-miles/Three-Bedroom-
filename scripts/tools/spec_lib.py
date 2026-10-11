#!/usr/bin/env python3
"""spec_lib -- shared, Blender-free helpers for ``apartment_spec.json`` (schema v2).

Pure Python + numpy. Every spec tool (validator, plan drawer, overlay projector) and every
later agent should use these helpers instead of re-deriving geometry, so that the plan, the
overlay, the Blender builders and the Godot bridge all agree.

Conventions (docs/CONVENTIONS.md section 1-2, scripts/blender/spec/SCHEMA.md):

* Metres, degrees, world coordinates. Blender Z-up; +X plan east, +Y plan north.
* Walls are centre lines + thickness. The LEFT face of a wall is the face on the left when
  walking ``start -> end``; it lies at ``centre + n_left * thickness/2`` with
  ``n_left = (-dy, dx)`` (unit wall direction ``(dx, dy)``). A face's ``normal`` points AWAY
  from the wall, into the space on that side.
* Opening ``offset`` is measured along ``start -> end`` from ``start`` to the opening's near
  edge; the same parameter ``s`` is used on the centre line and on both faces.
* Item ``yaw_deg`` = rotation about +Z. Local +X = width axis, local +Y = depth axis and the
  FRONT. yaw 0 -> front faces +Y, 90 -> -X, 180 -> -Y, 270 -> +X.
* Ceiling (sloped rooms): ``z(x, y) = min(height, min over slopes of
  knee_height + signed_distance_to_wall_face * tan(pitch))`` where the distance is measured
  from the wall face that bounds the room, positive into the room. The function is the
  minimum of affine planes, hence concave: its minimum over a convex footprint is reached at
  a corner.
* Dormer ``details.depth`` is measured from the ROOM-SIDE (interior) wall face outward.
* Camera math: implemented exactly as the binding block in SCHEMA.md (see ``camera_basis`` and
  ``project``).
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "references" / "manifest.json"
DEFAULT_SPEC_PATH = REPO_ROOT / "scripts" / "blender" / "spec" / "apartment_spec.json"

NEAR_CLIP = 0.05                 # binding: points with zc <= 0.05 are not visible
Z_UP = np.array([0.0, 0.0, 1.0])
EPS = 1e-9
FACE_TOL = 0.01                  # 1 cm: room edge <-> wall face coincidence tolerance

OPENING_TYPES = ("door", "doorway", "window", "roof_window", "dormer", "sliding_door", "louvered_pair")
PASSABLE_OPENINGS = ("door", "doorway", "sliding_door", "louvered_pair")
SWINGING_OPENINGS = ("door", "louvered_pair")
WINDOW_OPENINGS = ("window", "roof_window", "dormer")
NON_ROOM_TOKENS = ("exterior", "stairwell")
SCOPE_ROOMS = ("bedroom_1", "bedroom_2", "bedroom_3", "kitchen", "bathroom", "hall", "living_placeholder")
CANONICAL_REFS = {"bedroom_1": "MOOD03", "bedroom_2": "MOOD04", "bedroom_3": "MOOD06",
                  "kitchen": "MOOD01", "bathroom": "APT01", "hall": "MOOD07"}
ITEM_CATEGORIES = ("furniture", "appliance", "fixture", "decor", "prop", "light_fixture")

ITEM_TYPES = set("""
bed nightstand dresser wardrobe desk chair desk_chair bookcase shelf_wall dining_table dining_chair stool
side_table hutch_cabinet coat_rack bench rug
fridge stove microwave range_hood water_heater washing_machine crt_tv tv_flat computer_retro record_player
speaker floor_fan rice_cooker kettle telescope guitar guitar_amp
base_cabinet_run upper_cabinet kitchen_sink side_counter dish_rack
radiator electrical_panel toilet bathroom_vanity mirror bathtub shower towel_rail curtain_rod closet_louvered
door_hooks
ceiling_fan_light ceiling_light_flush pendant_shade bare_bulb floor_lamp table_lamp lava_lamp wall_light
poster framed_art vinyl_record_wall sticky_notes wall_clock calendar plant tablecloth tableware_set book_stack
cardboard_box clothes_pile pillow newspaper misc
""".split())

FLOOR_FINISHES = {"timber_worn_boards", "timber_dark_planks", "linoleum_patterned", "tile_bathroom_floor",
                  "carpet_low_pile", "concrete_bare"}
WALL_FINISHES = {"plaster_white", "plaster_beige", "plaster_teal", "plaster_sage", "plaster_green_dark",
                 "wallpaper_striped", "wood_panelling", "tile_white_square", "brick_red", "wainscot_white",
                 "exterior"}
CEILING_FINISHES = {"plaster_textured", "plaster_smooth", "wood_boards"}

# 12 edges of the 8-corner box returned by item_box_corners (bottom 0-3, top 4-7)
BOX_EDGES = ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7))


# ---------------------------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------------------------
def load_json(path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_spec(path) -> "Spec":
    """Load a spec file and return an indexed :class:`Spec`."""
    return Spec(load_json(path), path=str(path))


def load_manifest(path=MANIFEST_PATH) -> dict:
    """Return {ref_id: manifest entry} (empty dict when the manifest is missing)."""
    try:
        data = load_json(path)
    except (OSError, ValueError):
        return {}
    return {r["id"]: r for r in data.get("references", []) if isinstance(r, dict) and "id" in r}


def reference_image_path(ref_id: str, manifest: dict | None = None) -> Path | None:
    """Absolute path of the reference image for ``ref_id`` or None if it is not in the manifest."""
    manifest = load_manifest() if manifest is None else manifest
    entry = manifest.get(ref_id)
    if not entry:
        return None
    p = (MANIFEST_PATH.parent / entry["file"]).resolve()
    return p if p.exists() else None


# ---------------------------------------------------------------------------------------------
# 2D geometry
# ---------------------------------------------------------------------------------------------
def _arr2(poly) -> np.ndarray:
    return np.asarray(poly, dtype=float).reshape(-1, 2)


def polygon_signed_area(poly) -> float:
    """Shoelace area; positive for counter-clockwise polygons."""
    P = _arr2(poly)
    if len(P) < 3:
        return 0.0
    x, y = P[:, 0], P[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def polygon_area(poly) -> float:
    return abs(polygon_signed_area(poly))


def polygon_is_ccw(poly) -> bool:
    return polygon_signed_area(poly) > 0.0


def polygon_centroid(poly) -> np.ndarray:
    P = _arr2(poly)
    a = polygon_signed_area(P)
    if abs(a) < EPS:
        return P.mean(axis=0)
    x, y = P[:, 0], P[:, 1]
    xn, yn = np.roll(x, -1), np.roll(y, -1)
    cr = x * yn - xn * y
    return np.array([np.sum((x + xn) * cr), np.sum((y + yn) * cr)]) / (6.0 * a)


def _orient(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a, b, c, eps) -> bool:
    return (min(a[0], b[0]) - eps <= c[0] <= max(a[0], b[0]) + eps and
            min(a[1], b[1]) - eps <= c[1] <= max(a[1], b[1]) + eps)


def segments_intersect(p1, p2, q1, q2, eps: float = 1e-12) -> bool:
    """True if closed segments p1p2 and q1q2 share at least one point."""
    d1, d2 = _orient(q1, q2, p1), _orient(q1, q2, p2)
    d3, d4 = _orient(p1, p2, q1), _orient(p1, p2, q2)
    if ((d1 > eps and d2 < -eps) or (d1 < -eps and d2 > eps)) and \
       ((d3 > eps and d4 < -eps) or (d3 < -eps and d4 > eps)):
        return True
    if abs(d1) <= eps and _on_segment(q1, q2, p1, eps):
        return True
    if abs(d2) <= eps and _on_segment(q1, q2, p2, eps):
        return True
    if abs(d3) <= eps and _on_segment(p1, p2, q1, eps):
        return True
    if abs(d4) <= eps and _on_segment(p1, p2, q2, eps):
        return True
    return False


def polygon_is_simple(poly) -> tuple[bool, str]:
    """(ok, reason). Rejects <3 vertices, zero-length edges, spikes and self-intersections."""
    P = [tuple(map(float, p)) for p in _arr2(poly)]
    n = len(P)
    if n < 3:
        return False, "fewer than 3 vertices"
    for i in range(n):
        a, b = P[i], P[(i + 1) % n]
        if math.hypot(b[0] - a[0], b[1] - a[1]) < 1e-6:
            return False, f"zero-length edge at vertex {i}"
    for i in range(n):
        a, b, c = P[i - 1], P[i], P[(i + 1) % n]
        u = (b[0] - a[0], b[1] - a[1])
        v = (c[0] - b[0], c[1] - b[1])
        if abs(u[0] * v[1] - u[1] * v[0]) < 1e-12 and (u[0] * v[0] + u[1] * v[1]) < 0:
            return False, f"spike (edge doubles back) at vertex {i}"
    for i in range(n):
        a, b = P[i], P[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or (i + 1) % n == j:
                continue
            c, d = P[j], P[(j + 1) % n]
            if segments_intersect(a, b, c, d):
                return False, f"edges {i} and {j} intersect"
    return True, ""


def points_in_polygon(pts, poly) -> np.ndarray:
    """Vectorised even-odd test. Points exactly on the boundary are undefined (use distances)."""
    Q = np.atleast_2d(np.asarray(pts, dtype=float))[:, :2]
    P = _arr2(poly)
    x, y = Q[:, 0], Q[:, 1]
    inside = np.zeros(len(Q), dtype=bool)
    n = len(P)
    with np.errstate(divide="ignore", invalid="ignore"):
        for i in range(n):
            x1, y1 = P[i]
            x2, y2 = P[(i + 1) % n]
            cond = (y1 > y) != (y2 > y)
            xint = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            inside ^= cond & (x < xint)
    return inside


def point_in_polygon(pt, poly, tol: float = 0.0) -> bool:
    """True if ``pt`` is inside ``poly`` or within ``tol`` of its boundary."""
    if bool(points_in_polygon([pt], poly)[0]):
        return True
    return tol > 0 and float(distance_to_boundary([pt], poly)[0]) <= tol


def segment_distance(pts, a, b) -> np.ndarray:
    """Distance from each point to segment ab (vectorised)."""
    Q = np.atleast_2d(np.asarray(pts, dtype=float))[:, :2]
    a = np.asarray(a, float)[:2]
    b = np.asarray(b, float)[:2]
    ab = b - a
    L2 = float(ab @ ab)
    if L2 < EPS:
        return np.linalg.norm(Q - a, axis=1)
    t = np.clip(((Q - a) @ ab) / L2, 0.0, 1.0)
    return np.linalg.norm(Q - (a + t[:, None] * ab), axis=1)


def distance_to_boundary(pts, poly) -> np.ndarray:
    P = _arr2(poly)
    Q = np.atleast_2d(np.asarray(pts, dtype=float))[:, :2]
    d = np.full(len(Q), np.inf)
    for i in range(len(P)):
        d = np.minimum(d, segment_distance(Q, P[i], P[(i + 1) % len(P)]))
    return d


def polygon_signed_distance(pts, poly) -> np.ndarray:
    """Positive inside, negative outside (distance to the boundary)."""
    d = distance_to_boundary(pts, poly)
    return np.where(points_in_polygon(pts, poly), d, -d)


def _point_in_tri_strict(p, a, b, c, eps=1e-12) -> bool:
    return _orient(a, b, p) > eps and _orient(b, c, p) > eps and _orient(c, a, p) > eps


def triangulate(poly) -> list:
    """Ear-clipping triangulation of a simple polygon (any orientation). Returns CCW triangles."""
    P = [tuple(map(float, p)) for p in _arr2(poly)]
    if polygon_signed_area(P) < 0:
        P = P[::-1]
    idx = list(range(len(P)))
    tris = []
    guard = 0
    while len(idx) > 3 and guard < 100000:
        guard += 1
        found = False
        m = len(idx)
        for k in range(m):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % m]
            a, b, c = P[i0], P[i1], P[i2]
            if _orient(a, b, c) <= 1e-12:
                continue
            if any(_point_in_tri_strict(P[j], a, b, c) for j in idx if j not in (i0, i1, i2)):
                continue
            tris.append((a, b, c))
            idx.pop(k)
            found = True
            break
        if not found:  # remove one degenerate (collinear) vertex, else give up
            for k in range(m):
                a, b, c = P[idx[k - 1]], P[idx[k]], P[idx[(k + 1) % m]]
                if abs(_orient(a, b, c)) <= 1e-12:
                    idx.pop(k)
                    found = True
                    break
            if not found:
                break
    if len(idx) == 3:
        a, b, c = (P[i] for i in idx)
        if abs(_orient(a, b, c)) > 1e-12:
            tris.append((a, b, c))
    return tris


def convex_clip(subject, clip) -> list:
    """Sutherland-Hodgman: clip ``subject`` polygon by the CONVEX polygon ``clip``."""
    out = [tuple(map(float, p)) for p in _arr2(subject)]
    C = [tuple(map(float, p)) for p in _arr2(clip)]
    if polygon_signed_area(C) < 0:
        C = C[::-1]
    for i in range(len(C)):
        a, b = C[i], C[(i + 1) % len(C)]
        inp, out = out, []
        if not inp:
            break

        def inside(p):
            return _orient(a, b, p) >= -1e-12

        def cut(p, q):
            dp, dq = _orient(a, b, p), _orient(a, b, q)
            t = dp / (dp - dq) if abs(dp - dq) > 1e-15 else 0.0
            return (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))

        s = inp[-1]
        for e in inp:
            if inside(e):
                if not inside(s):
                    out.append(cut(s, e))
                out.append(e)
            elif inside(s):
                out.append(cut(s, e))
            s = e
    return out


def polygon_intersection_area(p, q) -> float:
    """Exact intersection area of two simple polygons (triangulate both, clip triangle pairs)."""
    tp, tq = triangulate(p), triangulate(q)
    total = 0.0
    for t1 in tp:
        b1 = (min(v[0] for v in t1), min(v[1] for v in t1), max(v[0] for v in t1), max(v[1] for v in t1))
        for t2 in tq:
            if (max(v[0] for v in t2) < b1[0] or min(v[0] for v in t2) > b1[2] or
                    max(v[1] for v in t2) < b1[1] or min(v[1] for v in t2) > b1[3]):
                continue
            r = convex_clip(t1, t2)
            if len(r) >= 3:
                total += polygon_area(r)
    return total


def clip_line_to_polygon(p0, d, poly, t_range=(-1e6, 1e6)) -> list:
    """Intervals [t0, t1] of the line p0 + t*d that lie inside ``poly``."""
    p0 = np.asarray(p0, float)[:2]
    d = np.asarray(d, float)[:2]
    P = _arr2(poly)
    ts = [t_range[0], t_range[1]]
    for i in range(len(P)):
        a, b = P[i], P[(i + 1) % len(P)]
        e = b - a
        den = d[0] * e[1] - d[1] * e[0]
        if abs(den) < 1e-12:
            continue
        w = a - p0
        t = (w[0] * e[1] - w[1] * e[0]) / den
        s = (w[0] * d[1] - w[1] * d[0]) / den
        if -1e-9 <= s <= 1 + 1e-9 and t_range[0] < t < t_range[1]:
            ts.append(t)
    ts = sorted(set(ts))
    out = []
    for t0, t1 in zip(ts[:-1], ts[1:]):
        if t1 - t0 < 1e-9:
            continue
        mid = p0 + d * (0.5 * (t0 + t1))
        if points_in_polygon([mid], P)[0]:
            if out and abs(out[-1][1] - t0) < 1e-9:
                out[-1] = (out[-1][0], t1)
            else:
                out.append((t0, t1))
    return out


def polygon_label_point(poly, grid: int = 48) -> np.ndarray:
    """Interior point far from the boundary (approximate pole of inaccessibility)."""
    P = _arr2(poly)
    c = polygon_centroid(P)
    lo, hi = P.min(axis=0), P.max(axis=0)
    xs = np.linspace(lo[0], hi[0], grid)
    ys = np.linspace(lo[1], hi[1], grid)
    X, Y = np.meshgrid(xs, ys)
    Q = np.column_stack([X.ravel(), Y.ravel()])
    ins = points_in_polygon(Q, P)
    if not ins.any():
        return c
    Q = Q[ins]
    d = distance_to_boundary(Q, P)
    # prefer central points: penalise distance from centroid slightly
    score = d - 0.05 * np.linalg.norm(Q - c, axis=1)
    return Q[int(np.argmax(score))]


def footprint_outside_distance(fp, poly, step: float = 0.02) -> float:
    """Max distance by which the convex footprint ``fp`` sticks out of ``poly`` (0 if inside).

    Samples corners, edges (1 cm) and the interior (``step``) -- adequate for the 2 cm rule.
    """
    F = _arr2(fp)
    samples = [F]
    for i in range(len(F)):
        a, b = F[i], F[(i + 1) % len(F)]
        n = max(2, int(math.ceil(np.linalg.norm(b - a) / 0.01)) + 1)
        t = np.linspace(0, 1, n)[:, None]
        samples.append(a + t * (b - a))
    lo, hi = F.min(axis=0), F.max(axis=0)
    nx = int(min(80, max(2, math.ceil((hi[0] - lo[0]) / step) + 1)))
    ny = int(min(80, max(2, math.ceil((hi[1] - lo[1]) / step) + 1)))
    X, Y = np.meshgrid(np.linspace(lo[0], hi[0], nx), np.linspace(lo[1], hi[1], ny))
    G = np.column_stack([X.ravel(), Y.ravel()])
    G = G[points_in_polygon(G, F)]
    if len(G):
        samples.append(G)
    S = np.vstack(samples)
    sd = polygon_signed_distance(S, poly)
    return float(max(0.0, -sd.min()))


def interval_union(intervals, join_tol: float = 0.0) -> list:
    iv = sorted((float(a), float(b)) for a, b in intervals if b > a)
    out = []
    for a, b in iv:
        if out and a <= out[-1][1] + join_tol:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def interval_gaps(intervals, lo: float, hi: float, tol: float = 0.0) -> list:
    """Parts of [lo, hi] not covered by ``intervals`` (each gap longer than ``tol``)."""
    gaps = []
    cur = lo
    for a, b in interval_union(intervals, join_tol=tol):
        if b <= cur:
            continue
        if a > cur + tol:
            gaps.append((cur, min(a, hi)))
        cur = max(cur, b)
        if cur >= hi:
            break
    if cur < hi - tol:
        gaps.append((cur, hi))
    return [(a, b) for a, b in gaps if b - a > tol]


# ---------------------------------------------------------------------------------------------
# walls
# ---------------------------------------------------------------------------------------------
def wall_frame(wall) -> tuple:
    """(start, end, unit_dir, left_normal, length) of the wall centre line (2D)."""
    a = np.asarray(wall["start"], float)[:2]
    b = np.asarray(wall["end"], float)[:2]
    v = b - a
    L = float(np.linalg.norm(v))
    d = v / L if L > EPS else np.array([1.0, 0.0])
    nl = np.array([-d[1], d[0]])
    return a, b, d, nl, L


def wall_length(wall) -> float:
    return wall_frame(wall)[4]


def wall_face(wall, side: str) -> dict:
    """Face line of ``side`` ('left'|'right'): centre +/- thickness/2. ``normal`` points away
    from the wall into the space on that side. ``a``/``b`` correspond to s=0 / s=length."""
    a, b, d, nl, L = wall_frame(wall)
    n = nl if side == "left" else -nl
    h = 0.5 * float(wall["thickness"])
    return {"wall": wall.get("id"), "side": side, "a": a + n * h, "b": b + n * h,
            "dir": d, "normal": n, "length": L}


def wall_faces(wall) -> dict:
    return {"left": wall_face(wall, "left"), "right": wall_face(wall, "right")}


def wall_point(wall, s: float, side: str | None = None, z: float | None = None) -> np.ndarray:
    """Point at parameter ``s`` along the wall, on the centre line (side=None) or a face."""
    a, b, d, nl, L = wall_frame(wall)
    p = a + d * s
    if side is not None:
        p = p + (nl if side == "left" else -nl) * 0.5 * float(wall["thickness"])
    if z is None:
        return p
    return np.array([p[0], p[1], z])


def wall_body_polygon(wall, s0: float = 0.0, s1: float | None = None, ext0: float = 0.0,
                      ext1: float = 0.0) -> np.ndarray:
    """Plan rectangle of the wall between s0-ext0 and s1+ext1 (CCW)."""
    a, b, d, nl, L = wall_frame(wall)
    s1 = L if s1 is None else s1
    h = 0.5 * float(wall["thickness"])
    p0 = a + d * (s0 - ext0)
    p1 = a + d * (s1 + ext1)
    poly = np.array([p0 - nl * h, p1 - nl * h, p1 + nl * h, p0 + nl * h])
    return poly


def opening_span(opening) -> tuple:
    s0 = float(opening["offset"])
    return s0, s0 + float(opening["width"])


def opening_z(opening) -> tuple:
    z0 = float(opening.get("sill_height") or 0.0)
    return z0, z0 + float(opening["height"])


def opening_face_rect(wall, opening, side: str) -> np.ndarray:
    """4x3 world corners of the opening on a face: [bottom@s0, bottom@s1, top@s1, top@s0]
    (s0 = near edge along start->end)."""
    s0, s1 = opening_span(opening)
    z0, z1 = opening_z(opening)
    return np.array([wall_point(wall, s0, side, z0), wall_point(wall, s1, side, z0),
                     wall_point(wall, s1, side, z1), wall_point(wall, s0, side, z1)])


def opening_plan_rect(wall, opening) -> np.ndarray:
    s0, s1 = opening_span(opening)
    return wall_body_polygon(wall, s0, s1)


# ---------------------------------------------------------------------------------------------
# items
# ---------------------------------------------------------------------------------------------
def yaw_axes(yaw_deg: float) -> tuple:
    """(local X, local Y=front) unit vectors in plan for a yaw. yaw 0 -> front +Y, 90 -> -X."""
    t = math.radians(float(yaw_deg or 0.0))
    ex = np.array([math.cos(t), math.sin(t)])
    ey = np.array([-math.sin(t), math.cos(t)])
    return ex, ey


def yaw_forward(yaw_deg: float) -> np.ndarray:
    return yaw_axes(yaw_deg)[1]


def item_footprint(item) -> np.ndarray:
    """4x2 CCW footprint corners: local (-w/2,-d/2), (+w/2,-d/2), (+w/2,+d/2), (-w/2,+d/2).
    The front edge is corners[2] -> corners[3]."""
    c = np.asarray(item["position"], float)[:2]
    w, d = float(item["dimensions"][0]), float(item["dimensions"][1])
    ex, ey = yaw_axes(item.get("yaw_deg", 0.0))
    return np.array([c - ex * w / 2 - ey * d / 2, c + ex * w / 2 - ey * d / 2,
                     c + ex * w / 2 + ey * d / 2, c - ex * w / 2 + ey * d / 2])


def item_front_edge(item) -> np.ndarray:
    fp = item_footprint(item)
    return np.array([fp[2], fp[3]])


def item_z_range(item) -> tuple:
    z0 = float(item["position"][2] if len(item["position"]) > 2 else 0.0)
    return z0, z0 + float(item["dimensions"][2])


def item_box_corners(item) -> np.ndarray:
    """8x3 corners: bottom (z) 0-3 then top (z+h) 4-7, same order as item_footprint."""
    fp = item_footprint(item)
    z0, z1 = item_z_range(item)
    return np.vstack([np.column_stack([fp, np.full(4, z0)]), np.column_stack([fp, np.full(4, z1)])])


def item_center(item) -> np.ndarray:
    z0, z1 = item_z_range(item)
    p = np.asarray(item["position"], float)
    return np.array([p[0], p[1], 0.5 * (z0 + z1)])


def short_label(ident: str) -> str:
    """'FURN_br1_bed' -> 'bed', 'FURN_hall_coat_rack' -> 'coat_rack', 'misc' -> 'misc'."""
    parts = str(ident).split("_")
    if len(parts) >= 3 and parts[0].isupper():
        return "_".join(parts[2:])
    if len(parts) == 2 and parts[0].isupper():
        return parts[1]
    return str(ident)


# ---------------------------------------------------------------------------------------------
# door leaves
# ---------------------------------------------------------------------------------------------
def door_leaves(wall, opening, swing_side: str) -> list:
    """Leaves of a swinging opening as dicts {hinge, closed_tip, open_tip, radius} (2D) on the
    ``swing_side`` face. 'door' = one leaf hinged at opening['hinge'] ('start'|'end');
    'louvered_pair' (type or leaf) = two half-width leaves hinged at both jambs."""
    s0, s1 = opening_span(opening)
    face = wall_face(wall, swing_side)
    n = face["normal"]

    def leaf(s_h, s_c):
        h = wall_point(wall, s_h, swing_side)
        c = wall_point(wall, s_c, swing_side)
        r = abs(s_c - s_h)
        return {"hinge": h, "closed_tip": c, "open_tip": h + n * r, "radius": r}

    if opening.get("type") == "louvered_pair" or opening.get("leaf") == "louvered_pair":
        m = 0.5 * (s0 + s1)
        return [leaf(s0, m), leaf(s1, m)]
    if opening.get("hinge", "start") == "end":
        return [leaf(s1, s0)]
    return [leaf(s0, s1)]


def leaf_sector_polygon(leaf, segments: int = 16) -> np.ndarray:
    """Quarter-disc swept by a leaf (hinge + arc from closed tip to open tip), convex."""
    h = np.asarray(leaf["hinge"])
    u = np.asarray(leaf["closed_tip"]) - h
    v = np.asarray(leaf["open_tip"]) - h
    pts = [h]
    for k in range(segments + 1):
        t = 0.5 * math.pi * k / segments
        pts.append(h + math.cos(t) * u + math.sin(t) * v)
    return np.array(pts)


# ---------------------------------------------------------------------------------------------
# camera (BINDING math -- SCHEMA.md "Camera math")
# ---------------------------------------------------------------------------------------------
def camera_basis(cam) -> tuple:
    """(r', u', f) per SCHEMA.md: f = normalize(T-P); r = normalize(cross(f, Z_UP));
    u = cross(r, f); r' = cos(rho) r + sin(rho) u; u' = -sin(rho) r + cos(rho) u."""
    P = np.asarray(cam["position"], float)
    T = np.asarray(cam["look_at"], float)
    f = T - P
    nf = float(np.linalg.norm(f))
    if nf < EPS:
        raise ValueError("camera position == look_at")
    f = f / nf
    r = np.cross(f, Z_UP)
    nr = float(np.linalg.norm(r))
    if nr < 1e-9:
        raise ValueError("camera looks straight up/down; cross(f, Z_UP) is undefined")
    r = r / nr
    u = np.cross(r, f)
    rho = math.radians(float(cam.get("roll_deg", 0.0) or 0.0))
    r2 = math.cos(rho) * r + math.sin(rho) * u
    u2 = -math.sin(rho) * r + math.cos(rho) * u
    return r2, u2, f


def focal_px(cam, W: float) -> float:
    """k = (W/2) / tan(h/2)."""
    return (0.5 * W) / math.tan(math.radians(float(cam["horizontal_fov_deg"])) / 2.0)


def vertical_fov_deg(cam, W: float, H: float) -> float:
    return math.degrees(2.0 * math.atan(math.tan(math.radians(float(cam["horizontal_fov_deg"])) / 2.0) * H / W))


def world_to_camera(points, cam) -> np.ndarray:
    """Nx3 camera coordinates (xc, yc, zc) = (d.r', d.u', d.f) with d = X - P."""
    X = np.atleast_2d(np.asarray(points, float))
    r2, u2, f = camera_basis(cam)
    d = X - np.asarray(cam["position"], float)
    return np.column_stack([d @ r2, d @ u2, d @ f])


def camera_to_pixel(pc, cam, W: float, H: float) -> np.ndarray:
    """Project camera-space points (no visibility test): (W/2 + k xc/zc, H/2 - k yc/zc)."""
    pc = np.atleast_2d(np.asarray(pc, float))
    k = focal_px(cam, W)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.column_stack([0.5 * W + k * pc[:, 0] / pc[:, 2], 0.5 * H - k * pc[:, 1] / pc[:, 2]])


def project(points, cam, W: float, H: float, near: float = NEAR_CLIP):
    """Project world points into a W x H image (pixel units, origin top-left, +v down).

    Returns ``(uv, zc)``: ``uv`` is Nx2 (NaN where zc <= near, i.e. not visible), ``zc`` the
    camera depth. A single 3-vector input returns a (2,) uv and a float zc.
    """
    single = np.asarray(points).ndim == 1
    pc = world_to_camera(points, cam)
    uv = camera_to_pixel(pc, cam, W, H)
    uv[pc[:, 2] <= near] = np.nan
    if single:
        return uv[0], float(pc[0, 2])
    return uv, pc[:, 2]


def clip_camera_segment(c0, c1, near: float = NEAR_CLIP):
    """Clip a camera-space segment to zc >= near. Returns (c0', c1') or None."""
    c0 = np.asarray(c0, float)
    c1 = np.asarray(c1, float)
    z0, z1 = c0[2], c1[2]
    if z0 <= near and z1 <= near:
        return None
    if z0 < near:
        c0 = c0 + (near - z0) / (z1 - z0) * (c1 - c0)
    elif z1 < near:
        c1 = c1 + (near - z1) / (z0 - z1) * (c0 - c1)
    return c0, c1


def clip_segment_2d(p0, p1, xmin, ymin, xmax, ymax):
    """Liang-Barsky clip of a 2D segment to a rectangle. Returns (p0', p1') or None."""
    x0, y0 = float(p0[0]), float(p0[1])
    dx, dy = float(p1[0]) - x0, float(p1[1]) - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - xmin), (dx, xmax - x0), (-dy, y0 - ymin), (dy, ymax - y0)):
        if abs(p) < 1e-15:
            if q < 0:
                return None
            continue
        t = q / p
        if p < 0:
            if t > t1:
                return None
            t0 = max(t0, t)
        else:
            if t < t0:
                return None
            t1 = min(t1, t)
    return (x0 + t0 * dx, y0 + t0 * dy), (x0 + t1 * dx, y0 + t1 * dy)


def project_segment(p0, p1, cam, W: float, H: float, near: float = NEAR_CLIP, margin: float = 1.0):
    """World segment -> 2D pixel segment clipped at zc=near (camera space) and to the image
    rectangle grown by ``margin`` * size. Returns ((u0, v0), (u1, v1)) or None. Never wraps."""
    pc = world_to_camera(np.array([p0, p1], float), cam)
    clipped = clip_camera_segment(pc[0], pc[1], near)
    if clipped is None:
        return None
    uv = camera_to_pixel(np.array(clipped), cam, W, H)
    return clip_segment_2d(uv[0], uv[1], -margin * W, -margin * H, (1 + margin) * W, (1 + margin) * H)


def project_polyline(points, cam, W: float, H: float, near: float = NEAR_CLIP) -> list:
    """List of clipped 2D segments for a 3D polyline."""
    pts = np.asarray(points, float)
    out = []
    for a, b in zip(pts[:-1], pts[1:]):
        s = project_segment(a, b, cam, W, H, near)
        if s is not None:
            out.append(s)
    return out


def blender_camera_matrix(cam) -> np.ndarray:
    """3x3 world rotation of the equivalent Blender camera (columns = camera local X, Y, Z in
    world): look-at (camera -Z -> f, +Y -> u) followed by a rotation of rho about local Z.
    Equals [r', u', -f]."""
    r2, u2, f = camera_basis(cam)
    return np.column_stack([r2, u2, -f])


def blender_lens_mm(cam, sensor_width_mm: float = 36.0) -> float:
    return sensor_width_mm / (2.0 * math.tan(math.radians(float(cam["horizontal_fov_deg"])) / 2.0))


# ---------------------------------------------------------------------------------------------
# indexed spec
# ---------------------------------------------------------------------------------------------
class Spec:
    """Indexed view over a spec dict. Geometry is computed lazily and cached."""

    def __init__(self, data: dict, path: str | None = None):
        self.data = data
        self.path = path
        self.rooms = {r["id"]: r for r in data.get("rooms", []) or [] if isinstance(r, dict) and "id" in r}
        self.walls = {w["id"]: w for w in data.get("walls", []) or [] if isinstance(w, dict) and "id" in w}
        self.items = [i for i in data.get("items", []) or [] if isinstance(i, dict)]
        self.lights = [l for l in data.get("lights", []) or [] if isinstance(l, dict)]
        self.cameras = [c for c in data.get("cameras", []) or [] if isinstance(c, dict)]
        self.spawn = data.get("spawn")
        self._planes: dict = {}
        self._wall_rooms = None

    @classmethod
    def load(cls, path) -> "Spec":
        return load_spec(path)

    # -- simple accessors
    @property
    def name(self) -> str:
        return str(self.data.get("name", "spec"))

    def room_polygon(self, room_id: str) -> np.ndarray:
        return _arr2(self.rooms[room_id]["polygon"])

    def items_in_room(self, room_id: str) -> list:
        return [i for i in self.items if i.get("room") == room_id]

    def camera(self, ref: str):
        for c in self.cameras:
            if c.get("ref") == ref:
                return c
        return None

    def openings(self) -> Iterable:
        """Yield (wall, opening) pairs."""
        for w in self.walls.values():
            for o in w.get("openings", []) or []:
                if isinstance(o, dict):
                    yield w, o

    def opening(self, opening_id: str):
        for w, o in self.openings():
            if o.get("id") == opening_id:
                return w, o
        return None

    def room_at(self, x: float, y: float):
        for rid, r in self.rooms.items():
            if points_in_polygon([[x, y]], r["polygon"])[0]:
                return rid
        return None

    # -- wall <-> room association
    def wall_rooms(self) -> dict:
        """{wall_id: {'left': {room_id: [(s0, s1), ...]}, 'right': {...}}}: parts of each face
        (wall parameter s) that coincide (1 cm) with an edge of a room lying on that side."""
        if self._wall_rooms is not None:
            return self._wall_rooms
        res = {}
        for wid, w in self.walls.items():
            res[wid] = {"left": {}, "right": {}}
            try:
                faces = wall_faces(w)
            except (KeyError, TypeError, ValueError):
                continue
            if faces["left"]["length"] < EPS:
                continue
            for side, face in faces.items():
                for rid, room in self.rooms.items():
                    try:
                        edges = _room_edges(room)
                    except (KeyError, TypeError, ValueError):
                        continue  # malformed polygon (reported by the validator)
                    for (p, q, ni) in edges:
                        if float(ni @ face["normal"]) < 0.999:
                            continue
                        dp = float((p - face["a"]) @ face["normal"])
                        dq = float((q - face["a"]) @ face["normal"])
                        if abs(dp) > FACE_TOL or abs(dq) > FACE_TOL:
                            continue
                        sp = float((p - face["a"]) @ face["dir"])
                        sq = float((q - face["a"]) @ face["dir"])
                        lo, hi = max(min(sp, sq), 0.0), min(max(sp, sq), face["length"])
                        if hi - lo > FACE_TOL:
                            res[wid][side].setdefault(rid, []).append((lo, hi))
                for rid in res[wid][side]:
                    res[wid][side][rid] = interval_union(res[wid][side][rid], join_tol=FACE_TOL)
        self._wall_rooms = res
        return res

    def room_side_of_wall(self, room_id: str, wall_id: str):
        """'left'/'right' if the wall bounds the room on that side, else None."""
        wr = self.wall_rooms().get(wall_id)
        if not wr:
            return None
        for side in ("left", "right"):
            if room_id in wr[side]:
                return side
        return None

    def opening_side_rooms(self, wall, opening, tol: float = FACE_TOL) -> dict:
        """{'left': room_id|None, 'right': room_id|None} -- the room on each face whose edge
        covers the full opening width (``tol``). Also returns partial matches under
        'left_partial'/'right_partial' (rooms that touch but do not cover the span)."""
        s0, s1 = opening_span(opening)
        out = {"left": None, "right": None, "left_partial": [], "right_partial": []}
        wr = self.wall_rooms().get(wall["id"], {"left": {}, "right": {}})
        for side in ("left", "right"):
            for rid, ivs in wr[side].items():
                if any(a <= s0 + tol and b >= s1 - tol for a, b in ivs):
                    out[side] = rid
                elif any(b > s0 + tol and a < s1 - tol for a, b in ivs):
                    out[side + "_partial"].append(rid)
        return out

    def room_face(self, room_id: str, wall) -> dict:
        """Face of ``wall`` that bounds ``room_id`` (falls back to the side containing the
        room's label point when the wall does not bound the room)."""
        side = self.room_side_of_wall(room_id, wall["id"])
        if side is None:
            a, b, d, nl, L = wall_frame(wall)
            c = polygon_label_point(self.rooms[room_id]["polygon"])
            side = "left" if float((c - a) @ nl) >= 0 else "right"
        return wall_face(wall, side)

    # -- ceilings
    def ceiling_planes(self, room_id: str) -> list:
        """[(label, slope_or_None, (c0, cx, cy))] with plane z = c0 + cx*x + cy*y. The first
        entry is the flat plane z = height."""
        if room_id in self._planes:
            return self._planes[room_id]
        room = self.rooms[room_id]
        ceil = room.get("ceiling") or {}
        H = float(ceil.get("height", (self.data.get("storey") or {}).get("default_ceiling_height", 2.6)))
        planes = [("flat", None, (H, 0.0, 0.0))]
        if ceil.get("type") == "sloped":
            for s in ceil.get("slopes", []) or []:
                w = self.walls.get(s.get("wall"))
                if w is None:
                    continue
                face = self.room_face(room_id, w)
                tp = math.tan(math.radians(float(s["pitch_deg"])))
                n, a = face["normal"], face["a"]
                c0 = float(s["knee_height"]) - tp * float(n @ a)
                planes.append((f"slope:{s['wall']}", s, (c0, tp * float(n[0]), tp * float(n[1]))))
        self._planes[room_id] = planes
        return planes

    def ceiling_height(self, room_id: str) -> float:
        return self.ceiling_planes(room_id)[0][2][0]

    def ceiling_z(self, room_id: str, x, y):
        """Ceiling height z(x, y) of ``room_id`` (vectorised over x, y). For sloped rooms:
        min(height, knee + signed distance to the bounding wall face * tan(pitch))."""
        x = np.asarray(x, float)
        y = np.asarray(y, float)
        z = None
        for _, _, (c0, cx, cy) in self.ceiling_planes(room_id):
            zz = c0 + cx * x + cy * y
            z = zz if z is None else np.minimum(z, zz)
        return float(z) if np.ndim(z) == 0 else z

    def slope_break_distance(self, room_id: str, slope) -> float:
        """Distance from the wall face at which the slope reaches the flat height."""
        H = self.ceiling_height(room_id)
        tp = math.tan(math.radians(float(slope["pitch_deg"])))
        return max(0.0, (H - float(slope["knee_height"])) / tp) if tp > EPS else float("inf")

    def ceiling_creases(self, room_id: str, step: float = 0.05) -> list:
        """3D polylines where two ceiling planes meet and are both the active minimum
        (slope/flat break lines, hips, ridges), clipped to the room polygon."""
        planes = self.ceiling_planes(room_id)
        poly = self.room_polygon(room_id)
        out = []
        for i in range(len(planes)):
            for j in range(i + 1, len(planes)):
                ci, cj = np.array(planes[i][2]), np.array(planes[j][2])
                g = ci[1:] - cj[1:]
                gn = float(np.linalg.norm(g))
                if gn < 1e-9:
                    continue
                p0 = -(ci[0] - cj[0]) * g / (gn * gn)
                d = np.array([-g[1], g[0]]) / gn
                for t0, t1 in clip_line_to_polygon(p0, d, poly):
                    n = max(2, int(math.ceil((t1 - t0) / step)) + 1)
                    ts = np.linspace(t0, t1, n)
                    P = p0[None, :] + ts[:, None] * d[None, :]
                    zi = ci[0] + ci[1] * P[:, 0] + ci[2] * P[:, 1]
                    zmin = np.asarray(self.ceiling_z(room_id, P[:, 0], P[:, 1]))
                    active = zi <= zmin + 1e-6
                    run = []
                    for k in range(n):
                        if active[k]:
                            run.append([P[k, 0], P[k, 1], zi[k]])
                        elif run:
                            if len(run) > 1:
                                out.append(np.array([run[0], run[-1]]))  # planes meet in a 3D line
                            run = []
                    if len(run) > 1:
                        out.append(np.array([run[0], run[-1]]))
        return out

    def slope_zone_polygons(self, room_id: str) -> list:
        """[(slope, face, break_distance, polygon)] -- plan region between the wall face and
        the line where each slope reaches the flat height, clipped to the room polygon."""
        room = self.rooms[room_id]
        ceil = room.get("ceiling") or {}
        out = []
        if ceil.get("type") != "sloped":
            return out
        poly = self.room_polygon(room_id)
        span = float(np.linalg.norm(poly.max(axis=0) - poly.min(axis=0))) + 10.0
        for s in ceil.get("slopes", []) or []:
            w = self.walls.get(s.get("wall"))
            if w is None:
                continue
            face = self.room_face(room_id, w)
            D = self.slope_break_distance(room_id, s)
            if not math.isfinite(D) or D <= 0:
                continue
            a = face["a"] - face["dir"] * span
            b = face["b"] + face["dir"] * span
            n = face["normal"]
            strip = np.array([a, b, b + n * D, a + n * D])
            zone = convex_clip(poly, strip)
            if len(zone) >= 3 and polygon_area(zone) > 1e-6:
                out.append((s, face, D, np.array(zone)))
        return out

    def dormer_geometry(self, wall, opening) -> dict | None:
        """Dormer recess geometry for a dormer opening. ``inner`` = 4x3 opening rect on the
        room-side face, ``front`` = the same rect moved outward by ``depth`` (from the room
        face), ``cut_lines`` = 3D polylines where the dormer cheeks/ceiling meet a sloped room
        ceiling that descends toward this wall."""
        sides = self.opening_side_rooms(wall, opening)
        room_id, side = None, None
        for sd in ("left", "right"):
            if sides[sd] in self.rooms:
                room_id, side = sides[sd], sd
                break
        if room_id is None:
            return None
        depth = float((opening.get("details") or {}).get("depth", 1.0))
        face = wall_face(wall, side)
        out_n = np.array([-face["normal"][0], -face["normal"][1], 0.0])
        inner = opening_face_rect(wall, opening, side)
        front = inner + out_n * depth
        cut_lines = []
        s0, s1 = opening_span(opening)
        z0, z1 = opening_z(opening)
        for _, s, _ in self.ceiling_planes(room_id)[1:]:
            if s.get("wall") != wall.get("id"):
                continue
            knee = float(s["knee_height"])
            tp = math.tan(math.radians(float(s["pitch_deg"])))
            top = min(z1, self.ceiling_height(room_id))
            if top <= knee or tp <= EPS:
                continue
            dt = (top - knee) / tp
            n = face["normal"]
            for sj in (s0, s1):
                p = wall_point(wall, sj, side)
                cut_lines.append(np.array([[p[0], p[1], knee], [p[0] + n[0] * dt, p[1] + n[1] * dt, top]]))
            pa = wall_point(wall, s0, side) + n * dt
            pb = wall_point(wall, s1, side) + n * dt
            cut_lines.append(np.array([[pa[0], pa[1], top], [pb[0], pb[1], top]]))
        return {"room": room_id, "side": side, "depth": depth, "inner": inner, "front": front,
                "cut_lines": cut_lines}

    def bounds(self, include_cameras: bool = True) -> tuple:
        """Plan bounding box (xmin, ymin, xmax, ymax) of walls, rooms, dormers, cameras."""
        pts = []
        for r in self.rooms.values():
            pts.extend(_arr2(r["polygon"]).tolist())
        for w in self.walls.values():
            try:
                pts.extend(wall_body_polygon(w).tolist())
            except (KeyError, TypeError, ValueError):
                continue
            for o in w.get("openings", []) or []:
                if o.get("type") == "dormer":
                    try:
                        g = self.dormer_geometry(w, o)
                    except (KeyError, TypeError, ValueError):
                        g = None
                    if g:
                        pts.extend(g["front"][:, :2].tolist())
        if include_cameras:
            for c in self.cameras:
                try:
                    pts.append(list(c["position"][:2]))
                except (KeyError, TypeError):
                    pass
        if not pts:
            return (0.0, 0.0, 1.0, 1.0)
        P = np.array(pts, float)
        return (float(P[:, 0].min()), float(P[:, 1].min()), float(P[:, 0].max()), float(P[:, 1].max()))


def _room_edges(room) -> list:
    """[(p, q, interior_normal)] for a room polygon (orientation-aware)."""
    P = _arr2(room["polygon"])
    sgn = 1.0 if polygon_signed_area(P) >= 0 else -1.0
    out = []
    for i in range(len(P)):
        p, q = P[i], P[(i + 1) % len(P)]
        e = q - p
        L = float(np.linalg.norm(e))
        if L < 1e-9:
            continue
        e = e / L
        out.append((p, q, sgn * np.array([-e[1], e[0]])))
    return out


def room_edges(room) -> list:
    return _room_edges(room)


# ---------------------------------------------------------------------------------------------
# fonts (shared by the drawing tools)
# ---------------------------------------------------------------------------------------------
_FONT_CANDIDATES = {
    False: ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"],
    True: ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
           "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"],
}


def load_font(size: int, bold: bool = False):
    from PIL import ImageFont
    for p in _FONT_CANDIDATES[bold]:
        try:
            return ImageFont.truetype(p, int(size))
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=int(size))
    except TypeError:
        return ImageFont.load_default()
