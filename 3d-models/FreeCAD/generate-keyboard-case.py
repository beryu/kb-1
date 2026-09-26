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
import struct
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

# Kailh Choc V2 switch opening. The previous 13.8 mm square printed loose
# enough for a switch to sink and enter at an angle, so apply 0.2 mm of
# diametral print compensation (0.1 mm more material at every edge).
SWITCH_WINDOW = 13.6

# The white component area of the XIAO that should remain visible.  Local X is
# along the 21 mm side of the XIAO footprint; local Y is along its 17.8 mm side.
XIAO_WHITE_WINDOW = (13.0, 14.0)
XIAO_WHITE_WINDOW_OFFSET = (-1.8, 0.0)

# The XIAO is surface-mounted on top of the main PCB. Seeed's official
# nRF52840 3D model measures 4.21 mm from its mounting datum to the tallest
# component. The physical USB-C shell reaches about local X=+12.3 mm while the
# antenna end is near X=-10.5 mm, so the cover envelope must not be centred on
# the footprint. Use a conservative 23.5 mm envelope shifted 0.5 mm toward USB,
# with 0.5 mm horizontal print clearance per side and extra vertical margin.
XIAO_ASSEMBLY_BODY = (23.5, 17.8)
XIAO_ASSEMBLY_CENTER_OFFSET = (0.5, 0.0)
XIAO_HORIZONTAL_CLEARANCE = 1.0
XIAO_ASSEMBLY_HEIGHT = 4.8
XIAO_VERTICAL_CLEARANCE = 0.8

# Cable opening centred on the USB-C receptacle at the +X end of the XIAO.
# The dimensions include print/cable-shell clearance; the long tunnel cuts
# through both the local XIAO cover and whichever case perimeter wall lies in
# front of it.
# A 12 mm opening also clears the moulded shoulder of typical USB-C plugs and
# avoids a thin angled remnant where the left case perimeter meets the tunnel.
XIAO_USB_OPENING_WIDTH = 12.0
XIAO_USB_OPENING_HEIGHT = 5.5
XIAO_USB_OPENING_LENGTH = 24.0
XIAO_USB_INWARD_OVERLAP = 1.0
XIAO_USB_CENTER_HEIGHT = 3.0
# The XIAO PCB raises the receptacle above the module mounting datum. The
# bottom-tray wall therefore only needs to be opened from this height upward;
# the taller top-cover cutter remains centred on the connector shell.
XIAO_USB_BOTTOM_ABOVE_DATUM = 0.9

# Reset and LED positions are expressed in the XIAO footprint's local
# coordinate system. Coordinates come from Seeed's official XIAO nRF52840 Plus
# v1.1 KiCad PCB (K1, RGB6, and CHG0). The reset hole is intentionally generous
# enough for a 1.5 mm pin tool.
XIAO_RESET_OFFSET = (8.5725, -5.715)
XIAO_RESET_DIAMETER = 3.0
XIAO_LED_OFFSETS = ((7.6835, 5.715), (9.8425, 5.715))
XIAO_LED_DIAMETER = 2.2

# The keyed FTSH body is 5.08 x 7.54 mm. Its footprint origin is pin 1,
# 0.635 mm left and 3.175 mm above the body centre in KiCad coordinates.
# The through-opening also admits the FFSD socket and lets the ribbon leave
# upward without trapping the cable under the switch plate.
SPLIT_HEADER_BODY_CENTER_OFFSET = (0.635, 3.175)
SPLIT_CABLE_OPENING = (10.0, 12.0)

# The current right PCB recess is 34 mm wide. A 30 mm slot leaves 2 mm of
# material at each end. Its 2.4 mm depth clears an M2 screw, and the 2.8 mm
# front lip retains the previous mounting height.
TRACKBALL_MOUNT_SLOT_WIDTH = 30.0
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
# right: 13.8 / 4 = 3.45 mm. Keep this independent from SWITCH_WINDOW so fit
# tuning the key-switch openings does not accidentally narrow the cable path.
# This is deliberately much narrower than the FFC adapter footprint because
# the connector itself remains inside the case.
FFC_WALL_OPENING_WIDTH = 3.45

