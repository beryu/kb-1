# Keyboard case generator

`generate-keyboard-case.py` reads both KiCad PCB files and regenerates the
bottom trays and top plates in FreeCAD. The PCB outline and the locations and
rotations of the key switches and XIAO footprints therefore stay synchronized
with the PCB design.

## Generate

From a terminal on macOS with FreeCAD installed in `/Applications`:

```sh
/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd \
  -c "exec(open('3d-models/FreeCAD/generate-keyboard-case.py').read())"
```

It can also be pasted directly into FreeCAD's Python console. Use the complete
absolute path on one line:

```python
exec(open('/absolute/path/to/torabo-tsuki-om/3d-models/FreeCAD/generate-keyboard-case.py').read())
```

The script detects checkouts stored under the conventional
`~/ghq/github.com/<account>/torabo-tsuki-om` path even though the FreeCAD Python
console does not define `__file__`. For a checkout elsewhere, start FreeCAD
from the repository directory or set `TORABO_TSUKI_OM_ROOT` before launching
FreeCAD.

Outputs are written to `3d-models/FreeCAD/generated/`:

- one editable FreeCAD document containing both halves;
- STL files for printing;
- STEP files for exchange and downstream CAD edits.

Open `torabo-tsuki-om-keyboard-case.FCStd` in FreeCAD. The model tree separates
the left/right halves, bottom trays, top plates, and hidden PCB references.

## Assembly hardware

The complete left/right enclosure uses the following printed parts and
hardware:

