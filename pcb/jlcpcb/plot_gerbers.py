#!/usr/bin/env python3
"""Plot JLCPCB Gerber and Excellon files using KiCad's Python API."""

from pathlib import Path
import sys

import pcbnew


board_path, output_dir = map(Path, sys.argv[1:3])
output_dir.mkdir(parents=True, exist_ok=True)
board = pcbnew.LoadBoard(str(board_path))

plotter = pcbnew.PLOT_CONTROLLER(board)
options = plotter.GetPlotOptions()
options.SetOutputDirectory(str(output_dir))
options.SetSubtractMaskFromSilk(True)
# JLCPCB identifies routed board outlines and internal cutouts most reliably
# when KiCad emits the conventional Protel extension (Edge.Cuts -> .gm1).
options.SetUseGerberProtelExtensions(True)

layers = (
    (pcbnew.F_Cu, "F_Cu"),
    (pcbnew.B_Cu, "B_Cu"),
    (pcbnew.F_Paste, "F_Paste"),
    (pcbnew.B_Paste, "B_Paste"),
    (pcbnew.F_SilkS, "F_Silkscreen"),
    (pcbnew.B_SilkS, "B_Silkscreen"),
    (pcbnew.F_Mask, "F_Mask"),
    (pcbnew.B_Mask, "B_Mask"),
    (pcbnew.Edge_Cuts, "Edge_Cuts"),
)

for layer, suffix in layers:
    plotter.SetLayer(layer)
    plotter.OpenPlotfile(suffix, pcbnew.PLOT_FORMAT_GERBER, suffix)
    plotter.PlotLayer()
plotter.ClosePlot()

drill_writer = pcbnew.EXCELLON_WRITER(board)
drill_writer.SetOptions(False, False, pcbnew.VECTOR2I(0, 0), False)
drill_writer.SetFormat(
    True,
    pcbnew.GENDRILL_WRITER_BASE.DECIMAL_FORMAT,
    3,
    3,
)
drill_writer.CreateDrillandMapFilesSet(str(output_dir), True, False)

print(f"Gerbers and drill files written to {output_dir}")
