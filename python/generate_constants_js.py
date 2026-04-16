#!/usr/bin/env python3
"""
Generate cobra_constants.js from core/protocol_spec.json.

Usage:
    python generate_constants_js.py

This reads the single source of truth (protocol_spec.json) and writes
the JavaScript constants file so Python and JS stay in sync.
"""

import json
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SPEC_PATH = os.path.join(SCRIPT_DIR, '..', 'core', 'protocol_spec.json')
JS_OUT_PATH = os.path.join(SCRIPT_DIR, '..', 'javascript', 'cobra_constants.js')


def hex_val(n, prefix='0x'):
    return f"{prefix}{n:02X}"


def generate():
    with open(SPEC_PATH, 'r') as f:
        spec = json.load(f)

    lines = [
        '/**',
        ' * COBRA Protocol Constants — JavaScript (WebSerial)',
        ' *',
        ' * AUTO-GENERATED from core/protocol_spec.json.',
        ' * Do not edit manually — update protocol_spec.json and regenerate.',
        ' *',
        ' * To regenerate: python generate_constants_js.py',
        ' */',
        '',
    ]

    pkt = spec['packet']
    lines.append(f"export const HEADER = {hex_val(pkt['header'])};")
    lines.append('')

    # Packet Types
    lines.append('// Packet Types')
    for name, val in pkt['types'].items():
        lines.append(f"export const TYPE_{name} = {hex_val(val)};")
    lines.append('')

    # System Commands
    lines.append('// System Commands')
    for name, val in spec['commands']['system'].items():
        lines.append(f"export const CMD_{name} = {hex_val(val)};")
    lines.append('')

    # I2C Commands
    lines.append('// I2C Commands')
    for name, val in spec['commands']['i2c'].items():
        lines.append(f"export const CMD_I2C_{name} = {hex_val(val)};")
    lines.append('')

    # SPI Commands
    lines.append('// SPI Commands')
    for name, val in spec['commands']['spi'].items():
        lines.append(f"export const CMD_SPI_{name} = {hex_val(val)};")
    lines.append('')

    # Status
    lines.append('// Response Status')
    lines.append(f"export const STATUS_OK = {hex_val(pkt['status']['OK'])};")
    lines.append('')

    # I2C Speed
    lines.append('// I2C Speed')
    for name, val in spec['i2c']['speed'].items():
        lines.append(f"export const I2C_SPEED_{name} = {val};")
    lines.append('')

    # SPI Speed & Mode
    lines.append('// SPI Speed & Mode')
    for name, val in spec['spi']['speed'].items():
        lines.append(f"export const SPI_SPEED_{name} = {val};")
    for name, val in spec['spi']['mode'].items():
        lines.append(f"export const {name} = {val};")
    lines.append('')

    # BMM350
    bmm = spec['sensors']['bmm350']
    lines.append('// ── BMM350 (from sensors.bmm350) ──────────────────────────────────────────')
    lines.append('')
    lines.append(f"export const BMM350_I2C_ADDR  = {hex_val(bmm['i2c_addr'])};")
    lines.append(f"export const BMM350_CHIP_ID   = {hex_val(bmm['chip_id'])};")
    lines.append(f"export const BMM350_SENSITIVITY = {bmm['sensitivity_ut_per_lsb']};")
    lines.append('')

    # BMM350 Registers
    lines.append('export const BMM350_REG = {')
    reg_items = list(bmm['registers'].items())
    for i, (name, entry) in enumerate(reg_items):
        comma = ',' if i < len(reg_items) - 1 else ','
        lines.append(f"    {name}: {hex_val(entry['address'])}{comma}")
    lines.append('};')
    lines.append('')

    # BMM350 PMU
    lines.append('export const BMM350_PMU = {')
    pmu_items = list(bmm['pmu_commands'].items())
    for i, (name, val) in enumerate(pmu_items):
        comma = ',' if i < len(pmu_items) - 1 else ','
        lines.append(f"    {name}: {hex_val(val)}{comma}")
    lines.append('};')
    lines.append('')

    # BMM350 ODR
    lines.append('export const BMM350_ODR = {')
    odr_items = list(bmm['odr'].items())
    for i, (name, val) in enumerate(odr_items):
        comma = ',' if i < len(odr_items) - 1 else ','
        lines.append(f"    {name}: {hex_val(val)}{comma}")
    lines.append('};')

    output = '\n'.join(lines) + '\n'

    with open(JS_OUT_PATH, 'w') as f:
        f.write(output)

    print(f"✓ Generated {JS_OUT_PATH}")
    print(f"  {len(lines)} lines from {SPEC_PATH}")


if __name__ == '__main__':
    generate()