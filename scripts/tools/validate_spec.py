#!/usr/bin/env python3
"""validate_spec.py -- check an apartment_spec.json (schema v2) for structural, architectural and
placement errors.

    python3 scripts/tools/validate_spec.py <spec.json> [--json out.json] [--quiet]

Prints a report (errors, warnings, info) and exits 1 when there is at least one error.
Rules: docs/CONVENTIONS.md, scripts/blender/spec/SCHEMA.md (v2). Levels:

* error   -- the spec is wrong / unbuildable (exit 1)
* warning -- probably wrong or worth a look (clearances, overlaps, roof consistency ...)
* info    -- notes (non-manifest camera refs, scope rooms missing in a partial spec ...)

Programmatic use: ``validate(spec_dict) -> list[Issue]``.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spec_lib as S  # noqa: E402

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None

# tolerances (metres)
TOL_FACE = 0.01          # room edge <-> wall face
TOL_ITEM_ROOM = 0.02     # item footprint may poke 2 cm into a wall
TOL_CEIL = 0.005         # item top vs ceiling
OPENING_END_MARGIN = 0.05
OVERLAP_AREA = 0.002     # m^2 -- below this, footprint contact is ignored
OVERLAP_HEIGHT = 0.02    # m -- vertical overlap needed for an item clash
LEAF_UNDERCUT = 0.02     # items lower than this (rugs) pass under door leaves
THIN_ITEM = 0.03

# --------------------------------------------------------------------------------------------
# JSON schema (structure + types). Geometry rules are checked in code below.
# --------------------------------------------------------------------------------------------
_num = {"type": "number"}
_vec2 = {"type": "array", "items": _num, "minItems": 2, "maxItems": 2}
_vec3 = {"type": "array", "items": _num, "minItems": 3, "maxItems": 3}
_str_or_null = {"type": ["string", "null"]}

SPEC_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["schema_version", "name", "storey", "rooms", "walls", "items", "lights", "cameras", "spawn"],
    "properties": {
        "schema_version": {"const": 2},
        "name": {"type": "string"},
        "storey": {"type": "object", "required": ["default_ceiling_height"],
                   "properties": {"default_ceiling_height": {"type": "number", "exclusiveMinimum": 0},
                                  "slab_thickness": {"type": "number", "minimum": 0}}},
        "rooms": {"type": "array", "minItems": 1, "items": {
            "type": "object",
            "required": ["id", "name", "references", "placeholder", "polygon", "floor_finish",
                         "wall_finish_default", "ceiling_finish", "ceiling"],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "name": {"type": "string"},
                "references": {"type": "array", "items": {"type": "string"}},
                "placeholder": {"type": "boolean"},
                "polygon": {"type": "array", "items": _vec2, "minItems": 3},
                "floor_finish": {"type": "string"},
                "floor_plank_direction_deg": _num,
                "wall_finish_default": {"type": "string"},
                "ceiling_finish": {"type": "string"},
                "ceiling": {
                    "type": "object", "required": ["type", "height"],
                    "properties": {
                        "type": {"enum": ["flat", "sloped"]},
                        "height": {"type": "number", "exclusiveMinimum": 0},
                        "slopes": {"type": "array", "items": {
                            "type": "object", "required": ["wall", "knee_height", "pitch_deg"],
                            "properties": {"wall": {"type": "string"},
                                           "knee_height": {"type": "number", "minimum": 0},
                                           "pitch_deg": {"type": "number", "exclusiveMinimum": 0,
                                                         "exclusiveMaximum": 90}}}}},
                    "if": {"properties": {"type": {"const": "sloped"}}},
                    "then": {"required": ["slopes"], "properties": {"slopes": {"minItems": 1}}},
                },
            }}},
        "walls": {"type": "array", "items": {
            "type": "object",
            "required": ["id", "kind", "start", "end", "thickness", "openings"],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "kind": {"enum": ["exterior", "interior", "party"]},
                "start": _vec2, "end": _vec2,
                "thickness": {"type": "number", "exclusiveMinimum": 0},
                "height": {"type": ["number", "null"]},
                "finish_left": _str_or_null, "finish_right": _str_or_null,
                "skirting": {"type": ["object", "null"]},
                "openings": {"type": "array", "items": {
                    "type": "object",
                    "required": ["id", "type", "offset", "width", "height", "connects"],
                    "properties": {
                        "id": {"type": "string", "minLength": 1},
                        "type": {"enum": list(S.OPENING_TYPES)},
                        "offset": {"type": "number"},
                        "width": {"type": "number", "exclusiveMinimum": 0},
                        "sill_height": {"type": "number", "minimum": 0},
                        "height": {"type": "number", "exclusiveMinimum": 0},
                        "connects": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 2},
                        "hinge": {"enum": ["start", "end"]},
                        "swing_into": {"type": "string"},
                        "leaf": {"type": "string"},
                        "details": {"type": ["object", "null"]},
                    },
                    "allOf": [
                        {"if": {"properties": {"type": {"const": "door"}}},
                         "then": {"required": ["hinge", "swing_into", "leaf"]}},
                        {"if": {"properties": {"type": {"const": "louvered_pair"}}},
                         "then": {"required": ["swing_into"]}},
                    ],
                }},
            }}},
        "items": {"type": "array", "items": {
            "type": "object",
            "required": ["id", "room", "category", "type", "position", "yaw_deg", "dimensions"],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "room": {"type": "string"},
                "category": {"enum": list(S.ITEM_CATEGORIES)},
                "type": {"type": "string"},
                "position": _vec3,
                "yaw_deg": _num,
                "dimensions": {"type": "array", "items": {"type": "number", "exclusiveMinimum": 0},
                               "minItems": 3, "maxItems": 3},
                "wall": _str_or_null,
                "interactive": {"type": "boolean"},
                "evidence": {"type": "array", "items": {"type": "string"}},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "notes": {"type": "string"},
            }}},
        "lights": {"type": "array", "items": {
            "type": "object", "required": ["id", "room", "type", "position"],
            "properties": {"id": {"type": "string"}, "room": {"type": "string"}, "type": {"type": "string"},
                           "position": _vec3}}},
        "cameras": {"type": "array", "items": {
            "type": "object", "required": ["ref", "room", "position", "look_at", "horizontal_fov_deg"],
            "properties": {"ref": {"type": "string"}, "room": {"type": "string"},
                           "position": _vec3, "look_at": _vec3,
                           "horizontal_fov_deg": {"type": "number", "exclusiveMinimum": 1, "exclusiveMaximum": 179},
                           "roll_deg": _num,
                           "confidence": {"type": "number", "minimum": 0, "maximum": 1}}}},
        "spawn": {"type": "object", "required": ["room", "position", "yaw_deg"],
                  "properties": {"room": {"type": "string"}, "position": _vec3, "yaw_deg": _num}},
        "uncertainties": {"type": "array", "items": {"type": "object"}},
    },
}


@dataclass
class Issue:
    level: str          # error | warning | info
    code: str
    message: str
    ids: list = field(default_factory=list)

    def as_dict(self):
        return {"level": self.level, "code": self.code, "message": self.message, "ids": self.ids}


class Report:
    def __init__(self):
        self.issues: list[Issue] = []

    def add(self, level, code, message, *ids):
        self.issues.append(Issue(level, code, message, [i for i in ids if i is not None]))

    def error(self, code, message, *ids):
        self.add("error", code, message, *ids)

    def warn(self, code, message, *ids):
        self.add("warning", code, message, *ids)

    def info(self, code, message, *ids):
        self.add("info", code, message, *ids)


def _fmt(p):
    return "(" + ", ".join(f"{float(v):.3f}" for v in p) + ")"


# --------------------------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------------------------
def check_schema(data, rep):
    if jsonschema is None:
        rep.warn("schema_unavailable", "jsonschema not installed; structural check skipped")
        return
    v = jsonschema.Draft202012Validator(SPEC_SCHEMA)
    for e in sorted(v.iter_errors(data), key=lambda e: list(e.absolute_path)):
        path = "/".join(str(p) for p in e.absolute_path) or "<root>"
        rep.error("schema", f"{path}: {e.message}")


def _ok_room(r):
    try:
        P = np.asarray(r["polygon"], float)
        return P.ndim == 2 and P.shape[1] == 2 and len(P) >= 3 and isinstance(r.get("ceiling"), dict)
    except (KeyError, TypeError, ValueError):
        return False


def _ok_wall(w):
    try:
        a = np.asarray(w["start"], float)
        b = np.asarray(w["end"], float)
        return a.shape == (2,) and b.shape == (2,) and float(w["thickness"]) > 0 and \
            float(np.linalg.norm(b - a)) > 1e-6
    except (KeyError, TypeError, ValueError):
        return False


def _ok_opening(o):
    try:
        float(o["offset"]); float(o["width"]); float(o["height"])
        return isinstance(o.get("connects"), list)
    except (KeyError, TypeError, ValueError):
        return False


def _ok_item(i):
    try:
        p = np.asarray(i["position"], float)
        d = np.asarray(i["dimensions"], float)
        return p.shape == (3,) and d.shape == (3,) and (d > 0).all()
    except (KeyError, TypeError, ValueError):
        return False


def check_ids(data, rep):
    seen = {}
    groups = [("room", data.get("rooms") or []), ("wall", data.get("walls") or []),
              ("item", data.get("items") or []), ("light", data.get("lights") or [])]
    openings = []
    for w in data.get("walls") or []:
        if isinstance(w, dict):
            openings.extend(w.get("openings") or [])
    groups.append(("opening", openings))
    for kind, entries in groups:
        local = set()
        for e in entries:
            if not isinstance(e, dict) or "id" not in e:
                continue
            i = e["id"]
            if i in local:
                rep.error("duplicate_id", f"duplicate {kind} id '{i}'", i)
            local.add(i)
            if i in seen and seen[i] != kind:
                lvl = rep.warn if {seen[i], kind} == {"item", "light"} else rep.error
                lvl("duplicate_id", f"id '{i}' used by both a {seen[i]} and a {kind}", i)
            seen.setdefault(i, kind)
    refs = [c.get("ref") for c in data.get("cameras") or [] if isinstance(c, dict)]
    for r in sorted({r for r in refs if refs.count(r) > 1}):
        rep.error("duplicate_camera", f"camera ref '{r}' appears more than once", r)


def check_rooms(spec, rep):
    rooms = {rid: r for rid, r in spec.rooms.items() if _ok_room(r)}
    for rid, r in spec.rooms.items():
        if rid not in rooms:
            rep.error("room_malformed", f"room '{rid}' has an unusable polygon/ceiling", rid)
    for rid, r in rooms.items():
        ok, why = S.polygon_is_simple(r["polygon"])
        if not ok:
            rep.error("room_not_simple", f"room '{rid}' polygon is not simple: {why}", rid)
            continue
        a = S.polygon_signed_area(r["polygon"])
        if a <= 0:
            rep.error("room_not_ccw", f"room '{rid}' polygon is clockwise (area {a:.3f}); must be counter-clockwise", rid)
        if abs(a) < 1.0:
            rep.warn("room_tiny", f"room '{rid}' area is only {abs(a):.2f} m2", rid)
        if r.get("placeholder") and rid != "living_placeholder":
            rep.error("placeholder_flag", f"room '{rid}' has placeholder:true (only living_placeholder may)", rid)
        if r.get("floor_finish") not in S.FLOOR_FINISHES:
            rep.warn("finish_key", f"room '{rid}' floor_finish '{r.get('floor_finish')}' is not a documented key", rid)
        if r.get("wall_finish_default") not in S.WALL_FINISHES:
            rep.warn("finish_key", f"room '{rid}' wall_finish_default '{r.get('wall_finish_default')}' is not a documented key", rid)
        if r.get("ceiling_finish") not in S.CEILING_FINISHES:
            rep.warn("finish_key", f"room '{rid}' ceiling_finish '{r.get('ceiling_finish')}' is not a documented key", rid)
        h = (r.get("ceiling") or {}).get("height")
        if isinstance(h, (int, float)) and not (2.0 <= h <= 4.0):
            rep.warn("ceiling_height", f"room '{rid}' ceiling height {h} m is outside 2.0-4.0 m", rid)
        canon = S.CANONICAL_REFS.get(rid)
        if canon and canon not in (r.get("references") or []):
            rep.info("room_reference", f"room '{rid}' does not list its canonical reference {canon}", rid)
    ids = sorted(rooms)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            pa, pb = np.asarray(rooms[a]["polygon"], float), np.asarray(rooms[b]["polygon"], float)
            if (pa[:, 0].max() <= pb[:, 0].min() or pb[:, 0].max() <= pa[:, 0].min() or
                    pa[:, 1].max() <= pb[:, 1].min() or pb[:, 1].max() <= pa[:, 1].min()):
                continue
            try:
                ov = S.polygon_intersection_area(pa, pb)
            except Exception as ex:  # noqa: BLE001
                rep.warn("overlap_check_failed", f"could not test overlap of '{a}' and '{b}': {ex}", a, b)
                continue
            if ov > 1e-4:
                rep.error("room_overlap", f"rooms '{a}' and '{b}' overlap by {ov:.3f} m2", a, b)
    present = set(spec.rooms)
    missing = [r for r in S.SCOPE_ROOMS if r not in present]
    if missing:
        rep.warn("scope_room_missing", "scope rooms missing from spec: " + ", ".join(missing))
    return rooms


def check_walls(spec, rooms, rep):
    walls = {wid: w for wid, w in spec.walls.items() if _ok_wall(w)}
    for wid, w in spec.walls.items():
        if wid not in walls:
            rep.error("wall_malformed", f"wall '{wid}' has unusable start/end/thickness (or zero length)", wid)
    wr = spec.wall_rooms()
    for wid, w in walls.items():
        t = float(w["thickness"])
        kind = w.get("kind")
        if kind == "exterior" and not (0.30 - 1e-6 <= t <= 0.40 + 1e-6):
            rep.warn("wall_thickness", f"exterior wall '{wid}' thickness {t} m outside 0.30-0.40", wid)
        if kind == "interior" and not (0.10 - 1e-6 <= t <= 0.15 + 1e-6):
            rep.warn("wall_thickness", f"interior wall '{wid}' thickness {t} m outside 0.10-0.15", wid)
        for side in ("left", "right"):
            rs = sorted(wr[wid][side])
            if len(rs) > 1:
                rep.error("wall_multi_room", f"wall '{wid}' bounds {len(rs)} rooms on its {side} side "
                          f"({', '.join(rs)}); split it at the partition junction", wid, *rs)
        if not wr[wid]["left"] and not wr[wid]["right"]:
            rep.warn("wall_orphan", f"wall '{wid}' does not bound any room", wid)
        # wall body must not intrude into rooms
        body = S.wall_body_polygon(w)
        for rid, r in rooms.items():
            P = np.asarray(r["polygon"], float)
            bb = body
            if (bb[:, 0].max() <= P[:, 0].min() or P[:, 0].max() <= bb[:, 0].min() or
                    bb[:, 1].max() <= P[:, 1].min() or P[:, 1].max() <= bb[:, 1].min()):
                continue
            try:
                ov = S.polygon_intersection_area(body, P)
            except Exception:  # noqa: BLE001
                continue
            L = S.wall_length(w)
            if ov > max(0.005, 0.01 * L):
                rep.error("wall_in_room", f"wall '{wid}' body overlaps room '{rid}' by {ov:.3f} m2 "
                          f"(face not on the room boundary)", wid, rid)
        # finishes
        for side in ("finish_left", "finish_right"):
            f = w.get(side)
            if f is not None and f not in S.WALL_FINISHES:
                rep.warn("finish_key", f"wall '{wid}' {side} '{f}' is not a documented key", wid)
        if kind == "exterior":
            ext_sides = [s for s in ("left", "right") if not wr[wid][s]]
            for s in ext_sides:
                f = w.get("finish_" + s)
                if f not in (None, "exterior"):
                    rep.info("exterior_finish", f"exterior wall '{wid}' {s} face (no room) has finish '{f}'", wid)
    return walls


def check_edge_coverage(spec, rooms, walls, rep):
    for rid, r in rooms.items():
        for k, (p, q, ni) in enumerate(S.room_edges(r)):
            e = q - p
            Le = float(np.linalg.norm(e))
            ed = e / Le
            ivs = []
            best = None
            for wid, w in walls.items():
                for side in ("left", "right"):
                    f = S.wall_face(w, side)
                    if float(ni @ f["normal"]) < 0.999:
                        continue
                    dp = float((p - f["a"]) @ f["normal"])
                    dq = float((q - f["a"]) @ f["normal"])
                    dist = max(abs(dp), abs(dq))
                    if dist > TOL_FACE:
                        # remember nearest parallel face for the message
                        ua = float((f["a"] - p) @ ed)
                        ub = float((f["b"] - p) @ ed)
                        if min(ua, ub) < Le and max(ua, ub) > 0 and (best is None or dist < best[0]):
                            best = (dist, f"{wid}.{side}")
                        continue
                    ua = float((f["a"] - p) @ ed)
                    ub = float((f["b"] - p) @ ed)
                    ivs.append((min(ua, ub), max(ua, ub)))
            gaps = S.interval_gaps(ivs, 0.0, Le, tol=TOL_FACE)
            for g0, g1 in gaps:
                hint = f"; nearest parallel wall face {best[1]} is {best[0]*100:.1f} cm away" if best else ""
                a = p + ed * g0
                b = p + ed * g1
                rep.error("edge_uncovered", f"room '{rid}' edge {k} {_fmt(p)}->{_fmt(q)}: stretch {_fmt(a)}->{_fmt(b)} "
                          f"is not covered by any wall face (1 cm){hint}", rid)


def check_openings(spec, rooms, walls, rep):
    wr = spec.wall_rooms()
    for wid, w in walls.items():
        L = S.wall_length(w)
        ops = [o for o in (w.get("openings") or []) if isinstance(o, dict)]
        good = []
        for o in ops:
            oid = o.get("id", "?")
            if not _ok_opening(o):
                rep.error("opening_malformed", f"opening '{oid}' on '{wid}' lacks offset/width/height/connects", oid)
                continue
            good.append(o)
            s0, s1 = S.opening_span(o)
            if s0 < OPENING_END_MARGIN - 1e-9 or s1 > L - OPENING_END_MARGIN + 1e-9:
                rep.error("opening_outside_wall", f"opening '{oid}' spans s={s0:.3f}..{s1:.3f} on wall '{wid}' "
                          f"(length {L:.3f}); must stay >= {OPENING_END_MARGIN} m from both ends", oid, wid)
            sides = spec.opening_side_rooms(w, o)
            for sd in ("left", "right"):
                if sides[sd] is None and sides[sd + "_partial"]:
                    rep.error("opening_off_room", f"opening '{oid}' on wall '{wid}' is only partly inside room(s) "
                              f"{sides[sd + '_partial']} on the {sd} face (runs into a corner/partition)", oid, wid)
            side_rooms = [sides["left"], sides["right"]]
            connects = list(o.get("connects") or [])
            # connects vs sides
            for c in connects:
                if c in spec.rooms and c not in side_rooms:
                    rep.error("connects_mismatch", f"opening '{oid}' connects '{c}' but that room is not on either "
                              f"face of wall '{wid}' over the opening (left={sides['left']}, right={sides['right']})", oid, c)
            for sr in side_rooms:
                if sr is not None and sr not in connects:
                    rep.error("connects_mismatch", f"opening '{oid}' on wall '{wid}' has room '{sr}' on one side but "
                              f"connects={connects}", oid, sr)
            nonroom = [c for c in connects if c not in spec.rooms]
            empty_sides = [sd for sd in ("left", "right") if sides[sd] is None and not sides[sd + "_partial"]]
            if len(nonroom) != len(empty_sides):
                rep.error("connects_mismatch", f"opening '{oid}': connects={connects} but rooms on faces are "
                          f"left={sides['left']}, right={sides['right']}", oid)
            for c in nonroom:
                if c not in S.NON_ROOM_TOKENS:
                    rep.warn("connects_token", f"opening '{oid}' connects unknown non-room '{c}' "
                             f"(expected a room id, 'exterior' or 'stairwell')", oid)
            otype = o.get("type")
            if otype in ("door", "louvered_pair") or o.get("swing_into") is not None:
                si = o.get("swing_into")
                if otype in ("door", "louvered_pair") and si not in connects:
                    rep.error("swing_into", f"door '{oid}' swing_into '{si}' is not one of connects {connects}", oid)
                if otype == "door" and o.get("hinge") not in ("start", "end"):
                    rep.error("door_hinge", f"door '{oid}' hinge must be 'start' or 'end'", oid)
            if otype in S.WINDOW_OPENINGS and "exterior" not in connects:
                rep.warn("window_interior", f"{otype} '{oid}' does not connect to 'exterior'", oid)
            if otype in S.WINDOW_OPENINGS and w.get("kind") != "exterior":
                rep.warn("window_interior", f"{otype} '{oid}' sits on a non-exterior wall '{wid}'", oid)
            if otype == "dormer" and "depth" not in (o.get("details") or {}):
                rep.warn("dormer_depth", f"dormer '{oid}' has no details.depth (1.0 m assumed)", oid)
            z0, z1 = S.opening_z(o)
            if otype in ("door", "doorway", "sliding_door", "louvered_pair") and z0 > 0.03:
                rep.warn("door_sill", f"{otype} '{oid}' has sill_height {z0} m", oid)
            if otype in ("door", "doorway", "sliding_door") and z1 < 1.9 and connects and "exterior" not in connects:
                rep.warn("door_low", f"{otype} '{oid}' height {z1:.2f} m < 1.90 m", oid)
            # top of opening under ceiling at the wall face (dormers / roof windows cut the roof)
            if otype not in ("dormer", "roof_window"):
                for sd in ("left", "right"):
                    rid = sides[sd]
                    if rid is None or rid not in rooms:
                        continue
                    pts = np.array([S.wall_point(w, s, sd) for s in (s0, s1)])
                    try:
                        zc = np.min(spec.ceiling_z(rid, pts[:, 0], pts[:, 1]))
                    except Exception:  # noqa: BLE001
                        continue
                    if z1 > zc + 0.01:
                        rep.error("opening_above_ceiling", f"{otype} '{oid}' top {z1:.2f} m exceeds the ceiling of "
                                  f"'{rid}' at the wall face ({zc:.2f} m); use a dormer/roof_window or lower it", oid, rid)
            if w.get("height") is not None and z1 > float(w["height"]) + 0.01:
                rep.error("opening_above_wall", f"opening '{oid}' top {z1:.2f} exceeds wall '{wid}' height {w['height']}", oid)
        # overlaps on the same wall
        good.sort(key=lambda o: float(o["offset"]))
        for i in range(len(good)):
            for j in range(i + 1, len(good)):
                a0, a1 = S.opening_span(good[i])
                b0, b1 = S.opening_span(good[j])
                if min(a1, b1) - max(a0, b0) > 1e-6:
                    rep.error("opening_overlap", f"openings '{good[i]['id']}' and '{good[j]['id']}' overlap on wall "
                              f"'{wid}' (s {a0:.2f}-{a1:.2f} vs {b0:.2f}-{b1:.2f})", good[i]["id"], good[j]["id"])


def _sector_items_clash(spec, wall, o, rooms, items, rep):
    si = o.get("swing_into")
    if si not in rooms:
        return []
    side = spec.room_side_of_wall(si, wall["id"])
    if side is None:
        return []
    leaves = S.door_leaves(wall, o, side)
    z1 = S.opening_z(o)[1]
    poly = rooms[si]["polygon"]
    sectors = []
    for lf in leaves:
        sec = S.leaf_sector_polygon(lf)
        sectors.append(sec)
        arc = sec[1:]
        sd = S.polygon_signed_distance(arc, poly)
        if sd.min() < -TOL_ITEM_ROOM:
            rep.warn("door_leaf_hits_wall", f"door '{o['id']}' leaf (r={lf['radius']:.2f} m) sweeps outside room "
                     f"'{si}' by {-sd.min()*100:.0f} cm", o["id"], si)
        for it in items:
            if it.get("room") != si:
                continue
            iz0, iz1 = S.item_z_range(it)
            if iz1 <= LEAF_UNDERCUT or iz0 >= z1:
                continue
            fp = S.item_footprint(it)
            ov = S.polygon_area(S.convex_clip(fp, sec))
            if ov > OVERLAP_AREA:
                rep.warn("door_swing_blocked", f"door '{o['id']}' leaf swing hits item '{it['id']}' "
                         f"({ov:.3f} m2 of its footprint inside the swing arc)", o["id"], it["id"])
    return [(si, sec) for sec in sectors]


def check_doors_and_clearance(spec, rooms, walls, items, rep):
    swept = []
    for wid, w in walls.items():
        for o in w.get("openings") or []:
            if not isinstance(o, dict) or not _ok_opening(o):
                continue
            if o.get("type") in S.SWINGING_OPENINGS:
                swept.extend((o["id"], si, sec) for si, sec in _sector_items_clash(spec, w, o, rooms, items, rep))
            if o.get("type") in S.PASSABLE_OPENINGS:
                # passage clearance: 0.30 m deep zone in front of the opening on each room side
                s0, s1 = S.opening_span(o)
                sides = spec.opening_side_rooms(w, o)
                z1 = S.opening_z(o)[1]
                for sd in ("left", "right"):
                    rid = sides[sd]
                    if rid is None:
                        continue
                    f = S.wall_face(w, sd)
                    a, b = S.wall_point(w, s0, sd), S.wall_point(w, s1, sd)
                    zone = np.array([a, b, b + f["normal"] * 0.30, a + f["normal"] * 0.30])
                    for it in items:
                        if it.get("room") != rid:
                            continue
                        iz0, iz1 = S.item_z_range(it)
                        if iz1 <= THIN_ITEM or iz0 >= z1:
                            continue
                        ov = S.polygon_area(S.convex_clip(S.item_footprint(it), zone))
                        if ov > OVERLAP_AREA:
                            rep.warn("opening_blocked", f"item '{it['id']}' stands in the passage of "
                                     f"{o.get('type')} '{o['id']}' ({ov:.3f} m2 within 30 cm)", it["id"], o["id"])
    for i in range(len(swept)):
        for j in range(i + 1, len(swept)):
            if swept[i][1] != swept[j][1] or swept[i][0] == swept[j][0]:
                continue
            ov = S.polygon_area(S.convex_clip(swept[i][2], swept[j][2]))
            if ov > OVERLAP_AREA:
                rep.warn("door_swings_collide", f"swing arcs of '{swept[i][0]}' and '{swept[j][0]}' overlap "
                         f"({ov:.3f} m2)", swept[i][0], swept[j][0])


def check_items(spec, rooms, walls, rep):
    items = []
    for it in spec.items:
        iid = it.get("id", "?")
        if not _ok_item(it):
            rep.error("item_malformed", f"item '{iid}' has unusable position/dimensions", iid)
            continue
        rid = it.get("room")
        if rid not in spec.rooms:
            rep.error("item_room", f"item '{iid}' references unknown room '{rid}'", iid)
            continue
        if spec.rooms[rid].get("placeholder") or rid == "living_placeholder":
            rep.error("placeholder_furnished", f"item '{iid}' is placed in placeholder room '{rid}'", iid, rid)
        items.append(it)
        if it.get("type") not in S.ITEM_TYPES:
            rep.warn("item_type", f"item '{iid}' type '{it.get('type')}' not in vocabulary (falls back to a box)", iid)
        if "evidence" not in it:
            rep.warn("item_evidence", f"item '{iid}' has no evidence list", iid)
        z0, z1 = S.item_z_range(it)
        if z0 < -0.001:
            rep.error("item_below_floor", f"item '{iid}' bottom z={z0:.3f} is below the floor", iid)
        wid = it.get("wall")
        if wid is not None and wid not in spec.walls:
            rep.error("item_wall", f"item '{iid}' references unknown wall '{wid}'", iid)
        if rid not in rooms:
            continue
        fp = S.item_footprint(it)
        poly = rooms[rid]["polygon"]
        out = S.footprint_outside_distance(fp, poly)
        if out > TOL_ITEM_ROOM:
            rep.error("item_outside_room", f"item '{iid}' footprint extends {out*100:.1f} cm outside room '{rid}' "
                      f"(tolerance {TOL_ITEM_ROOM*100:.0f} cm)", iid, rid)
        try:
            zc = np.asarray(spec.ceiling_z(rid, fp[:, 0], fp[:, 1]))
            k = int(np.argmin(zc - z1))
            if z1 > zc[k] + TOL_CEIL:
                rep.error("item_above_ceiling", f"item '{iid}' top z={z1:.3f} pierces the ceiling of '{rid}' at corner "
                          f"{_fmt(fp[k])} (ceiling {zc[k]:.3f} m)", iid, rid)
        except Exception as ex:  # noqa: BLE001
            rep.warn("ceiling_eval", f"could not evaluate ceiling for item '{iid}': {ex}", iid)
        if wid is not None and wid in walls:
            side = spec.room_side_of_wall(rid, wid)
            if side is None:
                rep.warn("item_wall_side", f"item '{iid}' is against wall '{wid}' which does not bound room '{rid}'", iid, wid)
            else:
                f = S.wall_face(walls[wid], side)
                d = np.abs((fp - f["a"]) @ f["normal"]).min()
                if d > 0.10:
                    rep.warn("item_wall_gap", f"item '{iid}' is {d:.2f} m from its wall '{wid}' face", iid, wid)
    # item-item overlaps
    by_room = {}
    for it in items:
        by_room.setdefault(it["room"], []).append(it)
    for rid, lst in by_room.items():
        fps = [S.item_footprint(i) for i in lst]
        bbs = [(f[:, 0].min(), f[:, 1].min(), f[:, 0].max(), f[:, 1].max()) for f in fps]
        zs = [S.item_z_range(i) for i in lst]
        for a in range(len(lst)):
            for b in range(a + 1, len(lst)):
                A, B = bbs[a], bbs[b]
                if A[2] <= B[0] or B[2] <= A[0] or A[3] <= B[1] or B[3] <= A[1]:
                    continue
                hz = min(zs[a][1], zs[b][1]) - max(zs[a][0], zs[b][0])
                if hz <= OVERLAP_HEIGHT:
                    continue
                ov = S.polygon_area(S.convex_clip(fps[a], fps[b]))
                if ov > OVERLAP_AREA:
                    rep.warn("item_overlap", f"items '{lst[a]['id']}' and '{lst[b]['id']}' intersect "
                             f"({ov:.3f} m2 footprint, {hz:.2f} m height overlap)", lst[a]["id"], lst[b]["id"])
    return items


def _inside_and_below(spec, rooms, rid, p, what, ident, rep, level="error"):
    add = rep.error if level == "error" else rep.warn
    if rid not in spec.rooms:
        add(f"{what}_room", f"{what} '{ident}' references unknown room '{rid}'", ident)
        return
    if rid not in rooms:
        return
    poly = rooms[rid]["polygon"]
    sd = float(S.polygon_signed_distance([p[:2]], poly)[0])
    if sd < 0:
        add(f"{what}_outside_room", f"{what} '{ident}' at {_fmt(p)} lies {-sd:.2f} m outside room '{rid}'", ident, rid)
    zc = float(spec.ceiling_z(rid, p[0], p[1]))
    if p[2] > zc + 0.01:
        add(f"{what}_above_ceiling", f"{what} '{ident}' z={p[2]:.2f} is above the ceiling of '{rid}' ({zc:.2f} m)", ident, rid)
    if p[2] < -0.001:
        add(f"{what}_below_floor", f"{what} '{ident}' z={p[2]:.2f} is below the floor", ident)


def check_cameras_spawn_lights(spec, rooms, items, manifest, rep):
    for cam in spec.cameras:
        ref = cam.get("ref", "?")
        try:
            P = np.asarray(cam["position"], float)
            S.camera_basis(cam)
            float(cam["horizontal_fov_deg"])
        except Exception as ex:  # noqa: BLE001
            rep.error("camera_invalid", f"camera '{ref}' is unusable: {ex}", ref)
            continue
        _inside_and_below(spec, rooms, cam.get("room"), P, "camera", ref, rep)
        if P[2] < 0.05:
            rep.error("camera_below_floor", f"camera '{ref}' z={P[2]:.2f} is at/below the floor", ref)
        if manifest and ref not in manifest:
            rep.info("camera_ref", f"camera ref '{ref}' is not in references/manifest.json", ref)
    sp = spec.spawn
    if not isinstance(sp, dict):
        rep.error("spawn_missing", "spawn is missing")
    else:
        try:
            P = np.asarray(sp["position"], float)
            _inside_and_below(spec, rooms, sp.get("room"), P, "spawn", "spawn", rep)
            if abs(P[2]) > 0.01:
                rep.warn("spawn_z", f"spawn z={P[2]:.2f} (expected 0 = floor)")
            for it in items:
                if it.get("room") != sp.get("room"):
                    continue
                z0, z1 = S.item_z_range(it)
                if z1 <= THIN_ITEM or z0 > 1.8:
                    continue
                if S.point_in_polygon(P[:2], S.item_footprint(it), tol=0.2):
                    rep.warn("spawn_in_item", f"spawn is inside/within 20 cm of item '{it['id']}'", it["id"])
        except Exception as ex:  # noqa: BLE001
            rep.error("spawn_invalid", f"spawn is unusable: {ex}")
    for lt in spec.lights:
        lid = lt.get("id", "?")
        try:
            P = np.asarray(lt["position"], float)
        except Exception:  # noqa: BLE001
            continue
        _inside_and_below(spec, rooms, lt.get("room"), P, "light", lid, rep, level="warning")
        r = spec.rooms.get(lt.get("room"))
        if r is not None and (r.get("placeholder") or lt.get("room") == "living_placeholder"):
            rep.warn("placeholder_light", f"light '{lid}' is in the placeholder room", lid)


def check_slopes_and_roof(spec, rooms, walls, rep):
    groups = []  # (wall_id, face, knee, pitch, room)
    for rid, r in rooms.items():
        ceil = r.get("ceiling") or {}
        if ceil.get("type") != "sloped":
            continue
        H = float(ceil.get("height", 0))
        for s in ceil.get("slopes") or []:
            wid = s.get("wall")
            if wid not in spec.walls:
                rep.error("slope_wall", f"room '{rid}' slope references unknown wall '{wid}'", rid, wid)
                continue
            side = spec.room_side_of_wall(rid, wid)
            if side is None:
                rep.error("slope_wall", f"room '{rid}' slope references wall '{wid}' which does not bound it", rid, wid)
                continue
            try:
                knee, pitch = float(s["knee_height"]), float(s["pitch_deg"])
            except (KeyError, TypeError, ValueError):
                continue
            if knee > H:
                rep.error("slope_knee", f"room '{rid}' slope on '{wid}': knee {knee} > ceiling height {H}", rid)
            if knee < 0.6:
                rep.warn("slope_knee", f"room '{rid}' slope on '{wid}': knee {knee} m is very low", rid)
            if spec.walls[wid].get("kind") != "exterior":
                rep.warn("slope_interior", f"room '{rid}' slopes toward non-exterior wall '{wid}'", rid, wid)
            groups.append((wid, S.wall_face(walls[wid], side), knee, pitch, rid))
    # roof consistency: collinear exterior faces (same line, same normal) share knee + pitch
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            wa, fa, ka, pa, ra = groups[i]
            wb, fb, kb, pb, rb = groups[j]
            if spec.walls[wa].get("kind") != "exterior" or spec.walls[wb].get("kind") != "exterior":
                continue
            if float(fa["normal"] @ fb["normal"]) < 0.999:
                continue
            if abs(float((fb["a"] - fa["a"]) @ fa["normal"])) > TOL_FACE:
                continue
            if abs(ka - kb) > 0.01 or abs(pa - pb) > 0.5:
                rep.warn("roof_inconsistent", f"slopes of '{ra}' (wall {wa}: knee {ka}, pitch {pa}) and '{rb}' "
                         f"(wall {wb}: knee {kb}, pitch {pb}) face the same roof plane but differ", ra, rb)


def check_topology(spec, rooms, walls, rep):
    adj = {r: set() for r in spec.rooms}
    stair_doors = []
    for wid, w in walls.items():
        for o in w.get("openings") or []:
            if not isinstance(o, dict) or not _ok_opening(o):
                continue
            con = o.get("connects") or []
            if o.get("type") in S.PASSABLE_OPENINGS:
                rs = [c for c in con if c in spec.rooms]
                if len(rs) == 2:
                    adj[rs[0]].add(rs[1])
                    adj[rs[1]].add(rs[0])
            if "stairwell" in con and o.get("type") in ("door",):
                stair_doors.append((o, [c for c in con if c != "stairwell"]))
    placeholders = {r for r, d in spec.rooms.items() if d.get("placeholder") or r == "living_placeholder"}
    if "hall" not in spec.rooms:
        rep.error("hall_missing", "no room with id 'hall'")
    else:
        def bfs(skip):
            seen = {"hall"}
            dq = deque(["hall"])
            while dq:
                cur = dq.popleft()
                for nb in adj[cur]:
                    if nb in seen:
                        continue
                    seen.add(nb)
                    if nb not in skip:
                        dq.append(nb)
            return seen
        reach_all = bfs(set())
        reach_direct = bfs(placeholders)
        for rid in spec.rooms:
            if rid in placeholders:
                continue
            if rid not in reach_all:
                rep.error("unreachable", f"room '{rid}' is not reachable from the hall through doors/doorways", rid)
            elif rid not in reach_direct:
                rep.warn("reachable_via_placeholder", f"room '{rid}' is only reachable through the living placeholder", rid)
    # bedrooms need an exterior window
    for rid in spec.rooms:
        if not rid.startswith("bedroom"):
            continue
        ok = False
        for wid, w in walls.items():
            for o in w.get("openings") or []:
                if isinstance(o, dict) and o.get("type") in S.WINDOW_OPENINGS and rid in (o.get("connects") or []) \
                        and ("exterior" in (o.get("connects") or []) or w.get("kind") == "exterior"):
                    ok = True
        if not ok:
            rep.error("bedroom_no_window", f"bedroom '{rid}' has no exterior window/dormer/roof_window", rid)
    # placeholder
    lp = spec.rooms.get("living_placeholder")
    if lp is None:
        rep.error("placeholder_missing", "room 'living_placeholder' is missing")
    else:
        if lp.get("placeholder") is not True:
            rep.error("placeholder_flag", "living_placeholder must have placeholder:true", "living_placeholder")
        if "hall" in spec.rooms and "hall" not in adj["living_placeholder"]:
            rep.error("placeholder_hall", "living_placeholder has no door/doorway to the hall", "living_placeholder")
    # stairwell entrance
    if not stair_doors:
        rep.error("entrance_missing", "no door connecting 'stairwell' (flat entrance door)")
    else:
        for o, others in stair_doors:
            if "hall" not in others:
                rep.warn("entrance_room", f"entrance door '{o['id']}' does not open into the hall ({others})", o["id"])


# --------------------------------------------------------------------------------------------
def validate(data: dict, manifest: dict | None = None) -> list:
    """Run every check on a spec dict; return a list of Issue."""
    rep = Report()
    manifest = S.load_manifest() if manifest is None else manifest
    check_schema(data, rep)
    try:
        check_ids(data, rep)
    except Exception as ex:  # noqa: BLE001
        rep.error("internal", f"id check crashed: {ex!r}")
    spec = S.Spec(data)
    rooms, walls, items = {}, {}, []

    def run(name, fn, *a):
        try:
            return fn(*a)
        except Exception as ex:  # noqa: BLE001
            rep.error("internal", f"check '{name}' crashed: {ex!r} (fix the errors above first)")
            return None

    rooms = {rid: r for rid, r in spec.rooms.items() if _ok_room(r)}
    walls = {wid: w for wid, w in spec.walls.items() if _ok_wall(w)}
    run("rooms", check_rooms, spec, rep)
    run("walls", check_walls, spec, rooms, rep)
    run("edge_coverage", check_edge_coverage, spec, rooms, walls, rep)
    run("openings", check_openings, spec, rooms, walls, rep)
    items = run("items", check_items, spec, rooms, walls, rep) or []
    run("doors", check_doors_and_clearance, spec, rooms, walls, items, rep)
    run("cameras", check_cameras_spawn_lights, spec, rooms, items, manifest, rep)
    run("slopes", check_slopes_and_roof, spec, rooms, walls, rep)
    run("topology", check_topology, spec, rooms, walls, rep)
    return rep.issues


def summarize(issues):
    return {lvl: sum(1 for i in issues if i.level == lvl) for lvl in ("error", "warning", "info")}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec")
    ap.add_argument("--json", dest="json_out", help="write the report as JSON")
    ap.add_argument("--quiet", action="store_true", help="print only the summary line")
    args = ap.parse_args(argv)
    try:
        data = S.load_json(args.spec)
        issues = validate(data)
    except (OSError, ValueError) as ex:
        issues = [Issue("error", "load", f"cannot read spec: {ex}")]
    counts = summarize(issues)
    if not args.quiet:
        for lvl in ("error", "warning", "info"):
            for i in issues:
                if i.level == lvl:
                    print(f"{lvl.upper():7s} [{i.code}] {i.message}")
    status = "FAIL" if counts["error"] else "OK"
    print(f"{status}: {args.spec}: {counts['error']} error(s), {counts['warning']} warning(s), {counts['info']} info")
    if args.json_out:
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump({"spec": str(args.spec), "ok": counts["error"] == 0, "counts": counts,
                       "issues": [i.as_dict() for i in issues]}, fh, indent=2)
    return 1 if counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
