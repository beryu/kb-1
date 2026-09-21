#!/usr/bin/env python3
"""Replace the split link headers with top-entry JST PHD connectors.

The right connector is centered directly below the XIAO.  The left connector
uses the equivalent location below the former left-XIAO position.  Both are
through-hole B12B-PHDSS headers for hand soldering and mate with PHDR-12VS
cable housings inserted from the top of the keyboard.

Run with KiCad's bundled Python/pcbnew module:

    place_vertical_phd_link.py LEFT_IN RIGHT_IN LEFT_OUT RIGHT_OUT
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import os
import math
import sys

import pcbnew
import migrate_to_single_xiao_wired as routerlib

from migrate_to_single_xiao_wired import (
    Endpoint,
    LINK_PIN_NETS,
    LocalRouter,
    TRACE_WIDTH,
    VIA_DIAMETER,
    VIA_DRILL,
    add_label,
    finish,
    get_or_create_net,
    mm,
    nearest_copper_endpoint,
    pad_endpoint,
    point,
    remove_link_labels,
    route_pad_to_endpoint,
    set_pad_net,
)


KICAD_FOOTPRINT_LIBRARY = Path(
    "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/Connector_JST.pretty"
)
FOOTPRINT_NAME = "JST_PHD_B12B-PHDSS_2x06_P2.00mm_Vertical"
NEW_TRACE_WIDTH = 0.15
NEW_VIA_DIAMETER = 0.50
NEW_VIA_DRILL = 0.25


def inside_box(position: pcbnew.VECTOR2I, box: tuple[float, float, float, float]) -> bool:
    x = pcbnew.ToMM(position.x)
    y = pcbnew.ToMM(position.y)
    x0, y0, x1, y1 = box
    return x0 <= x <= x1 and y0 <= y <= y1


def remove_old_link_copper(
    board: pcbnew.BOARD,
    net_names: set[str],
    box: tuple[float, float, float, float],
) -> dict[str, list[Endpoint]]:
    """Remove fanout copper and return every surviving boundary endpoint."""
    boundary: dict[str, list[Endpoint]] = defaultdict(list)
    for item in list(board.GetTracks()):
        if item.GetNetname() not in net_names:
            continue
        if isinstance(item, pcbnew.PCB_VIA):
            remove = inside_box(item.GetPosition(), box)
        else:
            start_inside = inside_box(item.GetStart(), box)
            end_inside = inside_box(item.GetEnd(), box)
            remove = start_inside or end_inside
            layer = 0 if item.GetLayer() == pcbnew.F_Cu else 1
            if start_inside and not end_inside:
                end = item.GetEnd()
                boundary[item.GetNetname()].append(
                    Endpoint(pcbnew.ToMM(end.x), pcbnew.ToMM(end.y), layer)
                )
            elif end_inside and not start_inside:
                start = item.GetStart()
                boundary[item.GetNetname()].append(
                    Endpoint(pcbnew.ToMM(start.x), pcbnew.ToMM(start.y), layer)
                )
        if remove:
            board.RemoveNative(item)
    return boundary


def load_vertical_phd(
    board: pcbnew.BOARD,
    reference: str,
    position: tuple[float, float],
    angle: float,
) -> pcbnew.FOOTPRINT:
    footprint = pcbnew.FootprintLoad(str(KICAD_FOOTPRINT_LIBRARY), FOOTPRINT_NAME)
    if footprint is None:
        raise RuntimeError(f"unable to load {FOOTPRINT_NAME}")
    footprint.SetReference(reference)
    footprint.SetValue("B12B-PHDSS")
    footprint.SetFPID(pcbnew.LIB_ID("Connector_JST", FOOTPRINT_NAME))
    footprint.SetLayer(pcbnew.F_Cu)
    footprint.SetPosition(point(*position))
    footprint.SetOrientationDegrees(angle)
    footprint.SetAttributes(
        footprint.GetAttributes()
        | pcbnew.FP_EXCLUDE_FROM_BOM
        | pcbnew.FP_EXCLUDE_FROM_POS_FILES
    )
    board.Add(footprint)
    return footprint


def one_goal_per_component(
    board: pcbnew.BOARD, net_name: str, goals: list[Endpoint]
) -> list[Endpoint]:
    """Discard stale cut points and keep one point per copper component."""
    board.BuildConnectivity()
    connectivity = board.GetConnectivity()
    selected: dict[frozenset[str], Endpoint] = {}
    tracks = [item for item in board.GetTracks() if item.GetNetname() == net_name]
    for goal in goals:
        candidate = None
        for item in tracks:
            positions = (
                (item.GetPosition(),)
                if isinstance(item, pcbnew.PCB_VIA)
                else (item.GetStart(), item.GetEnd())
            )
            if any(
                math.hypot(
                    pcbnew.ToMM(position.x) - goal.x,
                    pcbnew.ToMM(position.y) - goal.y,
                )
                < 0.01
                for position in positions
            ):
                candidate = item
                break
        if candidate is None:
            continue
        connected = list(connectivity.GetConnectedItems(candidate)) + [candidate]
        signature = frozenset(item.m_Uuid.AsString() for item in connected)
        selected.setdefault(signature, goal)
    return list(selected.values())


def add_pad_escape(
    board: pcbnew.BOARD,
    net_name: str,
    connector: pcbnew.FOOTPRINT,
    pin: str,
) -> Endpoint:
    """Add a perpendicular dog-bone escape and return its via endpoint."""
    start = pad_endpoint(connector, pin)
    pad_y = [pad_endpoint(connector, pad.GetNumber()).y for pad in connector.Pads()]
    center_y = (min(pad_y) + max(pad_y)) / 2
    escape = Endpoint(start.x, start.y + (-2.5 if start.y < center_y else 2.5), None)

    # The 2.00 mm pitch leaves no legal channel between adjacent 1.70 mm
    # plated pads.  A perpendicular dog-bone escape keeps every trace clear.
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(point(start.x, start.y))
    track.SetEnd(point(escape.x, escape.y))
    track.SetWidth(mm(NEW_TRACE_WIDTH))
    track.SetLayer(pcbnew.F_Cu)
    track.SetNet(board.FindNet(net_name))
    board.Add(track)

    via = pcbnew.PCB_VIA(board)
    via.SetPosition(point(escape.x, escape.y))
    via.SetWidth(mm(NEW_VIA_DIAMETER))
    via.SetDrill(mm(NEW_VIA_DRILL))
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNet(board.FindNet(net_name))
    board.Add(via)
    return escape


def route_link_escape(
    board: pcbnew.BOARD, net_name: str, connector: pcbnew.FOOTPRINT, pin: str,
    start: Endpoint, goal,
) -> None:
    """Route a previously reserved pad escape to existing copper."""

    router = LocalRouter(board, net_name, start, goal, 28.0)
    path = router.solve()
    router.add(path)
    print(f"routed {net_name}: {connector.GetReference()}:{pin} -> copper")


def replace_link(board: pcbnew.BOARD, side: str) -> None:
    if side == "right":
        reference = "J202"
        # Rotate the header toward the existing controller fanout.  Its
        # mechanical center is (51.9, 150.1), directly below the XIAO while
        # leaving its antenna keepout and USB-C area unobstructed.
        position = (56.9, 151.1)
        angle = 180.0
        cleanup_boxes = (
            (44.0, 145.0, 62.0, 155.0),
            (31.5, 149.0, 39.5, 174.5),
        )
        label_positions = ((45.5, 145.0), (54.0, 145.0))
    else:
        reference = "J101"
        # Mirrored about the former left-XIAO center.  At 180 degrees the
        # mechanical center is -5 mm, -1 mm from the footprint origin.
        position = (128.2, 74.0)
        angle = 180.0
        cleanup_boxes = (
            (115.0, 67.0, 132.0, 79.0),
            (134.5, 70.0, 142.5, 85.5),
        )
        label_positions = ((117.0, 78.8), (125.5, 78.8))

    old = board.FindFootprintByReference(reference)
    if old is None:
        raise RuntimeError(f"{side}: {reference} not found")

    pin_nets = {pad.GetNumber(): pad.GetNetname() for pad in old.Pads()}
    if set(pin_nets) != set(LINK_PIN_NETS):
        raise RuntimeError(f"{side}: unexpected {reference} pin set: {sorted(pin_nets)}")

    board.RemoveNative(old)
    cut_goals: dict[str, list[Endpoint]] = defaultdict(list)
    for cleanup_box in cleanup_boxes:
        removed = remove_old_link_copper(board, set(pin_nets.values()), cleanup_box)
        for net_name, endpoints in removed.items():
            cut_goals[net_name].extend(endpoints)

    extra_routes: list[tuple[str, list[Endpoint]]] = []
    if side == "right":
        removed = remove_old_link_copper(
            board, {"/right/RROW2"}, (44.0, 143.0, 56.0, 153.0)
        )
        if removed.get("/right/RROW2"):
            extra_routes.append(("/right/RROW2", removed["/right/RROW2"]))

    cut_goals = {
        net_name: one_goal_per_component(board, net_name, endpoints)
        for net_name, endpoints in cut_goals.items()
    }
    extra_routes = [
        (net_name, one_goal_per_component(board, net_name, endpoints))
        for net_name, endpoints in extra_routes
    ]
    remove_link_labels(board)

    connector = load_vertical_phd(board, reference, position, angle)
    for pin, net_name in pin_nets.items():
        set_pad_net(board, connector, pin, net_name)

    if not os.environ.get("SKIP_ROUTING"):
        # Reserve every dog-bone first so no later pad escape can cross a
        # route that has already been solved.
        escapes = {
            pin: add_pad_escape(board, pin_nets[pin], connector, pin)
            for pin in pin_nets
        }
        for net_name, endpoints in extra_routes:
            unique = list(dict.fromkeys((e.x, e.y, e.layer) for e in endpoints))
            if len(unique) >= 2:
                start = Endpoint(*unique[0])
                for raw_goal in unique[1:]:
                    goal = Endpoint(*raw_goal)
                    router = LocalRouter(board, net_name, start, goal, 28.0)
                    router.add(router.solve())
        # Route the longest fanout paths first; short local connections can
        # then use the remaining channels between the two pad rows.
        route_order = (
            ("1", "2", "8", "9", "11", "10", "7", "5", "4", "6", "12", "3")
            if side == "right"
            else ("1", "6", "2", "12", "9", "7", "11", "10", "3", "5", "8", "4")
        )
        for pin in route_order:
            net_name = pin_nets[pin]
            origin = pad_endpoint(connector, pin)
            raw_goals = cut_goals.get(net_name, [])
            unique_goals = list(
                dict.fromkeys((goal.x, goal.y, goal.layer) for goal in raw_goals)
            )
            goals = [Endpoint(*raw_goal) for raw_goal in unique_goals]
            if not goals:
                goals = [nearest_copper_endpoint(board, net_name, origin, 2.5)]
            goals.sort(
                key=lambda goal: math.hypot(
                    goal.x - escapes[pin].x, goal.y - escapes[pin].y
                )
            )
            route_start = escapes[pin]
            for goal in goals:
                route_link_escape(
                    board, net_name, connector, pin, route_start, goal
                )

    add_label(board, "LEFT LINK", *label_positions[0], 0.0, pcbnew.F_SilkS)
    add_label(board, "PHD-12 TOP", *label_positions[1], 0.0, pcbnew.F_SilkS)


def main(left_in: Path, right_in: Path, left_out: Path, right_out: Path) -> None:
    routerlib.TRACE_WIDTH = NEW_TRACE_WIDTH
    routerlib.VIA_DIAMETER = NEW_VIA_DIAMETER
    routerlib.VIA_DRILL = NEW_VIA_DRILL
    routerlib.ROUTER_CLEARANCE = 0.14
    routerlib.GRID = 0.10
    left = pcbnew.LoadBoard(str(left_in))
    right = pcbnew.LoadBoard(str(right_in))
    only_side = os.environ.get("ONLY_SIDE")
    if only_side != "right":
        replace_link(left, "left")
    if only_side != "left":
        replace_link(right, "right")
    # Keep the project's existing manufacturing minima; only the newly added
    # fanout uses the more conservative dimensions above.
    routerlib.TRACE_WIDTH = TRACE_WIDTH
    routerlib.VIA_DIAMETER = VIA_DIAMETER
    routerlib.VIA_DRILL = VIA_DRILL
    routerlib.ROUTER_CLEARANCE = 0.14
    routerlib.GRID = 0.15
    finish(left, left_out)
    finish(right, right_out)
    print(f"saved {left_out}")
    print(f"saved {right_out}")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit(
            f"usage: {sys.argv[0]} LEFT_IN RIGHT_IN LEFT_OUT RIGHT_OUT"
        )
    main(*(Path(arg) for arg in sys.argv[1:]))
