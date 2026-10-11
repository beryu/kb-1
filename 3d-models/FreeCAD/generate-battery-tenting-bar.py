#!/usr/bin/env python3
"""FreeCAD generator for a magnetic AAA power bar fitted to kb-1.

Run in FreeCAD's Python console or with freecadcmd -c exec(...).
The original keyboard document is read only. All outputs go to this checkout.
"""
from pathlib import Path
import hashlib
import json
import math
import os
import xml.etree.ElementTree as ET
import zipfile

import FreeCAD as App
import Part
import MeshPart

# Millimetres. Holder height is a conservative, unmeasured envelope including
# the installed AAA cell; change it after measuring GB-BH-4X1-WP.
BAR_LENGTH = 100.0
BAR_WIDTH = 28.0
CONTACT_CENTER_HEIGHT = 28.0
CORNER_RADIUS = 2.5
WALL = 2.0
FLOOR = 1.8
COVER_THICKNESS = 1.0             # vertical; screwed above the inner lid
COVER_MAGNET_SKIN = 0.5           # thin closed window over each magnet
INNER_LID_THICKNESS = 2.4
LID_THICKNESS = INNER_LID_THICKNESS+COVER_THICKNESS
TRAY_X = 8.0
TRAY_Y = 3.3
TRAY_LENGTH = 84.4
TRAY_WIDTH = 21.4
TRAY_BOTTOM_Z = 4.2
TRAY_THICKNESS = 2.0
TRAY_TOP_Z = TRAY_BOTTOM_Z+TRAY_THICKNESS
HOLDER_X = 13.0
HOLDER_Y = 9.0                   # base face; holder opening faces rear +V
HOLDER_BOTTOM_Z = 7.2
HOLDER_MIDDLE_Z = HOLDER_BOTTOM_Z+6.5
DOOR_OPEN_TRAVEL = 60.0
DOOR_RELEASE_DEFLECTION = .9
HOLDER_PIN_PITCH = 55.0
HOLDER_TERMINAL_HOLE = 3.4
MODULE_X = 76.0
MODULE_Y = 10.0
MODULE_WIDTH = 10.0
MODULE_DEPTH = 7.5
MODULE_HEIGHT = 3.0               # unmeasured component+solder envelope
MODULE_BOTTOM_Z = TRAY_TOP_Z+1.6
MODULE_CAGE_BOTTOM_Z = MODULE_BOTTOM_Z+MODULE_HEIGHT+.4
MODULE_CAGE_THICKNESS = 1.6
MODULE_BOLT_X = (72.0,90.0)
MODULE_BOLT_Y = MODULE_Y+MODULE_DEPTH/2
MODULE_POST_RADIUS = 3.0         # 2 mm radial wall outside hex pilot corners
TRAY_BOLTS = ((70.0,5.2),(69.0,22.8))
SWITCH_X = 79.0
SWITCH_Y = 22.5
SWITCH_WIDTH = 8.8
SWITCH_DEPTH = 3.9
SWITCH_HEIGHT = 3.5              # conservative envelope; check current lot
SWITCH_BOTTOM_Z = TRAY_TOP_Z+1.2
CABLE_DIAMETER = float(os.environ.get('TENTING_CABLE_DIAMETER_MM','3.0'))
CABLE_OUTLET_Z = 15.0
PTC_WIDTH = 8.5                 # conservative envelope; verify MF-R050
PTC_DEPTH = 3.5
PTC_HEIGHT = 10.0
HOLDER_LENGTH = 51.0
HOLDER_WIDTH = 13.0
HOLDER_HEIGHT = float(os.environ.get('TENTING_HOLDER_HEIGHT_MM', '15.0'))
MAGNET_DIAMETER = 12.0
MAGNET_THICKNESS = 1.0
MAGNET_POCKET_DIAMETER = 12.25
MAGNET_POCKET_DEPTH = 0.80        # magnet protrudes 0.2 mm into cover recess
FINGER_DIAMETER = 22.0
FINGER_FUNNEL_DEPTH = 0.50
PILOT_ACROSS_FLATS = math.sqrt(3) # same 1 mm circumradius hex as trackball case
LID_PILOT_DEPTH = 4.0
TRAY_PILOT_DEPTH = 3.2
MODULE_PILOT_DEPTH = 4.0
PILOT_ENTRY_DEPTH = .25
COVER_SCREW_LENGTH = 6.0
INTERNAL_SCREW_LENGTH = 5.0
SCREW_HOLE_DIAMETER = 2.4
SCREW_HEAD_DIAMETER = 4.4
SCREW_HEAD_RECESS = 0.5

if '__file__' in globals() and Path(__file__).name=='generate-battery-tenting-bar.py':
    REPO = Path(__file__).resolve().parents[2]
else:
    REPO = Path(os.environ.get('TORABO_TSUKI_OM_ROOT', '/Users/beryu/ghq/github.com/beryu/torabo-tsuki-om'))
CASE_FILE = Path(os.environ.get('KB1_CASE_FILE', str(REPO.parent / 'kb-1/kb.FCStd')))
OUTPUT = REPO / '3d-models/FreeCAD/generated/battery-tenting-bar'
OUTPUT.mkdir(parents=True, exist_ok=True)
V = App.Vector


def rounded_face(length,width,r):
    base=Part.makeBox(length-2*r,width,1,V(r,0,0)).fuse(Part.makeBox(length,width-2*r,1,V(0,r,0)))
    for x in [r,length-r]:
        for y in [r,width-r]: base=base.fuse(Part.makeCylinder(r,1,V(x,y,0)))
    base=base.removeSplitter()
    face=next(f for f in base.Faces if abs(f.CenterOfMass.z)<1e-6)
    return face


def plane_z(y, angle):
    return CONTACT_CENTER_HEIGHT-(y-BAR_WIDTH/2)*math.tan(angle)


def wedge(top_offset,bottom_offset,angle):
    # top/bottom offsets below the keyboard contact plane. If bottom_offset
    # is None the lower face lies on the desk.
    pts=[V(0,0,plane_z(0,angle)-top_offset),V(0,BAR_WIDTH,plane_z(BAR_WIDTH,angle)-top_offset)]
    if bottom_offset is None: pts += [V(0,BAR_WIDTH,0),V(0,0,0)]
    else: pts += [V(0,BAR_WIDTH,plane_z(BAR_WIDTH,angle)-bottom_offset),V(0,0,plane_z(0,angle)-bottom_offset)]
    section=Part.Face(Part.makePolygon(pts+[pts[0]]))
    return section.extrude(V(BAR_LENGTH,0,0)).common(rounded_face(BAR_LENGTH,BAR_WIDTH,CORNER_RADIUS).extrude(V(0,0,50))).removeSplitter()


def frame_matrix(a,b,angle):
    dx=b[0]-a[0];dy=b[1]-a[1];d=math.hypot(dx,dy)
    ex,ey=dx/d,dy/d;vx,vy=-ey,ex
    u0=(BAR_LENGTH-d)/2
    m=App.Matrix()
    m.A11=ex;m.A12=ey;m.A13=0;m.A14=u0-ex*a[0]-ey*a[1]
    m.A21=math.cos(angle)*vx;m.A22=math.cos(angle)*vy;m.A23=math.sin(angle)
    m.A24=BAR_WIDTH/2-math.cos(angle)*(vx*a[0]+vy*a[1])
    m.A31=-math.sin(angle)*vx;m.A32=-math.sin(angle)*vy;m.A33=math.cos(angle)
    m.A34=CONTACT_CENTER_HEIGHT+math.sin(angle)*(vx*a[0]+vy*a[1])
    return m


def map_shape(shape,a,b,angle):
    # transformShape mutates its receiver: never accumulate transformations
    # during the desk-contact search or alter the source keyboard geometry.
    mapped=shape.copy()
    mapped.transformShape(frame_matrix(a,b,angle),True)
    return mapped


def magnet_centers(shape):
    found=set()
    for f in shape.Faces:
        if isinstance(f.Surface,Part.Cylinder) and abs(f.Surface.Radius-6.05)<.01:
            c=f.Surface.Center
            if abs(c.z-.5)<.01: found.add((round(c.x,5),round(c.y,5)))
    if len(found)!=4: raise ValueError(f'Expected 4 existing Ø12.1 magnet pockets, got {found}')
    return sorted(found)


