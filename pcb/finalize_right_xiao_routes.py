#!/usr/bin/env python3
"""Apply the five DRC-guided via adjustments to the routed right PCB."""

from pathlib import Path
import sys

import wx

_WX_APP = wx.App(False)

import pcbnew


MOVES = {
    ("/right/COL1", 58.0, 128.8): (58.2, 128.8),
    ("/right/COL5", 61.0, 131.0): (61.3, 131.0),
    ("/right/COL3", 45.8, 127.2): (45.6, 127.2),
    ("GND", 61.8, 154.0): (61.6, 154.0),
    ("GND", 76.0, 138.4): (76.4, 138.4),
}

MERGES = ()


def point(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def main(input_path: Path, output_path: Path) -> None:
    board = pcbnew.LoadBoard(str(input_path))
    items = list(board.GetTracks())
    moved = 0
    for (net_name, old_x, old_y), (new_x, new_y) in MOVES.items():
        old = point(old_x, old_y)
        new = point(new_x, new_y)
        via_found = False
        for item in items:
            if item.GetNetname() != net_name:
                continue
            if isinstance(item, pcbnew.PCB_VIA):
                if item.GetPosition() == old:
                    item.SetPosition(new)
                    via_found = True
            else:
                if item.GetStart() == old:
                    item.SetStart(new)
                if item.GetEnd() == old:
                    item.SetEnd(new)
        if not via_found:
            raise RuntimeError(f"via not found: {net_name} @ {old_x},{old_y}")
        moved += 1

    for net_name, old_positions, new_position in MERGES:
        new = point(*new_position)
        for old_position in old_positions:
            old = point(*old_position)
            for item in items:
                if item.GetNetname() != net_name:
                    continue
                if isinstance(item, pcbnew.PCB_VIA):
                    if item.GetPosition() == old:
                        item.SetPosition(new)
                else:
                    if item.GetStart() == old:
                        item.SetStart(new)
                    if item.GetEnd() == old:
                        item.SetEnd(new)

    board.BuildListOfNets()
    board.SynchronizeNetsAndNetClasses(True)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())

    seen_vias = set()
    duplicates = []
    for item in items:
        if not isinstance(item, pcbnew.PCB_VIA):
            continue
        position = item.GetPosition()
        key = (item.GetNetname(), position.x, position.y)
        if key in seen_vias:
            duplicates.append(item)
        else:
            seen_vias.add(key)
    for item in duplicates:
        board.RemoveNative(item)

    pcbnew.SaveBoard(str(output_path), board)
    print(f"moved {moved} vias; removed {len(duplicates)} duplicate vias")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} INPUT OUTPUT")
    main(Path(sys.argv[1]), Path(sys.argv[2]))
