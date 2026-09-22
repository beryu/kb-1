#!/usr/bin/env python3
"""Convert both kb-1 halves to one USB-powered XIAO and a passive cable link.

The right PCB retains the XIAO and pointing-device connector.  The left PCB
becomes a passive switch/diode matrix.  A 12-circuit Samtec SHF right-angle
header on the back of each PCB carries four left rows, seven shared columns,
and ground.  The headers mate with a keyed FFTP twisted-pair cable assembly.

Run with KiCad's bundled Python/pcbnew module:

    migrate_to_single_xiao_wired.py LEFT_IN RIGHT_IN LEFT_OUT RIGHT_OUT
"""

from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from pathlib import Path
import math
import sys

import pcbnew


ROOT = Path(__file__).resolve().parent
SHF_LIBRARY = ROOT / "Library.pretty"
SHF_FOOTPRINT = "Samtec_SHF-106-01-L-D-RA"

TRACE_WIDTH = 0.15
VIA_DIAMETER = 0.40
VIA_DRILL = 0.20
CLEARANCE = 0.14
ROUTER_CLEARANCE = 0.14
EDGE_MARGIN = 0.25
GRID = 0.15

F = 0
B = 1
LAYER_ID = (pcbnew.F_Cu, pcbnew.B_Cu)


def mm(value: float) -> int:
    return pcbnew.FromMM(value)


