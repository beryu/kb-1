#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
pcb_dir="$(cd "$script_dir/.." && pwd)"
output_dir="$script_dir/output"
kicad_cli="${KICAD_CLI:-/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli}"
kicad_python="${KICAD_PYTHON:-/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3}"

mkdir -p "$output_dir"

for side in left right; do
    board="$pcb_dir/torabo-tsuki-lp-S-ortho-mini-$side.kicad_pcb"
    work_dir="$(mktemp -d "/tmp/torabo-jlc-$side.XXXXXX")"
    gerber_dir="$work_dir/gerbers"
    mkdir -p "$gerber_dir"

    "$kicad_cli" pcb drc --severity-all \
        -o "$output_dir/$side-drc.txt" "$board"
    "$kicad_cli" pcb export gerbers \
        --layers F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts \
        --subtract-soldermask --check-zones \
        -o "$gerber_dir" "$board"
    "$kicad_cli" pcb export drill \
        --format excellon --drill-origin absolute \
        --excellon-units mm --excellon-zeros-format decimal \
        --excellon-oval-format alternate --excellon-separate-th \
        -o "$gerber_dir" "$board"

    (
        cd "$gerber_dir"
        zip -q -r "$output_dir/$side-gerbers.zip" .
    )

    "$kicad_python" "$script_dir/make_bom_cpl.py" "$board" \
        "$output_dir/$side-bom.csv" "$output_dir/$side-cpl.csv"
done

echo "JLCPCB files written to $output_dir"
