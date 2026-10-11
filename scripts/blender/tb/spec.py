"""Schema-v2 spec loading and derived architecture data (pure python, no bpy).

Derived data computed here (and shared by every builder):
  * wall frames (direction d, left normal nL, length L)
  * wall joints: mitred L-corners, flat caps for collinear joins / T-abutments
    -> per-face s-extents sL0, sL1, sR0, sR1 (s measured along the centre line from `start`)
  * which room bounds each side of each wall, resolved finishes
  * per-room ceiling function z(x, y) (SCHEMA: min(height, knee + dist_to_wall_face * tan(pitch)))
    and its planes (for crisp break lines)
  * dormer geometry (recess outline, profile, window opening)
"""
import hashlib
import json
import math
import os

from . import geom as G

TOL = 1e-3          # endpoint coincidence tolerance (m)
DOOR_LIKE = ("door", "doorway", "sliding_door", "louvered_pair")
WINDOW_LIKE = ("window",)


class SpecError(Exception):
    pass


# --------------------------------------------------------------------------------------
# Rooms / ceiling function
# --------------------------------------------------------------------------------------
class Slope:
    def __init__(self, room, wall, side, knee, pitch_deg):
        self.room = room
        self.wall = wall
        self.side = side                      # wall side ('L'/'R') facing the room
        self.knee = float(knee)
        self.pitch_deg = float(pitch_deg)
        self.tan = math.tan(math.radians(self.pitch_deg))
        sgn = 1.0 if side == "L" else -1.0
        self.normal = G.mul(wall.nL, sgn)     # into the room
        self.face_point = G.add(wall.start, G.mul(wall.nL, sgn * wall.t * 0.5))

    def dist(self, x, y):
        return (x - self.face_point[0]) * self.normal[0] + (y - self.face_point[1]) * self.normal[1]

    def z(self, x, y, clamp=True):
        d = self.dist(x, y)
        if clamp and d < 0.0:
            d = 0.0
        return self.knee + d * self.tan

    def plane(self):
        """(a, b, c) with z = a*x + b*y + c (unclamped)."""
        a = self.tan * self.normal[0]
        b = self.tan * self.normal[1]
        c = self.knee - self.tan * (self.face_point[0] * self.normal[0] + self.face_point[1] * self.normal[1])
        return (a, b, c)


class Room:
    def __init__(self, d, spec):
        self.raw = d
        self.id = d["id"]
        self.name = d.get("name", self.id)
        self.placeholder = bool(d.get("placeholder", False))
        self.references = list(d.get("references", []))
        poly = [(float(p[0]), float(p[1])) for p in d["polygon"]]
        if G.polygon_area(poly) < 0:
            spec.warn("room %s polygon is clockwise; reversed to CCW" % self.id)
            poly = list(reversed(poly))
        self.polygon = G.remove_collinear(poly, 1e-6)
        self.floor_finish = d.get("floor_finish") or "concrete_bare"
        self.plank_dir = float(d.get("floor_plank_direction_deg", 0.0) or 0.0)
        self.wall_finish = d.get("wall_finish_default") or "plaster_white"
        self.ceiling_finish = d.get("ceiling_finish") or "plaster_smooth"
        c = d.get("ceiling") or {}
        self.ceiling_type = c.get("type", "flat")
        self.height = float(c.get("height", spec.default_height))
        self._slope_defs = list(c.get("slopes", [])) if self.ceiling_type == "sloped" else []
        self.slopes = []
        self.dormers = []
        self.area = G.polygon_area(self.polygon)
        self.centroid = G.polygon_centroid(self.polygon)
        xs = [p[0] for p in self.polygon]
        ys = [p[1] for p in self.polygon]
        self.bbox = (min(xs), min(ys), max(xs), max(ys))

    def resolve_slopes(self, spec):
        for s in self._slope_defs:
            w = spec.wall_by_id.get(s["wall"])
            if w is None:
                raise SpecError("room %s slope references unknown wall %s" % (self.id, s["wall"]))
            side = w.side_of_room(self.id)
            if side is None:
                # fall back: side facing the room centroid
                side = "L" if G.dot(G.sub(self.centroid, w.start), w.nL) > 0 else "R"
                spec.warn("room %s: slope wall %s does not bound the room; using side %s" % (self.id, w.id, side))
            self.slopes.append(Slope(self, w, side, s.get("knee_height", 1.0), s.get("pitch_deg", 45.0)))

    def z_ceiling(self, x, y, clamp=True):
        z = self.height
        for sl in self.slopes:
            z = min(z, sl.z(x, y, clamp))
        return z

    def planes(self):
        """Ceiling planes [(a,b,c)], first = flat plane."""
        return [(0.0, 0.0, self.height)] + [sl.plane() for sl in self.slopes]

    def min_ceiling(self):
        return min(self.z_ceiling(x, y) for (x, y) in self.polygon)