def tilt_for_desk(shape,a,b):
    # Exact BRep bounds: the opposite keyboard edge and bar base both reach
    # the same desk plane. No fixed angle is assumed from an unrelated case.
    lo=0.0;hi=math.radians(30)
    for _ in range(32):
        mid=(lo+hi)/2
        if map_shape(shape,a,b,mid).BoundBox.ZMin>0:lo=mid
        else:hi=mid
    return (lo+hi)/2


def add_feature(doc,group,name,label,shape,color,visible=True):
    o=doc.addObject('Part::Feature',name);o.Label=label;o.Shape=shape;group.addObject(o)
    if o.ViewObject:
        o.ViewObject.ShapeColor=color;o.ViewObject.LineColor=(.12,.12,.15);o.ViewObject.Visibility=visible
    return o


def intersection_volume(a,b):
    return a.common(b).Volume


def export_part(obj,name):
    Part.export([obj],str(OUTPUT/(name+'.step')))
    print_shape=obj.Shape.copy()
    if name.endswith('-lid') or name.endswith('-cover'):
        # Put the inclined keyboard contact face on the printer's flat bed.
        print_shape.rotate(V(0,0,0),V(1,0,0),180+obj.TentingAngle.Value)
        bb=print_shape.BoundBox
        print_shape.translate(V(-bb.XMin,-bb.YMin,-bb.ZMin))
    elif name.endswith('-battery-door'):
        # Inside face down: the in-plane release leaf starts on the bed and
        # does not need supports in its narrow release slots.
        print_shape.rotate(V(0,0,0),V(1,0,0),90)
    mesh=MeshPart.meshFromShape(Shape=print_shape,LinearDeflection=.08,AngularDeflection=.15,Relative=False)
    # OCCT's rotated curved-face bounding box can be conservative. Use the
    # actual print mesh to place the lowest printed surface exactly at Z=0.
    bb=mesh.BoundBox
    shift=App.Matrix();shift.A14=-bb.XMin;shift.A24=-bb.YMin;shift.A34=-bb.ZMin
    mesh.transform(shift)
    if not mesh.isSolid(): raise ValueError(f'{name}: mesh is not closed')
    mesh.write(str(OUTPUT/(name+'.stl')))
    return mesh


def save_headless_view_state(doc,path):
    """Supply the standard native GUI visibility record absent from CLI saves.

    Geometry stays in the FreeCAD document; this only chooses the initial view.
    The XML schema is the one used by FreeCAD's bundled example documents.
    """
    root=ET.Element('Document',SchemaVersion='1')
    data=ET.SubElement(root,'ViewProviderData',Count=str(len(doc.Objects)))
    shown={'RightBar','RightReferences','RightHousing','RightLid','RightCover','RightBatteryDoor','RightFixedCable','RightFixedUSBCPlug'}
    for obj in doc.Objects:
        vp=ET.SubElement(data,'ViewProvider',name=obj.Name,expanded='0',treeRank='-1')
        props=ET.SubElement(vp,'Properties',Count='1')
        prop=ET.SubElement(props,'Property',name='Visibility',type='App::PropertyBool',status='1')
        ET.SubElement(prop,'Bool',value='true' if obj.Name in shown else 'false')
    axis=V(-.74290609,-.30772182,-.59447277)
    rotation=App.Rotation(axis,math.degrees(5.0660691))
    rotation=App.Rotation(V(0,0,1),180).multiply(rotation)
    axis=rotation.Axis
    pos=V(28,8,22)+rotation.multVec(V(0,0,200))
    camera=f'OrthographicCamera {{\n viewportMapping ADJUST_CAMERA\n position {pos.x} {pos.y} {pos.z}\n orientation {axis.x} {axis.y} {axis.z} {rotation.Angle}\n nearDistance 1\n farDistance 1000\n aspectRatio 1.6\n focalDistance 200\n height 145\n}}\n'
    ET.SubElement(root,'Camera',settings=camera)
    tmp=path.with_suffix('.view-tmp')
    with zipfile.ZipFile(path) as src,zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            if info.filename!='GuiDocument.xml':dst.writestr(info,src.read(info.filename))
        dst.writestr('GuiDocument.xml',ET.tostring(root,encoding='utf-8',xml_declaration=True))
    tmp.replace(path)


def box(x,y,z,w,dep,h):
    return Part.makeBox(w,dep,h,V(x,y,z))


def component_tray():
    """Removable non-conductive carrier; presolder, insulate, then install.

    Ties secure the sideways holder, switch and leaded parts;
    a screwed bridge captures the purchased boost board without pressing it.
    """
    tray=box(TRAY_X,TRAY_Y,TRAY_BOTTOM_Z,TRAY_LENGTH,TRAY_WIDTH,TRAY_THICKNESS)
    tray=tray.fuse(box(87,23.5,TRAY_BOTTOM_Z,5.4,2.1,TRAY_THICKNESS))
    tray=tray.fuse(box(13,23.5,TRAY_BOTTOM_Z,51,2.0,TRAY_THICKNESS))
    cuts=[]
    for x in [38.5-HOLDER_PIN_PITCH/2,38.5+HOLDER_PIN_PITCH/2]:
        cuts.append(Part.makeCylinder(HOLDER_TERMINAL_HOLE/2,5,V(x,5.5,HOLDER_MIDDLE_Z),V(0,1,0)))
    # Open underside channels: 3 mm wide, 1 mm deep. Their shared floor is
    # the bar's cavity; the carrier still has 1 mm of insulating roof.
    for x,y,w,dep in [(10,12.5,81,3),(86.5,4.0,3,19),(75,4.0,15,3),(74,19.8,17,3)]:
        cuts.append(box(x,y,TRAY_BOTTOM_Z-.1,w,dep,1.1))
    # Hole pairs take 2.5 mm cable ties. The holder bands fall outside the
    # reference AAA cylinder, so battery exchange does not require cutting ties.
    ties=[]
    for x in [13.5,63.5]:
        for y in [5.2,24.25]:ties.append((x,y,2.8,1.4,'holder'))
    for x in [72.6,86.1]:ties.append((x,22.5,1.4,2.8,'switch'))
    for x in [75.3,86.7]:ties.append((x,5.5,1.4,2.8,'ptc'))
    for y in [18.2,24.2]:ties.append((89.5,y,2.8,1.4,'diode'))
    for x,y,w,dep,kind in ties:cuts.append(box(x-w/2,y-dep/2,TRAY_BOTTOM_Z-1,w,dep,8))
    # Vertical backplate: old bottom terminals now point toward -V. Leave
    # 5 mm between the plate and inner wall for presoldered/insulated leads.
    tray=tray.fuse(box(8.5,7,TRAY_TOP_Z,60,2,14))
    for y in [9,23]:tray=tray.fuse(box(13,y,TRAY_TOP_Z,51,1,1))
    for x in [11.6,64.4]:tray=tray.fuse(box(x,9,8.2,1,14,2))
    # Two short marginal seats lift the module above its presoldered underside.
    for y in [MODULE_Y,MODULE_Y+MODULE_DEPTH-.6]:
        tray=tray.fuse(box(MODULE_X,y,TRAY_TOP_Z,MODULE_WIDTH,.6,1.6))
    for x,y,w,dep in [(74.6,8.6,12.8,1),(74.6,17.9,12.8,1),(74.6,9.6,1,8.3),(86.4,9.6,1,8.3)]:
        tray=tray.fuse(box(x,y,TRAY_TOP_Z,w,dep,2.8))
    # A removable bridge leaves 0.4 mm above the component-height envelope.
    cage=box(MODULE_BOLT_X[0],MODULE_BOLT_Y-2.3,MODULE_CAGE_BOTTOM_Z,18,4.6,MODULE_CAGE_THICKNESS)
    for x in MODULE_BOLT_X:
        tray=tray.fuse(Part.makeCylinder(MODULE_POST_RADIUS,MODULE_CAGE_BOTTOM_Z-TRAY_BOTTOM_Z,V(x,MODULE_BOLT_Y,TRAY_BOTTOM_Z)))
        tray=tray.cut(direct_screw_pilot(V(x,MODULE_BOLT_Y,MODULE_CAGE_BOTTOM_Z),V(0,0,1),MODULE_PILOT_DEPTH))
        cage=cage.fuse(Part.makeCylinder(MODULE_POST_RADIUS,MODULE_CAGE_THICKNESS,V(x,MODULE_BOLT_Y,MODULE_CAGE_BOTTOM_Z)))
        cage=cage.cut(Part.makeCylinder(SCREW_HOLE_DIAMETER/2,3,V(x,MODULE_BOLT_Y,MODULE_CAGE_BOTTOM_Z-.5)))
    # Switch end seats + a generous terminal slot; fixed by a band along X,
    # behind the moving actuator. The band clamps the metal can, not the knob.
    for x in [74.6,82.6]:tray=tray.fuse(box(x,20.55,TRAY_TOP_Z,.8,3.9,1.2))
    for x in [73.3,83.7]:tray=tray.fuse(box(x,20.1,TRAY_TOP_Z,1,4.8,2.5))
    tray=tray.fuse(box(74.3,19.3,TRAY_TOP_Z,9.4,1,2.5))
    cuts.append(box(75.5,21.0,TRAY_BOTTOM_Z-1,7,3,5))
    # Upright PTC and horizontal insulated diode; approximate body cradles.
    for y in [2.5,7.5]:tray=tray.fuse(box(76.5,y,TRAY_TOP_Z,11,1,1.6))
    for x in [79.45,84.55]:cuts.append(Part.makeCylinder(1.1,5,V(x,5.5,TRAY_BOTTOM_Z-1)))
    for y in [18.7,22.9]:tray=tray.fuse(box(87.3,y,TRAY_TOP_Z,4.4,1,1.4))
    for x,y in TRAY_BOLTS:cuts.append(Part.makeCylinder(SCREW_HOLE_DIAMETER/2,5,V(x,y,TRAY_BOTTOM_Z-1)))
    for cut in cuts:tray=tray.cut(cut)
    holder=box(HOLDER_X,HOLDER_Y,HOLDER_BOTTOM_Z,HOLDER_LENGTH,HOLDER_HEIGHT,HOLDER_WIDTH)
    module=box(MODULE_X,MODULE_Y,MODULE_BOTTOM_Z,MODULE_WIDTH,MODULE_DEPTH,MODULE_HEIGHT)
    switch=box(SWITCH_X-SWITCH_WIDTH/2,SWITCH_Y-SWITCH_DEPTH/2,SWITCH_BOTTOM_Z,SWITCH_WIDTH,SWITCH_DEPTH,SWITCH_HEIGHT)
    knob=box(SWITCH_X-2,SWITCH_Y+SWITCH_DEPTH/2,SWITCH_BOTTOM_Z+1,4,4,2)
    ptc=box(82-PTC_WIDTH/2,5.5-PTC_DEPTH/2,TRAY_TOP_Z,PTC_WIDTH,PTC_DEPTH,PTC_HEIGHT)
    diode=Part.makeCylinder(1.3,3.5,V(87.75,21.3,TRAY_TOP_Z+1.3),V(1,0,0))
    # Single solids are printable; supplied parts remain separate references.
    return tray.removeSplitter(),cage.removeSplitter(),holder,module,switch.fuse(knob),ptc,diode,ties


