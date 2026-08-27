#!/usr/bin/env python3
"""Obstacle-aware two-layer router for the XIAO migration area.

This is intentionally limited to the explicit unrouted connections introduced
by migrate_right_to_xiao.py.  It does not rip up the original keyboard matrix.
"""

from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from pathlib import Path
import math
import sys

import wx

_WX_APP = wx.App(False)

import pcbnew


GRID = 0.20
X_MIN, X_MAX = 27.0, 82.0
Y_MIN, Y_MAX = 115.0, 180.0
TRACE_WIDTH = 0.20
VIA_DIAMETER = 0.50
VIA_DRILL = 0.30
CLEARANCE = 0.20
ROUTING_MARGIN = 0.00
EDGE_MARGIN = 0.65

F = 0
B = 1
LAYER_ID = (pcbnew.F_Cu, pcbnew.B_Cu)


@dataclass(frozen=True)
class Endpoint:
    x: float
    y: float
    layer: int


# The endpoints come from KiCad's DRC unconnected-item report.  Routes are
# ordered so the short, dense XIAO/FFC fan-out is established first.
CONNECTIONS: tuple[tuple[str, Endpoint, Endpoint], ...] = (
    ("/right/SDIO", Endpoint(60.155, 127.500, F), Endpoint(52.900, 127.500, B)),
    ("/right/MOTION", Endpoint(60.155, 130.040, F), Endpoint(50.900, 127.500, B)),
    ("/right/SCLK", Endpoint(60.155, 132.580, F), Endpoint(54.900, 127.500, B)),
    ("/right/CS", Endpoint(60.155, 135.120, F), Endpoint(48.900, 127.500, B)),
    ("VCC", Endpoint(43.645, 135.120, F), Endpoint(46.900, 127.500, B)),
    ("/right/COL5", Endpoint(60.555, 128.770, F), Endpoint(62.325, 129.700, B)),
    ("/right/ROW1", Endpoint(43.245, 121.150, F), Endpoint(63.700, 122.100, F)),
    ("/right/ROW2", Endpoint(60.555, 131.310, F), Endpoint(64.560, 135.060, F)),
    ("/right/COL1", Endpoint(43.245, 123.690, F), Endpoint(59.520, 142.680, F)),
    ("/right/COL2", Endpoint(43.645, 124.960, F), Endpoint(59.000, 143.700, F)),
    ("/right/COL3", Endpoint(43.245, 126.230, F), Endpoint(59.520, 145.220, F)),
    ("/right/COL4", Endpoint(43.645, 127.500, F), Endpoint(59.400, 146.500, F)),
    ("/right/ROW3", Endpoint(43.645, 130.040, F), Endpoint(58.300, 152.500, B)),
    ("/right/ROW4", Endpoint(60.555, 133.850, F), Endpoint(59.520, 140.140, F)),
    ("/right/COL0", Endpoint(43.245, 128.770, F), Endpoint(45.200, 155.400, F)),
    ("/right/COL6", Endpoint(43.645, 132.580, F), Endpoint(44.280, 162.655, B)),
    ("/right/SWDIO", Endpoint(50.630, 118.928, F), Endpoint(48.000, 119.000, B)),
    ("/right/SWDCLK", Endpoint(53.170, 118.928, F), Endpoint(53.000, 119.000, B)),
    ("/right/RESET_N", Endpoint(50.630, 121.468, F), Endpoint(35.200, 118.500, F)),
    ("/right/RESET_N", Endpoint(50.630, 121.468, F), Endpoint(45.000, 119.000, B)),
    ("/right/VBAT_ADC", Endpoint(41.325, 119.900, F), Endpoint(43.645, 119.880, F)),
    ("/right/VBAT_ADC", Endpoint(38.725, 122.500, F), Endpoint(41.325, 119.900, F)),
    ("+BATT", Endpoint(35.000, 122.800, F), Endpoint(39.675, 119.900, F)),
    ("+BATT", Endpoint(39.675, 119.900, F), Endpoint(48.090, 151.540, F)),
    ("+BATT", Endpoint(48.090, 151.540, F), Endpoint(55.710, 146.460, F)),
    ("/right/BOOST_3V3", Endpoint(55.710, 151.540, B), Endpoint(52.250, 150.138, B)),
    ("/right/BOOST_3V3", Endpoint(52.250, 150.138, B), Endpoint(50.350, 150.138, B)),
    ("/right/SYS_3V3", Endpoint(52.250, 147.863, B), Endpoint(51.150, 154.000, B)),
    ("/right/SYS_3V3", Endpoint(52.250, 147.863, B), Endpoint(54.275, 154.000, B)),
    ("/right/SYS_3V3", Endpoint(56.000, 119.000, B), Endpoint(60.155, 124.960, F)),
    ("/right/SYS_3V3", Endpoint(54.275, 154.000, B), Endpoint(56.000, 119.000, B)),
    ("GND", Endpoint(48.090, 146.460, B), Endpoint(51.300, 150.138, B)),
    ("GND", Endpoint(48.090, 146.460, F), Endpoint(40.275, 122.500, F)),
    ("GND", Endpoint(51.300, 150.138, B), Endpoint(52.725, 154.000, B)),
    ("GND", Endpoint(49.250, 154.000, B), Endpoint(55.710, 149.000, B)),
    ("GND", Endpoint(55.710, 149.000, B), Endpoint(52.725, 154.000, B)),
    ("GND", Endpoint(52.906, 133.018, F), Endpoint(53.170, 121.468, F)),
    ("Net-(BT201--)", Endpoint(30.300, 116.804, B), Endpoint(37.100, 177.925, B)),
    ("GND", Endpoint(49.250, 154.000, B), Endpoint(59.000, 119.000, B)),
    ("GND", Endpoint(49.250, 154.000, B), Endpoint(52.906, 133.018, F)),
    ("GND", Endpoint(56.900, 127.500, B), Endpoint(60.155, 122.420, F)),
)

