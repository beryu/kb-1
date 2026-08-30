from collections import defaultdict
from pathlib import Path
import sys, uuid
import pcbnew

board_path, output_path, side = sys.argv[1:4]
board = pcbnew.LoadBoard(board_path)
project = 'torabo-tsuki-lp-S-ortho-mini'
root_uuid = 'd470e7a4-966e-4b7e-b716-aac18e0b3811'
sheet_uuid = {'left': '875ad885-ab17-45c9-9ede-ac02233b55af', 'right': '7368bfa4-9957-402b-978e-3e10016f763f'}[side]
file_uuid = {'left': '64385587-d20f-4df4-94df-9d21f80edea6', 'right': '857e2c2d-ce73-4fe8-8b2b-b51c822c851c'}[side]
sheet_path = f'/{root_uuid}/{sheet_uuid}'

def uid(kind, name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'torabo-tsuki:{side}:{kind}:{name}'))

def q(value):
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'

def effect(size=1.0, hide=False, justify=None):
    out = [f'\t\t\t(effects (font (size {size} {size}))']
    if justify:
        out.append(f'\t\t\t\t(justify {justify})')
    if hide:
        out.append('\t\t\t\t(hide yes)')
    out.append('\t\t\t)')
    return '\n'.join(out)

footprints = {}
for fp in board.GetFootprints():
    ref = fp.GetReference()
    if not ref or ref == 'REF**' or ref.startswith('#'):
        continue
    pads = {}
    for pad in fp.Pads():
        num = str(pad.GetNumber())
        if not num:
            continue
        pads[num] = pad.GetNetname() or ''
    if pads:
        footprints[ref] = (fp, pads)

max_pins = max(max(map(int, pads)) for _, pads in footprints.values())

def block_definition(n):
    top = (n - 1) * 1.27 + 1.27
    bottom = -top
    s = [f'\t\t(symbol "Torabo:Block{n}"', '\t\t\t(pin_names (offset 0.6))',
         '\t\t\t(exclude_from_sim no)', '\t\t\t(in_bom yes)', '\t\t\t(on_board yes)']
    for name, value, y, hidden in [
        ('Reference', 'REF', top + 2.54, False), ('Value', 'VALUE', top + 5.08, False),
        ('Footprint', '', 0, True), ('Datasheet', '', 0, True),
        ('Description', 'PCB-derived symbol', 0, True), ('LCSC', '', 0, True), ('MPN', '', 0, True)]:
        s += [f'\t\t\t(property {q(name)} {q(value)}', f'\t\t\t\t(at 10.16 {y:.3f} 0)',
              '\t\t\t\t(effects (font (size 1.0 1.0))' + (' (hide yes)' if hidden else '') + ')', '\t\t\t)']
    s += [f'\t\t\t(symbol "Block{n}_0_1"',
          f'\t\t\t\t(rectangle (start 0 {top:.3f}) (end 20.32 {bottom:.3f}) (stroke (width 0) (type default)) (fill (type background)))',
          '\t\t\t)']
    s.append(f'\t\t\t(symbol "Block{n}_1_1"')
    for i in range(1, n + 1):
        y = (n - 1) * 1.27 - (i - 1) * 2.54
        s += [f'\t\t\t\t(pin passive line (at -2.54 {y:.3f} 0) (length 2.54)',
              f'\t\t\t\t\t(name {q("P" + str(i))} (effects (font (size 0.8 0.8))))',
              f'\t\t\t\t\t(number {q(i)} (effects (font (size 0.8 0.8))))', '\t\t\t\t)']
    s += ['\t\t\t)', '\t\t\t(embedded_fonts no)', '\t\t)']
    return '\n'.join(s)

lines = ['(kicad_sch', '\t(version 20250114)', '\t(generator "eeschema")', '\t(generator_version "9.0")',
         f'\t(uuid {q(file_uuid)})', '\t(paper "A3")', '\t(lib_symbols']
for n in sorted({max(map(int, pads)) for _, pads in footprints.values()}):
    lines.append(block_definition(n))
lines.append('\t)')

def property_line(name, value, x, y, hide=False):
    return [f'\t\t(property {q(name)} {q(value)}', f'\t\t\t(at {x:.3f} {y:.3f} 0)',
            '\t\t\t(effects (font (size 1.0 1.0))' + (' (hide yes)' if hide else '') + ')', '\t\t)']

def net_label(net, x, y, key):
    if not net:
        return [f'\t(no_connect (at {x:.3f} {y:.3f}) (uuid {q(uid("nc", key))}))']
    local_prefix = f'/{side}/'
    if net.startswith(local_prefix):
        name = net[len(local_prefix):]
        return [f'\t(label {q(name)}', f'\t\t(at {x:.3f} {y:.3f} 0)',
                '\t\t(effects (font (size 0.8 0.8)) (justify left bottom))', f'\t\t(uuid {q(uid("label", key))})', '\t)']
    return [f'\t(global_label {q(net)}', '\t\t(shape passive)', f'\t\t(at {x:.3f} {y:.3f} 0)',
            '\t\t(fields_autoplaced yes)', '\t\t(effects (font (size 0.8 0.8)) (justify left bottom))',
            f'\t\t(uuid {q(uid("global", key))})', '\t)']