# The four former mounting-hole centres per side now lie outside the PCB. The
# routed Edge.Cuts reliefs clear a 4.6 mm boss at these positions.
MOUNT_CENTERS = {
    "left": ((95.5, 41.5), (10.5, 45.5), (134.0, 115.5), (10.5, 115.5)),
    "right": ((79.3, 116.5), (164.3, 190.5), (40.8, 190.5), (164.3, 120.5)),
}
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


def _ordered_edges(records, tolerance=0.0001):
    """Order and orient unordered Edge.Cuts line/arc records into one loop."""
    if not records:
        raise ValueError("no Edge.Cuts geometry found")
    # Routed screw reliefs include segments shorter than 0.02 mm. A larger
    # matching tolerance skips those segments and leaves an open wire.
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
        # Reflecting both the board Y coordinate above and the footprint-local
        # Y coordinate in _local_point() preserves KiCad's rotation angle.
        # Negating it here would mirror asymmetric local features (such as the
        # XIAO reset button and LEDs) onto the antenna end of the footprint.
        footprint["cad_angle"] = footprint["angle"]

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
        "SwitchWindow": SWITCH_WINDOW,
        "XiaoAssemblyHeight": XIAO_ASSEMBLY_HEIGHT,
        "XiaoHorizontalClearance": XIAO_HORIZONTAL_CLEARANCE,
        "XiaoVerticalClearance": XIAO_VERTICAL_CLEARANCE,
        "XiaoUsbOpeningWidth": XIAO_USB_OPENING_WIDTH,
        "XiaoUsbOpeningHeight": XIAO_USB_OPENING_HEIGHT,
        "XiaoUsbBottomAboveDatum": XIAO_USB_BOTTOM_ABOVE_DATUM,
        "XiaoResetDiameter": XIAO_RESET_DIAMETER,
        "XiaoLedDiameter": XIAO_LED_DIAMETER,
        "SplitCableOpeningWidth": SPLIT_CABLE_OPENING[0],
        "SplitCableOpeningLength": SPLIT_CABLE_OPENING[1],
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


def _close_stl_roundoff(path: Path):
    """Weld sub-micron tessellation gaps at the routed right PCB corner."""
    data = path.read_bytes()
    count = struct.unpack_from("<I", data, 80)[0]
    if len(data) != 84 + 50 * count:
        raise ValueError(f"not a binary STL: {path}")
    facets = []
    for index in range(count):
        normal = data[84 + 50 * index:96 + 50 * index]
        vertices = [
            tuple(round(value, 4) for value in struct.unpack_from(
                "<fff", data, 96 + 50 * index + 12 * vertex))
            for vertex in range(3)
        ]
        if len(set(vertices)) < 3:
            continue
        facets.append(normal + b"".join(struct.pack("<fff", *v) for v in vertices)
                      + data[132 + 50 * index:134 + 50 * index])
    path.write_bytes(data[:80] + struct.pack("<I", len(facets)) + b"".join(facets))
    if not Mesh.Mesh(str(path)).isSolid():
        raise ValueError(f"STL mesh is not closed: {path}")


