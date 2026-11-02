"""Parametric TPU throwing-hatchet blade cover + optional back strap.

Coordinates (model space, mm):
  X = depth from open back (0) toward cutting edge (+)
  Y = along the cutting edge (0 = lower/curved end, + = top of blade)
  Z = blade thickness, centered on 0
The exported 3MF flips the cover so the straight top edge sits on the bed
(cutting edge vertical) - the print orientation discussed.
"""
import numpy as np
import zipfile
from manifold3d import Manifold, CrossSection

IN = 25.4

# ---------------- parameters ----------------
POCKET_DEPTH = 2.5 * IN      # back opening -> cutting edge
POCKET_LEN = 4.25 * IN       # along cutting edge (covers 4" legal max)
BACK_THK = 0.5 * IN          # pocket thickness at the open back
EDGE_THK = 1.5               # pocket thickness at the edge slot
FACE_WALL = 2.5
EDGE_WALL = 4.0
CURVE_TOP = 42.0             # where the lower sweep meets the back (Y)
CURVE_BOTTOM_X = 30.0        # where the lower sweep meets the bottom (X)
CURVE_CTRL = (25.0, 21.0)    # quadratic Bezier control point for the sweep

NUB_POS = (9.0, CURVE_TOP + 7.0)  # nub center (X, Y) on each face
NUB_STEM_D, NUB_HEAD_D = 4.0, 6.0
NUB_STEM_H, NUB_CHAMFER_H, NUB_CAP_H = 1.4, 1.0, 0.8

STRAP_W, STRAP_T = 12.0, 2.0
STRAP_HOLE_D = 3.6
STRAP_FIXED_TO_ADJ = [100.0, 108.0, 116.0]  # hole-center spacings (handle wrap)
SEG = 64


def bezier(p0, c, p2, n=24):
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 2 * np.array(p0) + 2 * (1 - t) * t * np.array(c) + t ** 2 * np.array(p2)


def blade_profile():
    """Pocket outline in the XY plane (side profile)."""
    sweep = bezier((0.0, CURVE_TOP), CURVE_CTRL, (CURVE_BOTTOM_X, 0.0))
    pts = [(-2.0, POCKET_LEN), (-2.0, CURVE_TOP)]          # extend past back -> open
    pts += [tuple(p) for p in sweep]
    pts += [(POCKET_DEPTH, 0.0), (POCKET_DEPTH, POCKET_LEN)]
    return CrossSection([pts])


def wedge(back_half, edge_half, x_end, nose=None, y0=-50, y1=250):
    """Wedge prism: XZ cross-section extruded along Y."""
    xs = [(-5.0, -back_half), (POCKET_DEPTH, -edge_half)]
    if nose:
        xs += [(x_end, -nose), (x_end, nose)]
    else:
        xs += [(x_end, -edge_half), (x_end, edge_half)]
    xs += [(POCKET_DEPTH, edge_half), (-5.0, back_half)]
    # extrude along +Z then rotate so extrusion axis -> +Y
    m = Manifold.extrude(CrossSection([xs]), y1 - y0)
    m = m.rotate((-90, 0, 0))            # (x, z_cs, h) -> extrusion along -Y... fix below
    bb = m.bounding_box()
    return m.translate((0, y0 - bb[1], 0))


def build_cover():
    prof = blade_profile()
    pocket2d = prof
    outer2d = prof.offset(FACE_WALL, circular_segments=SEG)
    # trim outer at the open back (x >= 0) and give the edge its thicker wall
    band = CrossSection.square((EDGE_WALL + 1, POCKET_LEN + 2 * FACE_WALL)).translate(
        (POCKET_DEPTH - 1, -FACE_WALL))
    clip = CrossSection.square((POCKET_DEPTH + EDGE_WALL, 400)).translate((0, -100))
    outer2d = (outer2d + band) ^ clip

    H = 60.0
    outer_side = Manifold.extrude(outer2d, 2 * H).translate((0, 0, -H))
    pocket_side = Manifold.extrude(pocket2d, 2 * H).translate((0, 0, -H))

    bh, eh = BACK_THK / 2, EDGE_THK / 2
    outer_w = wedge(bh + FACE_WALL, eh + FACE_WALL, POCKET_DEPTH + EDGE_WALL, nose=eh + FACE_WALL * 0.6)
    pocket_w = wedge(bh, eh, POCKET_DEPTH)

    cover = (outer_side ^ outer_w) - (pocket_side ^ pocket_w)

    # nubs on both faces
    nx, ny = NUB_POS
    face_z = (bh + FACE_WALL) - ((bh - eh) / POCKET_DEPTH) * (nx + 5.0) * (POCKET_DEPTH / (POCKET_DEPTH + 5.0))
    face_z = bh + FACE_WALL - (bh - eh) * (nx + 5.0) / (POCKET_DEPTH + 5.0)
    stem = Manifold.cylinder(NUB_STEM_H + 1.0, NUB_STEM_D / 2, NUB_STEM_D / 2, SEG).translate((0, 0, -1.0))
    cone = Manifold.cylinder(NUB_CHAMFER_H, NUB_STEM_D / 2, NUB_HEAD_D / 2, SEG).translate((0, 0, NUB_STEM_H))
    cap = Manifold.cylinder(NUB_CAP_H, NUB_HEAD_D / 2, NUB_HEAD_D / 2 - 0.4, SEG).translate(
        (0, 0, NUB_STEM_H + NUB_CHAMFER_H))
    nub = stem + cone + cap
    cover = cover + nub.translate((nx, ny, face_z))
    cover = cover + nub.mirror((0, 0, 1)).translate((nx, ny, -face_z))
    return cover


