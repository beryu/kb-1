#!/usr/bin/env python3
"""Generate an open 19.05 mm trackball cradle, reusing proven interface geometry.

Requires numpy, trimesh, manifold3d; optional matplotlib for the preview.
Existing sensor guides, rear mounting holes and three bearing seats are inherited
from the sensor-fit mesh. Dimensions below are in millimetres and degrees.
"""
import argparse
import json
import math
from pathlib import Path
import subprocess
import tempfile

import manifold3d as mf
import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[2]
BALL_CENTER = (0.0, 0.0, 9.8)
BALL_RADIUS = 19.05 / 2
BASE_HEIGHT = 2.5
# Leave the front bearing seats between 38..78 and -78..-38 degrees.
# Rear sensor housing / bearing seat is retained between 140..220 degrees.
WINDOWS = ((-38, 38), (78, 140), (-140, -78))


def solid(mesh):
    result = mf.Manifold(mf.Mesh64(np.asarray(mesh.vertices, dtype=np.float64),
                                  np.asarray(mesh.faces, dtype=np.uint64)))
    if result.status() != mf.Error.NoError:
        raise ValueError(f'Invalid mesh: {result.status()}')
    return result


def preview(case_mesh, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    fig = plt.figure(figsize=(12, 6), facecolor='#f4f3ef')
    ball = trimesh.creation.icosphere(subdivisions=3, radius=BALL_RADIUS)
    ball.apply_translation(BALL_CENTER)
    for index, (title, with_ball) in enumerate((('Open cradle', False),
                                               ('19.05 mm ball (reference)', True))):
        ax = fig.add_subplot(1, 2, index + 1, projection='3d')
        ax.set_facecolor('#f4f3ef')
        for mesh, color in [(case_mesh, '#a4bca5')] + ([(ball, '#42799c')] if with_ball else []):
            triangles = mesh.triangles
            normals = mesh.face_normals
            light = np.array([.5, -.4, .75]); light /= np.linalg.norm(light)
            shade = .55 + .45 * np.maximum(normals @ light, 0)
            from matplotlib.colors import to_rgb
            colors = shade[:, None] * np.array(to_rgb(color))
            ax.add_collection3d(Poly3DCollection(triangles, facecolors=colors,
                                                edgecolors='none'))
        ax.set(xlim=(-21, 13), ylim=(-17, 17), zlim=(0, 25))
        ax.set_box_aspect((34, 34, 25)); ax.view_init(38, -25)
        ax.set_axis_off(); ax.set_title(title, fontsize=13)
    fig.subplots_adjust(left=0, right=1, bottom=.03, top=.87, wspace=0)
    fig.savefig(path, dpi=160, bbox_inches='tight', pad_inches=.2); plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / '3d-models/STL/trackball-case-19mm-ortho-sensor-fit-Body.stl')
    parser.add_argument('--output', type=Path, default=ROOT / '3d-models/STL/trackball-case-19mm-open-Body.stl')
    parser.add_argument('--preview', type=Path)
    parser.add_argument('--freecadcmd', type=Path)
    parser.add_argument('--cad-output', type=Path)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error('Input must be preserved; choose a separate output')
    if bool(args.freecadcmd) != bool(args.cad_output):
        parser.error('Supply both --freecadcmd and --cad-output')
    source_mesh = trimesh.load_mesh(args.input)
    source = solid(source_mesh)
    result = source
    rear = mf.Manifold.cube((24, 40, 32)).translate((-30, -20, -1))
    for lo, hi in WINDOWS:
        angles = np.linspace(math.radians(lo), math.radians(hi), 32)
        polygon = np.vstack(([0, 0], 30 * np.column_stack((np.cos(angles), np.sin(angles)))))
        window = mf.CrossSection([polygon]).extrude(30).translate((0, 0, BASE_HEIGHT))
        result -= window - rear
    result = result.set_tolerance(1e-4).simplify(1e-4)
    assert result.status() == mf.Error.NoError
    assert len(result.decompose()) == 1, 'Cradle must remain connected'
    assert (result - source).volume() < 1e-3, 'Unexpected added material'
    # Check with a sphere 0.50 mm larger in radius, allowing 0.50 mm of
    # nominal radial clearance. This is a mesh-space check, not print QA.
    envelope = mf.Manifold.sphere(BALL_RADIUS + .50, 256).translate(BALL_CENTER)
    assert (result ^ envelope).volume() < 1e-5, 'Insufficient nominal ball clearance'
    # Preserve sensor/rear mounting geometry, lower frame and seat regions.
    lower = mf.Manifold.cube((60, 60, BASE_HEIGHT + 1)).translate((-30, -30, -1))
    for region in (rear, lower):
        assert ((source - result) ^ region).volume() < 1e-3, 'Interface geometry changed'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    m = result.to_mesh64()
    output = trimesh.Trimesh(m.vert_properties[:, :3], m.tri_verts, process=False)
    # Binary STL stores float32 coordinates. Weld sub-micron split vertices
    # and discard collapsed/duplicate triangles before validating the saved mesh.
    output.vertices = output.vertices.astype(np.float32).astype(np.float64)
    output.merge_vertices(digits_vertex=6)
    output.update_faces(output.nondegenerate_faces())
    output.update_faces(output.unique_faces())
    output.remove_unreferenced_vertices()
    assert output.is_watertight and output.is_winding_consistent
    output.export(args.output)
    saved = trimesh.load_mesh(args.output)
    assert saved.is_watertight and saved.is_winding_consistent
    reloaded = solid(saved)
    assert len(reloaded.decompose()) == 1
    assert (reloaded ^ envelope).volume() < 1e-5
    report = dict(ball_diameter_mm=19.05, ball_center_mm=BALL_CENTER,
                  checked_radial_clearance_mm=.50, base_height_mm=BASE_HEIGHT,
                  windows_degrees=WINDOWS, watertight=True, connected_components=1,
                  volume_mm3=result.volume(), removed_volume_mm3=(source-result).volume(),
                  ball_envelope_collision_mm3=(reloaded ^ envelope).volume(),
                  physical_fit_verified=False)
    args.output.with_suffix('.validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    if args.preview:
        preview(saved, args.preview)
    if args.freecadcmd:
        args.cad_output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as directory:
            macro = Path(directory) / 'save.py'
            macro.write_text(f'''import FreeCAD as App, Mesh, Part
D = App.newDocument("OpenTrackballCase")
F = D.addObject("Mesh::Feature", "OpenCase")
F.Mesh = Mesh.Mesh({str(args.output.resolve())!r})
F.Label = "19.05 mm open cradle - prototype"
F.addProperty("App::PropertyLength", "NominalBallDiameter", "Dimensions")
F.NominalBallDiameter = 19.05
F.addProperty("App::PropertyLength", "CheckedRadialClearance", "Dimensions")
F.CheckedRadialClearance = 0.5
B = D.addObject("Part::Feature", "ReferenceBall")
B.Shape = Part.makeSphere({BALL_RADIUS}, App.Vector{BALL_CENTER!r})
B.Visibility = False
D.recompute()
D.saveAs({str(args.cad_output.resolve())!r})
''')
            subprocess.run([str(args.freecadcmd), '-c', f'exec(open({str(macro)!r}).read())'], check=True)


if __name__ == '__main__':
    main()
