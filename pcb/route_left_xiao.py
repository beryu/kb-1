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


GRID = 0.10
X_MIN, X_MAX = 40.0, 148.0
Y_MIN, Y_MAX = 29.0, 106.0
TRACE_WIDTH = 0.20
VIA_DIAMETER = 0.50
VIA_DRILL = 0.30
CLEARANCE = 0.20
ROUTING_MARGIN = 0.15
EDGE_MARGIN = 0.65
Y_SHIFT = 2.6

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
_ORIGINAL_CONNECTIONS: tuple[tuple[str, Endpoint, Endpoint], ...] = (
    ("/left/VBAT_ADC", Endpoint(134.725, 45.000, F), Endpoint(114.945, 42.780, F)),
    ("/left/VBAT_ADC", Endpoint(136.325, 47.500, F), Endpoint(134.725, 45.000, F)),
    ("GND", Endpoint(122.000, 49.0625, B), Endpoint(122.000, 50.000, B)),
    ("GND", Endpoint(122.000, 50.000, B), Endpoint(121.450, 50.9375, B)),
    ("GND", Endpoint(124.206012, 55.917823, F), Endpoint(127.900, 71.800, B)),
    ("+BATT", Endpoint(122.550, 49.0625, B), Endpoint(119.450, 47.500, B)),
    ("+BATT", Endpoint(122.825, 46.000, B), Endpoint(122.550, 49.0625, B)),
    ("+BATT", Endpoint(134.675, 47.500, F), Endpoint(139.800, 47.800, F)),
    ("+BATT", Endpoint(134.675, 47.500, F), Endpoint(122.825, 46.000, B)),
    ("/left/COL2", Endpoint(44.525, 54.700, B), Endpoint(114.945, 47.860, F)),
    ("/left/COL4", Endpoint(78.525, 54.700, B), Endpoint(114.945, 50.400, F)),
    ("/left/ROW3", Endpoint(114.945, 52.940, F), Endpoint(112.551654, 60.125123, F)),
    ("/left/COL6", Endpoint(114.945, 55.480, F), Endpoint(112.525, 88.700, B)),
    ("VCC", Endpoint(114.945, 58.020, F), Endpoint(117.900, 71.800, B)),
    ("/left/CS", Endpoint(119.900, 71.800, B), Endpoint(131.455, 58.020, F)),
    ("/left/SCLK", Endpoint(125.900, 71.800, B), Endpoint(131.455, 55.480, F)),
    ("/left/MOTION", Endpoint(121.900, 71.800, B), Endpoint(131.455, 52.940, F)),
    ("/left/SDIO", Endpoint(123.900, 71.800, B), Endpoint(131.455, 50.400, F)),
    ("/left/SYS_3V3", Endpoint(124.8625, 49.050, B), Endpoint(126.775, 53.000, B)),
    ("/left/SYS_3V3", Endpoint(131.455, 47.860, F), Endpoint(124.8625, 49.050, B)),
    ("/left/ROW1", Endpoint(109.700, 47.100, F), Endpoint(114.545, 44.050, F)),
    ("/left/COL1", Endpoint(114.545, 46.590, F), Endpoint(107.300, 73.100, F)),
    ("/left/COL3", Endpoint(114.545, 49.130, F), Endpoint(108.700, 74.863604, F)),
    ("/left/COL0", Endpoint(114.545, 51.670, F), Endpoint(101.000, 61.500, F)),
    ("/left/ROW4", Endpoint(128.074, 97.326, B), Endpoint(131.855, 56.750, F)),
    ("/left/ROW2", Endpoint(103.350, 64.1005, B), Endpoint(131.855, 54.210, F)),
    ("/left/COL5", Endpoint(95.925, 77.900, F), Endpoint(131.855, 51.670, F)),
    ("/left/SWDIO", Endpoint(121.930, 41.8275, F), Endpoint(117.000, 43.500, B)),
    ("/left/SWDCLK", Endpoint(124.470, 41.8275, F), Endpoint(120.000, 43.500, B)),
    ("/left/RESET_N", Endpoint(121.930, 44.3675, F), Endpoint(139.600, 43.500, F)),
    ("Net-(BT101--)", Endpoint(139.800, 102.800, B), Endpoint(144.600, 43.500, B)),
    ("/left/BOOST_EN", Endpoint(121.175, 46.000, B), Endpoint(121.450, 49.0625, B)),
    ("/left/BOOST_3V3", Endpoint(122.550, 50.9375, B), Endpoint(119.275, 53.000, B)),
    ("/left/BOOST_3V3", Endpoint(127.1375, 50.950, B), Endpoint(127.1375, 49.050, B)),
    ("/left/BOOST_3V3", Endpoint(127.1375, 50.950, B), Endpoint(122.550, 50.9375, B)),
    ("GND", Endpoint(117.550, 47.500, B), Endpoint(121.350, 50.000, B)),
    ("GND", Endpoint(117.725, 53.000, B), Endpoint(121.350, 50.000, B)),
    ("GND", Endpoint(122.000, 49.0625, B), Endpoint(124.470, 44.3675, F)),
    ("GND", Endpoint(125.225, 53.000, B), Endpoint(124.206012, 55.917823, F)),
    ("GND", Endpoint(127.1375, 50.000, B), Endpoint(125.225, 53.000, B)),
    ("GND", Endpoint(136.275, 45.000, F), Endpoint(131.455, 45.320, F)),
)


