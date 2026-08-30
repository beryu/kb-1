#!/usr/bin/env python3
"""Generate JLCPCB BOM/CPL CSV files from PCB footprint attributes."""

import csv
from collections import defaultdict
from pathlib import Path
import sys

import pcbnew


board_path, bom_path, cpl_path = map(Path, sys.argv[1:4])
board = pcbnew.LoadBoard(str(board_path))

parts = []
for footprint in board.GetFootprints():
    attrs = footprint.GetAttributes()
    if attrs & (pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES):
        continue
    if not footprint.HasField("LCSC"):
        continue
    lcsc = footprint.GetFieldText("LCSC")
    if not lcsc:
        continue
    parts.append(footprint)

groups = defaultdict(list)
for footprint in parts:
    key = (
        footprint.GetValue(),
        str(footprint.GetFPID().GetLibItemName()),
        footprint.GetFieldText("LCSC"),
        footprint.GetFieldText("MPN") if footprint.HasField("MPN") else "",
    )
    groups[key].append(footprint.GetReference())

bom_path.parent.mkdir(parents=True, exist_ok=True)
with bom_path.open("w", newline="") as file:
    writer = csv.writer(file, lineterminator="\n")
    writer.writerow(["Comment", "Designator", "Footprint", "LCSC Part #", "MPN"])
    for (comment, package, lcsc, mpn), references in sorted(groups.items()):
        references.sort(key=lambda ref: (ref.rstrip("0123456789"), int(ref[len(ref.rstrip("0123456789")):] or 0)))
        writer.writerow([comment, ",".join(references), package, lcsc, mpn])

with cpl_path.open("w", newline="") as file:
    writer = csv.writer(file, lineterminator="\n")
    writer.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    for footprint in sorted(parts, key=lambda fp: fp.GetReference()):
        position = footprint.GetPosition()
        writer.writerow([
            footprint.GetReference(),
            f"{pcbnew.ToMM(position.x):.6f}",
            f"{-pcbnew.ToMM(position.y):.6f}",
            "Top" if footprint.GetLayer() == pcbnew.F_Cu else "Bottom",
            f"{footprint.GetOrientationDegrees() % 360:.3f}",
        ])

print(f"BOM: {len(groups)} rows; CPL: {len(parts)} placements")
