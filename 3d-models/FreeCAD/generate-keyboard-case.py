#!/usr/bin/env python3
"""Generate the torabo-tsuki-om keyboard case with FreeCAD.

Run with FreeCAD's Python interpreter, not CPython::

    freecadcmd -c "exec(open('3d-models/FreeCAD/generate-keyboard-case.py').read())"

The KiCad board outline and footprint positions are the source of truth.  The
generated FCStd file deliberately contains named, simple Part::Feature objects
so it remains convenient to inspect and modify in the FreeCAD GUI.
"""

from __future__ import annotations

import math
import os
import re
from pathlib import Path

import FreeCAD as App
import Part
import Mesh


# ---------------------------------------------------------------------------
# Human-editable dimensions (all values are millimetres)
# ---------------------------------------------------------------------------

BOTTOM_THICKNESS = 1.5
TOP_THICKNESS = 1.5
PCB_THICKNESS = 1.6
PCB_CLEARANCE = 0.25
WALL_THICKNESS = 1.8

# Clear height from the PCB top surface to the underside of the switch plate.
# This keeps the plate off the XIAO USB connector and other top-side parts.
TOP_PLATE_GAP = 3.5

# GB-BH-4X1-WP dimensions from its published mechanical drawing. The holder is
# mounted beside the PCB using its bent B.Cu pins, rests on the case floor, and
# is hidden by a raised cap that is part of the removable top plate.
BATTERY_HOLDER_BODY = (51.0, 13.0)
BATTERY_HOLDER_HEIGHT = 12.0
BATTERY_HOLDER_CLEARANCE = 0.8
BATTERY_HOLDER_VERTICAL_CLEARANCE = 0.8

# Kailh Choc V2 nominal plate opening. Increase for printer compensation.
SWITCH_WINDOW = 13.8

# The white component area of the XIAO that should remain visible.  Local X is
# along the 21 mm side of the XIAO footprint; local Y is along its 17.8 mm side.
XIAO_WHITE_WINDOW = (13.0, 10.0)
XIAO_WHITE_WINDOW_OFFSET = (-1.8, 0.0)

# Reset and LED positions are expressed in the XIAO footprint's local
# coordinate system. Coordinates come from Seeed's official XIAO nRF52840 Plus
# v1.1 KiCad PCB (K1, RGB6, and CHG0). The reset hole is intentionally generous
# enough for a 1.5 mm pin tool.
XIAO_RESET_OFFSET = (8.5725, -5.715)
XIAO_RESET_DIAMETER = 3.0
XIAO_LED_OFFSETS = ((7.6835, 5.715), (9.8425, 5.715))
XIAO_LED_DIAMETER = 2.2

# Trackball-case mount copied from the Edge.Cuts construction in
# torabo-tsuki-lp-S-ortho-mini-bottom.kicad_pcb. The original board has a
# 44.2 x 2.0 mm slot and leaves a 2.8 mm lip between that slot and its front
# edge. The printed slot is widened to 2.4 mm so an M2 x 3.5 screw passes without
# depending on printer over-extrusion tolerance. On the new right-hand tray the
# complete U-shaped PCB recess becomes a supporting floor, rather than
# reproducing only the old board's 4.8 mm tab.
TRACKBALL_MOUNT_SLOT_WIDTH = 44.2
TRACKBALL_MOUNT_SLOT_DEPTH = 2.4
TRACKBALL_MOUNT_FRONT_LIP = 2.8

# Bottom-side head recess for the M2 x 3.5 mm FX-0235EB low-profile screws
# referenced by build-guide.md. The manufacturer lists a 4.0 mm head diameter
# and 0.3 mm head height. Add 0.2 mm diametral and 0.1 mm depth clearance for
# printing. Since the screw position is adjustable along the mount slot, the
# shallow flat-bottom recess follows the full slot instead of using fixed round
# counterbores. This is not a conical countersink.
TRACKBALL_SCREW_HEAD_DIAMETER = 4.0
TRACKBALL_SCREW_HEAD_CLEARANCE = 0.2
TRACKBALL_SCREW_HEAD_RECESS_DEPTH = 0.4