# Dense, long matrix connections are routed before the shorter rows so they
# retain access to the narrow passages around the controller.
ROUTE_ORDER = (
    36, 37, 22, 23, 24, 5, 0, 1, 2, 3, 4, 29,
    11, 15, 13, 7, 9, 12, 14, 6, 8, 10,
    40,
    16, 17, 18, 19, 20, 21,
    25, 26, 27, 28, 30,
    34, 35, 32, 38, 39,
)

SECOND_PASS_ORDER = (14, 32)


def mm(value: float) -> int:
    return pcbnew.FromMM(value)


def point(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(mm(x), mm(y))


def cell(x: float, y: float) -> tuple[int, int]:
    return (round((x - X_MIN) / GRID), round((y - Y_MIN) / GRID))


def xy(ix: int, iy: int) -> tuple[float, float]:
    return (X_MIN + ix * GRID, Y_MIN + iy * GRID)


NX = round((X_MAX - X_MIN) / GRID) + 1
NY = round((Y_MAX - Y_MIN) / GRID) + 1


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


def mark_box(blocked: list[set[tuple[int, int]]], layers, bounds, inflate: float) -> None:
    left, top, right, bottom = bounds
    ix0, iy0 = cell(left - inflate, top - inflate)
    ix1, iy1 = cell(right + inflate, bottom + inflate)
    for layer in layers:
        target = blocked[layer]
        for ix in range(max(0, ix0), min(NX - 1, ix1) + 1):
            for iy in range(max(0, iy0), min(NY - 1, iy1) + 1):
                target.add((ix, iy))


def build_obstacles(board: pcbnew.BOARD, route_net: str) -> list[set[tuple[int, int]]]:
    blocked = [set(), set()]
    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, True)

    # Board exterior and cutouts.
    for ix in range(NX):
        for iy in range(NY):
            x, y = xy(ix, iy)
            probes = (
                (x, y),
                (x - EDGE_MARGIN, y), (x + EDGE_MARGIN, y),
                (x, y - EDGE_MARGIN), (x, y + EDGE_MARGIN),
            )
            if any(not outline.Contains(point(px, py)) for px, py in probes):
                blocked[F].add((ix, iy))
                blocked[B].add((ix, iy))

    for fp in board.GetFootprints():
        for pad in fp.Pads():
            net = item_net(pad)
            if net == route_net:
                continue
            layers = []
            if pad.IsOnLayer(pcbnew.F_Cu):
                layers.append(F)
            if pad.IsOnLayer(pcbnew.B_Cu):
                layers.append(B)
            if not layers:
                continue
            inflate = CLEARANCE + TRACE_WIDTH / 2 + ROUTING_MARGIN
            mark_box(blocked, layers, box_mm(pad), inflate)

    for track in board.GetTracks():
        net = item_net(track)
        if net == route_net:
            continue
        if isinstance(track, pcbnew.PCB_VIA):
            mark_box(blocked, (F, B), box_mm(track), CLEARANCE + TRACE_WIDTH / 2 + ROUTING_MARGIN)
        else:
            layer = F if track.GetLayer() == pcbnew.F_Cu else B
            mark_box(blocked, (layer,), box_mm(track), CLEARANCE + TRACE_WIDTH / 2 + ROUTING_MARGIN)

    # Copper teardrops from the retained board.
    for zone in board.Zones():
        if not zone.IsTeardropArea() or item_net(zone) == route_net:
            continue
        layers = []
        if zone.IsOnLayer(pcbnew.F_Cu):
            layers.append(F)
        if zone.IsOnLayer(pcbnew.B_Cu):
            layers.append(B)
        mark_box(blocked, layers, box_mm(zone), CLEARANCE + TRACE_WIDTH / 2 + ROUTING_MARGIN)

    # XIAO antenna keepout, with extra half-track margin.
    mark_box(blocked, (F, B), (45.0, 134.2, 58.8, 145.2), TRACE_WIDTH / 2)
    return blocked


