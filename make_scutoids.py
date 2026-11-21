#!/usr/bin/env python3
"""A 5-6 and a 6-7 scutoid for 3D printing, which together do everything:

  - fill a layer: groups of four (two 5-6, two 6-7 round one junction), each
    group upright or turned over as a block; stack layers hexagon on
    hexagon, pentagon/heptagon on pentagon/heptagon,
  - two or four 5-6 fitted together, flipped (as in Wikipedia's picture),
  - two or four 6-7 fitted together the same way.

  python3 make_scutoids.py [OUT_DIR]   writes scutoid_5-6.stl, scutoid_6-7.stl,
                                       and copies them into viewer.html there

Shape. The top of a layer is a honeycomb of one slightly squashed hexagon.
In each group of four, the edge between the two 5-6 pieces (P-Q) shrinks
half way down to a point M, the junction, and an edge between the two 6-7
pieces (P2-Q2) grows out of it: the 5-6s go from hexagon to pentagon, the
6-7s from hexagon to heptagon, and each has one triangular face (P, Q, M or
Q2, P2, M) — the scutoid's mark.

  5-6 (A)  hexagon P, Q, W, (2D, -h), (2D, h), V      with M at (0, 0)
  6-7 (C)  the cell above A, sharing P-V; D = DIAG, h = HALF

Why flipped copies fit: the upright edges V and W either side of the
junction sit on lines through M at right angles (45 degrees off the x
axis), Q = -P, and P2 is P mirrored across M-V. Then each non-planar face
(the face between a 5-6 and a 6-7 in a group; see below) maps onto itself
turned half a turn about the horizontal line from M to its upright edge, so
a turned-over copy of either piece fits it from the other side, and four
meet round a junction: two upright, two turned over.

Flat space can't be filled with 5-6 scutoids alone: a flat tiling's cells
average exactly six sides, so pentagons need heptagons to balance them.
"""
import base64
import json
import math
import random
import re
import struct
import sys
from pathlib import Path

R = 15.0      # size (mm): the hexagon's upright edges are R, the slanted ~0.99 R
H = 40.0      # height (mm)
GAP = 0.15    # clearance moved in per side (mm), so printed pieces fit

HALF = R / 2          # half the triangle's top edge
DIAG = 0.9 * R        # V and W are (DIAG, +-DIAG): 45 degrees from M
P, Q = (0.0, HALF), (0.0, -HALF)
V, W = (DIAG, DIAG), (DIAG, -DIAG)
NW = (-DIAG, DIAG)                    # = -W: the other 5-6's corner
M = (0.0, 0.0)
U = (math.sqrt(0.5), math.sqrt(0.5))  # the line M-V


def mirror(p):
    """Mirror across the line M-V."""
    d = p[0] * U[0] + p[1] * U[1]
    return (2 * d * U[0] - p[0], 2 * d * U[1] - p[1])


P2 = mirror(P)        # = (HALF, 0)
Q2 = (-P2[0], -P2[1])
A_CENTRE = (DIAG, 0.0)
C_CENTRE = (0.0, HALF + DIAG)


def t(p): return (p[0], p[1], H)
def b(p): return (p[0], p[1], 0.0)


def quad(p0, p1):
    return [(b(p0), b(p1), t(p1)), (b(p0), t(p1), t(p0))]


def lerp(p, q, s):
    return tuple(p[i] + (q[i] - p[i]) * s for i in range(3))


def flip3(p):
    """Half a turn about the horizontal line through M along M-V."""
    q = mirror(p[:2])
    return (q[0], q[1], H - p[2])


def mirror_y(p): return (p[0], -p[1], p[2])
def mirror_x(p): return (-p[0], p[1], p[2])


# --- the non-planar faces ---------------------------------------------------
#
# Each non-planar face is a pentagon: the top edge P-V, the upright edge at
# V, the bottom edge P2-V, and its fourth side the triangle's edge P-M with,
# below the junction M, the other piece's triangle edge M-P2. Its five
# corners aren't in a plane, as the faces of the scutoids in the paper
# aren't: here like a soap film stretched over that outline (the grid relaxed
# until each point is the average of its neighbours), smooth everywhere inside.
# It's worked out above the junction and turned half a turn about M-V for
# below it, so it maps onto itself exactly: the line M-V lies in it, and a
# turned-over piece fits it from the other side.