| Item | Quantity | Notes |
| --- | ---: | --- |
| [Left bottom tray](generated/left-bottom-tray.stl) | 1 | 3D printed |
| [Left top plate](generated/left-top-plate.stl) | 1 | 3D printed |
| [Right bottom tray](generated/right-bottom-tray.stl) | 1 | 3D printed |
| [Right top plate](generated/right-top-plate.stl) | 1 | 3D printed |
| M2 heat-set insert | 8 | Four per half. [Japan Drive-It Sonic Lock M2-3.0, MonotaRO order code 42131126](https://www.monotaro.com/p/4213/1126/) fits the 3.2 mm diameter, 4.0 mm deep pilot. It is sold in packs of six, so order two packs. |
| M2 x 3.5 mm low-profile screw | 8 | Original design specification for fastening the two top plates. |
| M2 x 4 mm ultra-low-head screw | 8 | Verified top-plate alternative: [AHN2 stainless screw, MonotaRO order code 69132245](https://www.monotaro.com/p/6913/2245/). Its M2 x 0.4 thread and 0.3 mm-high head fit; the extra 0.5 mm increases insert engagement to about 2.5 mm. One 13-piece pack is sufficient. |
| Thin self-adhesive rubber foot | 8 | Recommended, but not structurally required. |

Use either the 3.5 mm or 4 mm top-plate screws, not both. The printed bosses
replace the 4.5 mm spacers used by the original PCB top/bottom-plate stack, so
separate spacers, washers, and ordinary nuts are not required. The M2 x 4 mm
alternative above has only been checked for the enclosure top plates; continue
to use the specified M2 x 3.5 mm screw for the separate trackball-case mount.

## Design intent

- Bottom plate: 1.5 mm.
- PCB pocket depth: 1.6 mm, with 0.25 mm horizontal clearance.
- B.Cu battery holder: an enclosed lateral compartment based on the published
  51 x 13 x 12 mm holder dimensions, with 0.8 mm overall horizontal clearance.
  The 1.5 mm bottom extends under the holder. The removable top plate has a
  51.2 x 14.2 mm through-opening. The physical print needed force to seat, so
  the short axis has been enlarged by another 0.5 mm at both edges while the
  original 0.1 mm per-end clearance is retained along the holder length.
- Top-side component clearance: 3.5 mm above the PCB.
- Top plate: 1.5 mm, located above the component-clearance space.
- Top switch openings: 13.6 mm square, rotated from the KiCad footprints. The
  former 13.8 mm openings printed too loose and allowed a switch to sink into
  the plate at an angle, so the generated opening now leaves 0.1 mm more
  material at every edge.
- Power switch: the `ISH-1260-HA-G` body uses a conservative
  9.1 x 3.5 x 5.5 mm installed envelope. A hollow local top-plate cover rises
  over the complete body with 0.5 mm horizontal clearance per side and 0.3 mm
  clearance above it. The installed switch has a 1.5 mm-wide actuator
  projecting horizontally by 2 mm toward the case perimeter. A central 6.0 mm
  side tunnel opens only the upper 2.0 mm of the bottom-tray wall and continues
  upward through the cover side to its roof, leaving the lower wall intact.
  The switch body remains covered from above and at both ends while the
  actuator is reachable by a fingertip. There is no opening in the cover roof.
- XIAO: a local hollow cover follows a conservative 23.5 x 17.8 mm assembly
  envelope shifted 0.5 mm toward the USB-C end, matching the connector's
  asymmetric physical overhang. Its cavity has 0.5 mm horizontal clearance on
  each side and 0.8 mm above a 4.8 mm installed-height envelope. One 13 x 14 mm
  rectangular white-label viewing window,
  one reset access hole, and two LED viewing holes remain in its roof on each
  half. Each cover uses the position and rotation of its own KiCad footprint.
  A 12.0 x 5.5 mm cable opening follows the USB-C end of the footprint through
  both the local cover and the outer case wall, so the connector can be used
  without removing the case. On the bottom tray, the opening starts 0.9 mm
  above the XIAO mounting datum instead of at the main-PCB surface, preserving
  the wall below the receptacle. The cutter overlaps the XIAO envelope by
  1.0 mm and extends 24 mm outward to avoid a thin remnant on angled walls.
- Fastening: four PCB `MountingHole_5mm` positions per half are reused. A
  4.6 mm printed boss passes through each 4.9 mm PCB hole and contains a
  3.2 mm blind pilot for an M2 heat-set insert. The top plate has 2.4 mm M2
  clearance holes. Use M2 x 3.5 mm screws, matching the screws that fasten the
  separate trackball case. With the 1.5 mm top plate, approximately 2.0 mm of
  thread engages the insert. Screw heads remain above the plate; no countersink
  is generated.
- Right trackball area: the back edge of the PCB's U-shaped recess is detected
  from Edge.Cuts. The complete 49.3 x 19.6 mm recess is filled with a 1.5 mm
  mounting floor so the separate trackball housing can sit inside the keyboard
  outline. A 44.2 x 2.4 mm through-slot and 2.8 mm front lip reproduce the
  fastening geometry in `torabo-tsuki-lp-S-ortho-mini-bottom.kicad_pcb`; the
  original PCB's 2.0 mm slot is widened by 0.4 mm for reliable M2 screw
  clearance in a printed part. On the underside, a 4.2 mm wide and 0.4 mm deep
  flat-bottom recess follows the full mounting slot. It clears the 4.0 mm
  diameter, 0.3 mm high head of the M2 x 3.5 mm FX-0235EB low-profile screw
  referenced by `build-guide.md`, keeping the screw head within the bottom
  surface while preserving 1.1 mm of floor thickness. The
  rear vertical wall remains around the housing. Only a 3.45 mm opening for an
  edge-on FFC cable is cut at the rightmost quarter of the third switch window
  counted from the right; the FFC connector itself stays inside the case.

All dimensions and XIAO-local offsets are grouped near the top of
`generate-keyboard-case.py`. Edit those values and regenerate rather than
manually repeating geometry. The generated FCStd and STEP files can still be
edited directly when a one-off CAD adjustment is useful.

The reset, RGB LED, and charge LED offsets come from Seeed Studio's official
XIAO nRF52840 Plus v1.1 KiCad PCB. The offsets remain explicit because small
component positions may vary between board revisions. Before manufacturing,
compare the generated top plate with the physical board and adjust them if
necessary.