MOVES = (
    (1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
    (1, 1, math.sqrt(2)), (1, -1, math.sqrt(2)),
    (-1, 1, math.sqrt(2)), (-1, -1, math.sqrt(2)),
)


def route(board: pcbnew.BOARD, net: str, start: Endpoint, goal: Endpoint):
    blocked = build_obstacles(board, net)
    sx, sy = cell(start.x, start.y)
    gx, gy = cell(goal.x, goal.y)
    starts = [(sx, sy, start.layer)]
    goals = {(gx, gy, goal.layer)}
    # PTH endpoints may be approached on either copper layer.
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            px, py = pcbnew.ToMM(pad.GetPosition().x), pcbnew.ToMM(pad.GetPosition().y)
            if item_net(pad) != net:
                continue
            if abs(px - start.x) < 0.02 and abs(py - start.y) < 0.02 and pad.IsOnLayer(pcbnew.F_Cu) and pad.IsOnLayer(pcbnew.B_Cu):
                starts = [(sx, sy, F), (sx, sy, B)]
            if abs(px - goal.x) < 0.02 and abs(py - goal.y) < 0.02 and pad.IsOnLayer(pcbnew.F_Cu) and pad.IsOnLayer(pcbnew.B_Cu):
                goals = {(gx, gy, F), (gx, gy, B)}

    for ix, iy, layer in starts:
        blocked[layer].discard((ix, iy))
    for ix, iy, layer in goals:
        blocked[layer].discard((ix, iy))

    def heuristic(node):
        ix, iy, layer = node
        return min(math.hypot(ix - gx, iy - gy) + (0 if layer == gl else 10) for _, _, gl in goals)

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
        for dx, dy, move_cost in MOVES:
            nx, ny = ix + dx, iy + dy
            if not (0 <= nx < NX and 0 <= ny < NY):
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
        if (ix, iy) not in blocked[other]:
            nxt = (ix, iy, other)
            new_cost = cost + 12.0
            if new_cost < distance.get(nxt, float("inf")):
                distance[nxt] = new_cost
                previous[nxt] = current
                heappush(queue, (new_cost + heuristic(nxt), new_cost, serial, nxt))
                serial += 1

    if reached is None:
        raise RuntimeError(f"no route for {net}: {start} -> {goal}")

    path = [reached]
    while path[-1] not in starts:
        path.append(previous[path[-1]])
    path.reverse()
    return path


def add_path(board: pcbnew.BOARD, net_name: str, start: Endpoint, goal: Endpoint, path) -> None:
    net = board.FindNet(net_name)
    if net is None:
        raise RuntimeError(f"net not found: {net_name}")

    # Convert the grid path into exact endpoints and collapse collinear runs.
    raw = [(start.x, start.y, path[0][2])]
    for ix, iy, layer in path:
        raw.append((*xy(ix, iy), layer))
    raw.append((goal.x, goal.y, path[-1][2]))

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
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(point(a[0], a[1]))
            via.SetWidth(mm(VIA_DIAMETER))
            via.SetDrill(mm(VIA_DRILL))
            via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            via.SetNet(net)
            board.Add(via)
            continue
        if abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) < 1e-6:
            continue
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(point(a[0], a[1]))
        track.SetEnd(point(b[0], b[1]))
        track.SetWidth(mm(TRACE_WIDTH))
        track.SetLayer(LAYER_ID[a[2]])
        track.SetNet(net)
        board.Add(track)