# Only an edge-on FFC cable passes through the rear wall of the trackball
# recess. Cut the rightmost quarter of the third switch window counted from the
# right: 13.8 / 4 = 3.45 mm. This is deliberately much narrower than the FFC
# adapter footprint because the connector itself remains inside the case.
FFC_WALL_OPENING_WIDTH = SWITCH_WINDOW / 4

# Case fastening through the four 4.9 mm PCB mounting holes on each half. Use
# the same M2 x 3.5 mm screws as the separate trackball-case mount. A 4.6 mm
# printed boss passes through each PCB hole and receives an M2 heat-set insert
# from above. The removable top plate has a simple M2 clearance hole; the screw
# head remains accessible from the top. No countersink is generated.
PCB_MOUNTING_HOLE_DIAMETER = 4.9
SCREW_BOSS_DIAMETER = 4.6
CASE_SCREW_LENGTH = 3.5
M2_INSERT_PILOT_DIAMETER = 3.2
M2_INSERT_PILOT_DEPTH = 4.0
M2_TOP_CLEARANCE_DIAMETER = 2.4

SIDES = ("left", "right")
PCB_FILENAMES = {
    side: f"torabo-tsuki-lp-S-ortho-mini-{side}.kicad_pcb" for side in SIDES
}

SCRIPT_RELATIVE_PATH = Path("3d-models/FreeCAD/generate-keyboard-case.py")
REQUIRED_PCB = Path("pcb") / PCB_FILENAMES["left"]


def _tokenize(text: str):
    """Yield the small subset of S-expression tokens used by KiCad."""
    pattern = re.compile(r'"(?:\\.|[^"\\])*"|\(|\)|[^\s()]+')
    for match in pattern.finditer(text):
        token = match.group(0)
        if token.startswith('"'):
            yield token[1:-1].replace(r'\"', '"').replace("\\\\", "\\")
        else:
            yield token


def _parse_sexpr(text: str):
    stack = []
    root = None
    for token in _tokenize(text):
        if token == "(":
            node = []
            if stack:
                stack[-1].append(node)
            stack.append(node)
            if root is None:
                root = node
        elif token == ")":
            if not stack:
                raise ValueError("unmatched ')' in KiCad file")
            stack.pop()
        else:
            if not stack:
                raise ValueError("token outside S-expression")
            stack[-1].append(token)
    if stack:
        raise ValueError("unterminated S-expression in KiCad file")
    return root


def _children(node, name):
    return [item for item in node if isinstance(item, list) and item and item[0] == name]


def _child(node, name):
    found = _children(node, name)
    return found[0] if found else None


def _number(value):
    return float(value)


def _xy(node, name):
    item = _child(node, name)
    if item is None or len(item) < 3:
        raise ValueError(f"missing ({name} x y)")
    return (_number(item[1]), _number(item[2]))


def _distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _ordered_edges(records, tolerance=0.02):
    """Order and orient unordered Edge.Cuts line/arc records into one loop."""
    if not records:
        raise ValueError("no Edge.Cuts geometry found")
    remaining = list(records[1:])
    ordered = [records[0]]
    while remaining:
        tail = ordered[-1]["end"]
        for index, record in enumerate(remaining):
            if _distance(tail, record["start"]) <= tolerance:
                ordered.append(record)
                remaining.pop(index)
                break
            if _distance(tail, record["end"]) <= tolerance:
                reversed_record = dict(record)
                reversed_record["start"], reversed_record["end"] = (
                    record["end"],
                    record["start"],
                )
                ordered.append(reversed_record)
                remaining.pop(index)
                break
        else:
            raise ValueError(
                f"Edge.Cuts is not one connected loop near {tail}; "
                f"{len(remaining)} segment(s) remain"
            )
    if _distance(ordered[-1]["end"], ordered[0]["start"]) > tolerance:
        raise ValueError("Edge.Cuts loop is not closed")
    return ordered