def point(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(mm(x), mm(y))


def get_or_create_net(board: pcbnew.BOARD, name: str) -> pcbnew.NETINFO_ITEM:
    net = board.FindNet(name)
    if net is None:
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
    return net


def set_pad_net(
    board: pcbnew.BOARD, footprint: pcbnew.FOOTPRINT, number: str, name: str | None
) -> None:
    pad = footprint.FindPadByNumber(number)
    if pad is None:
        raise RuntimeError(f"{footprint.GetReference()}: pad {number} not found")
    if name is None:
        pad.SetNetCode(0)
    else:
        pad.SetNet(get_or_create_net(board, name))


def rename_net(board: pcbnew.BOARD, old: str, new: str) -> None:
    net = board.FindNet(old)
    if net is None:
        raise RuntimeError(f"net not found: {old}")
    if board.FindNet(new) is not None:
        raise RuntimeError(f"target net already exists: {new}")
    net.SetNetname(new)


def remove_net_copper(board: pcbnew.BOARD, names: set[str]) -> None:
    for item in list(board.GetTracks()):
        if item.GetNetname() in names:
            board.RemoveNative(item)


def remove_footprints(board: pcbnew.BOARD, references: set[str]) -> None:
    for reference in references:
        footprint = board.FindFootprintByReference(reference)
        if footprint is not None:
            board.RemoveNative(footprint)


def load_shf(
    board: pcbnew.BOARD,
    reference: str,
    x: float,
    y: float,
    angle: float,
) -> pcbnew.FOOTPRINT:
    # Build the footprint in memory instead of depending on KiCad's GUI-backed
    # plugin loader.  The checked-in .kicad_mod is the editable library source;
    # these dimensions mirror it so this migration also works headlessly.
    footprint = pcbnew.FOOTPRINT(board)
    footprint.SetFPID(pcbnew.LIB_ID("Library", SHF_FOOTPRINT))
    footprint.SetReference(reference)
    footprint.SetValue("SHF-106-01-L-D-RA")
    footprint.SetLayer(pcbnew.B_Cu)
    footprint.Reference().SetLayer(pcbnew.B_SilkS)
    footprint.Reference().SetVisible(False)
    footprint.Value().SetLayer(pcbnew.B_Fab)
    footprint.Value().SetVisible(False)
    for index in range(12):
        pad = pcbnew.PAD(footprint)
        pad.SetNumber(str(index + 1))
        pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
        pad.SetShape(pcbnew.PAD_SHAPE_RECT if index == 0 else pcbnew.PAD_SHAPE_CIRCLE)
        pad.SetSize(pcbnew.VECTOR2I(mm(1.0), mm(1.0)))
        pad.SetDrillSize(pcbnew.VECTOR2I(mm(0.65), mm(0.65)))
        pad.SetLayerSet(pad.PTHMask())
        pad.SetPosition(point(1.27 if index % 2 else 0.0, 1.27 * (index // 2)))
        footprint.Add(pad)

    def fp_line(
        start: tuple[float, float],
        end: tuple[float, float],
        layer: int,
        width: float,
    ) -> None:
        line = pcbnew.PCB_SHAPE(footprint)
        line.SetShape(pcbnew.SHAPE_T_SEGMENT)
        line.SetStart(point(*start))
        line.SetEnd(point(*end))
        line.SetLayer(layer)
        line.SetWidth(mm(width))
        footprint.Add(line)

    body = [(-0.95, -2.92), (9.91, -2.92), (9.91, 9.27), (-0.95, 9.27)]
    for start, end in zip(body, body[1:] + body[:1]):
        fp_line(start, end, pcbnew.B_Fab, 0.1)
    silk = [(-0.95, -1.2), (0.1, -2.92), (9.91, -2.92), (9.91, 9.27), (-0.95, 9.27), (-0.95, -1.2)]
    for start, end in zip(silk, silk[1:]):
        fp_line(start, end, pcbnew.B_SilkS, 0.12)
    courtyard = [(-1.25, -3.22), (10.21, -3.22), (10.21, 9.57), (-1.25, 9.57)]
    for start, end in zip(courtyard, courtyard[1:] + courtyard[:1]):
        fp_line(start, end, pcbnew.B_CrtYd, 0.05)

    footprint.SetPosition(point(x, y))
    footprint.SetOrientationDegrees(angle)
    footprint.SetAttributes(
        footprint.GetAttributes()
        | pcbnew.FP_EXCLUDE_FROM_BOM
        | pcbnew.FP_EXCLUDE_FROM_POS_FILES
    )
    board.Add(footprint)
    return footprint


def add_label(
    board: pcbnew.BOARD,
    value: str,
    x: float,
    y: float,
    angle: float = 0,
    layer: int = pcbnew.F_SilkS,
) -> None:
    label = pcbnew.PCB_TEXT(board)
    label.SetText(value)
    label.SetPosition(point(x, y))
    label.SetTextAngle(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T))
    label.SetLayer(layer)
    label.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
    label.SetTextThickness(mm(0.12))
    board.Add(label)


def clean_obsolete_labels(board: pcbnew.BOARD) -> None:
    obsolete = {
        "XCL103D503CR-G",
        "XC8111AA01MR-G",
        "BOOST",
        "BATTERY",
        "BMP Boost",
    }
    for drawing in list(board.GetDrawings()):
        if isinstance(drawing, pcbnew.PCB_TEXT):
            text = drawing.GetText()
            if text in obsolete or "BATT" in text or "BOOST" in text:
                board.RemoveNative(drawing)


def pad_endpoint(footprint: pcbnew.FOOTPRINT, number: str) -> "Endpoint":
    pad = footprint.FindPadByNumber(number)
    if pad is None:
        raise RuntimeError(f"{footprint.GetReference()}: pad {number} missing")
    position = pad.GetPosition()
    if pad.IsOnLayer(pcbnew.F_Cu) and pad.IsOnLayer(pcbnew.B_Cu):
        layer = None
    elif pad.IsOnLayer(pcbnew.F_Cu):
        layer = F
    elif pad.IsOnLayer(pcbnew.B_Cu):
        layer = B
    else:
        raise RuntimeError(f"{footprint.GetReference()}:{number} has no copper layer")
    return Endpoint(pcbnew.ToMM(position.x), pcbnew.ToMM(position.y), layer)


@dataclass(frozen=True)
class Endpoint:
    x: float
    y: float
    layer: int | None


def item_net(item) -> str:
    try:
        return item.GetNetname()
    except Exception:
        return ""


def box_mm(item) -> tuple[float, float, float, float]:
    box = item.GetBoundingBox()
    return (
        pcbnew.ToMM(box.GetLeft()),
        pcbnew.ToMM(box.GetTop()),
        pcbnew.ToMM(box.GetRight()),
        pcbnew.ToMM(box.GetBottom()),
    )


class LocalRouter:
    def __init__(
        self,
        board: pcbnew.BOARD,
        net_name: str,
        start: Endpoint,
        goal: Endpoint,
        margin: float = 16.0,
    ) -> None:
        self.board = board
        self.net_name = net_name
        self.start = start
        self.goal = goal
        self.x_min = min(start.x, goal.x) - margin
        self.x_max = max(start.x, goal.x) + margin
        self.y_min = min(start.y, goal.y) - margin
        self.y_max = max(start.y, goal.y) + margin
        self.nx = round((self.x_max - self.x_min) / GRID) + 1
        self.ny = round((self.y_max - self.y_min) / GRID) + 1

    def cell(self, x: float, y: float) -> tuple[int, int]:
        return (
            round((x - self.x_min) / GRID),
            round((y - self.y_min) / GRID),
        )

    def xy(self, ix: int, iy: int) -> tuple[float, float]:
        return self.x_min + ix * GRID, self.y_min + iy * GRID

    def mark_box(
        self,
        blocked: list[set[tuple[int, int]]],
        layers,
        bounds,
        inflate: float,
    ) -> None:
        left, top, right, bottom = bounds
        ix0, iy0 = self.cell(left - inflate, top - inflate)
        ix1, iy1 = self.cell(right + inflate, bottom + inflate)
        for layer in layers:
            target = blocked[layer]
            for ix in range(max(0, ix0), min(self.nx - 1, ix1) + 1):
                for iy in range(max(0, iy0), min(self.ny - 1, iy1) + 1):
                    target.add((ix, iy))

    def obstacles(
        self,
    ) -> tuple[list[set[tuple[int, int]]], list[set[tuple[int, int]]]]:
        blocked = [set(), set()]
        via_blocked = [set(), set()]
        outline = pcbnew.SHAPE_POLY_SET()
        self.board.GetBoardPolygonOutlines(outline, True)
        for ix in range(self.nx):
            for iy in range(self.ny):
                x, y = self.xy(ix, iy)
                probes = (
                    (x, y),
                    (x - EDGE_MARGIN, y),
                    (x + EDGE_MARGIN, y),
                    (x, y - EDGE_MARGIN),
                    (x, y + EDGE_MARGIN),
                )
                if any(not outline.Contains(point(px, py)) for px, py in probes):
                    blocked[F].add((ix, iy))
                    blocked[B].add((ix, iy))
                    via_blocked[F].add((ix, iy))
                    via_blocked[B].add((ix, iy))

        trace_inflate = ROUTER_CLEARANCE + TRACE_WIDTH / 2
        via_inflate = ROUTER_CLEARANCE + VIA_DIAMETER / 2
        for footprint in self.board.GetFootprints():
            for pad in footprint.Pads():
                if item_net(pad) == self.net_name:
                    continue
                layers = []
                if pad.IsOnLayer(pcbnew.F_Cu):
                    layers.append(F)
                if pad.IsOnLayer(pcbnew.B_Cu):
                    layers.append(B)
                if layers:
                    bounds = box_mm(pad)
                    self.mark_box(blocked, layers, bounds, trace_inflate)
                    self.mark_box(via_blocked, layers, bounds, via_inflate)

        for track in self.board.GetTracks():
            if item_net(track) == self.net_name:
                continue
            if isinstance(track, pcbnew.PCB_VIA):
                bounds = box_mm(track)
                self.mark_box(blocked, (F, B), bounds, trace_inflate)
                self.mark_box(via_blocked, (F, B), bounds, via_inflate)
            else:
                layer = F if track.GetLayer() == pcbnew.F_Cu else B
                bounds = box_mm(track)
                self.mark_box(blocked, (layer,), bounds, trace_inflate)
                self.mark_box(via_blocked, (layer,), bounds, via_inflate)

        # Filled copper zones are regenerated after routing.  Treating their
        # current bounding boxes as solid obstacles would make every ground
        # plane impassable; pad/track clearance and the final DRC are the
        # authoritative checks here.
        return blocked, via_blocked

    def solve(self):
        blocked, via_blocked = self.obstacles()
        sx, sy = self.cell(self.start.x, self.start.y)
        gx, gy = self.cell(self.goal.x, self.goal.y)
        start_layers = (F, B) if self.start.layer is None else (self.start.layer,)
        goal_layers = (F, B) if self.goal.layer is None else (self.goal.layer,)
        starts = [(sx, sy, layer) for layer in start_layers]
        goals = {(gx, gy, layer) for layer in goal_layers}
        for ix, iy, layer in starts:
            blocked[layer].discard((ix, iy))
            via_blocked[layer].discard((ix, iy))
        for ix, iy, layer in goals:
            blocked[layer].discard((ix, iy))
            via_blocked[layer].discard((ix, iy))

        def heuristic(node):
            ix, iy, layer = node
            return min(
                math.hypot(ix - gx, iy - gy) + (0 if layer == gl else 10)
                for _, _, gl in goals
            )

        moves = (
            (1, 0, 1.0),
            (-1, 0, 1.0),
            (0, 1, 1.0),
            (0, -1, 1.0),
            (1, 1, math.sqrt(2)),
            (1, -1, math.sqrt(2)),
            (-1, 1, math.sqrt(2)),
            (-1, -1, math.sqrt(2)),
        )
        queue = []
        distance = {}
        previous = {}
        serial = 0
        for node in starts:
            distance[node] = 0.0
            heappush(queue, (heuristic(node), 0.0, serial, node))
            serial += 1

        reached = None
        while queue:
            _, cost, _, current = heappop(queue)
            if cost != distance.get(current):
                continue
            if current in goals:
                reached = current
                break
            ix, iy, layer = current
            for dx, dy, move_cost in moves:
                nx, ny = ix + dx, iy + dy
                if not (0 <= nx < self.nx and 0 <= ny < self.ny):
                    continue
                if (nx, ny) in blocked[layer]:
                    continue
                nxt = (nx, ny, layer)
                new_cost = cost + move_cost
                if new_cost < distance.get(nxt, float("inf")):
                    distance[nxt] = new_cost
                    previous[nxt] = current
                    heappush(queue, (new_cost + heuristic(nxt), new_cost, serial, nxt))
                    serial += 1
            other = 1 - layer
            if (
                (ix, iy) not in blocked[other]
                and (ix, iy) not in via_blocked[F]
                and (ix, iy) not in via_blocked[B]
            ):
                nxt = (ix, iy, other)
                new_cost = cost + 12.0
                if new_cost < distance.get(nxt, float("inf")):
                    distance[nxt] = new_cost
                    previous[nxt] = current
                    heappush(queue, (new_cost + heuristic(nxt), new_cost, serial, nxt))
                    serial += 1

        if reached is None:
            raise RuntimeError(
                f"no route for {self.net_name}: {self.start} -> {self.goal}"
            )
        path = [reached]
        while path[-1] not in starts:
            path.append(previous[path[-1]])
        path.reverse()
        return path

    def add(self, path) -> None:
        net = self.board.FindNet(self.net_name)
        raw = [(self.start.x, self.start.y, path[0][2])]
        raw.extend((*self.xy(ix, iy), layer) for ix, iy, layer in path)
        raw.append((self.goal.x, self.goal.y, path[-1][2]))

        compact = [raw[0]]
        for item in raw[1:]:
            if item == compact[-1]:
                continue
            if len(compact) >= 2 and item[2] == compact[-1][2] == compact[-2][2]:
                ax, ay, _ = compact[-2]
                bx, by, _ = compact[-1]
                cx, cy, _ = item
                if abs((bx - ax) * (cy - by) - (by - ay) * (cx - bx)) < 1e-6:
                    compact[-1] = item
                    continue
            compact.append(item)

        for a, b in zip(compact, compact[1:]):
            if a[2] != b[2]:
                via = pcbnew.PCB_VIA(self.board)
                via.SetPosition(point(a[0], a[1]))
                via.SetWidth(mm(VIA_DIAMETER))
                via.SetDrill(mm(VIA_DRILL))
                via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                via.SetNet(net)
                self.board.Add(via)
            elif abs(a[0] - b[0]) > 1e-6 or abs(a[1] - b[1]) > 1e-6:
                track = pcbnew.PCB_TRACK(self.board)
                track.SetStart(point(a[0], a[1]))
                track.SetEnd(point(b[0], b[1]))
                track.SetWidth(mm(TRACE_WIDTH))
                track.SetLayer(LAYER_ID[a[2]])
                track.SetNet(net)
                self.board.Add(track)


def route_pads(
    board: pcbnew.BOARD,
    net_name: str,
    start_fp: pcbnew.FOOTPRINT,
    start_pad: str,
    goal_fp: pcbnew.FOOTPRINT,
    goal_pad: str,
    margin: float = 16.0,
) -> None:
    router = LocalRouter(
        board,
        net_name,
        pad_endpoint(start_fp, start_pad),
        pad_endpoint(goal_fp, goal_pad),
        margin,
    )
    path = router.solve()
    router.add(path)
    print(
        f"routed {net_name}: {start_fp.GetReference()}:{start_pad} -> "
        f"{goal_fp.GetReference()}:{goal_pad} ({len(path)} nodes)"
    )


def nearest_copper_endpoint(
    board: pcbnew.BOARD, net_name: str, origin: Endpoint, min_distance: float = 0.0
) -> Endpoint:
    """Return the closest point on existing routed copper for a net."""
    best: tuple[float, Endpoint] | None = None
    for item in board.GetTracks():
        if item_net(item) != net_name:
            continue
        if isinstance(item, pcbnew.PCB_VIA):
            pos = item.GetPosition()
            candidate = Endpoint(pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y), None)
        else:
            start = item.GetStart()
            end = item.GetEnd()
            ax, ay = pcbnew.ToMM(start.x), pcbnew.ToMM(start.y)
            bx, by = pcbnew.ToMM(end.x), pcbnew.ToMM(end.y)
            dx, dy = bx - ax, by - ay
            length2 = dx * dx + dy * dy
            if length2 == 0:
                ratio = 0.0
            else:
                ratio = max(
                    0.0,
                    min(1.0, ((origin.x - ax) * dx + (origin.y - ay) * dy) / length2),
                )
            candidate = Endpoint(
                ax + ratio * dx,
                ay + ratio * dy,
                F if item.GetLayer() == pcbnew.F_Cu else B,
            )
        distance = math.hypot(candidate.x - origin.x, candidate.y - origin.y)
        if distance < min_distance:
            continue
        if best is None or distance < best[0]:
            best = (distance, candidate)
    if best is None:
        raise RuntimeError(f"no routed copper found for {net_name}")
    return best[1]


def route_pad_to_endpoint(
    board: pcbnew.BOARD,
    net_name: str,
    start_fp: pcbnew.FOOTPRINT,
    start_pad: str,
    goal: Endpoint,
    margin: float = 16.0,
) -> None:
    start = pad_endpoint(start_fp, start_pad)
    if start_fp.GetValue() == "SHF-106-01-L-D-RA":
        pad_x = [pcbnew.ToMM(pad.GetPosition().x) for pad in start_fp.Pads()]
        center_x = (min(pad_x) + max(pad_x)) / 2
        escape_layer = B if start.x < center_x else F
        escape = Endpoint(
            start.x + (-1.2 if start.x < center_x else 1.2),
            start.y,
            escape_layer,
        )
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(point(start.x, start.y))
        track.SetEnd(point(escape.x, escape.y))
        track.SetWidth(mm(TRACE_WIDTH))
        track.SetLayer(LAYER_ID[escape_layer])
        track.SetNet(board.FindNet(net_name))
        board.Add(track)
        start = escape
    router = LocalRouter(board, net_name, start, goal, margin)
    try:
        path = router.solve()
        router.add(path)
    except RuntimeError:
        distance = math.hypot(start.x - goal.x, start.y - goal.y)
        if distance > 3.0 or goal.layer is None:
            raise
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(point(start.x, start.y))
        track.SetEnd(point(goal.x, goal.y))
        track.SetWidth(mm(TRACE_WIDTH))
        track.SetLayer(LAYER_ID[goal.layer])
        track.SetNet(board.FindNet(net_name))
        board.Add(track)
        path = [(0, 0, goal.layer)]
    print(
        f"routed {net_name}: {start_fp.GetReference()}:{start_pad} -> "
        f"copper@({goal.x:.2f},{goal.y:.2f}) ({len(path)} nodes)"
    )


LINK_PIN_NETS = {
    "1": "GND",
    "2": "COL0",
    "3": "COL1",
    "4": "COL2",
    "5": "COL3",
    "6": "COL4",
    "7": "COL5",
    "8": "COL6",
    "9": "LROW0",
    "10": "LROW1",
    "11": "LROW2",
    "12": "LROW3",
}

XIAO_MATRIX_PADS = {
    "LROW0": "1",
    "LROW1": "2",
    "LROW2": "7",
    "LROW3": "19",
    "RROW0": "15",
    "RROW1": "22",
    "RROW2": "5",
    "RROW3": "21",
    "COL0": "18",
    "COL1": "16",
    "COL2": "3",
    "COL3": "17",
    "COL4": "4",
    "COL5": "23",
    "COL6": "6",
}

OLD_MATRIX_PADS = {
    "ROW1": "15",
    "ROW2": "22",
    "ROW3": "5",
    "ROW4": "21",
    "COL0": "18",
    "COL1": "16",
    "COL2": "3",
    "COL3": "17",
    "COL4": "4",
    "COL5": "23",
    "COL6": "6",
}


def assign_link_nets(
    board: pcbnew.BOARD, connector: pcbnew.FOOTPRINT, side: str
) -> dict[str, str]:
    names = {}
    for pin, short_name in LINK_PIN_NETS.items():
        name = "GND" if short_name == "GND" else f"/{side}/{short_name}"
        set_pad_net(board, connector, pin, name)
        names[short_name] = name
    return names


def fill_former_battery_slot(board: pcbnew.BOARD, side: str) -> None:
    """Turn the old battery cutout into solid PCB for the link connector."""
    if side == "left":
        obsolete = {
            frozenset(((133.0, 52.4), (133.0, 103.4))),
            frozenset(((133.0, 103.4), (147.3, 103.4))),
            frozenset(((147.3, 52.4), (133.0, 52.4))),
        }
        replacement = ((147.3, 52.4), (147.3, 103.4))
    else:
        obsolete = {
            frozenset(((27.5, 178.4), (41.5, 178.4))),
            frozenset(((41.5, 127.4), (27.5, 127.4))),
            frozenset(((41.5, 178.4), (41.5, 127.4))),
        }
        replacement = ((27.5, 127.4), (27.5, 178.4))

    removed = set()
    for drawing in list(board.GetDrawings()):
        if not isinstance(drawing, pcbnew.PCB_SHAPE):
            continue
        if drawing.GetLayer() != pcbnew.Edge_Cuts:
            continue
        if drawing.GetShape() != pcbnew.SHAPE_T_SEGMENT:
            continue
        start = drawing.GetStart()
        end = drawing.GetEnd()
        edge = frozenset(
            (
                (round(pcbnew.ToMM(start.x), 3), round(pcbnew.ToMM(start.y), 3)),
                (round(pcbnew.ToMM(end.x), 3), round(pcbnew.ToMM(end.y), 3)),
            )
        )
        if edge in obsolete:
            removed.add(edge)
            board.RemoveNative(drawing)
    if removed != obsolete:
        raise RuntimeError(f"{side}: battery-slot outline did not match")

    edge = pcbnew.PCB_SHAPE(board)
    edge.SetShape(pcbnew.SHAPE_T_SEGMENT)
    edge.SetStart(point(*replacement[0]))
    edge.SetEnd(point(*replacement[1]))
    edge.SetLayer(pcbnew.Edge_Cuts)
    edge.SetWidth(mm(0.1))
    board.Add(edge)


def edge_key(drawing: pcbnew.PCB_SHAPE) -> frozenset[tuple[float, float]] | None:
    if drawing.GetLayer() != pcbnew.Edge_Cuts:
        return None
    if drawing.GetShape() not in (pcbnew.SHAPE_T_SEGMENT, pcbnew.SHAPE_T_ARC):
        return None
    start = drawing.GetStart()
    end = drawing.GetEnd()
    return frozenset(
        (
            (round(pcbnew.ToMM(start.x), 3), round(pcbnew.ToMM(start.y), 3)),
            (round(pcbnew.ToMM(end.x), 3), round(pcbnew.ToMM(end.y), 3)),
        )
    )


def replace_edges(
    board: pcbnew.BOARD,
    expected: set[frozenset[tuple[float, float]]],
    replacements: list[tuple[tuple[float, float], tuple[float, float]]],
    side: str,
) -> None:
    removed = set()
    for drawing in list(board.GetDrawings()):
        if not isinstance(drawing, pcbnew.PCB_SHAPE):
            continue
        key = edge_key(drawing)
        if key in expected:
            removed.add(key)
            board.RemoveNative(drawing)
    if removed != expected:
        missing = expected - removed
        raise RuntimeError(f"{side}: compact outline did not match: {missing}")
    for start, end in replacements:
        edge = pcbnew.PCB_SHAPE(board)
        edge.SetShape(pcbnew.SHAPE_T_SEGMENT)
        edge.SetStart(point(*start))
        edge.SetEnd(point(*end))
        edge.SetLayer(pcbnew.Edge_Cuts)
        edge.SetWidth(mm(0.1))
        board.Add(edge)


def compact_inner_edge(board: pcbnew.BOARD, side: str) -> None:
    """Remove the unused rectangle beyond the back-mounted SHF connector."""
    if side == "left":
        expected = {
            frozenset(((78.5, 42.5), (146.3, 42.5))),
            frozenset(((146.3, 42.5), (147.3, 43.5))),
            frozenset(((147.3, 43.5), (147.3, 52.4))),
            frozenset(((147.3, 52.4), (147.3, 103.4))),
        }
        replacements = [
            ((78.5, 42.5), (136.3, 42.5)),
            ((136.3, 42.5), (137.3, 43.5)),
            ((137.3, 43.5), (137.3, 103.4)),
            ((137.3, 103.4), (147.3, 103.4)),
        ]
    else:
        expected = {
            frozenset(((27.5, 127.4), (27.5, 178.4))),
        }
        replacements = [
            ((27.5, 127.4), (27.5, 136.0)),
            ((27.5, 136.0), (37.5, 136.0)),
            ((37.5, 136.0), (37.5, 178.4)),
            ((37.5, 178.4), (27.5, 178.4)),
        ]
    replace_edges(board, expected, replacements, side)


def remove_copper_in_cutout(board: pcbnew.BOARD, side: str) -> None:
    """Delete copper that belonged to the rectangle removed from Edge.Cuts."""
    if side == "left":
        inside = lambda x, y: x > 137.25 and y < 103.45
    else:
        inside = lambda x, y: x < 37.55 and 135.95 < y < 178.45
    for item in list(board.GetTracks()):
        if isinstance(item, pcbnew.PCB_VIA):
            pos = item.GetPosition()
            points = [(pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y))]
        else:
            start = item.GetStart()
            end = item.GetEnd()
            points = [
                (pcbnew.ToMM(start.x), pcbnew.ToMM(start.y)),
                (pcbnew.ToMM(end.x), pcbnew.ToMM(end.y)),
            ]
        if any(inside(x, y) for x, y in points):
            board.RemoveNative(item)


def remove_link_labels(board: pcbnew.BOARD) -> None:
    for drawing in list(board.GetDrawings()):
        if not isinstance(drawing, pcbnew.PCB_TEXT):
            continue
        if drawing.GetText() in {"PHD-12", "SHF-12", "LEFT LINK"}:
            board.RemoveNative(drawing)


def upgrade_link_connector(board: pcbnew.BOARD, side: str) -> None:
    """Replace the already-migrated PHD connector without rebuilding the board."""
    reference = "J101" if side == "left" else "J202"
    old = board.FindFootprintByReference(reference)
    if old is None:
        raise RuntimeError(f"{side}: {reference} not found")
    connector = load_shf(
        board,
        f"{reference}NEW",
        126.6 if side == "left" else 48.0,
        68.0 if side == "left" else 147.0,
        0.0 if side == "left" else 180.0,
    )
    net_names = {}
    for pad in old.Pads():
        net_names[pad.GetNumber()] = pad.GetNetname()
    board.RemoveNative(old)
    connector.SetReference(reference)
    for pin, name in net_names.items():
        set_pad_net(board, connector, pin, name)

    compact_inner_edge(board, side)
    remove_copper_in_cutout(board, side)
    remove_link_labels(board)

    for pin in reversed(tuple(LINK_PIN_NETS)):
        net_name = net_names[pin]
        origin = pad_endpoint(connector, pin)
        goal = nearest_copper_endpoint(board, net_name, origin, 5.0)
        route_pad_to_endpoint(board, net_name, connector, pin, goal, 20.0)

    if side == "left":
        add_label(board, "LEFT LINK", 126.0, 79.5, 0.0, pcbnew.B_SilkS)
        add_label(board, "SHF-12", 132.0, 79.5, 0.0, pcbnew.B_SilkS)
    else:
        add_label(board, "LEFT LINK", 43.0, 135.0, 0.0, pcbnew.B_SilkS)
        add_label(board, "SHF-12", 49.0, 135.0, 0.0, pcbnew.B_SilkS)


def migrate_left(board: pcbnew.BOARD) -> None:
    xiao = board.FindFootprintByReference("U101")
    if xiao is None:
        raise RuntimeError("left XIAO U101 not found")

    fill_former_battery_slot(board, "left")

    for old_row, new_row in zip(range(1, 5), range(4)):
        rename_net(board, f"/left/ROW{old_row}", f"/left/LROW{new_row}")

    # Load the library footprint before deleting any board objects.  KiCad's
    # SWIG plugin loader can be invalidated by object deletion in this process.
    connector = load_shf(board, "J901", 126.6, 68.0, 0.0)

    obsolete_nets = {
        "+BATT",
        "Net-(BT101--)",
        "VCC",
        "/left/ROW0",
        "/left/VBAT_ADC",
        "/left/BOOST_EN",
        "/left/BOOST_5V",
        "/left/SYS_5V",
        "/left/SYS_3V3",
        "/left/CS",
        "/left/SCLK",
        "/left/MOTION",
        "/left/SDIO",
        "/left/SWDIO",
        "/left/SWDCLK",
        "/left/RESET_N",
    }
    remove_net_copper(board, obsolete_nets)
    remove_footprints(
        board,
        {
            "BT101",
            "C101",
            "C102",
            "C103",
            "C104",
            "J101",
            "R101",
            "R102",
            "SW101",
            "TP101",
            "TP102",
            "U102",
            "U103",
        },
    )

    connector.SetReference("J101")
    names = assign_link_nets(board, connector, "left")

    # Join each cable signal to the nearest point on the already-routed key
    # matrix.  This avoids forcing eleven traces through the former MCU fanout.
    goals = {}
    for key, net_name in names.items():
        if key != "GND":
            pin = next(pin for pin, name in LINK_PIN_NETS.items() if name == key)
            goals[key] = nearest_copper_endpoint(
                board, net_name, pad_endpoint(connector, pin)
            )

    route_pad_to_endpoint(
        board,
        "GND",
        connector,
        "1",
        nearest_copper_endpoint(board, "GND", pad_endpoint(connector, "1")),
        22.0,
    )

    for short_name, old_pad in OLD_MATRIX_PADS.items():
        if short_name.startswith("ROW"):
            key = f"LROW{int(short_name[-1]) - 1}"
        else:
            key = short_name
        pin = next(pin for pin, name in LINK_PIN_NETS.items() if name == key)
        route_pad_to_endpoint(board, names[key], connector, pin, goals[key], 22.0)

    board.RemoveNative(xiao)
    clean_obsolete_labels(board)
    compact_inner_edge(board, "left")
    remove_copper_in_cutout(board, "left")
    add_label(board, "LEFT LINK", 126.0, 79.5, 0.0, pcbnew.B_SilkS)
    add_label(board, "SHF-12", 132.0, 79.5, 0.0, pcbnew.B_SilkS)


def migrate_right(board: pcbnew.BOARD) -> None:
    xiao = board.FindFootprintByReference("U201")
    sensor = board.FindFootprintByReference("J201")
    if xiao is None or sensor is None:
        raise RuntimeError("right controller/sensor footprint missing")

    fill_former_battery_slot(board, "right")

    for old_row, new_row in zip(range(1, 5), range(4)):
        rename_net(board, f"/right/ROW{old_row}", f"/right/RROW{new_row}")

    # See the matching note in migrate_left().
    connector = load_shf(board, "J202", 48.0, 147.0, 180.0)

    obsolete_nets = {
        "+BATT",
        "Net-(BT201--)",
        "VCC",
        "/right/ROW0",
        "/right/VBAT_ADC",
        "/right/BOOST_EN",
        "/right/BOOST_5V",
        "/right/SYS_5V",
        "/right/RESET_N",
    }
    remove_net_copper(board, obsolete_nets)
    remove_footprints(
        board,
        {
            "BT201",
            "C201",
            "C202",
            "C203",
            "C204",
            "R201",
            "R202",
            "SW201",
            "TP203",
            "U202",
            "U203",
        },
    )

    for pad in ("1", "2", "7", "19", "20", "26"):
        set_pad_net(board, xiao, pad, None)
    for short_name, pad in XIAO_MATRIX_PADS.items():
        set_pad_net(board, xiao, pad, f"/right/{short_name}")
    set_pad_net(board, xiao, "12", "/right/SYS_3V3")
    set_pad_net(board, xiao, "13", "GND")
    set_pad_net(board, xiao, "14", None)
    set_pad_net(board, xiao, "20", None)  # D16/AIN7_BAT remains unused.
    set_pad_net(board, xiao, "28", None)  # Bottom BAT pad.

    # Pointing-device power is now the XIAO's regulated 3.3 V output rather
    # than a GPIO-controlled rail.
    sensor_vcc_pad = next(
        pad for pad in sensor.Pads() if pad.GetNetname() == "VCC"
    )
    sensor_vcc_pad.SetNet(get_or_create_net(board, "/right/SYS_3V3"))

    names = assign_link_nets(board, connector, "right")

    route_pad_to_endpoint(
        board,
        "GND",
        connector,
        "1",
        nearest_copper_endpoint(board, "GND", pad_endpoint(connector, "1")),
        24.0,
    )

    # Power the pointing device first, before the denser link fanout is added.
    route_pads(
        board,
        "/right/SYS_3V3",
        xiao,
        "12",
        sensor,
        sensor_vcc_pad.GetNumber(),
        14.0,
    )

    for short_name in ("LROW0", "LROW1", "LROW2", "LROW3"):
        pin = next(pin for pin, name in LINK_PIN_NETS.items() if name == short_name)
        route_pads(
            board,
            names[short_name],
            connector,
            pin,
            xiao,
            XIAO_MATRIX_PADS[short_name],
            24.0,
        )

    for short_name in ("COL0", "COL1", "COL2", "COL3", "COL4", "COL5", "COL6"):
        pin = next(pin for pin, name in LINK_PIN_NETS.items() if name == short_name)
        route_pad_to_endpoint(
            board,
            names[short_name],
            connector,
            pin,
            nearest_copper_endpoint(
                board, names[short_name], pad_endpoint(connector, pin)
            ),
            24.0,
        )

    clean_obsolete_labels(board)
    compact_inner_edge(board, "right")
    remove_copper_in_cutout(board, "right")
    add_label(board, "LEFT LINK", 43.0, 135.0, 0.0, pcbnew.B_SilkS)
    add_label(board, "SHF-12", 49.0, 135.0, 0.0, pcbnew.B_SilkS)


def finish(board: pcbnew.BOARD, output: Path) -> None:
    # Teardrops store links to their parent tracks/pads.  The legacy board has
    # many of them around parts removed above, so rebuild without teardrops to
    # avoid leaving invalid parent references in the saved board.
    for zone in list(board.Zones()):
        if zone.IsTeardropArea():
            board.RemoveNative(zone)
    # A route may change layers immediately beside an existing same-net via.
    # Keep the original via and remove the redundant generated drill when the
    # annular rings already overlap electrically.
    vias = [item for item in board.GetTracks() if isinstance(item, pcbnew.PCB_VIA)]
    redundant = []
    for index, first in enumerate(vias):
        if first in redundant:
            continue
        a = first.GetPosition()
        for second in vias[index + 1 :]:
            if second in redundant or item_net(first) != item_net(second):
                continue
            b = second.GetPosition()
            distance = math.hypot(pcbnew.ToMM(a.x - b.x), pcbnew.ToMM(a.y - b.y))
            overlap_limit = pcbnew.ToMM(
                first.GetWidth(pcbnew.F_Cu) + second.GetWidth(pcbnew.F_Cu)
            ) / 2
            if distance < overlap_limit:
                generated = first if first.GetDrillValue() < second.GetDrillValue() else second
                if generated not in redundant:
                    redundant.append(generated)
    for via in redundant:
        board.RemoveNative(via)
    settings = board.GetDesignSettings()
    settings.m_MinClearance = mm(CLEARANCE)
    settings.m_CopperEdgeClearance = mm(0.20)
    settings.m_HoleClearance = mm(0.20)
    settings.m_TrackMinWidth = mm(TRACE_WIDTH)
    settings.m_ViasMinSize = mm(VIA_DIAMETER)
    settings.m_MinThroughDrill = mm(VIA_DRILL)
    default = board.GetAllNetClasses()["Default"]
    default.SetClearance(mm(CLEARANCE))
    default.SetTrackWidth(mm(TRACE_WIDTH))
    default.SetViaDiameter(mm(VIA_DIAMETER))
    default.SetViaDrill(mm(VIA_DRILL))
    board.BuildListOfNets()
    board.SynchronizeNetsAndNetClasses(True)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output), board)


def main(left_in: Path, right_in: Path, left_out: Path, right_out: Path) -> None:
    left = pcbnew.LoadBoard(str(left_in))
    right = pcbnew.LoadBoard(str(right_in))
    if left.FindFootprintByReference("U101") is None:
        upgrade_link_connector(left, "left")
    else:
        migrate_left(left)
    right_link = right.FindFootprintByReference("J202")
    if right_link is not None and right_link.GetValue() == "S12B-PHDSS":
        upgrade_link_connector(right, "right")
    else:
        migrate_right(right)
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
