"""Pure-python 2D geometry helpers (no bpy, importable by plain python3 for tests)."""
import math

EPS = 1e-9


def add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def mul(a, s):
    return (a[0] * s, a[1] * s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def length(a):
    return math.hypot(a[0], a[1])


def normalize(a):
    n = length(a)
    if n < EPS:
        raise ValueError("cannot normalize zero-length vector")
    return (a[0] / n, a[1] / n)


def left_normal(d):
    """Unit normal on the LEFT when walking along d."""
    return (-d[1], d[0])


def dist(a, b):
    return length(sub(a, b))


def line_intersect(p, d, q, e):
    """Intersection of lines p + l*d and q + m*e; None if parallel."""
    den = cross(d, e)
    if abs(den) < 1e-12:
        return None
    w = sub(q, p)
    lam = cross(w, e) / den
    return add(p, mul(d, lam))


def polygon_area(poly):
    """Signed area (CCW positive)."""
    a = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        a += x0 * y1 - x1 * y0
    return 0.5 * a


def polygon_centroid(poly):
    a = polygon_area(poly)
    if abs(a) < EPS:
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        return (sum(xs) / len(xs), sum(ys) / len(ys))
    cx = cy = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        c = x0 * y1 - x1 * y0
        cx += (x0 + x1) * c
        cy += (y0 + y1) * c
    return (cx / (6.0 * a), cy / (6.0 * a))


def point_in_polygon(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            xint = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < xint:
                inside = not inside
        j = i
    return inside


def dist_point_segment(p, a, b):
    ab = sub(b, a)
    l2 = dot(ab, ab)
    if l2 < EPS:
        return dist(p, a), 0.0
    t = max(0.0, min(1.0, dot(sub(p, a), ab) / l2))
    proj = add(a, mul(ab, t))
    return dist(p, proj), t


def remove_collinear(poly, tol=1e-7, closed=True):
    """Drop duplicate and collinear vertices."""
    pts = []
    for p in poly:
        if not pts or dist(p, pts[-1]) > tol:
            pts.append(p)
    if closed and len(pts) > 1 and dist(pts[0], pts[-1]) <= tol:
        pts.pop()
    changed = True
    while changed and len(pts) > 3:
        changed = False
        n = len(pts)
        rng = range(n) if closed else range(1, n - 1)
        for i in rng:
            a = pts[i - 1]
            b = pts[i]
            c = pts[(i + 1) % n]
            if abs(cross(sub(b, a), sub(c, b))) < tol and dot(sub(b, a), sub(c, b)) > 0:
                pts.pop(i)
                changed = True
                break
    return pts


def offset_polygon_inward(poly, offsets):
    """Offset a CCW polygon inward; offsets[i] applies to edge i (poly[i] -> poly[i+1]).

    Returns the vertex list of the offset polygon (miter joins)."""
    n = len(poly)
    lines = []
    for i in range(n):
        a = poly[i]
        b = poly[(i + 1) % n]
        d = normalize(sub(b, a))
        nin = left_normal(d)  # CCW polygon: interior is on the left
        lines.append((add(a, mul(nin, offsets[i])), d))
    out = []
    for i in range(n):
        p0, d0 = lines[i - 1]
        p1, d1 = lines[i]
        x = line_intersect(p0, d0, p1, d1)
        if x is None:
            x = p1
        out.append(x)
    return out


def ensure_ccw(poly):
    return list(poly) if polygon_area(poly) >= 0 else list(reversed(poly))