def _board_data(path: Path):
    root = _parse_sexpr(path.read_text(encoding="utf-8"))
    records = []
    footprints = []

    for item in root:
        if not isinstance(item, list) or not item:
            continue
        if item[0] in ("gr_line", "gr_arc"):
            layer = _child(item, "layer")
            if not layer or len(layer) < 2 or layer[1] != "Edge.Cuts":
                continue
            record = {
                "kind": item[0],
                "start": _xy(item, "start"),
                "end": _xy(item, "end"),
            }
            if item[0] == "gr_arc":
                record["mid"] = _xy(item, "mid")
            records.append(record)
        elif item[0] == "footprint":
            at = _child(item, "at")
            if at is None:
                continue
            reference = ""
            for prop in _children(item, "property"):
                if len(prop) >= 3 and prop[1] == "Reference":
                    reference = prop[2]
                    break
            footprints.append(
                {
                    "name": item[1],
                    "reference": reference,
                    "layer": (_child(item, "layer") or ["layer", ""])[1],
                    "x": _number(at[1]),
                    "y": _number(at[2]),
                    "angle": _number(at[3]) if len(at) > 3 else 0.0,
                }
            )

    records = _ordered_edges(records)
    points = [r["start"] for r in records] + [records[-1]["end"]]
    min_x = min(p[0] for p in points)
    max_y = max(p[1] for p in points)

    # KiCad Y grows downwards. Reflect it so the FreeCAD top view matches the
    # physical board while keeping a conventional right-handed coordinate set.
    def transform(point):
        return (point[0] - min_x, max_y - point[1])

    for record in records:
        record["start"] = transform(record["start"])
        record["end"] = transform(record["end"])
        if "mid" in record:
            record["mid"] = transform(record["mid"])
    for footprint in footprints:
        footprint["cad_x"], footprint["cad_y"] = transform(
            (footprint["x"], footprint["y"])
        )
        footprint["cad_angle"] = -footprint["angle"]

    return {
        "records": records,
        "footprints": footprints,
        "origin_x": min_x,
        "origin_max_y": max_y,
        "transform": transform,
    }


def _wire_from_records(records):
    edges = []
    for record in records:
        start = App.Vector(*record["start"], 0)
        end = App.Vector(*record["end"], 0)
        if record["kind"] == "gr_line":
            edges.append(Part.makeLine(start, end))
        else:
            mid = App.Vector(*record["mid"], 0)
            edges.append(Part.Arc(start, mid, end).toShape())
    return Part.Wire(edges)


def _largest_wire(shape):
    wires = list(shape.Wires)
    if not wires:
        raise ValueError("2D offset did not produce a wire")
    return max(wires, key=lambda wire: abs(Part.Face(wire).Area))


def _offset_wire(wire, distance):
    """Return an outward offset regardless of the source loop orientation."""
    candidates = []
    for signed_distance in (distance, -distance):
        result = wire.makeOffset2D(signed_distance, 0, False, False, False)
        candidate = result if result.ShapeType == "Wire" else _largest_wire(result)
        candidates.append(candidate)
    return max(candidates, key=lambda candidate: abs(Part.Face(candidate).Area))


def _rotated_box(width, height, x, y, angle, z=0.0, depth=1.0):
    box = Part.makeBox(width, height, depth, App.Vector(-width / 2, -height / 2, z))
    box.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), angle)
    box.translate(App.Vector(x, y, 0))
    return box


def _rotated_rectangle_face(width, height, x, y, angle):
    face = Part.makePlane(
        width,
        height,
        App.Vector(-width / 2, -height / 2, 0),
    )
    face.rotate(App.Vector(0, 0, 0), App.Vector(0, 0, 1), angle)
    face.translate(App.Vector(x, y, 0))
    return face


def _local_point(footprint, offset):
    angle = math.radians(footprint["cad_angle"])
    # KiCad's local footprint coordinates use the same downward-positive Y
    # convention as the board. The board import reflects Y for FreeCAD, so the
    # local offset must be reflected as well before applying the CAD rotation.
    dx, kicad_dy = offset
    dy = -kicad_dy
    return (
        footprint["cad_x"] + dx * math.cos(angle) - dy * math.sin(angle),
        footprint["cad_y"] + dx * math.sin(angle) + dy * math.cos(angle),
    )


def _add_feature(doc, group, name, label, shape, color):
    obj = doc.addObject("PartDesign::Feature", name)
    obj.Label = label
    obj.Shape = shape
    if obj.ViewObject is not None:
        obj.ViewObject.ShapeColor = color
    group.addObject(obj)
    return obj


