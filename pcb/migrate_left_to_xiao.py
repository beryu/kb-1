#!/usr/bin/env python3
"""Create the 180-degree mirrored XIAO placement for the left PCB."""

from pathlib import Path
import sys

from migrate_right_to_xiao import (
    KICAD_FP,
    LOCAL_FP,
    add_footprint,
    add_label,
    get_or_create_net,
    intersects,
    mm,
    pos,
    set_pad_net,
)

import pcbnew


def add_antenna_keepout(board: pcbnew.BOARD) -> None:
    zone = pcbnew.ZONE(board)
    zone.SetIsRuleArea(True)
    zone.SetDoNotAllowTracks(True)
    zone.SetDoNotAllowVias(True)
    zone.SetDoNotAllowZoneFills(True)
    zone.SetDoNotAllowFootprints(False)
    layers = pcbnew.LSET()
    layers.AddLayer(pcbnew.F_Cu)
    layers.AddLayer(pcbnew.B_Cu)
    zone.SetLayerSet(layers)
    outline = zone.Outline()
    outline.NewOutline()
    for x, y in ((116.3, 57.1), (130.1, 57.1), (130.1, 68.1), (116.3, 68.1)):
        outline.Append(pos(x, y))
    board.Add(zone)


def migrate(input_path: Path, output_path: Path) -> None:
    board = pcbnew.LoadBoard(str(input_path))
    existing_tracks = list(board.GetTracks())
    existing_footprints = list(board.GetFootprints())

    for footprint in existing_footprints:
        if footprint.GetReference() in ("U101", "D101", "R101"):
            board.RemoveNative(footprint)
        elif footprint.GetReference() == "J101":
            footprint.SetPosition(pos(122.9, 71.8))

    tracks_to_remove = []
    for item in existing_tracks:
        if intersects(item, 113.0, 31.1, 132.8, 75.8) or intersects(
            item, 116.3, 57.1, 130.1, 68.1
        ) or intersects(item, 133.0, 45.3, 139.0, 57.3):
            tracks_to_remove.append(item)
    for item in tracks_to_remove:
        board.RemoveNative(item)

    boot = board.FindNet("/left/BOOT")
    if boot is not None:
        boot.SetNetname("/left/RESET_N")

    xiao = add_footprint(
        board, LOCAL_FP, "XIAO-nRF52840-Plus-SMD", "U101",
        "XIAO nRF52840 Plus", 123.2, 50.4, 90,
    )
    xiao_nets = {
        "1": "/left/VBAT_ADC",
        "2": "/left/ROW0",
        "3": "/left/COL2",
        "4": "/left/COL4",
        "5": "/left/ROW3",
        "6": "/left/COL6",
        "7": "VCC",
        "8": "/left/CS",
        "9": "/left/SCLK",
        "10": "/left/MOTION",
        "11": "/left/SDIO",
        "12": "/left/SYS_3V3",
        "13": "GND",
        "15": "/left/ROW1",
        "16": "/left/COL1",
        "17": "/left/COL3",
        "18": "/left/COL0",
        "21": "/left/ROW4",
        "22": "/left/ROW2",
        "23": "/left/COL5",
        "24": "/left/SWDIO",
        "25": "/left/SWDCLK",
        "26": "/left/RESET_N",
        "27": "GND",
        "29": "GND",
    }
    for number, net_name in xiao_nets.items():
        set_pad_net(board, xiao, number, net_name)

    boost = add_footprint(
        board, LOCAL_FP, "CL-2025-02", "U102",
        "XCL103D333CR-G", 122.0, 50.0, 0, True,
    )
    for number, net_name in {
        "1": "+BATT", "2": "GND", "3": "/left/BOOST_EN",
        "4": "GND", "6": "/left/BOOST_3V3", "9": "GND",
    }.items():
        set_pad_net(board, boost, number, net_name)

    ideal = add_footprint(
        board, KICAD_FP / "Package_TO_SOT_SMD.pretty", "SOT-23-5",
        "U103", "XC8111AA01MR-G", 126.0, 50.0, 0, True,
    )
    for number, net_name in {
        "1": "/left/BOOST_3V3", "2": "GND",
        "3": "/left/BOOST_3V3", "5": "/left/SYS_3V3",
    }.items():
        set_pad_net(board, ideal, number, net_name)

    c_bulk = add_footprint(
        board, KICAD_FP / "Capacitor_SMD.pretty", "C_0805_2012Metric",
        "C101", "10uF X7R (CIN)", 118.5, 47.5, 0, True,
    )
    c_dec = add_footprint(
        board, KICAD_FP / "Capacitor_SMD.pretty", "C_0603_1608Metric",
        "C102", "10uF X7R (CL)", 118.5, 53.0, 0, True,
    )
    set_pad_net(board, c_bulk, "1", "+BATT")
    set_pad_net(board, c_bulk, "2", "GND")
    set_pad_net(board, c_dec, "1", "/left/BOOST_3V3")
    set_pad_net(board, c_dec, "2", "GND")

    r_enable = add_footprint(
        board, KICAD_FP / "Resistor_SMD.pretty", "R_0603_1608Metric",
        "R102", "100k", 122.0, 46.0, 0, True,
    )
    set_pad_net(board, r_enable, "1", "+BATT")
    set_pad_net(board, r_enable, "2", "/left/BOOST_EN")

    c_sys = add_footprint(
        board, KICAD_FP / "Capacitor_SMD.pretty", "C_0603_1608Metric",
        "C104", "0.1uF X7R", 126.0, 53.0, 0, True,
    )
    set_pad_net(board, c_sys, "1", "/left/SYS_3V3")
    set_pad_net(board, c_sys, "2", "GND")

    r_adc = add_footprint(
        board, KICAD_FP / "Resistor_SMD.pretty", "R_0603_1608Metric",
        "R101", "10k", 135.5, 47.5, 0,
    )
    set_pad_net(board, r_adc, "1", "+BATT")
    set_pad_net(board, r_adc, "2", "/left/VBAT_ADC")
    c_adc = add_footprint(
        board, KICAD_FP / "Capacitor_SMD.pretty", "C_0603_1608Metric",
        "C103", "0.1uF X7R", 135.5, 45.0, 0,
    )
    set_pad_net(board, c_adc, "1", "/left/VBAT_ADC")
    set_pad_net(board, c_adc, "2", "GND")

    test_nets = (
        ("TP101", "SWDIO", "/left/SWDIO", 117.0, 43.5),
        ("TP102", "SWDCLK", "/left/SWDCLK", 120.0, 43.5),
    )
    for reference, value, net_name, x, y in test_nets:
        testpoint = add_footprint(
            board, KICAD_FP / "TestPoint.pretty", "TestPoint_Pad_D1.5mm",
            reference, value, x, y, 180, True,
        )
        testpoint.SetPosition(pos(x, y))
        set_pad_net(board, testpoint, "1", net_name)
        testpoint.Reference().SetVisible(False)
        testpoint.Value().SetVisible(False)

    obsolete_teardrops = []
    for zone in board.Zones():
        if not zone.IsTeardropArea():
            continue
        box = zone.GetBoundingBox()
        left = pcbnew.ToMM(box.GetLeft())
        right = pcbnew.ToMM(box.GetRight())
        top = pcbnew.ToMM(box.GetTop())
        bottom = pcbnew.ToMM(box.GetBottom())
        in_mcu_area = not (
            right < 113.0 or left > 132.8 or bottom < 31.1 or top > 75.8
        )
        in_led_area = not (
            right < 133.0 or left > 139.0 or bottom < 45.3 or top > 57.3
        )
        if in_mcu_area or in_led_area:
            obsolete_teardrops.append(zone)
    for zone in obsolete_teardrops:
        board.RemoveNative(zone)

    add_antenna_keepout(board)
    for drawing in board.GetDrawings():
        if isinstance(drawing, pcbnew.PCB_TEXT) and drawing.GetText() == "BMP Boost":
            drawing.SetText("XIAO nRF52840 Plus")
            drawing.SetPosition(pos(112.0, 52.0))
            drawing.SetTextAngle(pcbnew.EDA_ANGLE(90, pcbnew.DEGREES_T))
    add_label(board, "ANTENNA KEEPOUT", 117.3, 66.6, 0)

    board.BuildListOfNets()
    board.SynchronizeNetsAndNetClasses(True)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(str(output_path), board)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} INPUT.kicad_pcb OUTPUT.kicad_pcb")
    migrate(Path(sys.argv[1]), Path(sys.argv[2]))