def _make_side(doc, repo_root: Path, side: str):
    pcb_path = repo_root / "pcb" / PCB_FILENAMES[side]
    data = _board_data(pcb_path)
    pcb_wire = _wire_from_records(data["records"])
    pcb_face = Part.Face(pcb_wire)
    cavity_wire = _offset_wire(pcb_wire, PCB_CLEARANCE)
    outer_wire = _offset_wire(pcb_wire, PCB_CLEARANCE + WALL_THICKNESS)
    cavity_face = Part.Face(cavity_wire)
    outer_face = Part.Face(outer_wire)

    xiaos = [fp for fp in data["footprints"] if "XIAO-nRF52840-Plus" in fp["name"]]
    if len(xiaos) != (1 if side == "right" else 0):
        raise ValueError(f"unexpected XIAO count on {side}: {len(xiaos)}")
    xiao = xiaos[0] if xiaos else None
    xiao_assembly_center = _local_point(xiao, XIAO_ASSEMBLY_CENTER_OFFSET) if xiao else None
    split_headers = [fp for fp in data["footprints"]
                     if "Samtec_FTSH-106-01-L-D-K" in fp["name"] and fp["layer"] == "F.Cu"]
    if len(split_headers) != 1:
        raise ValueError(f"expected one FTSH header on {side}, found {len(split_headers)}")
    split_header = split_headers[0]
    split_header_center = _local_point(split_header, SPLIT_HEADER_BODY_CENTER_OFFSET)
    mounting_holes = [{"cad_x": data["transform"](center)[0],
                       "cad_y": data["transform"](center)[1]}
                      for center in MOUNT_CENTERS[side]]
    case_outer_face = outer_face
    case_cavity_face = cavity_face

    side_group = doc.addObject("App::Part", side.capitalize())
    side_group.Label = f"{side.capitalize()} case"

    reference_group = doc.addObject("App::DocumentObjectGroup", f"{side}_References")
    reference_group.Label = "References (hidden)"
    side_group.addObject(reference_group)
    pcb_reference_shape = pcb_face.extrude(App.Vector(0, 0, PCB_THICKNESS))
    pcb_reference_shape.translate(App.Vector(0, 0, BOTTOM_THICKNESS))
    pcb_reference = _add_feature(
        doc, reference_group, f"{side}_PCB_reference",
        "PCB reference (1.6 mm)", pcb_reference_shape, (0.15, 0.55, 0.22))
    if pcb_reference.ViewObject is not None:
        pcb_reference.ViewObject.Transparency = 65
        pcb_reference.ViewObject.Visibility = False

    if xiao:
        xiao_reference = _add_feature(
            doc, reference_group, f"{side}_XIAO_reference",
            "XIAO nRF52840 Plus envelope reference",
            _rotated_box(XIAO_ASSEMBLY_BODY[0], XIAO_ASSEMBLY_BODY[1],
                         xiao_assembly_center[0], xiao_assembly_center[1],
                         xiao["cad_angle"], BOTTOM_THICKNESS + PCB_THICKNESS,
                         XIAO_ASSEMBLY_HEIGHT), (0.92, 0.92, 0.92))
        if xiao_reference.ViewObject is not None:
            xiao_reference.ViewObject.Transparency = 55
            xiao_reference.ViewObject.Visibility = False
    header_reference = _add_feature(
        doc, reference_group, f"{side}_SplitHeader_reference",
        "FTSH header body reference",
        _rotated_box(5.08, 7.54, split_header_center[0], split_header_center[1],
                     split_header["cad_angle"], BOTTOM_THICKNESS + PCB_THICKNESS,
                     TOP_PLATE_GAP + TOP_THICKNESS + 1.0), (0.15, 0.15, 0.15))
    if header_reference.ViewObject is not None:
        header_reference.ViewObject.Visibility = False
    bottom_group = doc.addObject("App::DocumentObjectGroup", f"{side}_Bottom")
    bottom_group.Label = "Bottom tray"
    side_group.addObject(bottom_group)

    bottom_shape = case_outer_face.extrude(App.Vector(0, 0, BOTTOM_THICKNESS))
    wall_height = PCB_THICKNESS + TOP_PLATE_GAP
    top_z = BOTTOM_THICKNESS + wall_height
    wall_ring = case_outer_face.cut(case_cavity_face).extrude(
        App.Vector(0, 0, wall_height)
    )
    wall_ring.translate(App.Vector(0, 0, BOTTOM_THICKNESS))

    if xiao:
        xiao_usb_center = _local_point(xiao, (
            XIAO_ASSEMBLY_BODY[0] / 2 + XIAO_ASSEMBLY_CENTER_OFFSET[0]
            - XIAO_USB_INWARD_OVERLAP + XIAO_USB_OPENING_LENGTH / 2, 0.0))
        xiao_usb_opening = _rotated_box(
            XIAO_USB_OPENING_LENGTH, XIAO_USB_OPENING_WIDTH,
            xiao_usb_center[0], xiao_usb_center[1], xiao["cad_angle"],
            BOTTOM_THICKNESS + PCB_THICKNESS + XIAO_USB_CENTER_HEIGHT
            - XIAO_USB_OPENING_HEIGHT / 2, XIAO_USB_OPENING_HEIGHT)
        xiao_usb_bottom_z = BOTTOM_THICKNESS + PCB_THICKNESS + XIAO_USB_BOTTOM_ABOVE_DATUM
        wall_ring = wall_ring.cut(_rotated_box(
            XIAO_USB_OPENING_LENGTH, XIAO_USB_OPENING_WIDTH,
            xiao_usb_center[0], xiao_usb_center[1], xiao["cad_angle"],
            xiao_usb_bottom_z, top_z + 0.2 - xiao_usb_bottom_z))

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
    # The removable plate follows the current PCB perimeter.
    top_shape = case_outer_face.extrude(App.Vector(0, 0, TOP_THICKNESS))
    top_shape.translate(App.Vector(0, 0, top_z))

    cut_depth = TOP_THICKNESS + 0.4
    cut_z = top_z - 0.2

    # The FFSD socket and ribbon pass vertically through the top plate.
    top_shape = top_shape.cut(_rotated_box(
        SPLIT_CABLE_OPENING[0], SPLIT_CABLE_OPENING[1],
        split_header_center[0], split_header_center[1],
        split_header["cad_angle"], cut_z, cut_depth))

    if xiao:
        xiao_inner_width = XIAO_ASSEMBLY_BODY[0] + XIAO_HORIZONTAL_CLEARANCE
        xiao_inner_height = XIAO_ASSEMBLY_BODY[1] + XIAO_HORIZONTAL_CLEARANCE
        xiao_roof_inner_z = (BOTTOM_THICKNESS + PCB_THICKNESS
                             + XIAO_ASSEMBLY_HEIGHT + XIAO_VERTICAL_CLEARANCE)
        xiao_roof_top_z = xiao_roof_inner_z + TOP_THICKNESS
        xiao_cap_outer = _rotated_box(
            xiao_inner_width + 2 * WALL_THICKNESS,
            xiao_inner_height + 2 * WALL_THICKNESS,
            xiao_assembly_center[0], xiao_assembly_center[1],
            xiao["cad_angle"], top_z, xiao_roof_top_z - top_z)
        xiao_cap_cavity = _rotated_box(
            xiao_inner_width, xiao_inner_height,
            xiao_assembly_center[0], xiao_assembly_center[1],
            xiao["cad_angle"], top_z - 0.1,
            xiao_roof_inner_z - top_z + 0.1)
        top_shape = top_shape.cut(_rotated_box(
            xiao_inner_width, xiao_inner_height,
            xiao_assembly_center[0], xiao_assembly_center[1],
            xiao["cad_angle"], cut_z, cut_depth)).fuse(
                xiao_cap_outer.cut(xiao_cap_cavity))
        top_shape = top_shape.cut(xiao_usb_opening)

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

    if xiao:
        window_center = _local_point(xiao, XIAO_WHITE_WINDOW_OFFSET)
        xiao_roof_cut_z = top_z - 0.2
        xiao_roof_cut_depth = xiao_roof_top_z - xiao_roof_cut_z + 0.2
        top_shape = top_shape.cut(_rotated_box(
            XIAO_WHITE_WINDOW[0], XIAO_WHITE_WINDOW[1],
            window_center[0], window_center[1], xiao["cad_angle"],
            xiao_roof_cut_z, xiao_roof_cut_depth))
        reset_center = _local_point(xiao, XIAO_RESET_OFFSET)
        top_shape = top_shape.cut(Part.makeCylinder(
            XIAO_RESET_DIAMETER / 2, xiao_roof_cut_depth,
            App.Vector(reset_center[0], reset_center[1], xiao_roof_cut_z)))
        for offset in XIAO_LED_OFFSETS:
            center = _local_point(xiao, offset)
            top_shape = top_shape.cut(Part.makeCylinder(
                XIAO_LED_DIAMETER / 2, xiao_roof_cut_depth,
                App.Vector(center[0], center[1], xiao_roof_cut_z)))

    for mounting_hole in mounting_holes:
        # Fuse a complete pad over each routed screw relief, then drill it.
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
        for part, obj in (("bottom-tray", bottom), ("top-plate", top)):
            path = output_dir / f"{side}-{part}.stl"
            Mesh.export([obj], str(path))
            _close_stl_roundoff(path)
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
