#!/usr/bin/env python3
"""Check that the screw clearances are real board-edge cutouts."""

import sys
from pathlib import Path

import pcbnew
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union


# Coordinates and drill radii from the original mounting-hole footprints.
# The centers lie outside the boards; a footprint or drill file alone does not
# make a clearance there. Edge.Cuts must stay at least this far away.
RELIEFS = {
    "left": ((95.5, 41.5, 2.45), (10.5, 45.5, 2.5),
             (134.0, 115.5, 2.5), (10.5, 115.5, 2.5)),
    "right": ((79.3, 116.5, 2.45), (164.3, 190.5, 2.5),
              (40.8, 190.5, 2.5), (164.3, 120.5, 2.45)),
}
PANEL_CENTERS = {"left": (100.0, 50.0), "right": (100.0, 126.1)}
TOLERANCE_MM = 0.05


def board_substrate(path):
    board = pcbnew.LoadBoard(str(path))
    outlines = pcbnew.SHAPE_POLY_SET()
    if not board.GetBoardPolygonOutlines(outlines, False):
        raise ValueError(f"Invalid Edge.Cuts outline: {path}")

    def coordinates(chain):
        return [(chain.CPoint(i).x / 1e6, chain.CPoint(i).y / 1e6)
                for i in range(chain.PointCount())]

    polygons = []
    for index in range(outlines.OutlineCount()):
        holes = [coordinates(outlines.CHole(index, i))
                 for i in range(outlines.HoleCount(index))]
        polygons.append(Polygon(coordinates(outlines.COutline(index)), holes))
    substrate = unary_union(polygons)
    if substrate.is_empty or not substrate.is_valid:
        raise ValueError(f"Invalid substrate polygon: {path}")
    return substrate


def check(path, side, offset=(0.0, 0.0)):
    substrate = board_substrate(path)
    for x, y, radius in RELIEFS[side]:
        distance = substrate.distance(Point(x + offset[0], y + offset[1]))
        if not radius - TOLERANCE_MM <= distance <= radius + TOLERANCE_MM:
            raise ValueError(
                f"{path}: {side} screw relief at ({x:g}, {y:g}) mm "
                f"has {distance:.3f} mm clearance; expected {radius:.3f} mm"
            )
    print(f"{path}: {side} screw reliefs verified (4/4)")
    return substrate


def main():
    left_path, right_path = map(Path, sys.argv[1:3])
    sources = {
        "left": check(left_path, "left"),
        "right": check(right_path, "right"),
    }
    if len(sys.argv) == 4:
        panel_path = Path(sys.argv[3])
        for side, substrate in sources.items():
            min_x, min_y, max_x, max_y = substrate.bounds
            target_x, target_y = PANEL_CENTERS[side]
            offset = (target_x - (min_x + max_x) / 2,
                      target_y - (min_y + max_y) / 2)
            check(panel_path, side, offset)


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        raise SystemExit("Usage: check_screw_reliefs.py LEFT RIGHT [PANEL]")
    main()
