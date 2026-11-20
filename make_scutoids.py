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
axis), Q = -P, and P2 is P mirrored across M-V. Then each bent face (the
face between a 5-6 and a 6-7 in a group) maps onto itself turned half a
turn about the horizontal line from M to its upright edge, so a turned-over
copy of either piece fits it from the other side, and four meet round a
junction: two upright, two turned over.

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
def j(p): return (p[0], p[1], H / 2)


def quad(p0, p1):
    return [(b(p0), b(p1), t(p1)), (b(p0), t(p1), t(p0))]


def caps(top, bot):
    out = []
    for i in range(1, len(top) - 1):
        out.append((t(top[0]), t(top[i]), t(top[i + 1])))
    for i in range(1, len(bot) - 1):
        out.append((b(bot[0]), b(bot[i + 1]), b(bot[i])))
    return out


def piece_5_6():
    """Hexagon on top, pentagon underneath."""
    v30, v330 = (2 * DIAG, HALF), (2 * DIAG, -HALF)
    tris = quad(v30, V)
    # bent face with C (symmetric triangulation, so it matches when flipped)
    tris += [(b(V), b(P2), j(M)), (b(V), j(M), t(V)), (j(M), t(P), t(V))]
    tris += [(j(M), t(Q), t(P))]                         # the triangle
    tris += [(b(P2), b(W), j(M)), (b(W), t(W), j(M)), (t(W), t(Q), j(M))]
    tris += quad(W, v330) + quad(v330, v30)
    return tris + caps([v30, V, P, Q, W, v330], [v30, V, P2, W, v330])


def piece_6_7():
    """The cell above the 5-6: hexagon on top, heptagon underneath."""
    top_r = (DIAG, DIAG + 2 * HALF)
    top_t = (0.0, 2 * DIAG + HALF)
    top_l = (-DIAG, DIAG + 2 * HALF)
    # bent face with A (the 5-6), its triangles reversed
    tris = [(b(V), j(M), b(P2)), (b(V), t(V), j(M)), (j(M), t(V), t(P))]
    tris += quad(V, top_r) + quad(top_r, top_t) + quad(top_t, top_l) + quad(top_l, NW)
    # bent face with B (the other 5-6)
    tris += [(b(Q2), j(M), b(NW)), (b(NW), j(M), t(NW)), (t(NW), j(M), t(P))]
    tris += [(b(Q2), b(P2), j(M))]                       # the triangle
    return tris + caps([P, V, top_r, top_t, top_l, NW], [Q2, P2, V, top_r, top_t, top_l, NW])


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


def sample(pieces, box, n, seed, near=None):
    """Random points in two pieces, and (within `near` of the upright through
    the origin, if given) in none."""
    random.seed(seed)
    both = gaps = 0
    for _ in range(n):
        pt = (random.uniform(-box[0], box[0]), random.uniform(-box[1], box[1]), random.uniform(0, H))
        k = sum(inside(pt, tr) for tr in pieces)
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
    assert shared(group[0], group[2]) == 3 and shared(group[0], group[1]) == 1
    assert shared(group[2], group[3]) == 1
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
        assert counts == [1, 1, 3, 3, 3, 3]
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
