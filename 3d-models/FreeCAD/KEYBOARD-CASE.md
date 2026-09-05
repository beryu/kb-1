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

## Design intent

- Bottom plate: 1.5 mm.
- PCB pocket depth: 1.6 mm, with 0.25 mm horizontal clearance.
- B.Cu battery holder: an enclosed compartment based on the published
  51 x 13 x 12 mm holder dimensions, with 0.8 mm overall horizontal clearance
  and 0.8 mm vertical clearance. The 1.5 mm bottom extends under the holder.
  A hollow raised cover is integrated into the removable top plate, so the
  battery holder is hidden when assembled and accessible when the plate is off.
- Top-side component clearance: 3.5 mm above the PCB.
- Top plate: 1.5 mm, located above the component-clearance space.
- Top switch openings: 13.8 mm square, rotated from the KiCad footprints.
- XIAO: one rectangular viewing window, one reset access hole, and two LED
  viewing holes on each half.
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
