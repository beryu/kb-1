#!/usr/bin/env python3
"""Panelize the left and right PCBs for one JLCPCB PCBA order."""

from pathlib import Path
import sys

import pcbnew

try:
    from kikit.common import fromMm
    from kikit.panelize import Panel
except ImportError as error:
    raise SystemExit(
        "KiKit 1.8.0 is required. Install pcb/jlcpcb/requirements-panel.txt "
        "with KiCad's Python interpreter."
    ) from error


left_path, right_path, output_path = map(Path, sys.argv[1:4])
output_path.parent.mkdir(parents=True, exist_ok=True)

panel = Panel(str(output_path))
panel.inheritDesignSettings(str(left_path))

# Each source board is 138.9 x 74.1 mm. A 2 mm routing gap gives a
# 138.9 x 150.2 mm customer panel before JLCPCB adds its handling rails.
placements = (
    (left_path, (100.0, 50.0)),
    (right_path, (100.0, 126.1)),
)

for board_path, (x_mm, y_mm) in placements:
    panel.appendBoard(
        board_path,
        pcbnew.VECTOR2I(fromMm(x_mm), fromMm(y_mm)),
        refRenamer=lambda _board_number, reference: reference,
        inheritDrc=False,
        bakeRef=True,
    )

# Join the two boards with three 5 mm mouse-bite tabs across their shared
# edge. JLCPCB adds the two 5 mm handling rails and fiducials at quote time.
panel.buildPartitionLineFromBB()
panel.buildTabAnnotationsFixed(
    hcount=0,
    vcount=3,
    hwidth=fromMm(5),
    vwidth=fromMm(5),
    minDistance=fromMm(15),
    ghostSubstrates=[],
)
cuts = panel.buildTabsFromAnnotations(fillet=0)
panel.makeMouseBites(
    cuts,
    diameter=fromMm(0.5),
    spacing=fromMm(1.0),
    offset=fromMm(0.2),
)
panel.save(refillAllZones=True)

# KiKit creates project-sidecar files while saving. The panel is a generated
# manufacturing artifact, so only the board file is retained in output/.
for suffix in (".kicad_pro", ".kicad_prl", ".kicad_dru"):
    output_path.with_suffix(suffix).unlink(missing_ok=True)

if panel.hasErrors():
    for position, message in panel.errors:
        print(f"Panel error at {position}: {message}", file=sys.stderr)
    raise SystemExit("KiKit reported panelization errors")

print(f"Combined panel written to {output_path}")
