"""Parametric TPU block-style throwing-axe blade cover ("sleeve").

A rectangular block with a straight, parallel slot that is open along one long
side. The blade slides in edge-first through that open side. Modeled on the
simple block covers used in axe-throwing venues.

Coordinates (model space, mm):
  X = along the cutting edge
  Y = depth from the open side (0) toward the closed edge wall (+)
  Z = blade thickness, centered on 0
Exported in print orientation: closed edge wall on the bed, slot opening facing
up, so the slot walls print vertically with no bridges or supports.
"""
import sys
import zipfile

import numpy as np
from manifold3d import Manifold

IN = 25.4

# ---------------- parameters ----------------
SLOT_LEN = 4.25 * IN     # slot length along the cutting edge (covers the 4" legal max)
SLOT_DEPTH = 2.0 * IN    # how far the blade goes in, open side -> edge wall
SLOT_GAP = 6.0           # slot thickness: blade thickness at SLOT_DEPTH back from the edge
                         # + about 0.8 mm total clearance. MEASURE YOUR BLADE.
FACE_WALL = 4.0          # each flat face (room for a debossed logo)
END_WALL = 5.0           # the two short ends
EDGE_WALL = 6.0          # wall in front of the cutting edge
CORNER_R = 2.0           # outer corner rounding
LEAD_IN = 1.5            # chamfer on the slot mouth so the blade finds the slot
SEG = 48

FIT_TEST_LEN = 15.0      # length of the fit-test slice (full depth, full thickness)


def _hull_box(sx, sy, sz, r):
    s = Manifold.sphere(r, SEG)
    pts = [s.translate((x, y, z)) for x in (r, sx - r) for y in (r, sy - r) for z in (r, sz - r)]
    return Manifold.batch_hull(pts)


def build_sleeve(length=None):
    out_x = SLOT_LEN + 2 * END_WALL
    out_y = SLOT_DEPTH + EDGE_WALL
    out_z = SLOT_GAP + 2 * FACE_WALL
    body = _hull_box(out_x, out_y, out_z, CORNER_R).translate((-END_WALL, 0, -out_z / 2))

    slot = Manifold.cube((SLOT_LEN, SLOT_DEPTH + 5.0, SLOT_GAP)).translate((0, -5.0, -SLOT_GAP / 2))
    # lead-in: a wedge that widens the slot mouth by LEAD_IN per side
    mouth = Manifold.batch_hull([
        Manifold.cube((SLOT_LEN, 0.01, SLOT_GAP + 2 * LEAD_IN)).translate((0, -0.5, -SLOT_GAP / 2 - LEAD_IN)),
        Manifold.cube((SLOT_LEN, 0.01, SLOT_GAP)).translate((0, LEAD_IN * 1.5, -SLOT_GAP / 2)),
    ])
    sleeve = body - slot - mouth
    if length is not None:  # fit-test slice through the middle
        x0 = SLOT_LEN / 2 - length / 2
        sleeve = sleeve ^ Manifold.cube((length, 500, 500)).translate((x0, -250, -250))
    return sleeve


def to_print(m):
    """Edge wall on the bed, slot opening facing up."""
    p = m.rotate((-90, 0, 0))  # +Y (edge wall) -> -Z, onto the bed
    bb = p.bounding_box()
    return p.translate((-bb[0] + 50, -bb[1] + 50, -bb[2]))


def write_3mf(path, objects):
    objs, items = [], []
    for i, (name, m) in enumerate(objects, start=1):
        mesh = m.to_mesh()
        v = np.array(mesh.vert_properties)[:, :3]
        t = np.array(mesh.tri_verts)
        vs = "".join(f'<vertex x="{a:.4f}" y="{b:.4f}" z="{c:.4f}"/>' for a, b, c in v)
        ts = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in t)
        objs.append(f'<object id="{i}" name="{name}" type="model"><mesh><vertices>{vs}</vertices>'
                    f'<triangles>{ts}</triangles></mesh></object>')
        items.append(f'<item objectid="{i}"/>')
    model = ('<?xml version="1.0" encoding="UTF-8"?>'
             '<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
             f'<resources>{"".join(objs)}</resources><build>{"".join(items)}</build></model>')
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


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "axe_sleeve.3mf"
    sleeve = to_print(build_sleeve())
    test = to_print(build_sleeve(FIT_TEST_LEN))
    write_3mf(out, [("Axe sleeve", sleeve)])
    write_3mf(out.replace(".3mf", "_fit_test.3mf"), [("Axe sleeve fit test", test)])
    for n, m in [("sleeve", sleeve), ("fit test", test)]:
        b = m.bounding_box()
        print(n, "size mm:", [round(b[i + 3] - b[i], 2) for i in range(3)],
              "vol cm3:", round(m.volume() / 1000, 2), "genus:", m.genus())