ACROSS = 12      # grid steps across a non-planar face (P side to V)
UP = 16          # grid steps up it (even: the junction's on a grid line)


def _face_grid():
    n, m = ACROSS, UP
    tP, tV, bP2, bV = t(P), t(V), b(P2), b(V)
    Mj = (M[0], M[1], H / 2)

    def left(jj):
        if jj >= m // 2:
            return lerp(Mj, tP, (jj - m // 2) / (m // 2))
        return lerp(Mj, bP2, (m // 2 - jj) / (m // 2))

    def right(jj):
        return (V[0], V[1], H * jj / m)

    g = [[lerp(left(jj), right(jj), i / n) for jj in range(m + 1)] for i in range(n + 1)]
    for i in range(n + 1):
        g[i][m] = lerp(tP, tV, i / n)
        g[i][0] = lerp(bP2, bV, i / n)
    for _ in range(20000):
        moved_most = 0.0
        for i in range(1, n):
            for jj in range(1, m):
                a, c, d, e = g[i - 1][jj], g[i + 1][jj], g[i][jj - 1], g[i][jj + 1]
                p = tuple((a[k] + c[k] + d[k] + e[k]) / 4 for k in range(3))
                moved_most = max(moved_most, max(abs(p[k] - g[i][jj][k]) for k in range(3)))
                g[i][jj] = p
        if moved_most < 1e-10:
            break
    # exactly symmetric: the junction's row on the line M-V, below it the top
    # half turned over
    for i in range(n + 1):
        g[i][m // 2] = lerp(Mj, right(m // 2), i / n)
        for jj in range(m // 2):
            g[i][jj] = flip3(g[i][m - jj])
    return g


GRID = _face_grid()


def non_planar_face():
    """The 5-6's non-planar face with the 6-7 above it (C), facing out of the 5-6.
    Each cell's diagonal is mirrored about the junction's row, so the
    triangles map onto themselves when turned over too."""
    g, n, m = GRID, ACROSS, UP
    out = []
    for i in range(n):
        for jj in range(m):
            a, bb, c, d = g[i][jj], g[i + 1][jj], g[i + 1][jj + 1], g[i][jj + 1]
            if jj >= m // 2:
                out += [(a, d, c), (a, c, bb)]
            else:
                out += [(a, d, bb), (bb, d, c)]
    return out


def reverse(tris):
    return [(p0, p2, p1) for p0, p1, p2 in tris]


def facing(tris, centre):
    """Each (flat-face) triangle turned to face away from `centre`."""
    out = []
    for tri in tris:
        n = cross(sub(tri[1], tri[0]), sub(tri[2], tri[0]))
        mid = tuple(sum(p[k] for p in tri) / 3 for k in range(3))
        out.append(tri if sum(n[k] * (mid[k] - centre[k]) for k in range(3)) > 0
                   else (tri[0], tri[2], tri[1]))
    return out


def fan(poly):
    return [(poly[0], poly[i], poly[i + 1]) for i in range(1, len(poly) - 1)]


def scutoid_triangle(left, right):
    """The triangle face between two pieces of a pair (5-6: P, Q, M; 6-7: P2,
    Q2, M), cut at the non-planar faces' rows so no edge has a corner in its middle;
    `left`, `right` run from M out to its wide edge. Symmetric under half a
    turn about the upright, so the pair's triangles are the same."""
    mid = [((l[0] + r[0]) / 2, (l[1] + r[1]) / 2, l[2]) for l, r in zip(left, right)]
    out = [(left[0], left[1], mid[1]), (right[0], mid[1], right[1])]
    for k in range(1, len(left) - 1):
        out += [(left[k], mid[k], mid[k + 1]), (left[k], mid[k + 1], left[k + 1]),
                (right[k], mid[k + 1], mid[k]), (right[k], right[k + 1], mid[k + 1])]
    return out


def upright_side(edge, c0, c1):
    """A plain face from an upright edge cut at the non-planar face's rows (`edge`,
    bottom to top) to the straight upright c0-c1 (bottom, top)."""
    return fan([c0, c1] + edge[::-1])


def piece_5_6():
    """Hexagon on top, pentagon underneath."""
    g, n, m = GRID, ACROSS, UP
    centre = (A_CENTRE[0], A_CENTRE[1], H / 2)
    v30, v330 = (2 * DIAG, HALF), (2 * DIAG, -HALF)
    face_v = non_planar_face()                           # with C
    face_w = reverse(moved(face_v, mirror_y))            # with D
    tri = scutoid_triangle([g[0][k] for k in range(m // 2, m + 1)],
                           [mirror_y(g[0][k]) for k in range(m // 2, m + 1)])
    v_edge = [g[n][k] for k in range(m + 1)]
    w_edge = [mirror_y(p) for p in v_edge]
    flat = (upright_side(v_edge, b(v30), t(v30)) + upright_side(w_edge, b(v330), t(v330))
            + quad(v330, v30) + tri)
    top = ([t(v30)] + [g[i][m] for i in range(n, -1, -1)] + [(0.0, 0.0, H)]
           + [mirror_y(g[i][m]) for i in range(n + 1)] + [t(v330)])
    bottom = ([b(v30)] + [g[i][0] for i in range(n, 0, -1)]
              + [mirror_y(g[i][0]) for i in range(n + 1)] + [b(v330)])
    flat += fan(top) + fan(bottom)
    return face_v + face_w + facing(flat, centre)


def piece_6_7():
    """The cell above the 5-6: hexagon on top, heptagon underneath."""
    g, n, m = GRID, ACROSS, UP
    centre = (C_CENTRE[0], C_CENTRE[1], H / 2)
    top_r = (DIAG, DIAG + 2 * HALF)
    top_t = (0.0, 2 * DIAG + HALF)
    top_l = (-DIAG, DIAG + 2 * HALF)
    face_a = reverse(non_planar_face())                  # with A (the 5-6)
    face_b = moved(non_planar_face(), mirror_x)          # with B (the other 5-6)
    tri = scutoid_triangle([g[0][k] for k in range(m // 2, -1, -1)],
                           [mirror_x(g[0][k]) for k in range(m // 2, -1, -1)])
    v_edge = [g[n][k] for k in range(m + 1)]
    nw_edge = [mirror_x(p) for p in v_edge]
    flat = (upright_side(v_edge, b(top_r), t(top_r)) + upright_side(nw_edge, b(top_l), t(top_l))
            + quad(top_r, top_t) + quad(top_t, top_l) + tri)
    top = ([t(top_t), t(top_r)] + [g[i][m] for i in range(n, -1, -1)]
           + [mirror_x(g[i][m]) for i in range(1, n + 1)] + [t(top_l)])
    bottom = ([b(top_t), b(top_r)] + [g[i][0] for i in range(n, -1, -1)] + [(0.0, 0.0, 0.0)]
              + [mirror_x(g[i][0]) for i in range(n + 1)] + [b(top_l)])
    flat += fan(top) + fan(bottom)
    return face_a + face_b + facing(flat, centre)


# --- moves -------------------------------------------------------------------

def flip(p):
    """Half a turn about the horizontal line through M along M-V."""
    q = mirror(p[:2])
    return (q[0], q[1], H - p[2])


def turn_upright(p):
    """Half a turn about the upright through M."""
    return (-p[0], -p[1], p[2])


def flip_group(p):
    """Turn a whole group of four over: half a turn about its long (y) axis."""
    return (-p[0], p[1], H - p[2])


def moved(tris, f):
    return [tuple(f(p) for p in tri) for tri in tris]


def shift(d):
    return lambda p: (p[0] + d[0], p[1] + d[1], p[2])


# --- checks ------------------------------------------------------------------

def sub(a, c):
    return (a[0] - c[0], a[1] - c[1], a[2] - c[2])


def cross(a, c):
    return (a[1] * c[2] - a[2] * c[1], a[2] * c[0] - a[0] * c[2], a[0] * c[1] - a[1] * c[0])


def volume(tris):
    v = 0.0
    for p0, p1, p2 in tris:
        v += (p0[0] * (p1[1] * p2[2] - p1[2] * p2[1])
              - p0[1] * (p1[0] * p2[2] - p1[2] * p2[0])
              + p0[2] * (p1[0] * p2[1] - p1[1] * p2[0])) / 6
    return v


def check_closed(tris, name):
    key = lambda p: tuple(round(x, 6) for x in p)  # noqa: E731
    edges = {}
    for tri in tris:
        for i in range(3):
            e = (key(tri[i]), key(tri[(i + 1) % 3]))
            edges[e] = edges.get(e, 0) + 1
    bad = [e for e, n in edges.items() if n != 1 or edges.get((e[1], e[0]), 0) != 1]
    if bad:
        sys.exit(f"{name}: not watertight/consistent, {len(bad)} bad edges")


def inside(pt, tris):
    """Ray-cast parity along a slightly skewed direction."""
    d = (1.0, 0.0123, 0.0071)
    n = 0
    for p0, p1, p2 in tris:
        e1 = sub(p1, p0)
        e2 = sub(p2, p0)
        h = cross(d, e2)
        a = sum(e1[i] * h[i] for i in range(3))
        if abs(a) < 1e-12:
            continue
        f = 1 / a
        s = sub(pt, p0)
        u = f * sum(s[i] * h[i] for i in range(3))
        if u < 0 or u > 1:
            continue
        q = cross(s, e1)
        v = f * sum(d[i] * q[i] for i in range(3))
        if v < 0 or u + v > 1:
            continue
        if f * sum(e2[i] * q[i] for i in range(3)) > 0:
            n += 1
    return n % 2 == 1


KEY = lambda tri: frozenset(tuple(round(x, 6) for x in p) for p in tri)  # noqa: E731


def shared(x, y):
    return len({KEY(a) for a in x} & {KEY(a) for a in y})


class Solid:
    """A piece's triangles bucketed by y and z, so a ray along x (`inside`)
    only tests the few it might cross."""
    CELL = 2.0

    def __init__(self, tris):
        self.buckets = {}
        self.lo = tuple(min(p[k] for tri in tris for p in tri) for k in range(3))
        self.hi = tuple(max(p[k] for tri in tris for p in tri) for k in range(3))
        for tri in tris:
            # the ray is skewed a little, so widen by what it drifts across a piece
            y0, y1 = min(p[1] for p in tri) - 1, max(p[1] for p in tri) + 1
            z0, z1 = min(p[2] for p in tri) - 1, max(p[2] for p in tri) + 1
            for i in range(math.floor(y0 / self.CELL), math.floor(y1 / self.CELL) + 1):
                for k in range(math.floor(z0 / self.CELL), math.floor(z1 / self.CELL) + 1):
                    self.buckets.setdefault((i, k), []).append(tri)

    def contains(self, pt):
        if any(pt[k] < self.lo[k] or pt[k] > self.hi[k] for k in range(3)):
            return False
        key = (math.floor(pt[1] / self.CELL), math.floor(pt[2] / self.CELL))
        return inside(pt, self.buckets.get(key, ()))


def sample(pieces, box, n, seed, near=None):
    """Random points in two pieces, and (within `near` of the upright through
    the origin, if given) in none."""
    random.seed(seed)
    solids = [Solid(tr) for tr in pieces]
    both = gaps = 0
    for _ in range(n):
        pt = (random.uniform(-box[0], box[0]), random.uniform(-box[1], box[1]), random.uniform(0, H))
        k = sum(s.contains(pt) for s in solids)
        both += k > 1
        if near is None or math.hypot(pt[0], pt[1]) < near:
            gaps += k == 0
    return both, gaps


# --- output ------------------------------------------------------------------

def shrink(tris, centre, gap):
    """Pull every vertex `gap` towards the piece's own axis (clearance)."""
    def mv(p):
        dx, dy = p[0] - centre[0], p[1] - centre[1]
        d = math.hypot(dx, dy)
        k = max(d - gap, 0.0) / d if d > 0 else 1.0
        return (centre[0] + dx * k, centre[1] + dy * k, p[2])
    return [tuple(mv(p) for p in tri) for tri in tris]


def recentre(tris, centre):
    return [tuple((p[0] - centre[0], p[1] - centre[1], p[2]) for p in tri) for tri in tris]


def write_stl(path, tris, header):
    """Binary STL. The 80-byte header holds `header` (ASCII, at most 80)."""
    data = header.encode("ascii")
    assert len(data) <= 80, header
    with open(path, "wb") as f:
        f.write(data.ljust(80, b" "))
        f.write(struct.pack("<I", len(tris)))
        for p0, p1, p2 in tris:
            n = cross(sub(p1, p0), sub(p2, p0))
            ln = math.sqrt(sum(x * x for x in n)) or 1.0
            f.write(struct.pack("<3f", *(x / ln for x in n)))
            for p in (p0, p1, p2):
                f.write(struct.pack("<3f", *p))
            f.write(b"\0\0")


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent
    out.mkdir(parents=True, exist_ok=True)
    f = piece_5_6()
    g = piece_6_7()
    check_closed(f, "5-6")
    check_closed(g, "6-7")
    assert volume(f) > 0 and volume(g) > 0
    print(f"volumes: 5-6 {volume(f):.1f}, 6-7 {volume(g):.1f}")

    # a layer: groups of four, some turned over, round a middle group
    group = [f, moved(f, turn_upright), g, moved(g, turn_upright)]
    # triangles in a non-planar face, and in a scutoid triangle (cut into strips)
    face, tri = 2 * ACROSS * UP, 2 + 4 * (UP // 2 - 1)
    assert shared(group[0], group[2]) == face and shared(group[0], group[1]) == tri
    assert shared(group[2], group[3]) == tri
    a = (DIAG, DIAG + HALF)
    steps = [(0, 0), (1, 0), (0, 1), (-1, 0), (0, -1), (1, -1), (-1, 1)]
    for flipped in (set(), {0}, {0, 2, 4, 6}):
        layer = []
        for k, (i, jj) in enumerate(steps):
            d = (2 * a[0] * (i - jj), 2 * a[1] * (i + jj))
            for piece in group:
                piece = moved(piece, flip_group) if k in flipped else piece
                layer.append(moved(piece, shift(d)))
        both, gaps = sample(layer, (2 * DIAG + 2, 2 * DIAG + 2 * HALF + 2), 20000, 1)
        print(f"layer, groups {sorted(flipped)} turned over: in two pieces {both}, in none {gaps}")
        assert both == 0 and gaps == 0

    # four of one piece round a junction (any two neighbours make a pair)
    for name, piece in (("5-6", f), ("6-7", g)):
        turned = moved(piece, flip)
        four = [piece, moved(piece, turn_upright), turned, moved(turned, turn_upright)]
        counts = [shared(four[x], four[y]) for x, y in ((0, 1), (2, 3), (0, 2), (1, 3), (0, 3), (1, 2))]
        both, gaps = sample(four, (2 * DIAG + 2 * HALF, 2 * DIAG + 2 * HALF), 30000, 2, near=HALF)
        print(f"four {name}: shared triangles {counts}, in two pieces {both}, "
              f"near the junction in none {gaps}")
        assert counts == [tri, tri, face, face, face, face]
        assert both == 0 and gaps == 0

    for name, piece, centre in (("scutoid_5-6", f, A_CENTRE), ("scutoid_6-7", g, C_CENTRE)):
        part = recentre(shrink(piece, centre, GAP), centre)
        check_closed(part, name)
        # where the piece sits in its group of four (the junction at x = y = 0),
        # for viewer.html, which puts it back there
        header = f"{name} centre={centre[0]:g},{centre[1]:g}"
        write_stl(out / f"{name}.stl", part, header)
        print(f"wrote {out / (name + '.stl')}")
    embed_in_viewer(out)


def embed_in_viewer(out):
    """Copy the STLs into the viewer.html beside them (if there is one): a
    page opened from disk can't read the files next to it."""
    viewer = out / "viewer.html"
    if not viewer.exists():
        return
    stls = {name: base64.b64encode((out / name).read_bytes()).decode("ascii")
            for name in ("scutoid_5-6.stl", "scutoid_6-7.stl")}
    data = json.dumps(stls, indent=1)
    html = viewer.read_text()
    new, n = re.subn(r'(<script id="stls" type="application/json">\n).*?(\n</script>)',
                     lambda m: m.group(1) + data + m.group(2), html, flags=re.S)
    if n != 1:
        sys.exit(f"{viewer}: no <script id=\"stls\"> block to copy the STLs into")
    viewer.write_text(new)
    print(f"copied them into {viewer}")


if __name__ == "__main__":
    main()