def hex_prism(center,across_flats,height):
    r=across_flats/math.sqrt(3)
    pts=[V(center.x+r*math.cos(math.pi*i/3),center.y+r*math.sin(math.pi*i/3),center.z) for i in range(6)]
    return Part.Face(Part.makePolygon(pts+[pts[0]])).extrude(V(0,0,height))


def direct_screw_pilot(top,axis,depth):
    """Unthreaded printed hex pilot; an M2 screw forms its own PLA thread.

    The circumradius matches the inherited trackball mounting holes (1 mm).
    A small mouth lead-in helps start the screw square without heated inserts.
    """
    hole=hex_prism(V(0,0,0),PILOT_ACROSS_FLATS,depth+.01)
    hole.transformShape(App.Placement(top-axis*depth,App.Rotation(V(0,0,1),axis)).toMatrix(),True)
    lead=Part.makeCone(PILOT_ACROSS_FLATS/2,1.1,PILOT_ENTRY_DEPTH+.01,top-axis*PILOT_ENTRY_DEPTH,axis)
    return hole.fuse(lead)


def band_reference(points,width_axis,width=2.5,thickness=.5):
    pieces=[]
    for p,q in zip(points,points[1:]+points[:1]):
        along=q-p;along.normalize()
        offset=width_axis.cross(along)*(thickness/2)
        corners=[p-width_axis*(width/2)-offset,q-width_axis*(width/2)-offset,q-width_axis*(width/2)+offset,p-width_axis*(width/2)+offset]
        pieces.append(Part.Face(Part.makePolygon(corners+[corners[0]])).extrude(width_axis*width))
    for p in points:pieces.append(Part.makeCylinder(thickness/2,width,p-width_axis*(width/2),width_axis))
    band=pieces[0]
    for piece in pieces[1:]:band=band.fuse(piece)
    return band.removeSplitter()


def component_ties(holder):
    straps=[];holder_straps=[]
    top=HOLDER_BOTTOM_Z+HOLDER_WIDTH+.25
    for x in [13.5,63.5]:
        rear=HOLDER_Y+HOLDER_HEIGHT+.25
        pts=[V(x,5.2,3.4),V(x,5.2,top),V(x,rear,top),V(x,rear,3.4)]
        band=band_reference(pts,V(1,0,0));straps.append(band);holder_straps.append(band)
    for low,high,y,part_low,part_high,top,turn in [
        (75.3,86.7,5.5,77.5,86.5,TRAY_TOP_Z+PTC_HEIGHT+.25,TRAY_TOP_Z),
        (72.6,86.1,22.5,74.35,83.65,SWITCH_BOTTOM_Z+SWITCH_HEIGHT+.25,9.2)]:
        pts=[V(low,y,3.4),V(low,y,turn),V(part_low,y,top),V(part_high,y,top),V(high,y,turn),V(high,y,3.4)]
        straps.append(band_reference(pts,V(0,1,0)))
    pts=[V(89.5,18.2,3.4),V(89.5,18.2,8.2),V(89.5,19.75,TRAY_TOP_Z+2.85),V(89.5,22.85,TRAY_TOP_Z+2.85),V(89.5,24.2,8.2),V(89.5,24.2,3.4)]
    straps.append(band_reference(pts,V(1,0,0)))
    return Part.makeCompound(straps),Part.makeCompound(holder_straps)


def tie_head_references(side):
    # Keep the thicker locks ABOVE the tray. Its 2.4 mm underside gap only
    # accommodates insulated leads and the 0.5 mm tie bands, not their locks.
    # Conservative 4.5 x 4 x 4 mm boxes; switch lock is rotated in plan.
    heads=[box(x-2.25,2.5,12,4.5,4,4) for x in [13.5,63.5]]
    heads += [box(73.05,3.5,7.8,4.5,4,4),box(70.6,20.25,9.2,4,4.5,4),box(87.25,21.7,9.05,4.5,4,4)]
    cable_x=95.25 if side=='Left' else 4.75
    cable_head=box(cable_x-2.25,15.5,CABLE_OUTLET_Z,4.5,4,4)
    return Part.makeCompound(heads),cable_head


