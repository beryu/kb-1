#!/usr/bin/env python3
"""Keep the board compatible with the standard 0.3 mm via quote option."""

import sys
from pathlib import Path

import pcbnew


MIN_DRILL = pcbnew.FromMM(0.3)
MIN_DIAMETER = pcbnew.FromMM(0.5)


def check(path):
    board = pcbnew.LoadBoard(str(path))
    vias = [item for item in board.GetTracks()
            if isinstance(item, pcbnew.PCB_VIA)]
    for via in vias:
        if via.GetDrillValue() < MIN_DRILL or via.GetWidth(pcbnew.F_Cu) < MIN_DIAMETER:
            point = via.GetPosition()
            raise ValueError(
                f"{path}: via at ({pcbnew.ToMM(point.x):.3f}, "
                f"{pcbnew.ToMM(point.y):.3f}) mm is smaller than "
                "0.3 mm drill / 0.5 mm diameter"
            )
    print(f"{path}: {len(vias)} standard-size vias verified")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Usage: check_standard_vias.py BOARD [BOARD...]")
    for name in sys.argv[1:]:
        check(Path(name))