def _add_dimension_properties(obj):
    properties = {
        "BottomThickness": BOTTOM_THICKNESS,
        "TopThickness": TOP_THICKNESS,
        "PcbThickness": PCB_THICKNESS,
        "PcbClearance": PCB_CLEARANCE,
        "WallThickness": WALL_THICKNESS,
        "TopPlateGap": TOP_PLATE_GAP,
        "BatteryHolderClearance": BATTERY_HOLDER_CLEARANCE,
        "BatteryHolderHeight": BATTERY_HOLDER_HEIGHT,
        "BatteryVerticalClearance": BATTERY_HOLDER_VERTICAL_CLEARANCE,
        "SwitchWindow": SWITCH_WINDOW,
        "XiaoResetDiameter": XIAO_RESET_DIAMETER,
        "XiaoLedDiameter": XIAO_LED_DIAMETER,
        "TrackballMountSlotWidth": TRACKBALL_MOUNT_SLOT_WIDTH,
        "TrackballMountSlotDepth": TRACKBALL_MOUNT_SLOT_DEPTH,
        "TrackballMountFrontLip": TRACKBALL_MOUNT_FRONT_LIP,
        "TrackballScrewHeadDiameter": TRACKBALL_SCREW_HEAD_DIAMETER,
        "TrackballHeadRecessDepth": TRACKBALL_SCREW_HEAD_RECESS_DEPTH,
        "FfcWallOpeningWidth": FFC_WALL_OPENING_WIDTH,
        "ScrewBossDiameter": SCREW_BOSS_DIAMETER,
        "CaseScrewLength": CASE_SCREW_LENGTH,
        "M2InsertPilotDiameter": M2_INSERT_PILOT_DIAMETER,
        "M2InsertPilotDepth": M2_INSERT_PILOT_DEPTH,
        "M2TopClearanceDiameter": M2_TOP_CLEARANCE_DIAMETER,
    }
    for name, value in properties.items():
        obj.addProperty("App::PropertyLength", name, "Case dimensions")
        setattr(obj, name, value)
    obj.addProperty("App::PropertyString", "Source", "Generation")
    obj.Source = "generate-keyboard-case.py (edit script values, then regenerate)"


