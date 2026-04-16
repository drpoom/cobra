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
        lines.append(f"export const SPI_{name} = {val};")
    lines.append('')

    # BMM350
    bmm = spec['sensors']['bmm350']
    lines.append('// ── BMM350 (from sensors.bmm350) ──────────────────────────────────────────')
    lines.append('')
    lines.append(f"export const BMM350_I2C_ADDR = {hex_val(bmm['i2c_addr'])};")
    lines.append(f"export const BMM350_CHIP_ID = {hex_val(bmm['chip_id'])};")
    lines.append(f"export const BMM350_DATA_LEN = {bmm['data_length_bytes']}; // bytes per sample (24-bit × 4 channels)")
    lines.append('')

    # BMM350 Registers
    lines.append('export const BMM350_REG = {')
    reg_items = list(bmm['registers'].items())
    for i, (name, entry) in enumerate(reg_items):
        comma = ',' if i < len(reg_items) - 1 else ','
        lines.append(f"    {name}: {hex_val(entry['address'])}{comma}  // {entry['description']}")
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
    lines.append('// ODR map: human Hz → register value')
    lines.append('export const BMM350_ODR = {')
    odr_display = {}
    for name, val in bmm['odr'].items():
        hz = name.replace('_HZ', '').replace('_', '.')
        try:
            hz = int(hz)
        except ValueError:
            hz = f"'{hz}'"
        odr_display[hz] = val
    odr_items = list(odr_display.items())
    for i, (hz, val) in enumerate(odr_items):
        comma = ',' if i < len(odr_items) - 1 else ','
        lines.append(f"    {hz}: {hex_val(val)}{comma}")
    lines.append('};')
    lines.append('')

    # BMM350 Averaging
    lines.append('export const BMM350_AVG = {')
    avg_items = list(bmm['averaging'].items())
    for i, (name, val) in enumerate(avg_items):
        comma = ',' if i < len(avg_items) - 1 else ','
        lines.append(f"    {name}: {val}{comma}")
    lines.append('};')
    lines.append('')

    # BMM350 OTP Addresses
    lines.append('export const BMM350_OTP_ADDR = {')
    otp_items = list(bmm['otp_addresses'].items())
    for i, (name, val) in enumerate(otp_items):
        comma = ',' if i < len(otp_items) - 1 else ','
        lines.append(f"    {name}: {val}{comma}")
    lines.append('};')
    lines.append('')

    # BMM350 Conversion Coefficients
    conv = bmm['conversion']
    lines.append('// ── BMM350 Conversion Coefficients (Bosch BMM350_SensorAPI v1.10.0) ────')
    lines.append('')
    lines.append(f"export const BMM350_LSB_TO_UT_XY = {conv['lsb_to_ut_xy']};  // μT/LSB for X,Y axes")
    lines.append(f"export const BMM350_LSB_TO_UT_Z = {conv['lsb_to_ut_z']};   // μT/LSB for Z axis")
    lines.append(f"export const BMM350_LSB_TO_DEGC = {conv['lsb_to_degc']};  // °C/LSB for temperature")
    lines.append(f"export const BMM350_TEMP_OFFSET = {conv['temp_offset_degc']};  // °C offset")

    output = '\n'.join(lines) + '\n'

    with open(JS_OUT_PATH, 'w') as f:
        f.write(output)

    print(f"✓ Generated {JS_OUT_PATH}")
    print(f"  {len(lines)} lines from {SPEC_PATH}")


if __name__ == '__main__':
    generate()