def battery_access(body):
    """Side-facing fixed holder, sliding PLA door, integral release leaf.

    Rear is the long +V face. Rails capture the door in Z/V; a right end
    stop and a left catch prevent travel until the integral leaf is pressed.
    The released envelope is a clearance aid, not an elastic simulation.
    """
    opening=box(12,25.5,7.7,53,9,12.1)
    body=body.cut(opening)
    for z in [6.0,20.5]:body=body.fuse(box(7,28,z,62.3,3.4,1))
    body=body.fuse(box(7,30.5,7,62.3,.9,1.1))
    body=body.fuse(box(7,30.5,19.3,62.3,.9,1.2))
    body=body.fuse(box(68.3,28,7,1,3.4,13.5))
    # Outer catch hangs from the upper rail. Press the IN-PLANE leaf down
    # to bring its hook below Z=11.1; this avoids a hidden underside support.
    body=body.fuse(box(7.2,30.5,11.1,1.5,.9,9.4))
    door=box(9,28.3,7.3,59,1.9,12.9)
    door=door.cut(box(8.9,28.2,8.75,16.1,2.1,1.25))
    door=door.cut(box(8.9,28.2,10.8,16.1,2.1,3.7))
    # 16 mm long, 0.8 mm thick leaf, free at -U. Closing ramp on the hook.
    pts=[V(9,30.2,10.8),V(9,30.2,11.7),V(10.2,30.2,10.8)]
    hook=Part.Face(Part.makePolygon(pts+[pts[0]])).extrude(V(0,.9,0)).fuse(box(9,30.2,10,1.2,.9,.8))
    pad=box(10.3,30.2,10,5,.4,.8)
    proud=hook.fuse(pad)
    door=door.fuse(proud).fuse(box(34.5,30.2,8.8,8,2.8,1.8)).removeSplitter()
    shifted=proud.copy();shifted.translate(V(0,0,-DOOR_RELEASE_DEFLECTION))
    released=door.cut(proud).fuse(shifted).removeSplitter()
    opened=door.copy();opened.translate(V(-DOOR_OPEN_TRAVEL,0,0))
    blocked=door.copy();blocked.translate(V(-1,0,0))
    assert intersection_volume(blocked,body)>.01,'Door hook does not catch'
    # Extrude every door face backwards to cover the complete sliding motion,
    # not only a few sampled poses; degenerate swept faces have no volume.
    # Press only until the hook passes the catch (3 mm), then the leaf can
    # relax while the door continues to slide out normally.
    relaxed=door.copy();relaxed.translate(V(-3,0,0))
    sweeps=[released,relaxed,opened]
    for shape,travel in [(released,3),(relaxed,DOOR_OPEN_TRAVEL-3)]:
        for face in shape.Faces:
            swept=face.extrude(V(-travel,0,0))
            if abs(swept.Volume)>1e-8:
                if swept.Volume<0:swept.reverse()
                sweeps.append(swept)
    # A rigid rotation of the free leaf region checks the available pressing
    # space. This is only a clearance approximation, not a bending analysis.
    free=box(9,28.3,10,14,1.9,.8).fuse(proud)
    free.rotate(V(25,29.25,10.4),V(0,1,0),-math.degrees(math.atan(DOOR_RELEASE_DEFLECTION/16)))
    frame=door.cut(box(8.9,28.2,9.99,16.2,2.1,.82).fuse(proud))
    assert intersection_volume(free,frame)<1e-5,'Insufficient release-leaf pressing space'
    sweep=Part.makeCompound(sweeps)
    return body.removeSplitter(),door,released,opened,sweep,opening,intersection_volume(blocked,body)


def cable_reference(side,usb_shape,a,b,angle,case_shapes):
    """Position reference, not a vendor STEP or a verified connector fit."""
    bb=usb_shape.BoundBox
    cx=(bb.XMin+bb.XMax)/2;cz=(bb.ZMin+bb.ZMax)/2
    metal=box(cx-4.125,bb.YMax-1.5,cz-1.2,8.25,6,2.4)
    boot=box(cx-6,bb.YMax+4.5,cz-3,12,12,6)
    plug=map_shape(metal.fuse(boot),a,b,angle)
    end=frame_matrix(a,b,angle).multVec(V(cx,bb.YMax+16.5,cz))
    direction=frame_matrix(a,b,angle).multVec(V(cx,bb.YMax+17.5,cz))-end
    sign=1 if side=='Left' else -1
    x=BAR_LENGTH if sign==1 else 0
    extent=max(s.BoundBox.XMax for s in case_shapes) if sign==1 else min(s.BoundBox.XMin for s in case_shapes)
    outside=(max(extent,plug.BoundBox.XMax)+20) if sign==1 else (min(extent,plug.BoundBox.XMin)-20)
    points=[V(x,14,CABLE_OUTLET_Z),V(outside,14,CABLE_OUTLET_Z),V(outside,8,CABLE_OUTLET_Z+12),end+direction*18,end+direction*8,end]
    curve=Part.BSplineCurve();curve.interpolate(Points=points,InitialTangent=V(sign,0,0),FinalTangent=-direction)
    edge=curve.toShape()
    profile=Part.Wire([Part.makeCircle(CABLE_DIAMETER/2,points[0],V(sign,0,0))])
    cable=Part.Wire([edge]).makePipeShell([profile],True,False)
    stub=Part.makeCylinder(CABLE_DIAMETER/2,6,V(BAR_LENGTH-6 if sign==1 else 6,14,CABLE_OUTLET_Z),V(sign,0,0))
    cable=cable.fuse(stub).removeSplitter()
    return plug,cable,edge.Length,end


