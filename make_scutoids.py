#!/usr/bin/env python3
"""Space-filling scutoids for 3D printing.

Top face of the slab: a regular honeycomb. Bottom face: the same honeycomb
after a T1 transition on one edge in every group of four cells (a rhombus of
cells A, B, C, D). Half way down, the edge A|B shrinks to a point and the edge
C|D grows out of it, so:

  A, B: hexagon on top, pentagon underneath, one triangular face  (5/6 scutoid)
  C, D: hexagon on top, heptagon underneath, one triangular face  (6/7 scutoid)

B is A turned 180 degrees, D is C turned 180 degrees, and every rhombus is a
translate of the first, so two STL files tile the slab. Each piece is mirror
symmetric, so flipping it upside down gives the same piece: the next layer is
the first one flipped, hexagons on hexagons, and the slabs stack. (In flat
space, scutoids with only 5- and 6-sided ends can't fill space alone: the
average cell of a flat tiling has exactly 6 sides, so pentagons need
heptagons to balance them.)
"""
import math
import struct
import sys
from pathlib import Path

R = 15.0          # honeycomb edge length (mm) = hexagon corner radius
H = 40.0          # piece height (mm)
ZJ = H / 2        # height of the junction (where the scutoid's triangle tips meet)
T = 0.35 * R      # half length of the new C|D edge on the bottom
GAP = 0.15        # clearance moved in per side (mm), so printed pieces fit

S = math.sqrt(3) / 2 * R
A_C = (S, 0.0)
C_C = (0.0, 1.5 * R)


def hexv(c, deg):
    a = math.radians(deg)
    return (c[0] + R * math.cos(a), c[1] + R * math.sin(a))


P = (0.0, 0.5 * R)    # top: cells A, B, C meet
Q = (0.0, -0.5 * R)   # top: cells A, B, D meet
P2 = (T, 0.0)         # bottom: A, C, D meet
Q2 = (-T, 0.0)        # bottom: B, C, D meet
M = (0.0, 0.0)        # junction, at z = ZJ


def piece_a():
    """Hexagon on top, pentagon underneath."""
    v30, v90, v270, v330 = (hexv(A_C, d) for d in (30, 90, 270, 330))
    top = [v30, v90, P, Q, v270, v330]
    bot = [v30, v90, P2, v270, v330]
    tris = []
    # lateral faces, walking round counter-clockwise from above
    tris += quad(v30, v90)
    # with C: X = v90, polyline P(top) -> M -> P2(bottom)
    tris += [(b(v90), b(P2), j(M)), (b(v90), j(M), t(v90)), (j(M), t(P), t(v90))]
    # with B: the scutoid triangle
    tris += [(j(M), t(Q), t(P))]
    # with D: X = v270, polyline Q(top) -> M -> P2(bottom)
    tris += [(b(P2), b(v270), j(M)), (b(v270), t(v270), j(M)), (t(v270), t(Q), j(M))]
    tris += quad(v270, v330)
    tris += quad(v330, v30)
    tris += caps(top, bot)
    return A_C, tris


def piece_c():
    """Hexagon on top, heptagon underneath."""
    v30, v90, v150, v210, v330 = (hexv(C_C, d) for d in (30, 90, 150, 210, 330))
    top = [v30, v90, v150, v210, P, v330]
    bot = [v30, v90, v150, v210, Q2, P2, v330]
    tris = []
    tris += quad(v30, v90)
    tris += quad(v90, v150)
    tris += quad(v150, v210)
    # with B: X = v210, polyline P(top) -> M -> Q2(bottom)
    tris += [(b(v210), b(Q2), j(M)), (b(v210), j(M), t(v210)), (j(M), t(P), t(v210))]
    # with D: the upside-down scutoid triangle
    tris += [(b(Q2), b(P2), j(M))]
    # with A: X = v330, polyline P(top) -> M -> P2(bottom)
    tris += [(b(P2), b(v330), j(M)), (b(v330), t(v330), j(M)), (t(v330), t(P), j(M))]
    tris += quad(v330, v30)
    tris += caps(top, bot)
    return C_C, tris


def t(p):
    return (p[0], p[1], H)


def b(p):
    return (p[0], p[1], 0.0)


def j(p):
    return (p[0], p[1], ZJ)


def quad(p0, p1):
    return [(b(p0), b(p1), t(p1)), (b(p0), t(p1), t(p0))]


def caps(top, bot):
    out = []
    for i in range(1, len(top) - 1):
        out.append((t(top[0]), t(top[i]), t(top[i + 1])))
    for i in range(1, len(bot) - 1):
        out.append((b(bot[0]), b(bot[i + 1]), b(bot[i])))
    return out


# --- checks and output -------------------------------------------------------

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
    key = lambda p: tuple(round(x, 6) for x in p)
    edges = {}
    for tri in tris:
        for i in range(3):
            e = (key(tri[i]), key(tri[(i + 1) % 3]))
            edges[e] = edges.get(e, 0) + 1
    bad = [e for e, n in edges.items() if n != 1 or edges.get((e[1], e[0]), 0) != 1]
    if bad:
        sys.exit(f"{name}: not watertight/consistent, {len(bad)} bad edges")


def shrink(tris, centre, gap):
    """Pull every vertex `gap` towards the cell's own axis (clearance)."""
    def mv(p):
        dx, dy = p[0] - centre[0], p[1] - centre[1]
        d = math.hypot(dx, dy)
        k = max(d - gap, 0.0) / d if d > 0 else 1.0
        return (centre[0] + dx * k, centre[1] + dy * k, p[2])
    return [tuple(mv(p) for p in tri) for tri in tris]


def recentre(tris, centre):
    return [tuple((p[0] - centre[0], p[1] - centre[1], p[2]) for p in tri) for tri in tris]


def write_stl(path, tris, name):
    with open(path, "wb") as f:
        f.write(name.encode().ljust(80, b" ")[:80])
        f.write(struct.pack("<I", len(tris)))
        for p0, p1, p2 in tris:
            n = cross(sub(p1, p0), sub(p2, p0))
            ln = math.sqrt(sum(x * x for x in n)) or 1.0
            f.write(struct.pack("<3f", *(x / ln for x in n)))
            for p in (p0, p1, p2):
                f.write(struct.pack("<3f", *p))
            f.write(b"\0\0")


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    a_c, a = piece_a()
    c_c, c = piece_c()
    check_closed(a, "A")
    check_closed(c, "C")
    va, vc = volume(a), volume(c)
    hex_area = 3 * math.sqrt(3) / 2 * R * R
    # A, B (= A turned), C, D (= C turned) fill one rhombus of 4 cells
    print(f"vol A {va:.1f}  vol C {vc:.1f}  2A+2C {2 * (va + vc):.1f}  "
          f"4 prisms {4 * hex_area * H:.1f}")
    assert va > 0 and vc > 0
    assert abs(2 * (va + vc) - 4 * hex_area * H) < 1e-6 * hex_area * H
    for name, centre, tris in (("scutoid_5-6", a_c, a), ("scutoid_6-7", c_c, c)):
        part = recentre(shrink(tris, centre, GAP), centre)
        check_closed(part, name)
        write_stl(out / f"{name}.stl", part, name)
        print(f"wrote {out / (name + '.stl')}  ({len(part)} triangles)")


if __name__ == "__main__":
    main()