def add_forced_local_routes(board: pcbnew.BOARD) -> None:
    """Add short local escapes whose legal channel is narrower than GRID."""
    routes = (
        (
            "/right/VBAT_ADC",
            F,
            ((43.645, 119.880), (41.325, 119.900)),
        ),
        (
            "/right/VBAT_ADC",
            F,
            ((41.325, 119.900), (41.325, 121.300), (38.725, 121.300), (38.725, 122.500)),
        ),
        (
            "GND",
            B,
            ((51.300, 150.138), (51.300, 151.800), (50.200, 153.000), (49.250, 154.000)),
        ),
    )
    for net_name, layer, points in routes:
        net = board.FindNet(net_name)
        for start, end in zip(points, points[1:]):
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(point(*start))
            track.SetEnd(point(*end))
            track.SetWidth(mm(TRACE_WIDTH))
            track.SetLayer(LAYER_ID[layer])
            track.SetNet(net)
            board.Add(track)

def add_c203_ground_via(board: pcbnew.BOARD) -> None:
    """Connect C203 GND to the filled planes with one short via escape."""
    net = board.FindNet("GND")
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(point(40.275, 122.500))
    track.SetEnd(point(40.275, 123.500))
    track.SetWidth(mm(TRACE_WIDTH))
    track.SetLayer(pcbnew.F_Cu)
    track.SetNet(net)
    board.Add(track)
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(point(40.275, 123.500))
    via.SetWidth(mm(VIA_DIAMETER))
    via.SetDrill(mm(VIA_DRILL))
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNet(net)
    board.Add(via)

    # Join U202 pad 1 to the nearby routed GND branch.  Pad 5 is a separate
    # module pin, so both module ground pads need explicit board copper.
    stitch = pcbnew.PCB_TRACK(board)
    stitch.SetStart(point(48.090, 146.460))
    stitch.SetEnd(point(49.600, 147.400))
    stitch.SetWidth(mm(TRACE_WIDTH))
    stitch.SetLayer(pcbnew.B_Cu)
    stitch.SetNet(net)
    board.Add(stitch)


def main(input_path: Path, output_path: Path, second_pass: bool = False) -> None:
    board = pcbnew.LoadBoard(str(input_path))
    if not second_pass:
        # Establish the three dense local escapes first so all subsequent
        # routes treat them as copper obstacles instead of crossing them.
        add_forced_local_routes(board)
    failed = []
    order = SECOND_PASS_ORDER if second_pass else ROUTE_ORDER
    for index, connection_index in enumerate(order, 1):
        net, start, goal = CONNECTIONS[connection_index]
        try:
            path = route(board, net, start, goal)
        except RuntimeError as error:
            failed.append((connection_index, str(error)))
            print(f"{index:02d}/{len(order)} FAILED {error}")
            continue
        add_path(board, net, start, goal, path)
        print(f"{index:02d}/{len(order)} {net}: {len(path)} grid nodes")
    if not second_pass:
        add_c203_ground_via(board)
    board.BuildListOfNets()
    board.SynchronizeNetsAndNetClasses(True)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output_path), board)
    if failed:
        print(f"saved with {len(failed)} unrouted requested connections")


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        raise SystemExit(f"usage: {sys.argv[0]} INPUT.kicad_pcb OUTPUT.kicad_pcb [--second-pass]")
    if len(sys.argv) == 4 and sys.argv[3] != "--second-pass":
        raise SystemExit("the only supported optional argument is --second-pass")
    main(Path(sys.argv[1]), Path(sys.argv[2]), len(sys.argv) == 4)
