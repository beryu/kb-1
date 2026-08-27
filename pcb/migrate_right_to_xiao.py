#!/usr/bin/env python3
"""Create the XIAO nRF52840 Plus placement for the right PCB.

Run with KiCad's bundled Python/pcbnew module.  The script writes to the
explicit output path so the generated board can be reviewed before replacing
the checked-in board.
"""

from pathlib import Path
import sys

import wx

_WX_APP = wx.App(False)

import pcbnew


ROOT = Path(__file__).resolve().parent
LOCAL_FP = ROOT / "Library.pretty"
KICAD_FP = Path(
    "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
)


def mm(x: float) -> int:
    return pcbnew.FromMM(x)


def pos(x: float, y: float) -> pcbnew.VECTOR2I:
    # VECTOR2I_MM selects an integer overload when one coordinate is a whole
    # number, which truncates the other coordinate (for example 117.3 -> 117).
    return pcbnew.VECTOR2I(mm(x), mm(y))


def get_or_create_net(board: pcbnew.BOARD, name: str) -> pcbnew.NETINFO_ITEM:
    net = board.FindNet(name)
    if net is None:
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
    return net


def set_pad_net(
    board: pcbnew.BOARD, footprint: pcbnew.FOOTPRINT, number: str, name: str
) -> None:
    pad = footprint.FindPadByNumber(number)
    if pad is None:
        raise RuntimeError(f"{footprint.GetReference()}: pad {number} not found")
    pad.SetNet(get_or_create_net(board, name))


def add_footprint(
    board: pcbnew.BOARD,
    lib: Path,
    name: str,
    reference: str,
    value: str,
    x: float,
    y: float,
    angle: float = 0,
    back: bool = False,
) -> pcbnew.FOOTPRINT:
    footprint = pcbnew.FootprintLoad(str(lib), name)
    if footprint is None:
        raise RuntimeError(f"Cannot load footprint {lib}:{name}")
    footprint.SetReference(reference)
    footprint.SetValue(value)
    footprint.SetPosition(pos(x, y))
    footprint.SetOrientationDegrees(angle)
    board.Add(footprint)
    if back:
        footprint.Flip(pos(x, y), False)
    return footprint


def remove_footprint(board: pcbnew.BOARD, reference: str) -> None:
    footprint = board.FindFootprintByReference(reference)
    if footprint is not None:
        board.Remove(pcbnew.Cast_to_FOOTPRINT(footprint))


def intersects(item: pcbnew.BOARD_ITEM, x1: float, y1: float, x2: float, y2: float) -> bool:
    start = item.GetStart()
    end = item.GetEnd()
    if isinstance(item, pcbnew.PCB_VIA):
        width = pcbnew.ToMM(item.GetWidth(pcbnew.F_Cu)) / 2
    else:
        width = pcbnew.ToMM(item.GetWidth()) / 2
    left = min(pcbnew.ToMM(start.x), pcbnew.ToMM(end.x)) - width
    top = min(pcbnew.ToMM(start.y), pcbnew.ToMM(end.y)) - width
    right = max(pcbnew.ToMM(start.x), pcbnew.ToMM(end.x)) + width
    bottom = max(pcbnew.ToMM(start.y), pcbnew.ToMM(end.y)) + width
    return not (right < x1 or left > x2 or bottom < y1 or top > y2)


def add_antenna_keepout(board: pcbnew.BOARD) -> None:
    zone = pcbnew.ZONE(board)
    zone.SetIsRuleArea(True)
    zone.SetDoNotAllowTracks(True)
    zone.SetDoNotAllowVias(True)
    zone.SetDoNotAllowZoneFills(True)
    # The rule area deliberately sits under the XIAO's own antenna.  Copper and
    # vias are forbidden, but the XIAO footprint itself must be allowed.
    zone.SetDoNotAllowFootprints(False)
    layers = pcbnew.LSET()
    layers.AddLayer(pcbnew.F_Cu)
    layers.AddLayer(pcbnew.B_Cu)
    zone.SetLayerSet(layers)
    outline = zone.Outline()
    outline.NewOutline()
    for x, y in ((45.0, 134.2), (58.8, 134.2), (58.8, 145.2), (45.0, 145.2)):
        outline.Append(pos(x, y))
    board.Add(zone)