def _make_side(doc, repo_root: Path, side: str):
    pcb_path = repo_root / "pcb" / PCB_FILENAMES[side]
    data = _board_data(pcb_path)
    pcb_wire = _wire_from_records(data["records"])
    pcb_face = Part.Face(pcb_wire)
    cavity_wire = _offset_wire(pcb_wire, PCB_CLEARANCE)
    outer_wire = _offset_wire(pcb_wire, PCB_CLEARANCE + WALL_THICKNESS)
    cavity_face = Part.Face(cavity_wire)
    outer_face = Part.Face(outer_wire)

    battery_holders = [
        fp
        for fp in data["footprints"]
        if "battery_holder_AAA_1x_P55mm" in fp["name"] and fp["layer"] == "B.Cu"
    ]
    if len(battery_holders) != 1:
        raise ValueError(
            f"expected one B.Cu battery holder on {side}, "
            f"found {len(battery_holders)}"
        )
    battery = battery_holders[0]
    mounting_holes = [
        fp
        for fp in data["footprints"]
        if "MountingHole_5mm" in fp["name"]
    ]
    if len(mounting_holes) != 4:
        raise ValueError(
            f"expected four 5 mm mounting holes on {side}, "
            f"found {len(mounting_holes)}"
        )
    battery_inner_width = BATTERY_HOLDER_BODY[0] + BATTERY_HOLDER_CLEARANCE
    battery_inner_height = BATTERY_HOLDER_BODY[1] + BATTERY_HOLDER_CLEARANCE
    battery_outer_width = battery_inner_width + 2 * WALL_THICKNESS
    battery_outer_height = battery_inner_height + 2 * WALL_THICKNESS
    battery_inner_face = _rotated_rectangle_face(
        battery_inner_width,
        battery_inner_height,
        battery["cad_x"],
        battery["cad_y"],
        battery["cad_angle"],
    )
    battery_outer_face = _rotated_rectangle_face(
        battery_outer_width,
        battery_outer_height,
        battery["cad_x"],
        battery["cad_y"],
        battery["cad_angle"],
    )
    case_outer_face = outer_face.fuse(battery_outer_face)
    case_cavity_face = cavity_face.fuse(battery_inner_face)

    side_group = doc.addObject("App::Part", side.capitalize())
    side_group.Label = f"{side.capitalize()} case"

    reference_group = doc.addObject("App::DocumentObjectGroup", f"{side}_References")
    reference_group.Label = "References (hidden)"
    side_group.addObject(reference_group)
    pcb_reference_shape = pcb_face.extrude(App.Vector(0, 0, PCB_THICKNESS))
    pcb_reference_shape.translate(App.Vector(0, 0, BOTTOM_THICKNESS))
    for mounting_hole in mounting_holes:
        pcb_hole = Part.makeCylinder(
            PCB_MOUNTING_HOLE_DIAMETER / 2,
            PCB_THICKNESS + 0.2,
            App.Vector(
                mounting_hole["cad_x"],
                mounting_hole["cad_y"],
                BOTTOM_THICKNESS - 0.1,
            ),
        )
        pcb_reference_shape = pcb_reference_shape.cut(pcb_hole)
    pcb_reference = _add_feature(
        doc,
        reference_group,
        f"{side}_PCB_reference",
        "PCB reference (1.6 mm)",
        pcb_reference_shape,
        (0.15, 0.55, 0.22),
    )
    if pcb_reference.ViewObject is not None:
        pcb_reference.ViewObject.Transparency = 65
        pcb_reference.ViewObject.Visibility = False

    battery_reference_shape = _rotated_box(
        BATTERY_HOLDER_BODY[0],
        BATTERY_HOLDER_BODY[1],
        battery["cad_x"],
        battery["cad_y"],
        battery["cad_angle"],
        BOTTOM_THICKNESS,
        BATTERY_HOLDER_HEIGHT,
    )
    battery_reference = _add_feature(
        doc,
        reference_group,
        f"{side}_Battery_reference",
        "GB-BH-4X1-WP reference (51 x 13 x 12 mm)",
        battery_reference_shape,
        (0.12, 0.12, 0.12),
    )
    if battery_reference.ViewObject is not None:
        battery_reference.ViewObject.Transparency = 45
        battery_reference.ViewObject.Visibility = False

    bottom_group = doc.addObject("App::DocumentObjectGroup", f"{side}_Bottom")
    bottom_group.Label = "Bottom tray"
    side_group.addObject(bottom_group)

    bottom_shape = case_outer_face.extrude(App.Vector(0, 0, BOTTOM_THICKNESS))
    wall_height = PCB_THICKNESS + TOP_PLATE_GAP
    wall_ring = case_outer_face.cut(case_cavity_face).extrude(
        App.Vector(0, 0, wall_height)
    )
    wall_ring.translate(App.Vector(0, 0, BOTTOM_THICKNESS))

    trackball_mount_floor = None
    trackball_mount_slot = None
    trackball_head_recess = None
    if side == "right":
        switch_columns = sorted(
            {
                round(fp["x"], 3)
                for fp in data["footprints"]
                if "CHOC_V2_SOCKET" in fp["name"]
            },
            reverse=True,
        )
        if len(switch_columns) != 7:
            raise ValueError(
                "expected seven right-hand switch columns, "
                f"found {len(switch_columns)}: {switch_columns}"
            )
        third_from_right = switch_columns[2]
        fourth_from_right = switch_columns[3]
        fifth_from_right = switch_columns[4]
        recess_probe_x = data["transform"](
            ((fourth_from_right + fifth_from_right) / 2, 0)
        )[0]

        # Find the horizontal back edge of the U-shaped recess. It is the
        # lowest horizontal Edge.Cuts segment that crosses the intended
        # trackball position and is wide enough for the original mount slot.
        recess_edges = []
        for record in data["records"]:
            if record["kind"] != "gr_line":
                continue
            x1, y1 = record["start"]
            x2, y2 = record["end"]
            if abs(y1 - y2) > 0.02:
                continue
            xmin, xmax = sorted((x1, x2))
            if (
                xmin <= recess_probe_x <= xmax
                and xmax - xmin >= TRACKBALL_MOUNT_SLOT_WIDTH
                and y1 > 0.02
            ):
                recess_edges.append((y1, xmin, xmax))
        if not recess_edges:
            raise ValueError("could not find the right-hand trackball recess edge")
        recess_y, recess_xmin, recess_xmax = min(recess_edges)
        recess_width = recess_xmax - recess_xmin
        if TRACKBALL_MOUNT_SLOT_WIDTH > recess_width:
            raise ValueError(
                f"trackball mount slot is {TRACKBALL_MOUNT_SLOT_WIDTH} mm wide, "
                f"but the PCB recess is only {recess_width:.3f} mm"
            )

        # Fill the complete U-shaped recess with a horizontal mounting floor.
        # The recess opens onto y=0 in the transformed board coordinates.
        recess_center_x = (recess_xmin + recess_xmax) / 2
        trackball_mount_floor = Part.makeBox(
            recess_width,
            recess_y,
            BOTTOM_THICKNESS,
            App.Vector(
                recess_xmin,
                0,
                0,
            ),
        )

        # Keep the original bottom PCB's 2.8 mm front lip and 2.0 mm through
        # slot. The long slot permits the separate trackball case to be aligned
        # between switch columns four and five before it is fastened.
        trackball_mount_slot = Part.makeBox(
            TRACKBALL_MOUNT_SLOT_WIDTH,
            TRACKBALL_MOUNT_SLOT_DEPTH,
            BOTTOM_THICKNESS + 0.2,
            App.Vector(
                recess_center_x - TRACKBALL_MOUNT_SLOT_WIDTH / 2,
                TRACKBALL_MOUNT_FRONT_LIP,
                -0.1,
            ),
        )
        head_recess_width = (
            TRACKBALL_MOUNT_SLOT_WIDTH
            + TRACKBALL_SCREW_HEAD_DIAMETER
            + TRACKBALL_SCREW_HEAD_CLEARANCE
            - TRACKBALL_MOUNT_SLOT_DEPTH
        )
        head_recess_depth = (
            TRACKBALL_SCREW_HEAD_DIAMETER + TRACKBALL_SCREW_HEAD_CLEARANCE
        )
        trackball_head_recess = Part.makeBox(
            head_recess_width,
            head_recess_depth,
            TRACKBALL_SCREW_HEAD_RECESS_DEPTH + 0.1,
            App.Vector(
                recess_center_x - head_recess_width / 2,
                TRACKBALL_MOUNT_FRONT_LIP
                + TRACKBALL_MOUNT_SLOT_DEPTH / 2
                - head_recess_depth / 2,
                -0.1,
            ),
        )

        # Pass only the FFC cable through the rightmost quarter of the third
        # switch window counted from the right. The opening is edge-on and
        # intentionally narrow; the connector remains inside the enclosure.
        third_column_cad_x = data["transform"]((third_from_right, 0))[0]
        ffc_opening_center_x = (
            third_column_cad_x + 3 * SWITCH_WINDOW / 8
        )
        ffc_wall_opening = Part.makeBox(
            FFC_WALL_OPENING_WIDTH,
            2 * (PCB_CLEARANCE + WALL_THICKNESS) + 0.4,
            wall_height + 0.2,
            App.Vector(
                ffc_opening_center_x - FFC_WALL_OPENING_WIDTH / 2,
                recess_y - (PCB_CLEARANCE + WALL_THICKNESS) - 0.2,
                BOTTOM_THICKNESS - 0.1,
            ),
        )
        wall_ring = wall_ring.cut(ffc_wall_opening)

    bottom_shape = bottom_shape.fuse(wall_ring)
    if trackball_mount_floor is not None:
        bottom_shape = bottom_shape.fuse(trackball_mount_floor)
        bottom_shape = bottom_shape.cut(trackball_mount_slot)
        bottom_shape = bottom_shape.cut(trackball_head_recess)

    top_z = BOTTOM_THICKNESS + PCB_THICKNESS + TOP_PLATE_GAP
    boss_height = top_z - BOTTOM_THICKNESS
    for mounting_hole in mounting_holes:
        boss = Part.makeCylinder(
            SCREW_BOSS_DIAMETER / 2,
            boss_height,
            App.Vector(
                mounting_hole["cad_x"],
                mounting_hole["cad_y"],
                BOTTOM_THICKNESS,
            ),
        )
        pilot_hole = Part.makeCylinder(
            M2_INSERT_PILOT_DIAMETER / 2,
            M2_INSERT_PILOT_DEPTH + 0.1,
            App.Vector(
                mounting_hole["cad_x"],
                mounting_hole["cad_y"],
                top_z - M2_INSERT_PILOT_DEPTH,
            ),
        )
        bottom_shape = bottom_shape.fuse(boss).cut(pilot_hole)

    bottom_obj = _add_feature(
        doc,
        bottom_group,
        f"{side}_BottomTray",
        f"{side.capitalize()} bottom tray",
        bottom_shape,
        (0.18, 0.32, 0.72),
    )
    _add_dimension_properties(bottom_obj)

    top_group = doc.addObject("App::DocumentObjectGroup", f"{side}_Top")
    top_group.Label = "Top plate"
    side_group.addObject(top_group)
    top_shape = outer_face.extrude(App.Vector(0, 0, TOP_THICKNESS))
    top_shape.translate(App.Vector(0, 0, top_z))

    cut_depth = TOP_THICKNESS + 0.4
    cut_z = top_z - 0.2
    switch_count = 0
    for footprint in data["footprints"]:
        if "CHOC_V2_SOCKET" not in footprint["name"]:
            continue
        switch_count += 1
        cutter = _rotated_box(
            SWITCH_WINDOW,
            SWITCH_WINDOW,
            footprint["cad_x"],
            footprint["cad_y"],
            footprint["cad_angle"],
            cut_z,
            cut_depth,
        )
        top_shape = top_shape.cut(cutter)

    xiaos = [fp for fp in data["footprints"] if "XIAO-nRF52840-Plus" in fp["name"]]
    if len(xiaos) != 1:
        raise ValueError(f"expected one XIAO on {side}, found {len(xiaos)}")
    xiao = xiaos[0]

    window_center = _local_point(xiao, XIAO_WHITE_WINDOW_OFFSET)
    xiao_window = _rotated_box(
        XIAO_WHITE_WINDOW[0],
        XIAO_WHITE_WINDOW[1],
        window_center[0],
        window_center[1],
        xiao["cad_angle"],
        cut_z,
        cut_depth,
    )
    top_shape = top_shape.cut(xiao_window)

    reset_center = _local_point(xiao, XIAO_RESET_OFFSET)
    reset_hole = Part.makeCylinder(
        XIAO_RESET_DIAMETER / 2,
        cut_depth,
        App.Vector(reset_center[0], reset_center[1], cut_z),
    )
    top_shape = top_shape.cut(reset_hole)

    for offset in XIAO_LED_OFFSETS:
        center = _local_point(xiao, offset)
        led_hole = Part.makeCylinder(
            XIAO_LED_DIAMETER / 2,
            cut_depth,
            App.Vector(center[0], center[1], cut_z),
        )
        top_shape = top_shape.cut(led_hole)

    # Raised, hollow battery cover. It is fused to the removable top plate, so
    # removing the top plate exposes the battery while the assembled keyboard
    # hides the complete holder. The holder itself rests on the 1.5 mm floor.
    battery_roof_inner_z = (
        BOTTOM_THICKNESS
        + BATTERY_HOLDER_HEIGHT
        + BATTERY_HOLDER_VERTICAL_CLEARANCE
    )
    battery_roof_top_z = battery_roof_inner_z + TOP_THICKNESS
    battery_cap_outer = _rotated_box(
        battery_outer_width,
        battery_outer_height,
        battery["cad_x"],
        battery["cad_y"],
        battery["cad_angle"],
        top_z,
        battery_roof_top_z - top_z,
    )
    battery_cap_cavity = _rotated_box(
        battery_inner_width,
        battery_inner_height,
        battery["cad_x"],
        battery["cad_y"],
        battery["cad_angle"],
        top_z - 0.1,
        battery_roof_inner_z - top_z + 0.1,
    )
    battery_cap = battery_cap_outer.cut(battery_cap_cavity)
    battery_plate_opening = _rotated_box(
        battery_inner_width,
        battery_inner_height,
        battery["cad_x"],
        battery["cad_y"],
        battery["cad_angle"],
        cut_z,
        cut_depth,
    )
    top_shape = top_shape.cut(battery_plate_opening).fuse(battery_cap)

    for mounting_hole in mounting_holes:
        # Fuse a complete pad first because some PCB holes sit very close to an
        # Edge.Cuts boundary, then drill the M2 clearance hole through it.
        screw_pad = Part.makeCylinder(
            SCREW_BOSS_DIAMETER / 2,
            TOP_THICKNESS,
            App.Vector(
                mounting_hole["cad_x"],
                mounting_hole["cad_y"],
                top_z,
            ),
        )
        screw_clearance = Part.makeCylinder(
            M2_TOP_CLEARANCE_DIAMETER / 2,
            TOP_THICKNESS + 0.4,
            App.Vector(
                mounting_hole["cad_x"],
                mounting_hole["cad_y"],
                cut_z,
            ),
        )
        top_shape = top_shape.fuse(screw_pad).cut(screw_clearance)

    top_obj = _add_feature(
        doc,
        top_group,
        f"{side}_TopPlate",
        f"{side.capitalize()} top plate ({switch_count} switch windows)",
        top_shape,
        (0.82, 0.82, 0.86),
    )
    _add_dimension_properties(top_obj)
    return bottom_obj, top_obj


