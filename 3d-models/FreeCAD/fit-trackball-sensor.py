#!/usr/bin/env python3
"""Add guides to the ORIGINAL 19 mm case STL (requires trimesh/manifold3d/numpy).

Use an unmodified input STL; do not use the already fitted output as input.
All dimensions are in mm. See TRACKBALL-SENSOR-FIT.md.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile

import manifold3d as mf
import numpy as np
import trimesh


def manifold(mesh):
    result = mf.Manifold(mf.Mesh64(np.asarray(mesh.vertices, dtype=np.float64),
                                 np.asarray(mesh.faces, dtype=np.uint64)))
    if result.status() != mf.Error.NoError:
        raise ValueError(f"Invalid input mesh: {result.status()}")
    return result


def mesh(solid):
    m = solid.to_mesh64()
    return trimesh.Trimesh(vertices=m.vert_properties[:, :3],
                           faces=m.tri_verts, process=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--clearance', type=float, default=0.15,
                        help='PCB clearance per side (default: 0.15 mm)')
    parser.add_argument('--freecadcmd', type=Path)
    parser.add_argument('--cad-output', type=Path)
    args = parser.parse_args()
    width = 7.4 + 2 * args.clearance
    if not (0 < args.clearance < 0.2):
        parser.error('clearance must be > 0 and < 0.2 mm for this original slot')
    if bool(args.freecadcmd) != bool(args.cad_output):
        parser.error('--freecadcmd and --cad-output must be supplied together')
    if args.input.resolve() == args.output.resolve():
        parser.error("Use a separate output path to preserve the original STL")
    source_mesh = trimesh.load_mesh(args.input)
    source = manifold(source_mesh)
    # The original Sketch's rectangular sensor slot, in world coordinates.
    # u follows the 7.8 mm side; v follows its 2.5 mm insertion depth.
    a = np.array([-14.50420828193446, 0, 10.752863245310591])
    b = np.array([-12.057084358625477, 0, 11.264316570618826])
    c = np.array([-10.461349983663785, 0, 3.6292899298947994])
    u, v = c - b, b - a
    u /= np.linalg.norm(u)
    v /= np.linalg.norm(v)

    def box(start, w, depth, y0, y1):
        transform = np.column_stack((u, v, [0, 1, 0],
                                     start + [0, y0, 0]))
        return mf.Manifold.cube((w, depth, y1 - y0)).transform(transform)

    # The original slot is loaded sideways along Y, not along v.
    # Keep both mouths open so the board can slide out from either side.
    # The 0.05 mm overlap joins the guides to the surrounding case walls.
    blank = box(a - u * .05 - v * .05, 7.9, 2.55, -9.5025, 9.5025)
    # The rear channel ALSO houses the sensor assembly (see assembly photos).
    # Reinforce only outside a continuous module channel spanning both the
    # 2.8 mm rear recess and the 2.5 mm forward component recess.
    backfill = box(a - u * 2.85 - v * 2.85, 12.4, 2.85, -9.5025, 9.5025)
    # Preserve the original rear hexagonal mounting holes (circumradius 1 mm,
    # z=0..6 mm). These are holes, not the structural channel being filled.
    holes = []
    for yy in (-6.0, 6.0):
        angles = np.arange(6) * np.pi / 3 + np.pi / 2
        polygon = np.column_stack((-17.5025 + np.cos(angles),
                                   yy + np.sin(angles)))
        holes.append(mf.CrossSection([polygon]).extrude(6.0))
    hole_mask = holes[0] + holes[1]
    module_channel = box(a + u * ((7.8 - width) / 2) - v * 2.95,
                         width, 5.65, -25.0, 25.0)
    reinforcement = (blank + backfill) - hole_mask - module_channel
    result = (source + reinforcement).set_tolerance(1e-4).simplify(1e-4)
    components = result.decompose()
    assert sum(part.volume() >= 1e-8 for part in components) == 1, "Disconnected reinforcement"
    assert sum(part.volume() for part in components if part.volume() < 1e-8) < 1e-8
    result = max(components, key=lambda part: part.volume())
    assert (result ^ hole_mask).volume() < 1e-4, 'Mounting holes obstructed'
    # Check the original optical cutout beyond the seat, excluding its
    # surrounding supports; it must retain exactly its original free space.
    optical_region = box(a + u * 1.45 + v * 2.5, 4.9, 9.5, -5.9, 5.9)
    assert ((result - source) ^ optical_region).volume() < 1e-4, 'Optical path obstructed'
    added, removed = result - source, source - result
    assert removed.volume() < 1e-5, 'Unexpected removal of original case material'
    assert added.volume() > 0
    # Sweep the assembly corridor, including its rear board recess and both
    # mouths. A clear full-length corridor permits insertion and removal
    # from either side, without an end stop trapping the board.
    travel = box(a + u * ((7.8 - 7.4) / 2) - v * 2.79,
                 7.4, 5.28, -25.0, 25.0)
    insertion_collision = (result ^ travel).volume()
    assert insertion_collision < 1e-4, 'Blocked through-slot path'
    output = mesh(result)
    assert output.is_watertight and output.is_winding_consistent
    assert len(result.decompose()) == 1, 'Guides must connect to the case'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.export(args.output)
    reloaded = trimesh.load_mesh(args.output)
    assert reloaded.is_watertight and reloaded.is_winding_consistent
    assert np.allclose(reloaded.bounds, source_mesh.bounds, atol=1e-5), 'Outer bounds changed'
    saved_collision = (manifold(reloaded) ^ travel).volume()
    assert saved_collision < 1e-4, 'Saved STL blocks the insertion path'
    print(json.dumps({'slot_width_mm': width, 'clearance_per_side_mm': args.clearance,
                      'added_volume_mm3': added.volume(),
                      'removed_volume_mm3': removed.volume(),
                      'watertight': reloaded.is_watertight,
                      'insertion_collision_mm3': saved_collision,
                      'back_channel_reinforced_outside_module': True}, indent=2))
    if args.freecadcmd:
        with tempfile.TemporaryDirectory() as tmp:
            base_path = Path(tmp)/'base.stl'
            source_mesh.export(base_path)
            macro = Path(tmp)/'save.py'
            macro.write_text(f'''import FreeCAD as App, Mesh
D = App.newDocument("TrackballSensorFit")
for name, label, path, visible in {repr([
    ('OriginalCase', 'Original STL (reference)', str(base_path), False),
    ('FittedCase', '19 mm case - PAW3222 through slot + reinforced back', str(args.output.resolve()), True)])}:
    obj = D.addObject("Mesh::Feature", name)
    obj.Label = label
    obj.Mesh = Mesh.Mesh(path)
    obj.Visibility = visible
F = D.FittedCase
for name, value in [("PCBLength",13.4),("PCBWidth",7.4),("ClearancePerSide",{args.clearance}),("SlotWidth",{width})]:
    F.addProperty("App::PropertyLength",name,"Sensor fit")
    setattr(F,name,value)
    F.setEditorMode(name,1)
F.addProperty("App::PropertyBool","BackChannelFilled","Sensor fit")
F.BackChannelFilled = False
F.addProperty("App::PropertyLength","ModuleChannelDepth","Sensor fit")
F.ModuleChannelDepth = 5.3
F.addProperty("App::PropertyString","InsertionSide","Sensor fit")
F.InsertionSide = "Through slot: insert/remove from either -Y or +Y side"
F.addProperty("App::PropertyString","Regeneration","Sensor fit")
F.Regeneration = "Use fit-trackball-sensor.py with the original STL; dimensions here are read-only."
D.recompute()
D.saveAs({str(args.cad_output.resolve())!r})
''')
            subprocess.run([str(args.freecadcmd), '-c',
                            f'exec(open({str(macro)!r}).read())'], check=True)


if __name__ == '__main__':
    main()