def build_strap():
    total = STRAP_FIXED_TO_ADJ[-1] + 2 * STRAP_W
    body = CrossSection.square((total - STRAP_W, STRAP_W)).translate((STRAP_W / 2, -STRAP_W / 2))
    body = body + CrossSection.circle(STRAP_W / 2, SEG).translate((STRAP_W / 2, 0))
    # tapered pull tab
    tip = total + 8
    body = body + CrossSection([[(total - STRAP_W / 2, -STRAP_W / 2), (tip, -3.0), (tip, 3.0),
                                 (total - STRAP_W / 2, STRAP_W / 2)]])
    holes = CrossSection.circle(STRAP_HOLE_D / 2, SEG).translate((STRAP_W / 2, 0))
    for d in STRAP_FIXED_TO_ADJ:
        holes = holes + CrossSection.circle(STRAP_HOLE_D / 2, SEG).translate((STRAP_W / 2 + d, 0))
    return Manifold.extrude(body - holes, STRAP_T)


def to_arrays(m):
    mesh = m.to_mesh()
    return np.array(mesh.vert_properties)[:, :3], np.array(mesh.tri_verts)


def write_3mf(path, objects):
    verts_xml, items = [], []
    for i, (name, m) in enumerate(objects, start=1):
        v, t = to_arrays(m)
        vs = "".join(f'<vertex x="{a:.4f}" y="{b:.4f}" z="{c:.4f}"/>' for a, b, c in v)
        ts = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in t)
        verts_xml.append(f'<object id="{i}" name="{name}" type="model"><mesh><vertices>{vs}</vertices>'
                         f'<triangles>{ts}</triangles></mesh></object>')
        items.append(f'<item objectid="{i}"/>')
    model = ('<?xml version="1.0" encoding="UTF-8"?>'
             '<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
             f'<resources>{"".join(verts_xml)}</resources><build>{"".join(items)}</build></model>')
    ct = ('<?xml version="1.0" encoding="UTF-8"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
          '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", model)


def build_fit_coupon(y0=55.0, h=12.0):
    """Short band cut across the cover (full depth, no curve, no nub) to test
    the wedge pocket fit on the real blade before printing the whole cover."""
    box = Manifold.cube((200, h, 200)).translate((-50, y0, -100))
    return build_cover() ^ box


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "axe_blade_cover.3mf"
    cover = build_cover()
    strap = build_strap()
    # print orientation: top edge of blade (Y max) on the bed, cutting edge vertical
    printed = cover.rotate((-90, 0, 0))
    bb = printed.bounding_box()
    printed = printed.translate((-bb[0] + 100, -bb[1] + 100, -bb[2]))
    sb = strap.bounding_box()
    strap_p = strap.translate((-sb[0] + 60, -sb[1] + 160, -sb[2]))
    write_3mf(out, [("Axe blade cover", printed), ("Back strap (optional)", strap_p)])
    coupon = build_fit_coupon().rotate((-90, 0, 0))
    cb = coupon.bounding_box()
    coupon = coupon.translate((-cb[0] + 100, -cb[1] + 30, -cb[2]))
    write_3mf(out.replace(".3mf", "_fit_test.3mf"), [("Fit test band", coupon)])
    for n, m in [("cover", printed), ("strap", strap_p), ("fit test", coupon)]:
        b = m.bounding_box()
        print(n, "size mm:", [round(b[i + 3] - b[i], 2) for i in range(3)],
              "vol cm3:", round(m.volume() / 1000, 2), "genus:", m.genus())