def _find_repo_root():
    """Locate the checkout even when FreeCAD console omits ``__file__``."""
    candidates = []

    file_value = globals().get("__file__")
    if file_value and not str(file_value).startswith("<"):
        script_path = Path(file_value).expanduser().resolve()
        if len(script_path.parents) >= 3:
            candidates.append(script_path.parents[2])

    override = os.environ.get("TORABO_TSUKI_OM_ROOT")
    if override:
        candidates.append(Path(override).expanduser().resolve())

    current = Path.cwd().resolve()
    candidates.extend((current, *current.parents))

    # FreeCAD.app commonly starts its Python console with '/' as the working
    # directory. Search the conventional ghq location without hard-coding the
    # GitHub account name.
    ghq_root = Path.home() / "ghq" / "github.com"
    if ghq_root.is_dir():
        candidates.extend(ghq_root.glob("*/torabo-tsuki-om"))

    seen = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in seen:
            continue
        seen.add(candidate)
        if (candidate / REQUIRED_PCB).is_file() and (
            candidate / SCRIPT_RELATIVE_PATH
        ).is_file():
            return candidate

    raise FileNotFoundError(
        "torabo-tsuki-om repository could not be located. Set "
        "TORABO_TSUKI_OM_ROOT to the repository's absolute path."
    )


def main():
    repo_root = _find_repo_root()
    script_path = repo_root / SCRIPT_RELATIVE_PATH
    output_dir = script_path.parent / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = App.newDocument("ToraboTsukiKeyboardCase")
    doc.Label = "torabo-tsuki-om keyboard case"
    generated = {}
    for side in SIDES:
        generated[side] = _make_side(doc, repo_root, side)

    doc.recompute()
    fcstd_path = output_dir / "torabo-tsuki-om-keyboard-case.FCStd"
    doc.saveAs(str(fcstd_path))

    for side, (bottom, top) in generated.items():
        Mesh.export([bottom], str(output_dir / f"{side}-bottom-tray.stl"))
        Mesh.export([top], str(output_dir / f"{side}-top-plate.stl"))
        Part.export([bottom], str(output_dir / f"{side}-bottom-tray.step"))
        Part.export([top], str(output_dir / f"{side}-top-plate.step"))

    print(f"Generated {fcstd_path}")
    for side, (bottom, top) in generated.items():
        print(
            f"  {side}: bottom {bottom.Shape.Volume:.1f} mm^3, "
            f"top {top.Shape.Volume:.1f} mm^3"
        )


if __name__ == "__main__":
    main()
