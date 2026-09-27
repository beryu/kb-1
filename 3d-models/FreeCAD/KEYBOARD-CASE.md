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
| Thin self-adhesive rubber foot | 8 | Recommended for grip and bottom protection. |

Use either the 3.5 mm or 4 mm top-plate screws, not both. The printed bosses
replace the 4.5 mm spacers used by the original PCB top/bottom-plate stack, so
separate spacers, washers, and ordinary nuts are not required. The M2 x 4 mm
alternative above has only been checked for the enclosure top plates; continue
to use the specified M2 x 3.5 mm screw for the separate trackball-case mount.

## Design intent

The generator reads the current left and right `Edge.Cuts` and footprints. The
2026-09 PCB revision has a single right-side XIAO, no AAA holders or power
switches, and a vertical Samtec FTSH header on each side. The case has been
regenerated from those boards.

- The bottom is 1.5 mm thick. The PCB pocket is 1.6 mm deep with 0.25 mm
  horizontal clearance and a 1.8 mm perimeter wall.
- Each top plate is 1.5 mm thick, 3.5 mm above the PCB surface, with
  14.2 x 14.0 mm switch windows positioned from the KiCad footprints. These
  match the 20 `Edge.Cuts` switch cutouts in the supplied
  `torabo-tsuki-lp-S-ortho-mini-top.kicad_pcb` reference.
- Each FTSH header has a 6.4 x 13.0 mm through-opening in its top plate for
  the FFSD-06 socket and upward cable exit. [Samtec's FFSD series drawing](https://suddendocs.samtec.com/catalog_english/ffsd.pdf) gives
  the unrelieved six-position socket body as 5.08 x 11.81 mm; the opening
  provides about 0.6 mm clearance per side. The left J101 and right J202
  footprints are both at 0 degrees, and each opening is centred on its
  connector body rather than the pin-1 footprint origin.
- Only the right plate has a raised XIAO cover and the right tray has a USB-C
  wall opening. The cover retains the white-label window, reset access hole,
  and LED viewing holes. The visible window is 10.5 x 12.5 mm, based on the
  supplied `xiao-nrf52840-plus-v2.step` label (10.2 x 12.2 mm). A wider
  11.2 x 13.2 mm underside pocket clears its metal shield (10.6 x 12.6 mm)
  while a 0.3 mm masking lip hides nearly all of the black border. Only the
  central USB-C region rises in a convex profile
  when viewed from the cable entry; the lower 9.8 mm pocket narrows toward the
  connector crown while the reset and LED areas retain the original roof.
  The metal shell extends 1.51 mm beyond the XIAO PCB and reaches 4.41 mm
  above the underside solder-pad plane. The pocket clears the complete STEP
  assembly with the bare XIAO held against the inverted top plate, and its
  roof remains 1.5 mm thick. The separate 12 mm wall opening provides the
  cable passage. The top plate also has a 12 mm wide, full-height notch starting
  at local X=11.5 mm, 0.8 mm before the STEP receptacle mouth, so the raised
  roof does not protrude in front of the port or block the plug housing.
- Four M2 insert bosses per half follow the former mounting-hole centres. The
  current boards have routed `Edge.Cuts` screw reliefs in place of the old
  `MountingHole_5mm` footprints. The bosses are 4.6 mm in diameter, with 3.2 mm
  insert pilots. The bosses extend to the tray bottom so their routed-edge
  portions have no underside gaps; each top plate has 2.4 mm screw holes.
- The right PCB's trackball cutout has a 34 mm back edge and continues one
  17 mm switch column to the right. The tray floor spans both areas and its
  exposed front-left corner has a 2 mm radius. It has a
  44.2 x 2.4 mm fastening slot, 2.8 mm front lip, and shallow underside screw-head
  recess. The separate trackball-case STL is about 29.8 x 19.4 mm in plan view.
  At the lower-right corner of the third switch column from the right, a
  3.45 mm FFC slit passes through the wall at the PCB's stepped edge. The
  floor remains its full 1.5 mm thick beneath the slit.

The four generated STL files and the editable FreeCAD document are in
`generated/`. The STEP files are also exported for CAD exchange. The STL
meshes are checked for closure during generation. Check the printed cable
connector and trackball fit with physical parts before ordering a full set.