# --------------------------------------------------------------------------------------
# Walls / openings
# --------------------------------------------------------------------------------------
class Opening:
    def __init__(self, d, wall):
        self.raw = d
        self.wall = wall
        self.id = d["id"]
        self.type = d.get("type", "window")
        self.offset = float(d.get("offset", 0.0))
        self.width = float(d.get("width", 0.9))
        self.sill = float(d.get("sill_height", 0.0) or 0.0)
        self.height = float(d.get("height", 2.0))
        self.connects = list(d.get("connects", []))
        self.hinge = d.get("hinge", "start")
        self.swing_into = d.get("swing_into")
        self.leaf = d.get("leaf")
        self.details = dict(d.get("details") or {})
        if self.type in ("door", "doorway", "sliding_door", "louvered_pair"):
            self.sill = 0.0
        self.s0 = self.offset
        self.s1 = self.offset + self.width
        self.head = self.sill + self.height
        if self.leaf is None:
            self.leaf = {"door": "panel_white", "louvered_pair": "louvered_pair",
                         "sliding_door": "panel_wood"}.get(self.type, "none")
        self.dormer = None   # Dormer when type == 'dormer' and resolvable

    @property
    def door_like(self):
        return self.type in DOOR_LIKE

    @property
    def window_like(self):
        return self.type == "window" or (self.type == "dormer" and self.dormer is None)


class Wall:
    def __init__(self, d, spec):
        self.raw = d
        self.id = d["id"]
        self.kind = d.get("kind", "interior")
        self.start = (float(d["start"][0]), float(d["start"][1]))
        self.end = (float(d["end"][0]), float(d["end"][1]))
        self.t = float(d.get("thickness", 0.12))
        self.height = d.get("height")
        self.height = None if self.height is None else float(self.height)
        self.finish_raw = {"L": d.get("finish_left"), "R": d.get("finish_right")}
        sk = d.get("skirting")
        self.skirting = None if sk is None else {"height": float(sk.get("height", 0.12)),
                                                 "depth": float(sk.get("depth", 0.018))}
        cn = d.get("cornice")
        self.cornice = None if not cn else {"height": float(cn.get("height", 0.08)),
                                            "depth": float(cn.get("depth", 0.08))}
        v = G.sub(self.end, self.start)
        self.L = G.length(v)
        if self.L < 1e-4:
            raise SpecError("wall %s has zero length" % self.id)
        self.d = G.normalize(v)
        self.nL = G.left_normal(self.d)
        # face extents along s (set by joints)
        self.s_ext = {"L": [0.0, self.L], "R": [0.0, self.L]}
        self.joined = {"start": False, "end": False}     # mitred / collinear joint
        self.abuts = {"start": None, "end": None}        # wall id whose face this end touches
        self.room = {"L": None, "R": None}
        self.finish = {"L": None, "R": None}
        self.openings = [Opening(o, self) for o in d.get("openings", [])]
        self.openings.sort(key=lambda o: o.s0)

    # --- frames -------------------------------------------------------------------
    def sgn(self, side):
        return 1.0 if side == "L" else -1.0

    def point(self, s, nl=0.0):
        """Plan point at centre-line parameter s, offset nl along the LEFT normal."""
        return (self.start[0] + self.d[0] * s + self.nL[0] * nl,
                self.start[1] + self.d[1] * s + self.nL[1] * nl)

    def face_point(self, side, s):
        return self.point(s, self.sgn(side) * self.t * 0.5)

    def side_normal(self, side):
        return G.mul(self.nL, self.sgn(side))

    def side_of_room(self, room_id):
        for side in ("L", "R"):
            if self.room[side] == room_id:
                return side
        return None

    def other(self, side):
        return "R" if side == "L" else "L"

    def interior_range(self):
        lo = max(self.s_ext["L"][0], self.s_ext["R"][0])
        hi = min(self.s_ext["L"][1], self.s_ext["R"][1])
        return lo, hi

    def project(self, p):
        """(s, nl) of plan point p in the wall frame."""
        w = G.sub(p, self.start)
        return G.dot(w, self.d), G.dot(w, self.nL)