def add_label(board: pcbnew.BOARD, text: str, x: float, y: float, angle: float = 0) -> None:
    label = pcbnew.PCB_TEXT(board)
    label.SetText(text)
    label.SetPosition(pos(x, y))
    label.SetLayer(pcbnew.F_SilkS)
    label.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
    label.SetTextThickness(mm(0.12))
    label.SetTextAngle(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T))
    board.Add(label)


def add_track(
    board: pcbnew.BOARD,
    net_name: str,
    points: tuple[tuple[float, float], ...],
    layer: int,
    width: float = 0.25,
) -> None:
    net = get_or_create_net(board, net_name)
    for start, end in zip(points, points[1:]):
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(pos(*start))
        track.SetEnd(pos(*end))
        track.SetWidth(mm(width))
        track.SetLayer(layer)
        track.SetNet(net)
        board.Add(track)


def add_via(
    board: pcbnew.BOARD, net_name: str, x: float, y: float, diameter: float = 0.65
) -> None:
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(pos(x, y))
    via.SetWidth(mm(diameter))
    via.SetDrill(mm(0.3))
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNet(get_or_create_net(board, net_name))
    board.Add(via)


def migrate(input_path: Path, output_path: Path) -> None:
    board = pcbnew.LoadBoard(str(input_path))
    existing_tracks = list(board.GetTracks())
    existing_footprints = list(board.GetFootprints())

    for footprint in existing_footprints:
        if footprint.GetReference() == "J201":
            footprint.SetPosition(pos(51.9, 127.5))
    for footprint in existing_footprints:
        if footprint.GetReference() in ("U201", "D201", "R201"):
            board.Remove(footprint)

    # Remove the old MCU/LED fan-out and all copper below the antenna area.
    tracks_to_remove = []
    for item in existing_tracks:
        if intersects(item, 42.0, 114.5, 61.8, 138.7) or intersects(
            item, 45.0, 134.2, 58.8, 145.2
        ) or intersects(item, 35.8, 112.5, 41.8, 124.5):
            tracks_to_remove.append(item)
    for item in tracks_to_remove:
        board.Remove(item)

    boot = board.FindNet("/right/BOOT")
    if boot is not None:
        boot.SetNetname("/right/RESET_N")

    xiao = add_footprint(
        board,
        LOCAL_FP,
        "XIAO-nRF52840-Plus-SMD",
        "U201",
        "XIAO nRF52840 Plus",
        51.9,
        127.5,
        90,
    )
    xiao_nets = {
        "1": "/right/VBAT_ADC",
        "2": "/right/ROW0",
        "3": "/right/COL2",
        "4": "/right/COL4",
        "5": "/right/ROW3",
        "6": "/right/COL6",
        "7": "VCC",
        "8": "/right/CS",
        "9": "/right/SCLK",
        "10": "/right/MOTION",
        "11": "/right/SDIO",
        "12": "/right/SYS_3V3",
        "13": "GND",
        "15": "/right/ROW1",
        "16": "/right/COL1",
        "17": "/right/COL3",
        "18": "/right/COL0",
        "21": "/right/ROW4",
        "22": "/right/ROW2",
        "23": "/right/COL5",
        "24": "/right/SWDIO",
        "25": "/right/SWDCLK",
        "26": "/right/RESET_N",
        "27": "GND",
        "29": "GND",
    }
    for number, name in xiao_nets.items():
        set_pad_net(board, xiao, number, name)

    boost = add_footprint(
        board, LOCAL_FP, "AE-XCL103-3V3", "U202", "AE-XCL103-3V3", 51.9, 149.0
    )
    for number, name in {
        "1": "GND",
        "3": "+BATT",
        "4": "+BATT",
        "5": "GND",
        "6": "/right/BOOST_3V3",
    }.items():
        set_pad_net(board, boost, number, name)

    ideal = add_footprint(
        board,
        KICAD_FP / "Package_TO_SOT_SMD.pretty",
        "SOT-23-5",
        "U203",
        "XC8111AA01MR-G",
        51.3,
        149.0,
        90,
        True,
    )
    for number, name in {
        "1": "/right/BOOST_3V3",
        "2": "GND",
        "3": "/right/BOOST_3V3",
        "5": "/right/SYS_3V3",
    }.items():
        set_pad_net(board, ideal, number, name)

    c_bulk = add_footprint(
        board,
        KICAD_FP / "Capacitor_SMD.pretty",
        "C_0805_2012Metric",
        "C201",
        "10uF X7R",
        50.2,
        154.0,
        0,
        True,
    )
    c_dec = add_footprint(
        board,
        KICAD_FP / "Capacitor_SMD.pretty",
        "C_0603_1608Metric",
        "C202",
        "0.1uF X7R",
        53.5,
        154.0,
        0,
        True,
    )
    for capacitor in (c_bulk, c_dec):
        set_pad_net(board, capacitor, "1", "/right/SYS_3V3")
        set_pad_net(board, capacitor, "2", "GND")

    r_adc = add_footprint(
        board,
        KICAD_FP / "Resistor_SMD.pretty",
        "R_0603_1608Metric",
        "R201",
        "10k",
        40.5,
        119.9,
        0,
        False,
    )
    set_pad_net(board, r_adc, "1", "+BATT")
    set_pad_net(board, r_adc, "2", "/right/VBAT_ADC")
    c_adc = add_footprint(
        board,
        KICAD_FP / "Capacitor_SMD.pretty",
        "C_0603_1608Metric",
        "C203",
        "0.1uF X7R",
        39.5,
        122.5,
        0,
        False,
    )
    set_pad_net(board, c_adc, "1", "/right/VBAT_ADC")
    set_pad_net(board, c_adc, "2", "GND")

    test_nets = (
        ("TP201", "SWDIO", "/right/SWDIO", 48.0, 119.0),
        ("TP202", "SWDCLK", "/right/SWDCLK", 53.0, 119.0),
        ("TP203", "RESET", "/right/RESET_N", 45.0, 119.0),
        ("TP204", "3V3", "/right/SYS_3V3", 56.0, 119.0),
        ("TP205", "GND", "GND", 59.0, 119.0),
    )
    for reference, value, net_name, x, y in test_nets:
        testpoint = add_footprint(
            board,
            KICAD_FP / "TestPoint.pretty",
            "TestPoint_Pad_D1.5mm",
            reference,
            value,
            x,
            y,
            back=True,
        )
        # TestPoint_Pad_D1.5mm snaps to an integer-mm anchor during Flip().
        # Restore the requested sub-mm position afterwards.
        testpoint.SetPosition(pos(x, y))
        set_pad_net(board, testpoint, "1", net_name)
        testpoint.Reference().SetVisible(False)
        testpoint.Value().SetVisible(False)

    # Routing is intentionally left for KiCad's interactive router.  The old
    # board is very dense and straight-line scripted routes can silently cross
    # matrix and sensor nets.  This migration establishes the verified
    # placement, footprints, keepout and net assignments without introducing
    # unsafe copper.

    # Tracks removed from the old MCU fan-out leave their teardrop zones
    # behind.  Remove those obsolete copper islands only after all footprint
    # libraries have been loaded (KiCad's SWIG bindings invalidate the plugin
    # loader if zone objects are destroyed earlier in the run).
    obsolete_teardrops = []
    for zone in board.Zones():
        if not zone.IsTeardropArea():
            continue
        box = zone.GetBoundingBox()
        left = pcbnew.ToMM(box.GetLeft())
        right = pcbnew.ToMM(box.GetRight())
        top = pcbnew.ToMM(box.GetTop())
        bottom = pcbnew.ToMM(box.GetBottom())
        in_mcu_area = not (right < 42.0 or left > 61.8 or bottom < 114.5 or top > 145.2)
        in_led_area = not (right < 35.8 or left > 41.8 or bottom < 112.5 or top > 124.5)
        if in_mcu_area or in_led_area:
            obsolete_teardrops.append(zone)
    for zone in obsolete_teardrops:
        board.Remove(zone)

    add_antenna_keepout(board)

    for drawing in board.GetDrawings():
        if isinstance(drawing, pcbnew.PCB_TEXT) and drawing.GetText() == "BMP Boost":
            drawing.SetText("XIAO nRF52840 Plus")
            drawing.SetPosition(pos(62.0, 137.0))
            drawing.SetTextAngle(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T))

    add_label(board, "ANTENNA KEEPOUT", 46.0, 143.7)

    board.BuildListOfNets()
    board.SynchronizeNetsAndNetClasses(True)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output_path), board)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} INPUT.kicad_pcb OUTPUT.kicad_pcb")
    migrate(Path(sys.argv[1]), Path(sys.argv[2]))