def relocated(endpoint: Endpoint) -> Endpoint:
    """Apply the compact-top layout shift to controller and battery endpoints."""
    in_controller_group = endpoint.x >= 114.5 and endpoint.y < 60.2
    is_battery_bottom = (
        abs(endpoint.x - 139.8) < 0.01 and abs(endpoint.y - 102.8) < 0.01
    )
    if in_controller_group or is_battery_bottom:
        return Endpoint(endpoint.x, endpoint.y + Y_SHIFT, endpoint.layer)
    return endpoint


CONNECTIONS: tuple[tuple[str, Endpoint, Endpoint], ...] = tuple(
    (net, relocated(start), relocated(goal))
    for net, start, goal in _ORIGINAL_CONNECTIONS
) + (
    # Join the retained matrix trunks to the newly routed XIAO fan-out.  The
    # original far-side endpoints alone can land on another same-net island.
    ("/left/COL2", Endpoint(100.400, 44.600, F), Endpoint(114.945, 50.460, F)),
    ("/left/COL4", Endpoint(108.000, 53.500, F), Endpoint(114.945, 53.000, F)),
    ("/left/COL6", Endpoint(112.300, 75.760, F), Endpoint(114.945, 58.080, F)),
    ("GND", Endpoint(142.100, 46.100, F), Endpoint(136.275, 47.600, F)),
)

# Dense, long matrix connections are routed before the shorter rows so they
# retain access to the narrow passages around the controller.
ROUTE_ORDER = (
    21, 20, 41, 42, 43,
    18, 19, 27, 28, 29,
    4, 17, 15, 16, 14, 13,
    22, 11, 26, 24, 25, 30, 23,
    8, 7, 1, 0,
)

SECOND_PASS_ORDER = (35, 36, 37, 38, 39, 40, 9, 10, 44)


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
    mark_box(blocked, (F, B), (118.8, 60.6, 124.0, 64.2), TRACE_WIDTH / 2)
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
        via_radius_cells = max(1, round((VIA_DIAMETER - TRACE_WIDTH) / 2 / GRID))
        via_is_clear = True
        for vx in range(ix - via_radius_cells, ix + via_radius_cells + 1):
            for vy in range(iy - via_radius_cells, iy + via_radius_cells + 1):
                if not (0 <= vx < NX and 0 <= vy < NY):
                    via_is_clear = False
                    break
                if (vx, vy) in blocked[F] or (vx, vy) in blocked[B]:
                    via_is_clear = False
                    break
            if not via_is_clear:
                break
        if via_is_clear:
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
    """Add compact B-side power routes whose channels are narrower than GRID."""
    routes = (
        (
            "GND", B,
            ((122.000, 49.0625), (122.000, 50.000), (121.350, 50.000),
             (121.450, 50.9375)),
        ),
        (
            "+BATT", B,
            ((122.825, 46.000), (122.825, 44.800), (119.450, 44.800),
             (119.450, 47.500)),
        ),
        (
            "+BATT", B,
            ((122.550, 49.0625), (122.550, 48.000), (123.800, 48.000),
             (123.800, 46.000),
             (122.825, 46.000)),
        ),
        (
            "/left/BOOST_EN", B,
            ((121.175, 46.000), (120.800, 47.200), (121.450, 48.200),
             (121.450, 49.0625)),
        ),
        (
            "/left/BOOST_3V3", B,
            ((122.550, 50.9375), (122.550, 51.700), (121.000, 52.200),
             (119.275, 53.000)),
        ),
        (
            "/left/BOOST_3V3", B,
            ((127.1375, 50.950), (128.200, 50.950), (128.200, 49.050),
             (127.1375, 49.050)),
        ),
        (
            "/left/BOOST_3V3", B,
            ((122.550, 50.9375), (122.550, 51.700), (123.500, 52.200),
             (128.000, 52.200), (128.000, 50.950), (127.1375, 50.950)),
        ),
    )
    for net_name, layer, points in routes:
        points = tuple((x, y + Y_SHIFT) for x, y in points)
        net = board.FindNet(net_name)
        for start, end in zip(points, points[1:]):
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(point(*start))
            track.SetEnd(point(*end))
            track.SetWidth(mm(TRACE_WIDTH))
            track.SetLayer(LAYER_ID[layer])
            track.SetNet(net)
            board.Add(track)


def add_forced_compact_routes(board: pcbnew.BOARD) -> None:
    """Hook for compact-layout routes that cannot be handled automatically."""
    routes = ()
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
    global ROUTING_MARGIN
    if second_pass:
        ROUTING_MARGIN = 0.00
    board = pcbnew.LoadBoard(str(input_path))
    if not second_pass:
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
        add_forced_compact_routes(board)
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
