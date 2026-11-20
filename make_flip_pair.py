#!/usr/bin/env python3
"""A 5-6 scutoid that fits flipped copies of itself: two (as in Wikipedia's
picture) or four round one junction.

Top: a nearly regular hexagon. Half way down, its left edge (P-Q) shrinks to
a point M and the two corners become one, P2, so the bottom is a pentagon;
the side face that P-Q was is the scutoid's triangle (P, Q, M).

Four copies meet round M, one in each quarter, each the first turned half
a turn about one of three axes at right angles through M:

  A  the piece                       hexagon on top, triangle at the top
  B  turned about the upright        shares A's triangle
  C  turned about the line M-V       shares A's bent face (V, P, M, P2)
  D  turned about the line M-W       shares A's other bent face (W, Q, M, P2)

For that the upright edges V and W sit on lines through M at right angles
(45 degrees either side of the x axis), P2 is P mirrored across M-V (and Q
across M-W), and Q = -P. C and D share their triangle at the bottom, B and
C, B and D their bent faces. Any two that share a face also fit as a pair.

Needs make_scutoids.py beside it.
"""
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from make_scutoids import check_closed, volume, write_stl, shrink, recentre  # noqa: E402

R = 15.0      # hexagon size (mm): its upright edges are R, the slanted ~0.99 R
H = 40.0      # height (mm)
GAP = 0.15    # clearance per side (mm)

HALF = R / 2          # half the triangle's top edge
DIAG = 0.9 * R        # V and W are (DIAG, +-DIAG): 45 degrees from M
P, Q = (0.0, HALF), (0.0, -HALF)
V, W = (DIAG, DIAG), (DIAG, -DIAG)
V30, V330 = (2 * DIAG, HALF), (2 * DIAG, -HALF)
CENTRE = (DIAG, 0.0)
M = (0.0, 0.0)
U = (math.sqrt(0.5), math.sqrt(0.5))   # the line M-V: C's turning axis


def mirror(p):
    d = p[0] * U[0] + p[1] * U[1]
    return (2 * d * U[0] - p[0], 2 * d * U[1] - p[1])


P2 = mirror(P)


def t(p): return (p[0], p[1], H)
def b(p): return (p[0], p[1], 0.0)
def j(p): return (p[0], p[1], H / 2)


def quad(p0, p1):
    return [(b(p0), b(p1), t(p1)), (b(p0), t(p1), t(p0))]


def piece():
    top = [V30, V, P, Q, W, V330]
    bot = [V30, V, P2, W, V330]
    tris = quad(V30, V)
    # the bent face shared with the flipped copy (symmetric triangulation)
    tris += [(b(V), b(P2), j(M)), (b(V), j(M), t(V)), (j(M), t(P), t(V))]
    tris += [(j(M), t(Q), t(P))]                         # the triangle
    tris += [(b(P2), b(W), j(M)), (b(W), t(W), j(M)), (t(W), t(Q), j(M))]
    tris += quad(W, V330) + quad(V330, V30)
    for i in range(1, len(top) - 1):
        tris.append((t(top[0]), t(top[i]), t(top[i + 1])))
    for i in range(1, len(bot) - 1):
        tris.append((b(bot[0]), b(bot[i + 1]), b(bot[i])))
    return tris


def flip(p):
    """180 degrees about the horizontal line through M along U (A -> C)."""
    q = mirror(p[:2])
    return (q[0], q[1], H - p[2])


def turn_upright(p):
    """180 degrees about the upright through M (A -> B, C -> D)."""
    return (-p[0], -p[1], p[2])


def four():
    """A, B, C, D round the junction (rotations, so windings stay outward)."""
    a = piece()
    c = [tuple(flip(p) for p in tri) for tri in a]
    b = [tuple(turn_upright(p) for p in tri) for tri in a]
    d = [tuple(turn_upright(p) for p in tri) for tri in c]
    return {"A": a, "B": b, "C": c, "D": d}


def inside(pt, tris):
    """Ray-cast parity along a slightly skewed direction."""
    d = (1.0, 0.0123, 0.0071)
    n = 0
    for p0, p1, p2 in tris:
        e1 = [p1[i] - p0[i] for i in range(3)]
        e2 = [p2[i] - p0[i] for i in range(3)]
        h = (d[1] * e2[2] - d[2] * e2[1], d[2] * e2[0] - d[0] * e2[2], d[0] * e2[1] - d[1] * e2[0])
        a = sum(e1[i] * h[i] for i in range(3))
        if abs(a) < 1e-12:
            continue
        f = 1 / a
        s = [pt[i] - p0[i] for i in range(3)]
        u = f * sum(s[i] * h[i] for i in range(3))
        if u < 0 or u > 1:
            continue
        q = (s[1] * e1[2] - s[2] * e1[1], s[2] * e1[0] - s[0] * e1[2], s[0] * e1[1] - s[1] * e1[0])
        v = f * sum(d[i] * q[i] for i in range(3))
        if v < 0 or u + v > 1:
            continue
        if f * sum(e2[i] * q[i] for i in range(3)) > 0:
            n += 1
    return n % 2 == 1


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent
    out.mkdir(parents=True, exist_ok=True)
    pieces = four()
    for name, tris in pieces.items():
        check_closed(tris, name)
        assert volume(tris) > 0
    print(f"volume {volume(pieces['A']):.1f} each")
    # faces each pair shares: the triangles (1) or a bent face (3)
    key = lambda tri: frozenset(tuple(round(x, 6) for x in p) for p in tri)
    want = {"AB": 1, "CD": 1, "AC": 3, "AD": 3, "BC": 3, "BD": 3}
    for pair, n in want.items():
        got = len({key(x) for x in pieces[pair[0]]} & {key(x) for x in pieces[pair[1]]})
        print(f"{pair} share {got} triangles")
        assert got == n, pair
    # no two overlap, and round the junction there's no gap: random points
    random.seed(1)
    reach = 2 * DIAG + 1
    both = gaps = near = 0
    for _ in range(40000):
        pt = (random.uniform(-reach, reach), random.uniform(-reach, reach), random.uniform(0, H))
        ins = [inside(pt, tris) for tris in pieces.values()]
        both += sum(ins) > 1
        if math.hypot(pt[0], pt[1]) < HALF:
            near += 1
            gaps += sum(ins) == 0
    print(f"samples in two pieces: {both}; within {HALF} mm of the junction: {near}, in none: {gaps}")
    assert both == 0 and gaps == 0
    part = recentre(shrink(pieces["A"], CENTRE, GAP), CENTRE)
    check_closed(part, "part")
    write_stl(out / "scutoid_5-6_flip.stl", part, "scutoid_5-6_flip")
    print(f"wrote {out / 'scutoid_5-6_flip.stl'}")
    return pieces


if __name__ == "__main__":
    main()