def add_symbol(ref, x, y):
    fp, pads = footprints[ref]
    n = max(map(int, pads))
    top = (n - 1) * 1.27 + 1.27
    sym_uuid = uid('symbol', ref)
    chunk = ['\t(symbol', f'\t\t(lib_id {q("Torabo:Block" + str(n))})', f'\t\t(at {x:.3f} {y:.3f} 0)',
             '\t\t(unit 1)', '\t\t(exclude_from_sim no)', '\t\t(in_bom yes)', '\t\t(on_board yes)',
             '\t\t(dnp no)', f'\t\t(uuid {q(sym_uuid)})']
    chunk += property_line('Reference', ref, x + 10.16, y + top + 2.54)
    chunk += property_line('Value', fp.GetValue(), x + 10.16, y + top + 5.08)
    fpid = fp.GetFPID()
    nickname, item_name = str(fpid.GetLibNickname()), str(fpid.GetLibItemName())
    if not nickname:
        if item_name.startswith('C_'):
            nickname = 'Capacitor_SMD'
        elif item_name.startswith('R_'):
            nickname = 'Resistor_SMD'
        elif item_name == 'SOT-23-5':
            nickname = 'Package_TO_SOT_SMD'
        elif item_name.startswith('TestPoint_'):
            nickname = 'TestPoint'
        else:
            nickname = 'Library'
    fp_name = nickname + ':' + item_name
    chunk += property_line('Footprint', fp_name, x + 10.16, y, True)
    chunk += property_line('Datasheet', '', x + 10.16, y, True)
    chunk += property_line('Description', 'Generated from PCB connectivity', x + 10.16, y, True)
    lcsc = fp.GetFieldText('LCSC') if fp.HasField('LCSC') else ''
    mpn = fp.GetFieldText('MPN') if fp.HasField('MPN') else ''
    chunk += property_line('LCSC', lcsc, x + 10.16, y, True)
    chunk += property_line('MPN', mpn, x + 10.16, y, True)
    for i in range(1, n + 1):
        chunk += [f'\t\t(pin {q(i)} (uuid {q(uid("pin", ref + ":" + str(i)))}) )']
    chunk += ['\t\t(instances', f'\t\t\t(project {q(project)}', f'\t\t\t\t(path {q(sheet_path)}',
              f'\t\t\t\t\t(reference {q(ref)})', '\t\t\t\t\t(unit 1)', '\t\t\t\t)', '\t\t\t)', '\t\t)', '\t)']
    lines.extend(chunk)
    for i in range(1, n + 1):
        # KiCad symbol-space Y is inverted when placed on the sheet.
        py = y - ((n - 1) * 1.27 - (i - 1) * 2.54)
        lines.extend(net_label(pads.get(str(i), ''), x - 2.54, py, ref + ':' + str(i)))

# Key matrix first, grouped by PCB row/column connectivity.
switches = sorted((r for r in footprints if r.startswith('SW') and r not in {'SW101', 'SW201'}), key=lambda r: int(r[2:]))
by_row = defaultdict(list)
for ref in switches:
    _, pads = footprints[ref]
    diode_ref = 'D' + ref[2:]
    row = footprints[diode_ref][1].get('2', 'ROW?').split('/')[-1]
    by_row[row].append((ref, diode_ref))

for row_index, row in enumerate(sorted(by_row)):
    for col_index, (sw, diode) in enumerate(sorted(by_row[row], key=lambda p: int(p[0][2:]))):
        x = 12.7 + col_index * 48.26
        y = 27.94 + row_index * 25.4
        add_symbol(sw, x, y)
        add_symbol(diode, x + 25.4, y)

lines += ['\t(text "Key matrix — every symbol and net is generated from the PCB"', '\t\t(at 12.7 11.43 0)',
          '\t\t(effects (font (size 2 2)) (justify left bottom))', f'\t\t(uuid {q(uid("text", "matrix"))})', '\t)']

# Non-matrix circuitry is packed below the matrix.
matrix_refs = set(switches) | {'D' + r[2:] for r in switches}
others = sorted((r for r in footprints if r not in matrix_refs), key=lambda r: (r[0], int(''.join(filter(str.isdigit, r)) or 0), r))
x, y, column_width = 12.7, 171.45, 48.26
for ref in others:
    n = max(map(int, footprints[ref][1]))
    height = max(15.24, (n + 4) * 2.54)
    if y + height > 284.48:
        x += column_width
        y = 171.45
    add_symbol(ref, x, y + (n - 1) * 1.27)
    y += height

lines += ['\t(text "Power, controller, reset, sensor connector and test points"', '\t\t(at 12.7 160.02 0)',
          '\t\t(effects (font (size 2 2)) (justify left bottom))', f'\t\t(uuid {q(uid("text", "other"))})', '\t)',
          '\t(text "Source of truth: PCB pad/net assignment"', '\t\t(at 299.72 284.48 0)',
          '\t\t(effects (font (size 1.27 1.27)) (justify left bottom))', f'\t\t(uuid {q(uid("text", "source"))})', '\t)', ')']

Path(output_path).write_text('\n'.join(lines) + '\n')