# --------------------------------------------------------------------------------------
# Dormer
# --------------------------------------------------------------------------------------
class Dormer:
    """Dormer recess through a ceiling slope.

    Local frame: origin O on the host wall's room-side face at the opening centre,
    a = wall direction d, n = into the room, u along a, v along n (v = 0 at the face).
      * cheek walls at |u| = W/2 .. W/2 + tc, vertical, from the main slope up to eave h_e
      * dormer ceiling z_d(u): flat (h_e) or gable (h_e + (W/2-|u|)*tan(roof_pitch)), clamped to H
      * recess ends where z_d meets the main slope: v_end(u) = (z_d(u) - knee) / tan(pitch)
      * window (opening width minus 2*margin) sits in the host wall at the outer end
    `details.depth` = horizontal distance from the host face to where the cheeks end; the eave is
    raised if needed so the window head keeps >= 0.10 m of lintel below it."""
    CHEEK_T = 0.10
    WIN_MARGIN = 0.10
    SLAB_T = 0.10

    def __init__(self, opening, room, slope, spec):
        self.opening = opening
        self.wall = opening.wall
        self.room = room
        self.slope = slope
        self.side = slope.side
        w = self.wall
        self.W = opening.width
        self.tc = float(opening.details.get("cheek_thickness", self.CHEEK_T))
        self.sc = 0.5 * (opening.s0 + opening.s1)
        self.O = w.face_point(self.side, self.sc)
        self.a = w.d
        self.n = slope.normal
        self.knee = slope.knee
        self.tanp = max(slope.tan, 1e-3)
        self.H = room.height
        self.roof = opening.details.get("roof", "gable")
        self.roof_pitch = float(opening.details.get("roof_pitch_deg", 30.0))
        self.depth_req = float(opening.details.get("depth", 1.0))
        self.sill = opening.sill
        self.head = opening.head
        h_e = self.knee + self.depth_req * self.tanp
        if h_e < self.head + 0.10:
            spec.warn("dormer %s: eave raised from %.3f to %.3f to clear the window head"
                      % (opening.id, h_e, self.head + 0.10))
            h_e = self.head + 0.10
        if h_e > self.H:
            spec.warn("dormer %s: eave %.3f clamped to room height %.3f" % (opening.id, h_e, self.H))
            h_e = self.H
        if self.head > h_e - 0.05:
            spec.warn("dormer %s: window head lowered to fit under the eave" % opening.id)
            self.head = h_e - 0.08
        self.h_e = h_e
        self.depth = (h_e - self.knee) / self.tanp
        self.margin = float(opening.details.get("window_margin", self.WIN_MARGIN))
        self.win_s0 = self.sc - self.W * 0.5 + self.margin
        self.win_s1 = self.sc + self.W * 0.5 - self.margin
        # gable clip point (where the gable reaches the flat height)
        self.u_clip = None
        if self.roof == "gable":
            tg = math.tan(math.radians(self.roof_pitch))
            ridge = h_e + self.W * 0.5 * tg
            if ridge > self.H + 1e-6 and tg > 1e-6:
                self.u_clip = self.W * 0.5 - (self.H - h_e) / tg

    # profile ------------------------------------------------------------------
    def z_d(self, u):
        au = abs(u)
        if au >= self.W * 0.5:
            return self.h_e
        if self.roof == "gable":
            z = self.h_e + (self.W * 0.5 - au) * math.tan(math.radians(self.roof_pitch))
        else:
            z = self.h_e
        return min(z, self.H)

    def v_end(self, u):
        return (self.z_d(u) - self.knee) / self.tanp

    def u_breaks(self):
        """Sorted u values where z_d has kinks within the recess (excluding +-W/2)."""
        out = []
        if self.roof == "gable":
            out.append(0.0)
            if self.u_clip is not None:
                out += [-self.u_clip, self.u_clip]
        return sorted(set(round(u, 9) for u in out))

    def s_breaks(self):
        u = [-(self.W * 0.5 + self.tc), -self.W * 0.5, self.W * 0.5, self.W * 0.5 + self.tc] + self.u_breaks()
        return [self.sc + x for x in u] + [self.win_s0, self.win_s1]

    def s_range(self):
        return (self.sc - self.W * 0.5 - self.tc, self.sc + self.W * 0.5 + self.tc)

    def top_at_s(self, s):
        return self.z_d(s - self.sc)

    def P(self, u, v):
        return (self.O[0] + self.a[0] * u + self.n[0] * v, self.O[1] + self.a[1] * u + self.n[1] * v)

    def recess_uv(self):
        """Recess outline (u, v), CCW-agnostic: front edge, cheek line, valley(s), cheek line."""
        hw = self.W * 0.5
        pts = [(-hw, 0.0), (hw, 0.0), (hw, self.depth)]
        for u in reversed(self.u_breaks()):
            pts.append((u, self.v_end(u)))
        pts.append((-hw, self.depth))
        return pts

    def notch_uv(self):
        """Hole cut into the room's main ceiling (recess + cheek strips), ordered along +u."""
        hw = self.W * 0.5
        tc = self.tc
        pts = [(-(hw + tc), 0.0), (-(hw + tc), self.depth), (-hw, self.depth)]
        for u in self.u_breaks():
            pts.append((u, self.v_end(u)))
        pts += [(hw, self.depth), (hw + tc, self.depth), (hw + tc, 0.0)]
        return pts


