#!/usr/bin/env python3
"""Apply DRC-guided via moves to the fine-grid left-board route."""

from pathlib import Path
import sys

import wx

_WX_APP = wx.App(False)

import pcbnew


MOVES = (
    ("/left/ROW2", (102.1, 64.4), (101.8, 64.1)),
    ("/left/COL5", (96.0, 78.1), (95.525, 78.3)),
)


def point(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def move(board, net_name, old_xy, new_xy):
    old = point(*old_xy)
    new = point(*new_xy)
    def matches(candidate):
        return abs(candidate.x - old.x) <= 2_000 and abs(candidate.y - old.y) <= 2_000
    found = False
    for item in list(board.GetTracks()):
        if item.GetNetname() != net_name:
            continue
        if isinstance(item, pcbnew.PCB_VIA):
            if matches(item.GetPosition()):
                item.SetPosition(new)
                found = True
        else:
            if matches(item.GetStart()):
                item.SetStart(new)
            if matches(item.GetEnd()):
                item.SetEnd(new)
    if not found:
        raise RuntimeError(f"via not found: {net_name} {old_xy}")


def remove_duplicate_vias(board):
    seen = set()
    duplicates = []
    for item in board.GetTracks():
        if not isinstance(item, pcbnew.PCB_VIA):
            continue
        pos = item.GetPosition()
        key = (item.GetNetname(), pos.x, pos.y)
        if key in seen:
            duplicates.append(item)
        else:
            seen.add(key)
    for item in duplicates:
        board.RemoveNative(item)


def add_adc_route(board):
    net = board.FindNet("/left/VBAT_ADC")
    front_routes = (
        ((133.200, 43.600), (133.200, 42.900)),
        ((135.800, 49.500), (130.300, 49.500)),
        ((136.800, 47.500), (136.325, 47.500)),
    )
    for start, end in front_routes:
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(point(*start))
        track.SetEnd(point(*end))
        track.SetWidth(pcbnew.FromMM(0.20))
        track.SetLayer(pcbnew.F_Cu)
        track.SetNet(net)
        board.Add(track)
    for via_position in (
        (133.200, 43.600),
        (130.300, 49.500),
        (135.800, 49.500),
        (136.800, 47.500),
    ):
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(point(*via_position))
        via.SetWidth(pcbnew.FromMM(0.50))
        via.SetDrill(pcbnew.FromMM(0.30))
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via.SetNet(net)
        board.Add(via)
    # Cross the long battery-negative lead on F.Cu, then pass beyond the end
    # of RESET_N on B.Cu and join the already-routed ADC trace on F.Cu.
    back_routes = (
        ((136.800, 47.500), (135.800, 49.500)),
        ((130.300, 49.500), (130.300, 45.000)),
        ((130.300, 45.000), (132.300, 45.000)),
        ((132.300, 45.000), (133.200, 43.600)),
    )
    for start, end in back_routes:
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(point(*start))
        track.SetEnd(point(*end))
        track.SetWidth(pcbnew.FromMM(0.20))
        track.SetLayer(pcbnew.B_Cu)
        track.SetNet(net)
        board.Add(track)


def main(input_path, output_path):
    board = pcbnew.LoadBoard(str(input_path))
    for net_name, old_xy, new_xy in MOVES:
        move(board, net_name, old_xy, new_xy)
    remove_duplicate_vias(board)
    add_adc_route(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output_path), board)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} INPUT OUTPUT")
    main(Path(sys.argv[1]), Path(sys.argv[2]))