def build_bar(doc,side,case_shape,a,b,usb_shape,top_shape):
    angle=tilt_for_desk(case_shape,a,b)
    n=V(0,math.sin(angle),math.cos(angle))
    d=math.dist(a,b);mu=[(BAR_LENGTH-d)/2,(BAR_LENGTH+d)/2]
    print(f'{side}: magnet span {d:.4f}; tent angle {math.degrees(angle):.3f} degrees')
    group=doc.addObject('App::DocumentObjectGroup',side+'Bar');group.Label=side+' bar / assembled'
    refs=doc.addObject('App::DocumentObjectGroup',side+'References');refs.Label=side+' reference envelopes';group.addObject(refs)

    outer_body=wedge(LID_THICKNESS,None,angle)
    body=outer_body.cut(Part.makeBox(BAR_LENGTH-2*WALL,BAR_WIDTH-2*WALL,50,V(WALL,WALL,FLOOR)))
    tray,cage,holder,module,switch,ptc,diode,ties=component_tray()
    for x,y,depth in [(8,3.3,1),(8,23.7,1),(88,3.3,1),(74,24.0,.7)]:
        body=body.fuse(box(x,y,FLOOR,4,depth,TRAY_BOTTOM_Z-FLOOR))
    # Solid PLA bosses replace captive nuts. Blind pilots extend into the
    # floor but retain 1 mm beneath them; M2x5 tips stop 1.2 mm above the desk.
    for x,y in TRAY_BOLTS:
        body=body.fuse(Part.makeCylinder(3.1,TRAY_BOTTOM_Z-FLOOR,V(x,y,FLOOR)))
        body=body.cut(direct_screw_pilot(V(x,y,TRAY_BOTTOM_Z),V(0,0,1),TRAY_PILOT_DEPTH))
    bolt_positions=[(x,y) for x in [4.2,BAR_LENGTH-4.2] for y in [5.5,BAR_WIDTH-5.5]]
    # The inclined lids must meet the vertical boss tops along the SAME
    # normal axis, not at the same XY: project the boss centers to the roof.
    roof_shift=LID_THICKNESS*math.sin(angle)*math.cos(angle)
    cover_bolt_positions=[(x,y+roof_shift) for x,y in bolt_positions]
    for x,y in bolt_positions:
        boss=Part.makeCylinder(2.9,40,V(x,y,FLOOR)).common(outer_body)
        body=body.fuse(boss)
        top=V(x,y,plane_z(y,angle)-LID_THICKNESS)
        body=body.cut(direct_screw_pilot(top,n,LID_PILOT_DEPTH))

    switch_cutter=box(SWITCH_X-7,BAR_WIDTH-4,SWITCH_BOTTOM_Z-.4,14,6,SWITCH_HEIGHT+.8)
    body=body.cut(switch_cutter)
    # Each outlet now faces the near USB-C port. The flexible C-plug cable is
    # anchored by its jacket; there is deliberately no rigid plug cantilever.
    exit_x=BAR_LENGTH if side=='Left' else 0
    sign=1 if side=='Left' else -1
    saddle_x=93.2 if side=='Left' else 2.25
    saddle=box(saddle_x,10,FLOOR,5,8,CABLE_OUTLET_Z-FLOOR)
    saddle=saddle.cut(Part.makeCylinder((CABLE_DIAMETER+.6)/2,7,V(saddle_x-1,14,CABLE_OUTLET_Z),V(1,0,0)))
    saddle=saddle.cut(box(saddle_x+1,9.5,10.5,3,9,2))
    body=body.fuse(saddle)
    wire_hole=Part.makeCylinder((CABLE_DIAMETER+1)/2,6,V(exit_x-sign*4,14,CABLE_OUTLET_Z),V(sign,0,0))
    body=body.cut(wire_hole)
    body,door,released_door,open_door,door_sweep,access_opening,door_blocked_volume=battery_access(body)

    lid=wedge(COVER_THICKNESS,LID_THICKNESS,angle)
    cover=wedge(0,COVER_THICKNESS,angle)
    # Side alignment tongues stop before the end screw bosses.
    for y in [2.35,BAR_WIDTH-3.2]:
        rail=Part.makeBox(84,.85,40,V(8,y,0)).common(wedge(LID_THICKNESS,LID_THICKNESS+1.2,angle))
        lid=lid.fuse(rail)
    for x,y in cover_bolt_positions:
        top=V(x,y,plane_z(y,angle))
        lid=lid.cut(Part.makeCylinder(SCREW_HOLE_DIAMETER/2,8,top-n*7,n))
        cover=cover.cut(Part.makeCylinder(SCREW_HOLE_DIAMETER/2,8,top-n*7,n))
        cover=cover.cut(Part.makeCylinder(SCREW_HEAD_DIAMETER/2,SCREW_HEAD_RECESS+.1,top-n*SCREW_HEAD_RECESS,n))

    magnets=[];finger_envelopes=[]
    for i,x in enumerate(mu,1):
        contact=V(x,BAR_WIDTH/2,CONTACT_CENTER_HEIGHT)
        top=contact-n*(COVER_THICKNESS*math.cos(angle))
        pocket=Part.makeCylinder(MAGNET_POCKET_DIAMETER/2,MAGNET_POCKET_DEPTH+.2,top-n*MAGNET_POCKET_DEPTH,n)
        funnel=Part.makeCone(MAGNET_POCKET_DIAMETER/2,FINGER_DIAMETER/2,FINGER_FUNNEL_DEPTH+.001,top-n*FINGER_FUNNEL_DEPTH,n)
        lid=lid.cut(pocket.fuse(funnel))
        # The counterbore opens from below; 0.5 mm of continuous plastic
        # remains above the magnet. Shared corner screws capture the cover.
        window=Part.makeCylinder(6.5,3,contact-n*2,n).common(wedge(COVER_MAGNET_SKIN,COVER_THICKNESS+.1,angle))
        cover=cover.cut(window)
        magnet=Part.makeCylinder(MAGNET_DIAMETER/2,MAGNET_THICKNESS,top-n*MAGNET_POCKET_DEPTH,n)
        magnets.append(magnet)
        finger_envelopes.append(Part.makeCylinder(FINGER_DIAMETER/2,10,top,n))
        add_feature(doc,refs,side+f'Magnet{i}',f'Ø12 × 1 captive magnet {i} / match polarity to case',magnet,(.7,.72,.76),False)
    lid=lid.removeSplitter()
    cover=cover.removeSplitter()
    magnet_cover_checks=[]
    for x,magnet in zip(mu,magnets):
        contact=V(x,BAR_WIDTH/2,CONTACT_CENTER_HEIGHT)
        skin_normal=COVER_MAGNET_SKIN*math.cos(angle)
        membrane=Part.makeCylinder(MAGNET_DIAMETER/2,skin_normal,contact-n*skin_normal,n)
        coverage=intersection_volume(cover,membrane)/membrane.Volume
        movement=(COVER_THICKNESS-COVER_MAGNET_SKIN)*math.cos(angle)+MAGNET_POCKET_DEPTH-MAGNET_THICKNESS
        displaced=magnet.copy();displaced.translate(n*(movement+.01))
        blocked=intersection_volume(cover,displaced)
        assert coverage>1-1e-6 and blocked>.01,(coverage,blocked)
        magnet_cover_checks.append({'closed_membrane_coverage_ratio':coverage,'blocked_escape_overlap_mm3':blocked})

    # Thread crests intentionally bite into PLA. Only a Ø1.5 core is used
    # here to check axial insertion/clearance; it is not a thread strength test.
    screw_cores=[];screw_heads=[]
    for x,y in cover_bolt_positions:
        seat=V(x,y,plane_z(y,angle))-n*SCREW_HEAD_RECESS
        screw_cores.append(Part.makeCylinder(.75,COVER_SCREW_LENGTH,seat-n*COVER_SCREW_LENGTH,n))
        screw_heads.append(Part.makeCylinder(2.1,.5,seat,n))
    for positions,z in [(TRAY_BOLTS,TRAY_TOP_Z),([(x,MODULE_BOLT_Y) for x in MODULE_BOLT_X],MODULE_CAGE_BOTTOM_Z+MODULE_CAGE_THICKNESS)]:
        for x,y in positions:
            screw_cores.append(Part.makeCylinder(.75,INTERNAL_SCREW_LENGTH,V(x,y,z-INTERNAL_SCREW_LENGTH)))
            screw_heads.append(Part.makeCylinder(1.9,1.6,V(x,y,z)))
    core_envelope=Part.makeCompound(screw_cores)
    head_envelope=Part.makeCompound(screw_heads)

    hx=HOLDER_X+HOLDER_LENGTH/2
    hy=HOLDER_Y+HOLDER_HEIGHT-5.25
    # A cell cylinder is for visual inspection; all acceptance checks use the
    # larger holder+cell envelope, not an invented precise holder STEP model.
    battery=Part.makeCylinder(5.25,44.5,V(hx-22.25,hy,HOLDER_MIDDLE_Z),V(1,0,0))
    battery_out=battery.copy();battery_out.translate(V(0,22,0))
    # Continuous pull-out capsule, enlarged 1 mm at EACH axial end to allow
    # spring compression / end-first removal without hitting retaining bands.
    cell_sweep=Part.makeCylinder(5.4,46.5,V(hx-23.25,hy,HOLDER_MIDDLE_Z),V(1,0,0))
    end_sweep=cell_sweep.copy();end_sweep.translate(V(0,22,0))
    cell_sweep=cell_sweep.fuse(end_sweep).fuse(box(hx-23.25,hy,HOLDER_MIDDLE_Z-5.4,46.5,22,10.8)).removeSplitter()
    finger_access=Part.makeCylinder(5,10,V(hx,HOLDER_Y+HOLDER_HEIGHT,HOLDER_MIDDLE_Z),V(0,1,0))
    straps,holder_straps=component_ties(holder)
    component_heads,cable_head=tie_head_references(side)
    tie_heads=Part.makeCompound([component_heads,cable_head])
    electronics=Part.makeCompound([module,switch,ptc,diode])
    tilted_case=map_shape(case_shape,a,b,angle)
    tilted_top=map_shape(top_shape,a,b,angle)
    plug,cable,cable_length,cable_end=cable_reference(side,usb_shape,a,b,angle,[tilted_case,tilted_top])

    bobj=add_feature(doc,group,side+'Housing',side+' housing / print base down',body,(.15,.31,.43))
    lobj=add_feature(doc,group,side+'Lid',side+' inner lid / load magnets with cover removed',lid,(.72,.82,.87))
    cobj=add_feature(doc,group,side+'Cover',side+' screwed magnet cover / 0.5 mm closed windows',cover,(.44,.69,.79))
    tobj=add_feature(doc,group,side+'Tray',side+' PLA component tray / solder before mounting',tray,(.35,.64,.46))
    mcobj=add_feature(doc,group,side+'ModuleCage',side+' removable boost-module retaining bridge',cage,(.47,.72,.57))
    dobj=add_feature(doc,group,side+'BatteryDoor',side+' rear sliding door / press leaf then slide -U',door,(.44,.69,.79))
    hobj=add_feature(doc,refs,side+'Holder','GB-BH-4X1-WP + AAA clearance envelope (height unmeasured)',holder,(.30,.30,.33),False)
    add_feature(doc,refs,side+'AAA','AAA cell reference',battery,(.95,.63,.21),False)
    add_feature(doc,refs,side+'BatteryDoorOpen','open rear door / 60 mm slide, release-envelope assumption',open_door,(.44,.69,.79),False)
    add_feature(doc,refs,side+'BatteryPullOut','AAA removed to rear / holder stays fixed',battery_out,(.95,.63,.21),False)
    add_feature(doc,refs,side+'BatteryExchangeSweep','continuous AAA pull-out + 1 mm axial end clearance',cell_sweep,(.95,.63,.21),False)
    add_feature(doc,refs,side+'BatteryFingerAccess','Ø10 mm fingertip/nail approach / access assumption',finger_access,(.1,.75,.9),False)
    add_feature(doc,refs,side+'BoostModule','AE-XCL103-5V0 / 10 × 7.5 × 3 mm assumed height',module,(.1,.48,.22),False)
    add_feature(doc,refs,side+'Switch','SS12D01G4 + actuator envelope',switch,(.35,.35,.38),False)
    add_feature(doc,refs,side+'PTC','MF-R050 / conservative unmeasured envelope',ptc,(.8,.6,.23),False)
    add_feature(doc,refs,side+'Diode','1S4 / Ø2.6 × 3.5 mm body envelope',diode,(.3,.3,.33),False)
    add_feature(doc,refs,side+'ScrewCores','eight screw cores / Ø1.5 axial fit reference; threads not modeled',core_envelope,(.65,.65,.67),False)
    add_feature(doc,refs,side+'ScrewHeads','M2x6 low heads + M2x5 pan heads / dimensional assumptions',head_envelope,(.65,.65,.67),False)
    add_feature(doc,refs,side+'ComponentTies','five 2.5 mm tie routing references / separate lock envelopes',straps,(.22,.25,.29),False)
    add_feature(doc,refs,side+'TieHeads','six tie lock envelopes / place ABOVE tray, actual locks unmeasured',tie_heads,(.22,.25,.29),False)
    add_feature(doc,refs,side+'FixedUSBCPlug','fixed Type-C male plug / assumed molding envelope',plug,(.55,.56,.60),False)
    add_feature(doc,refs,side+'FixedCable','fixed USB-C cable route / assumed Ø'+str(CABLE_DIAMETER),cable,(.18,.18,.21),False)
    for i,shape in enumerate(finger_envelopes,1):
        o=add_feature(doc,refs,side+f'Finger{i}','Ø22 mm fingertip approach / remove cover first',shape,(.1,.75,.9),False)
        if o.ViewObject:o.ViewObject.Transparency=80
    kobj=add_feature(doc,refs,side+'Keyboard','kb-1 bottom shell / tilted fit reference',map_shape(case_shape,a,b,angle),(.82,.82,.85),False)
    uobj=add_feature(doc,refs,side+'KeyboardUSB','kb-1 existing USB-C receptacle / position reference only',map_shape(usb_shape,a,b,angle),(.9,.44,.28),False)
    add_feature(doc,refs,side+'KeyboardTop','kb-1 top shell / cable clearance reference',tilted_top,(.8,.8,.83),False)
    if kobj.ViewObject:kobj.ViewObject.Transparency=60
    for obj in [bobj,lobj,cobj,tobj,mcobj,dobj]:
        for name,value in [('Length',BAR_LENGTH),('Width',BAR_WIDTH),('CenterHeight',CONTACT_CENTER_HEIGHT),('HolderHeightAssumption',HOLDER_HEIGHT),('MagnetPitch',d)]:
            obj.addProperty('App::PropertyLength',name,'Design dimensions');setattr(obj,name,value)
            obj.setEditorMode(name,1)
        obj.addProperty('App::PropertyAngle','TentingAngle','Design dimensions');obj.TentingAngle=math.degrees(angle)
        obj.setEditorMode('TentingAngle',1)

    for obj in [tobj,mcobj]:
        obj.addProperty('App::PropertyString','Assembly','Assembly notes')
        obj.Assembly='Presolder insulated leads; ties secure holder/switch/PTC/diode; M2x5 screws directly into PLA secure tray and module bridge; no nuts or inserts.'
    tobj.addProperty('App::PropertyLength','UndersideWireChannelWidth','Design dimensions');tobj.UndersideWireChannelWidth=3
    tobj.addProperty('App::PropertyLength','UndersideWireChannelDepth','Design dimensions');tobj.UndersideWireChannelDepth=1

    checks={
        'body_valid':body.isValid(),'lid_valid':lid.isValid(),'cover_valid':cover.isValid(),
        'tray_valid':tray.isValid(),'module_cage_valid':cage.isValid(),
        'body_solids':len(body.Solids),'lid_solids':len(lid.Solids),'cover_solids':len(cover.Solids),
        'tray_solids':len(tray.Solids),'module_cage_solids':len(cage.Solids),
        'door_valid':door.isValid(),'door_solids':len(door.Solids),
        'door_body_overlap_mm3':intersection_volume(door,body),
        'door_lid_overlap_mm3':intersection_volume(door,lid),
        'door_cover_overlap_mm3':intersection_volume(door,cover),
        'door_keyboard_overlap_mm3':intersection_volume(door,Part.makeCompound([tilted_case,tilted_top])),
        'door_slide_body_overlap_mm3':intersection_volume(door_sweep,body),
        'door_slide_keyboard_overlap_mm3':intersection_volume(door_sweep,Part.makeCompound([tilted_case,tilted_top])),
        'door_slide_cable_overlap_mm3':intersection_volume(door_sweep,cable),
        'door_slide_holder_overlap_mm3':intersection_volume(door_sweep,holder),
        'battery_exchange_plastic_overlap_mm3':intersection_volume(cell_sweep,Part.makeCompound([body,tray,cage,lid,cover,open_door])),
        'battery_exchange_ties_overlap_mm3':intersection_volume(cell_sweep,Part.makeCompound([straps,tie_heads])),
        'battery_exchange_keyboard_overlap_mm3':intersection_volume(cell_sweep,Part.makeCompound([tilted_case,tilted_top])),
        'battery_finger_plastic_overlap_mm3':intersection_volume(finger_access,Part.makeCompound([body,tray,cage,lid,cover,open_door])),
        'battery_finger_keyboard_overlap_mm3':intersection_volume(finger_access,Part.makeCompound([tilted_case,tilted_top])),
        'door_requires_screws_for_battery_exchange':False,
        'door_opening_mm':[53,12.1],
        'door_slide_travel_mm':DOOR_OPEN_TRAVEL,
        'door_release_deflection_assumption_mm':DOOR_RELEASE_DEFLECTION,
        'door_release_leaf_dimensions_mm':[16,1.9,.8],
        'door_rail_clearance_mm':.3,
        'battery_exchange_radius_allowance_mm':.15,
        'battery_exchange_axial_allowance_each_end_mm':1.0,
        'door_latch_blocks_slide_overlap_mm3':door_blocked_volume,
        'body_lid_overlap_mm3':intersection_volume(body,lid),
        'cover_body_overlap_mm3':intersection_volume(cover,body),
        'cover_lid_overlap_mm3':intersection_volume(cover,lid),
        'cover_magnets_overlap_mm3':sum(intersection_volume(cover,m) for m in magnets),
        'body_tray_overlap_mm3':intersection_volume(body,tray),
        'lid_tray_overlap_mm3':intersection_volume(lid,tray),
        'body_module_cage_overlap_mm3':intersection_volume(body,cage),
        'lid_module_cage_overlap_mm3':intersection_volume(lid,cage),
        'tray_module_cage_overlap_mm3':intersection_volume(tray,cage),
        'tray_holder_overlap_mm3':intersection_volume(tray,holder),
        'tray_electronics_overlap_mm3':intersection_volume(tray,electronics),
        'cage_electronics_overlap_mm3':intersection_volume(cage,electronics),
        'cage_holder_overlap_mm3':intersection_volume(cage,holder),
        'screw_cores_plastic_overlap_mm3':intersection_volume(core_envelope,Part.makeCompound([body,tray,cage,lid,cover])),
        'screw_heads_plastic_overlap_mm3':intersection_volume(head_envelope,Part.makeCompound([body,tray,cage,lid,cover])),
        'screw_heads_holder_overlap_mm3':intersection_volume(head_envelope,holder),
        'screw_heads_components_overlap_mm3':intersection_volume(head_envelope,electronics),
        'screw_heads_ties_overlap_mm3':intersection_volume(head_envelope,Part.makeCompound([straps,tie_heads])),
        'component_ties_body_overlap_mm3':intersection_volume(straps,body),
        'component_ties_tray_overlap_mm3':intersection_volume(straps,tray),
        'component_ties_lid_overlap_mm3':intersection_volume(straps,lid),
        'component_ties_components_overlap_mm3':intersection_volume(straps,electronics),
        'component_ties_holder_overlap_mm3':intersection_volume(straps,holder),
        'holder_ties_battery_overlap_mm3':intersection_volume(holder_straps,battery),
        'tie_heads_body_overlap_mm3':intersection_volume(tie_heads,body),
        'tie_heads_tray_overlap_mm3':intersection_volume(tie_heads,tray),
        'tie_heads_lid_overlap_mm3':intersection_volume(tie_heads,lid),
        'tie_heads_cage_overlap_mm3':intersection_volume(tie_heads,cage),
        'tie_heads_components_overlap_mm3':intersection_volume(tie_heads,electronics),
        'tie_heads_holder_overlap_mm3':intersection_volume(tie_heads,holder),
        'tie_heads_cable_overlap_mm3':intersection_volume(tie_heads,cable),
        'holder_body_overlap_mm3':intersection_volume(body,holder),
        'holder_lid_overlap_mm3':intersection_volume(lid,holder),
        'electronics_body_overlap_mm3':intersection_volume(body,electronics),
        'electronics_lid_overlap_mm3':intersection_volume(lid,electronics),
        'magnets_lid_overlap_mm3':sum(intersection_volume(lid,m) for m in magnets),
        'keyboard_bar_overlap_mm3':intersection_volume(kobj.Shape,Part.makeCompound([body,lid,cover,tray,cage])),
        'keyboard_top_bar_overlap_mm3':intersection_volume(tilted_top,Part.makeCompound([body,lid,cover,tray,cage])),
        'cable_body_overlap_mm3':intersection_volume(cable,body),
        'cable_keyboard_overlap_mm3':intersection_volume(cable,Part.makeCompound([tilted_case,tilted_top])),
        'cable_tray_overlap_mm3':intersection_volume(cable,tray),
        'cable_lid_overlap_mm3':intersection_volume(cable,lid),
        'cable_cover_overlap_mm3':intersection_volume(cable,cover),
        'magnet_case_xy_mm':[a,b],'magnet_span_mm':d,'magnet_bar_u_mm':mu,
        'tenting_angle_deg':math.degrees(angle),
        'keyboard_fore_aft_axis_inclination_deg':math.degrees(math.asin(math.sin(angle)*abs(b[0]-a[0])/d)),
        'keyboard_lowest_z_mm':kobj.Shape.BoundBox.ZMin,
        'holder_height_assumption_mm':HOLDER_HEIGHT,
        'holder_opening_faces_rear':True,
        'holder_rotated_envelope_mm':[HOLDER_LENGTH,HOLDER_HEIGHT,HOLDER_WIDTH],
        'holder_roof_clearance_mm':plane_z(HOLDER_Y+HOLDER_HEIGHT,angle)-LID_THICKNESS-(HOLDER_BOTTOM_Z+HOLDER_WIDTH),
        'finger_opening_diameter_mm':FINGER_DIAMETER,
        'magnet_pocket_diameter_mm':MAGNET_POCKET_DIAMETER,
        'magnet_face_recess_mm':COVER_THICKNESS*math.cos(angle)+MAGNET_POCKET_DEPTH-MAGNET_THICKNESS,
        'cover_thickness_vertical_mm':COVER_THICKNESS,
        'cover_magnet_skin_vertical_mm':COVER_MAGNET_SKIN,
        'cover_magnet_skin_normal_mm':COVER_MAGNET_SKIN*math.cos(angle),
        'magnet_travel_before_cover_mm':(COVER_THICKNESS-COVER_MAGNET_SKIN)*math.cos(angle)+MAGNET_POCKET_DEPTH-MAGNET_THICKNESS,
        'magnet_case_gap_after_attraction_mm':.5+COVER_MAGNET_SKIN*math.cos(angle),
        'contact_center_height_mm':CONTACT_CENTER_HEIGHT,
        'total_lid_thickness_vertical_mm':LID_THICKNESS,
        'keyboard_usb_center_bar_xyz_mm':[uobj.Shape.CenterOfMass.x,uobj.Shape.CenterOfMass.y,uobj.Shape.CenterOfMass.z],
        'usb_c_plug_mount_implemented':False,
        'fixed_usb_c_cable_saddle_implemented':True,
        'custom_power_pcb_used':False,
        'inner_lid_long_posts_count':0,
        'tray_dimensions_mm':[TRAY_LENGTH,TRAY_WIDTH,TRAY_THICKNESS],
        'tray_bottom_z_mm':TRAY_BOTTOM_Z,
        'tray_floor_gap_mm':TRAY_BOTTOM_Z-FLOOR,
        'holder_terminal_pitch_mm':HOLDER_PIN_PITCH,
        'holder_terminal_hole_diameter_mm':HOLDER_TERMINAL_HOLE,
        'module_body_assumption_mm':[MODULE_WIDTH,MODULE_DEPTH,MODULE_HEIGHT],
        'module_underside_clearance_mm':MODULE_BOTTOM_Z-TRAY_TOP_Z,
        'module_cage_top_clearance_mm':MODULE_CAGE_BOTTOM_Z-(MODULE_BOTTOM_Z+MODULE_HEIGHT),
        'switch_body_assumption_mm':[SWITCH_WIDTH,SWITCH_DEPTH,SWITCH_HEIGHT],
        'ptc_body_assumption_mm':[PTC_WIDTH,PTC_DEPTH,PTC_HEIGHT],
        'cable_diameter_assumption_mm':CABLE_DIAMETER,
        'cable_outlet_side_u_mm':exit_x,
        'cable_outside_centerline_length_mm':cable_length,
        'cable_plug_boot_assumption_mm':[12,12,6],
        'tie_slot_positions':ties,
        'tray_fastener_positions':TRAY_BOLTS,
        'cover_fastener_positions':cover_bolt_positions,
        'housing_cover_boss_positions':bolt_positions,
        'fastening_method':'M2 screws form threads directly in printed PLA hex pilots',
        'insert_nuts_count':0,
        'hex_nuts_count':0,
        'pilot_hex_across_flats_mm':PILOT_ACROSS_FLATS,
        'pilot_hex_circumdiameter_mm':2.0,
        'pilot_depths_cover_tray_module_mm':[LID_PILOT_DEPTH,TRAY_PILOT_DEPTH,MODULE_PILOT_DEPTH],
        'screw_lengths_cover_internal_mm':[COVER_SCREW_LENGTH,INTERNAL_SCREW_LENGTH],
        'screw_engagement_cover_tray_module_mm':[COVER_SCREW_LENGTH+SCREW_HEAD_RECESS-LID_THICKNESS*math.cos(angle),INTERNAL_SCREW_LENGTH-TRAY_THICKNESS,INTERNAL_SCREW_LENGTH-MODULE_CAGE_THICKNESS],
        'screw_bottom_clearance_cover_tray_module_mm':[LID_PILOT_DEPTH-(COVER_SCREW_LENGTH+SCREW_HEAD_RECESS-LID_THICKNESS*math.cos(angle)),TRAY_PILOT_DEPTH-(INTERNAL_SCREW_LENGTH-TRAY_THICKNESS),MODULE_PILOT_DEPTH-(INTERNAL_SCREW_LENGTH-MODULE_CAGE_THICKNESS)],
        'tray_pilot_floor_remaining_mm':TRAY_BOTTOM_Z-TRAY_PILOT_DEPTH,
        'holder_ties_aaa_axial_clearance_mm':1.5,
        'tie_head_envelope_assumption_mm':[4.5,4,4],
        'tie_heads_placed_above_tray':True,
        'magnet_cover_checks':magnet_cover_checks,
    }
    assert all(checks[k+'_valid'] for k in ['body','lid','cover','tray','module_cage','door']),checks
    assert all(checks[k+'_solids']==1 for k in ['body','lid','cover','tray','module_cage','door']),checks
    for key,value in checks.items():
        if key.endswith('_overlap_mm3') and key!='door_latch_blocks_slide_overlap_mm3':
            if key.startswith('component_ties') and value>=1e-5:
                target={'component_ties_body_overlap_mm3':body,'component_ties_tray_overlap_mm3':tray,'component_ties_lid_overlap_mm3':lid,'component_ties_components_overlap_mm3':electronics,'component_ties_holder_overlap_mm3':holder}[key]
                for i,s in enumerate(straps.Solids):
                    overlap=s.common(target)
                    if overlap.Volume>1e-5:print(key,i,overlap.Volume,overlap.BoundBox,flush=True)
            assert value<1e-5,(key,value)
    assert checks['holder_roof_clearance_mm']>.5,checks
    assert min(checks['screw_bottom_clearance_cover_tray_module_mm'])>.15,checks
    assert checks['tray_pilot_floor_remaining_mm']>=1.0,checks
    assert abs(checks['keyboard_lowest_z_mm'])<1e-5,checks
    doc.recompute()
    export_part(bobj,side.lower()+'-housing');export_part(lobj,side.lower()+'-lid');export_part(cobj,side.lower()+'-cover')
    export_part(tobj,side.lower()+'-tray');export_part(mcobj,side.lower()+'-module-cage')
    export_part(dobj,side.lower()+'-battery-door')
    # A second pose makes the magnetic pockets and battery cavity reviewable.
    exploded=doc.addObject('App::DocumentObjectGroup',side+'Exploded');exploded.Label=side+' exploded view (hidden)'
    door_copy=door.copy();door_copy.translate(V(-75,48,0))
    add_feature(doc,exploded,side+'ExplodedBatteryDoor','Rear door removed',door_copy,(.44,.69,.79),False)
    for name,shape,color,z in [('Housing',body,(.15,.31,.43),0),('Tray',tray,(.35,.64,.46),28),('ModuleCage',cage,(.47,.72,.57),34),('HolderEnvelope',holder,(.3,.3,.33),28),('BoostModule',module,(.1,.48,.22),28),('Switch',switch,(.35,.35,.38),28),('PTC',ptc,(.8,.6,.23),28),('Diode',diode,(.3,.3,.33),28),('Ties',straps,(.22,.25,.29),28),('TieHeads',component_heads,(.22,.25,.29),28),('Lid',lid,(.72,.82,.87),62),('Cover',cover,(.44,.69,.79),75),('Magnets',Part.makeCompound(magnets),(.7,.72,.76),62)]:
        s=shape.copy();s.translate(V(0,48,z))
        add_feature(doc,exploded,side+'Exploded'+name,name,s,color,False)
    # Geometry for offline previews comes from actual BRep tessellation.
    preview={}
    for name,shape in [('housing',body),('door',door),('open_door',open_door),('battery_out',battery_out),('lid',lid),('cover',cover),('tray',tray),('module_cage',cage),('holder',holder),('battery',battery),('module',module),('switch',switch),('ptc',ptc),('diode',diode),('components',electronics),('ties',straps),('tie_heads',component_heads),('magnets',Part.makeCompound(magnets)),('keyboard',kobj.Shape),('keyboard_top',tilted_top),('keyboard_usb',uobj.Shape),('usb_plug',plug),('cable',cable)]:
        verts,tri=shape.tessellate(.15)
        preview[name]={'vertices':[[v.x,v.y,v.z] for v in verts],'triangles':tri}
    (OUTPUT/(side.lower()+'-preview-mesh.json')).write_text(json.dumps(preview))
    return checks