# --------------------------------------------------------------------------------------
# Spec
# --------------------------------------------------------------------------------------
class Spec:
    def __init__(self, data, path=None, sha256=None):
        self.data = data
        self.path = path
        self.sha256 = sha256
        self.warnings = []
        if int(data.get("schema_version", 0)) != 2:
            raise SpecError("schema_version must be 2 (got %r)" % data.get("schema_version"))
        st = data.get("storey") or {}
        self.default_height = float(st.get("default_ceiling_height", 2.6))
        self.slab = float(st.get("slab_thickness", 0.25))
        self.name = data.get("name", "apartment")
        self.rooms = [Room(r, self) for r in data["rooms"]]
        self.room_by_id = {r.id: r for r in self.rooms}
        self.walls = [Wall(w, self) for w in data["walls"]]
        self.wall_by_id = {w.id: w for w in self.walls}
        self.items = list(data.get("items", []))
        self.lights = list(data.get("lights", []))
        self.cameras = list(data.get("cameras", []))
        self.spawn = data.get("spawn")
        self._compute_joints()
        self._assign_rooms()
        for r in self.rooms:
            r.resolve_slopes(self)
        self._resolve_dormers()
        self._validate_openings()

    def warn(self, msg):
        self.warnings.append(msg)

    # ---------------------------------------------------------------- joints
    def _compute_joints(self):
        ends = []
        for w in self.walls:
            ends.append((w, "start", w.start))
            ends.append((w, "end", w.end))
        groups = []
        for e in ends:
            for g in groups:
                if G.dist(g[0][2], e[2]) < TOL:
                    g.append(e)
                    break
            else:
                groups.append([e])
        for g in groups:
            if len(g) == 1:
                continue
            # pair up: collinear continuations first, then the remaining two as a mitre
            used = set()
            for i in range(len(g)):
                for j in range(i + 1, len(g)):
                    if i in used or j in used:
                        continue
                    A, ea, P = g[i]
                    B, eb, _ = g[j]
                    a = A.d if ea == "start" else G.mul(A.d, -1)
                    b = B.d if eb == "start" else G.mul(B.d, -1)
                    if abs(G.cross(a, b)) < 1e-6 and G.dot(a, b) < 0:
                        A.joined[ea] = True
                        B.joined[eb] = True
                        used.update((i, j))
            rest = [k for k in range(len(g)) if k not in used]
            if len(rest) == 2:
                self._mitre(g[rest[0]], g[rest[1]])
            elif len(rest) > 2:
                self.warn("joint at %s has %d unpaired walls; flat caps used"
                          % (str(g[0][2]), len(rest)))
        # T-abutments: an endpoint lying on another wall's face
        for w in self.walls:
            for end, P in (("start", w.start), ("end", w.end)):
                if w.joined[end]:
                    continue
                for o in self.walls:
                    if o is w:
                        continue
                    s, nl = o.project(P)
                    if -1e-3 <= s <= o.L + 1e-3 and abs(abs(nl) - o.t * 0.5) < 2e-3:
                        w.abuts[end] = o.id
                        break

    def _mitre(self, ea, eb):
        A, enda, P = ea
        B, endb, _ = eb
        a = A.d if enda == "start" else G.mul(A.d, -1)
        b = B.d if endb == "start" else G.mul(B.d, -1)
        cr = G.cross(a, b)
        if abs(cr) < 1e-9:
            return
        na = G.left_normal(a)
        nb = G.left_normal(b)
        sa = 1.0 if cr > 0 else -1.0
        sb = -sa
        inner = G.line_intersect(G.add(P, G.mul(na, sa * A.t / 2)), a, G.add(P, G.mul(nb, sb * B.t / 2)), b)
        outer = G.line_intersect(G.add(P, G.mul(na, -sa * A.t / 2)), a, G.add(P, G.mul(nb, -sb * B.t / 2)), b)
        if inner is None or outer is None:
            return
        for (W, end, dirv, s_in) in ((A, enda, a, sa), (B, endb, b, sb)):
            lam_in = G.dot(G.sub(inner, P), dirv)
            lam_out = G.dot(G.sub(outer, P), dirv)
            if end == "start":
                inner_side = "L" if s_in > 0 else "R"
                s_inner, s_outer = lam_in, lam_out
                idx = 0
            else:
                inner_side = "L" if s_in < 0 else "R"
                s_inner, s_outer = W.L - lam_in, W.L - lam_out
                idx = 1
            outer_side = W.other(inner_side)
            W.s_ext[inner_side][idx] = s_inner
            W.s_ext[outer_side][idx] = s_outer
            W.joined[end] = True

    # ---------------------------------------------------------------- rooms per side
    def _assign_rooms(self):
        for w in self.walls:
            lo, hi = w.interior_range()
            for side in ("L", "R"):
                votes = {}
                for f in (0.2, 0.35, 0.5, 0.65, 0.8):
                    s = lo + (hi - lo) * f
                    p = w.point(s, w.sgn(side) * (w.t * 0.5 + 0.03))
                    for r in self.rooms:
                        if G.point_in_polygon(p, r.polygon):
                            votes[r.id] = votes.get(r.id, 0) + 1
                            break
                if votes:
                    rid = sorted(votes.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
                    w.room[side] = rid
                    if len(votes) > 1:
                        self.warn("wall %s side %s bounds several rooms %s; using %s"
                                  % (w.id, side, sorted(votes), rid))
            for side in ("L", "R"):
                raw = w.finish_raw[side]
                rid = w.room[side]
                if raw:
                    w.finish[side] = raw
                elif rid:
                    w.finish[side] = self.room_by_id[rid].wall_finish
                else:
                    w.finish[side] = "exterior"

    # ---------------------------------------------------------------- dormers
    def _resolve_dormers(self):
        for w in self.walls:
            for o in w.openings:
                if o.type != "dormer":
                    continue
                found = None
                for side in ("L", "R"):
                    rid = w.room[side]
                    if not rid:
                        continue
                    r = self.room_by_id[rid]
                    for sl in r.slopes:
                        if sl.wall is w:
                            found = (r, sl)
                if found is None:
                    self.warn("dormer %s: host wall %s carries no ceiling slope; built as a window" % (o.id, w.id))
                    continue
                r, sl = found
                o.dormer = Dormer(o, r, sl, self)
                r.dormers.append(o.dormer)

    def _validate_openings(self):
        for w in self.walls:
            lo, hi = w.interior_range()
            for o in w.openings:
                if o.s0 < lo + 0.02 or o.s1 > hi - 0.02:
                    self.warn("opening %s on %s runs into the wall end zone (%.3f..%.3f vs %.3f..%.3f)"
                              % (o.id, w.id, o.s0, o.s1, lo, hi))
            for a, b in zip(w.openings, w.openings[1:]):
                if b.s0 < a.s1 + 0.05:
                    self.warn("openings %s and %s on %s overlap or nearly touch" % (a.id, b.id, w.id))

    # ---------------------------------------------------------------- helpers
    def room_at(self, x, y):
        for r in self.rooms:
            if G.point_in_polygon((x, y), r.polygon):
                return r
        return None

    def top_room(self, wall, side):
        """Room whose ceiling governs the top of `wall` on `side`."""
        rid = wall.room[side] or wall.room[wall.other(side)]
        return self.room_by_id.get(rid) if rid else None

    def bbox(self):
        xs, ys = [], []
        for w in self.walls:
            for side in ("L", "R"):
                for s in w.s_ext[side]:
                    p = w.face_point(side, s)
                    xs.append(p[0])
                    ys.append(p[1])
        for r in self.rooms:
            xs += [p[0] for p in r.polygon]
            ys += [p[1] for p in r.polygon]
        zmax = max([r.height for r in self.rooms] + [self.default_height])
        return (min(xs), min(ys), -self.slab, max(xs), max(ys), zmax + 0.5)

    def edge_wall(self, room, i):
        """(wall, side, s_a, s_b) covering polygon edge i of `room` (s at the edge endpoints)."""
        a = room.polygon[i]
        b = room.polygon[(i + 1) % len(room.polygon)]
        mid = G.mul(G.add(a, b), 0.5)
        best = None
        for w in self.walls:
            for side in ("L", "R"):
                if w.room[side] != room.id:
                    continue
                s, nl = w.project(mid)
                if abs(nl - w.sgn(side) * w.t * 0.5) > 0.012:
                    continue
                lo, hi = w.s_ext[side]
                if lo - 0.012 <= s <= hi + 0.012:
                    sa, _ = w.project(a)
                    sb, _ = w.project(b)
                    cand = (w, side, sa, sb)
                    if best is None:
                        best = cand
        return best


def load_spec(path):
    with open(path, "rb") as f:
        raw = f.read()
    data = json.loads(raw.decode("utf-8"))
    return Spec(data, os.path.abspath(path), hashlib.sha256(raw).hexdigest())