def main():
    if not CASE_FILE.is_file():raise FileNotFoundError(CASE_FILE)
    source=App.openDocument(str(CASE_FILE))
    doc=App.newDocument('Kb1AAATentingBars');doc.Label='kb-1 AAA magnetic tenting bars — rear battery access Rev E'
    results={}
    for side,name in [('Left','BottomShell'),('Right','R_BottomShell')]:
        shape=source.getObject(name).Shape.copy()
        centers=magnet_centers(shape)
        # Inner-edge pair. The reversed ordering on Right keeps a rigid,
        # right-handed transform and puts the outer desk edge at positive V.
        pair=sorted(centers,key=lambda xy:xy[0],reverse=side=='Left')[:2]
        pair=sorted(pair,key=lambda xy:xy[1],reverse=side=='Right')
        usb=source.getObject(('R_' if side=='Right' else '')+'USBC_Connector').Shape.copy()
        top_shape=source.getObject(('R_' if side=='Right' else '')+'TopShell').Shape.copy()
        results[side]=build_bar(doc,side,shape,*pair,usb,top_shape)
    coupon=Part.makeBox(32,28,3.0)
    top=V(16,14,3.0)
    coupon=coupon.cut(Part.makeCylinder(MAGNET_POCKET_DIAMETER/2,MAGNET_POCKET_DEPTH+.2,top-V(0,0,MAGNET_POCKET_DEPTH)))
    coupon=coupon.cut(Part.makeCone(MAGNET_POCKET_DIAMETER/2,FINGER_DIAMETER/2,FINGER_FUNNEL_DEPTH+.001,top-V(0,0,FINGER_FUNNEL_DEPTH)))
    cg=doc.addObject('App::DocumentObjectGroup','FitCoupon');cg.Label='Magnet fit coupon / optional small test print'
    co=add_feature(doc,cg,'MagnetFitCoupon','Ø12.25 pocket + Ø22 fingertip funnel',coupon,(.72,.82,.87),False)
    assert coupon.isValid() and len(coupon.Solids)==1
    export_part(co,'magnet-fit-coupon')
    coupon_cover=Part.makeBox(32,28,COVER_THICKNESS,V(0,0,3))
    coupon_cover=coupon_cover.cut(Part.makeCylinder(6.5,COVER_THICKNESS-COVER_MAGNET_SKIN,V(16,14,3)))
    cc=add_feature(doc,cg,'MagnetFitCover','Coupon cover / 0.5 mm closed magnet window',coupon_cover,(.44,.69,.79),False)
    cc.addProperty('App::PropertyAngle','TentingAngle');cc.TentingAngle=0
    assert coupon_cover.isValid() and len(coupon_cover.Solids)==1
    export_part(cc,'magnet-fit-cover')
    # Show only Right by default; the two bars occupy the same local frame.
    for obj in doc.Objects:
        if obj.Name.startswith('Left') and obj.ViewObject:obj.ViewObject.Visibility=False
    if App.GuiUp:
        for name in ['RightFixedUSBCPlug','RightFixedCable']:doc.getObject(name).ViewObject.Visibility=True
    model_file=OUTPUT/'kb1-aaa-tenting-bars.FCStd'
    doc.recompute();doc.saveAs(str(model_file))
    if not App.GuiUp:save_headless_view_state(doc,model_file)
    results['source']={'keyboard':str(CASE_FILE),'keyboard_sha256':hashlib.sha256(CASE_FILE.read_bytes()).hexdigest(),'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest() if '__file__' in globals() and Path(__file__).name=='generate-battery-tenting-bar.py' else None,'freecad':App.Version()[:3],'power_architecture':'purchased boost module, insulated wires, removable PLA tray; no custom power PCB'}
    (OUTPUT/'validation.json').write_text(json.dumps(results,indent=2)+'\n')
    App.closeDocument(source.Name)
    if App.GuiUp:
        import FreeCADGui as Gui
        Gui.activeDocument().activeView().viewAxonometric()
        Gui.activeDocument().activeView().fitAll()
        doc.save()
    print('Saved',OUTPUT/'kb1-aaa-tenting-bars.FCStd')
    print(json.dumps(results,indent=2))


if __name__=='__main__':main()
