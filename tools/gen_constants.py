#!/usr/bin/env python3
"""
Generate cobra_bridge/constants.py and cobra-js/src/constants.js
from core/protocol_spec.json (board-level only).

Also generate per-sensor constants from core/sensors/*.json:
  - py/src/cobra_bridge/drivers/{sensor}_constants.py
  - js/src/drivers/{sensor}_constants.js

This is the ONLY tool that updates constants for both languages.
Edit protocol_spec.json or sensor JSON, then run:

    python tools/gen_constants.py

Single source of truth → both packages stay in sync.
"""

import json
import glob
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC_PATH = os.path.join(REPO_ROOT, 'core', 'protocol_spec.json')
SENSORS_DIR = os.path.join(REPO_ROOT, 'core', 'sensors')
PY_CONSTANTS_OUT = os.path.join(REPO_ROOT, 'py', 'src', 'cobra_bridge', 'constants.py')
JS_CONSTANTS_OUT = os.path.join(REPO_ROOT, 'js', 'src', 'constants.js')
PY_DRIVERS_DIR = os.path.join(REPO_ROOT, 'py', 'src', 'cobra_bridge', 'drivers')
JS_DRIVERS_DIR = os.path.join(REPO_ROOT, 'js', 'src', 'drivers')


def hex_val(n, prefix='0x'):
    return f"{prefix}{n:02X}"


def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)


# ── Board-level Python constants ───────────────────────────────────────────

def generate_board_py(spec):
    lines = [
        '"""',
        'COBRA Protocol Constants — Python',
        '',
        'AUTO-GENERATED from core/protocol_spec.json.',
        'Do not edit manually — update protocol_spec.json and run:',
        '    python tools/gen_constants.py',
        '"""',
        '',
    ]

    pkt = spec['packet']

    lines.append(f"HEADER = {hex_val(pkt['header'])}")
    lines.append('')

    lines.append('# Packet Types')
    for name, val in pkt['types'].items():
        lines.append(f"TYPE_{name} = {hex_val(val)}")
    lines.append('')

    lines.append('# Response Status')
    lines.append(f"STATUS_OK = {hex_val(pkt['status']['OK'])}")
    lines.append('')

    lines.append('# System Commands')
    for name, val in spec['commands']['system'].items():
        lines.append(f"CMD_{name} = {hex_val(val)}")
    lines.append('')

    lines.append('# I2C Commands')
    for name, val in spec['commands']['i2c'].items():
        lines.append(f"CMD_I2C_{name} = {hex_val(val)}")
    lines.append('')

    lines.append('# SPI Commands')
    for name, val in spec['commands']['spi'].items():
        lines.append(f"CMD_SPI_{name} = {hex_val(val)}")
    lines.append('')

    lines.append('# I2C Bus')
    for name, val in spec['i2c']['bus'].items():
        lines.append(f"I2C_{name} = {val}")
    lines.append('')

    lines.append('# I2C Speed')
    for name, val in spec['i2c']['speed'].items():
        lines.append(f"I2C_SPEED_{name} = {val}")
    lines.append('')

    lines.append('# SPI Bus')
    for name, val in spec['spi']['bus'].items():
        lines.append(f"SPI_{name} = {val}")
    lines.append('')

    lines.append('# SPI Speed & Mode')
    for name, val in spec['spi']['speed'].items():
        lines.append(f"SPI_SPEED_{name} = {val}")
    for name, val in spec['spi']['mode'].items():
        lines.append(f"SPI_{name} = {val}")
    lines.append('')

    # Shuttle Board Pins — fix double-prefix bug
    lines.append('# Shuttle Board Pins')
    for name, val in spec['shuttle_board']['pins'].items():
        if name.startswith('SHUTTLE_PIN_'):
            lines.append(f"{name} = {val}")
        else:
            lines.append(f"SHUTTLE_PIN_{name} = {val}")
    lines.append('')

    lines.append('# Pin Direction & Value')
    for name, val in spec['shuttle_board']['pin_direction'].items():
        lines.append(f"PIN_{name} = {val}")
    for name, val in spec['shuttle_board']['pin_value'].items():
        lines.append(f"PIN_{name} = {val}")
    lines.append('')

    return '\n'.join(lines) + '\n'


# ── Board-level JavaScript constants ────────────────────────────────────────

def generate_board_js(spec):
    lines = [
        '/**',
        ' * COBRA Protocol Constants — JavaScript',
        ' *',
        ' * AUTO-GENERATED from core/protocol_spec.json.',
        ' * Do not edit manually — update protocol_spec.json and run:',
        ' *     python tools/gen_constants.py',
        ' */',
        '',
    ]

    pkt = spec['packet']

    lines.append(f"export const HEADER = {hex_val(pkt['header'])};")
    lines.append('')

    lines.append('// Packet Types')
    for name, val in pkt['types'].items():
        lines.append(f"export const TYPE_{name} = {hex_val(val)};")
    lines.append('')

    lines.append('// System Commands')
    for name, val in spec['commands']['system'].items():
        lines.append(f"export const CMD_{name} = {hex_val(val)};")
    lines.append('')

    lines.append('// I2C Commands')
    for name, val in spec['commands']['i2c'].items():
        lines.append(f"export const CMD_I2C_{name} = {hex_val(val)};")
    lines.append('')

    lines.append('// SPI Commands')
    for name, val in spec['commands']['spi'].items():
        lines.append(f"export const CMD_SPI_{name} = {hex_val(val)};")
    lines.append('')

    lines.append('// Response Status')
    lines.append(f"export const STATUS_OK = {hex_val(pkt['status']['OK'])};")
    lines.append('')

    lines.append('// I2C Bus')
    for name, val in spec['i2c']['bus'].items():
        lines.append(f"export const I2C_{name} = {val};")
    lines.append('')

    lines.append('// I2C Speed')
    for name, val in spec['i2c']['speed'].items():
        lines.append(f"export const I2C_SPEED_{name} = {val};")
    lines.append('')

    lines.append('// SPI Bus')
    for name, val in spec['spi']['bus'].items():
        lines.append(f"export const SPI_{name} = {val};")
    lines.append('')

    lines.append('// SPI Speed & Mode')
    for name, val in spec['spi']['speed'].items():
        lines.append(f"export const SPI_SPEED_{name} = {val};")
    for name, val in spec['spi']['mode'].items():
        lines.append(f"export const SPI_{name} = {val};")
    lines.append('')

    # Shuttle Board Pins — fix double-prefix bug
    lines.append('// Shuttle Board Pins')
    for name, val in spec['shuttle_board']['pins'].items():
        if name.startswith('SHUTTLE_PIN_'):
            const_name = name
        else:
            const_name = f"SHUTTLE_PIN_{name}"
        lines.append(f"export const {const_name} = {val};")
    lines.append('')

    lines.append('// Pin Direction & Value')
    for name, val in spec['shuttle_board']['pin_direction'].items():
        lines.append(f"export const PIN_{name} = {val};")
    for name, val in spec['shuttle_board']['pin_value'].items():
        lines.append(f"export const PIN_{name} = {val};")
    lines.append('')

    return '\n'.join(lines) + '\n'


# ── Per-Sensor Python constants ─────────────────────────────────────────────

def generate_sensor_py(sensor_name, sensor_spec):
    meta = sensor_spec.get('_meta', {})
    display_name = meta.get('name', sensor_name.upper())
    api_ver = meta.get('api_version', '')

    lines = [
        '"""',
        f'COBRA {display_name} Sensor Constants — Python',
        '',
        f'AUTO-GENERATED from core/sensors/{sensor_name}.json.',
        'Do not edit manually — update the sensor JSON and run:',
        '    python tools/gen_constants.py',
        '"""',
        '',
    ]

    prefix = sensor_name.upper()

    lines.append(f"# ── {display_name} ─{'─' * max(0, 60 - len(display_name))}")
    lines.append('')
    lines.append(f"{prefix}_I2C_ADDR = {hex_val(sensor_spec['i2c_addr'])}")
    lines.append(f"{prefix}_CHIP_ID = {hex_val(sensor_spec['chip_id'])}")
    lines.append(f"{prefix}_DATA_LEN = {sensor_spec['data_length_bytes']}  # bytes per sample")
    if 'spi_read_cmd' in sensor_spec:
        lines.append(f"{prefix}_SPI_READ_CMD = {hex_val(sensor_spec['spi_read_cmd'])}")
    if 'spi_write_cmd' in sensor_spec:
        lines.append(f"{prefix}_SPI_WRITE_CMD = {hex_val(sensor_spec['spi_write_cmd'])}")
    lines.append('')

    # Registers
    lines.append(f'{prefix}_REG = {{')
    reg_items = list(sensor_spec['registers'].items())
    for i, (name, entry) in enumerate(reg_items):
        comma = ',' if i < len(reg_items) - 1 else ','
        lines.append(f"    '{name}': {hex_val(entry['address'])}{comma}  # {entry['description']}")
    lines.append('}')
    lines.append('')

    # PMU Commands
    if 'pmu_commands' in sensor_spec:
        lines.append(f'{prefix}_PMU = {{')
        pmu_items = list(sensor_spec['pmu_commands'].items())
        for i, (name, val) in enumerate(pmu_items):
            comma = ',' if i < len(pmu_items) - 1 else ','
            lines.append(f"    '{name}': {hex_val(val)}{comma}")
        lines.append('}')
        lines.append('')

    # PMU Status
    if 'pmu_status' in sensor_spec:
        lines.append(f'{prefix}_PMU_STATUS = {{')
        pmu_status_items = list(sensor_spec['pmu_status'].items())
        for i, (name, val) in enumerate(pmu_status_items):
            comma = ',' if i < len(pmu_status_items) - 1 else ','
            lines.append(f"    '{name}': {hex_val(val)}{comma}")
        lines.append('}')
        lines.append('')

    # ODR
    if 'odr' in sensor_spec:
        lines.append(f'# ODR map: human Hz key → register value')
        lines.append(f'{prefix}_ODR = {{')
        odr_items = list(sensor_spec['odr'].items())
        for i, (name, val) in enumerate(odr_items):
            comma = ',' if i < len(odr_items) - 1 else ','
            lines.append(f"    '{name}': {hex_val(val)}{comma}")
        lines.append('}')
        lines.append('')

    # Averaging
    if 'averaging' in sensor_spec:
        lines.append(f'{prefix}_AVG = {{')
        avg_items = list(sensor_spec['averaging'].items())
        for i, (name, val) in enumerate(avg_items):
            comma = ',' if i < len(avg_items) - 1 else ','
            lines.append(f"    '{name}': {val}{comma}")
        lines.append('}')
        lines.append('')

    # OTP Addresses
    if 'otp_addresses' in sensor_spec:
        lines.append(f'{prefix}_OTP_ADDR = {{')
        otp_items = list(sensor_spec['otp_addresses'].items())
        for i, (name, val) in enumerate(otp_items):
            comma = ',' if i < len(otp_items) - 1 else ','
            lines.append(f"    '{name}': {val}{comma}")
        lines.append('}')
        lines.append('')

    # Conversion Coefficients
    if 'conversion' in sensor_spec:
        conv = sensor_spec['conversion']
        lines.append(f'# {display_name} Conversion Coefficients (Bosch {display_name}_SensorAPI v{api_ver})')
        if 'lsb_to_ut_xy' in conv:
            lines.append(f"{prefix}_LSB_TO_UT_XY = {conv['lsb_to_ut_xy']}  # uT/LSB for X,Y axes")
        if 'lsb_to_ut_z' in conv:
            lines.append(f"{prefix}_LSB_TO_UT_Z = {conv['lsb_to_ut_z']}   # uT/LSB for Z axis")
        if 'lsb_to_degc' in conv:
            lines.append(f"{prefix}_LSB_TO_DEGC = {conv['lsb_to_degc']}  # degC/LSB for temperature")
        if 'temp_offset_degc' in conv:
            lines.append(f"{prefix}_TEMP_OFFSET = {conv['temp_offset_degc']}   # degC offset")

    return '\n'.join(lines) + '\n'


# ── Per-Sensor JavaScript constants ─────────────────────────────────────────

def generate_sensor_js(sensor_name, sensor_spec):
    meta = sensor_spec.get('_meta', {})
    display_name = meta.get('name', sensor_name.upper())
    api_ver = meta.get('api_version', '')

    lines = [
        '/**',
        f' * COBRA {display_name} Sensor Constants — JavaScript',
        ' *',
        f' * AUTO-GENERATED from core/sensors/{sensor_name}.json.',
        ' * Do not edit manually — update the sensor JSON and run:',
        ' *     python tools/gen_constants.py',
        ' */',
        '',
    ]

    prefix = sensor_name.upper()

    lines.append(f"// ── {display_name} ─{'─' * max(0, 60 - len(display_name))}")
    lines.append('')
    lines.append(f"export const {prefix}_I2C_ADDR = {hex_val(sensor_spec['i2c_addr'])};")
    lines.append(f"export const {prefix}_CHIP_ID = {hex_val(sensor_spec['chip_id'])};")
    lines.append(f"export const {prefix}_DATA_LEN = {sensor_spec['data_length_bytes']}; // bytes per sample")
    if 'spi_read_cmd' in sensor_spec:
        lines.append(f"export const {prefix}_SPI_READ_CMD = {hex_val(sensor_spec['spi_read_cmd'])};")
    if 'spi_write_cmd' in sensor_spec:
        lines.append(f"export const {prefix}_SPI_WRITE_CMD = {hex_val(sensor_spec['spi_write_cmd'])};")
    lines.append('')

    # Registers
    lines.append(f'export const {prefix}_REG = {{')
    reg_items = list(sensor_spec['registers'].items())
    for i, (name, entry) in enumerate(reg_items):
        comma = ',' if i < len(reg_items) - 1 else ','
        lines.append(f"    {name}: {hex_val(entry['address'])}{comma}  // {entry['description']}")
    lines.append('};')
    lines.append('')

    # PMU Commands
    if 'pmu_commands' in sensor_spec:
        lines.append(f'export const {prefix}_PMU = {{')
        pmu_items = list(sensor_spec['pmu_commands'].items())
        for i, (name, val) in enumerate(pmu_items):
            comma = ',' if i < len(pmu_items) - 1 else ','
            lines.append(f"    {name}: {hex_val(val)}{comma}")
        lines.append('};')
        lines.append('')

    # PMU Status
    if 'pmu_status' in sensor_spec:
        lines.append(f'export const {prefix}_PMU_STATUS = {{')
        pmu_status_items = list(sensor_spec['pmu_status'].items())
        for i, (name, val) in enumerate(pmu_status_items):
            comma = ',' if i < len(pmu_status_items) - 1 else ','
            lines.append(f"    {name}: {hex_val(val)}{comma}")
        lines.append('};')
        lines.append('')

    # ODR
    if 'odr' in sensor_spec:
        lines.append(f'// ODR map: human Hz → register value')
        lines.append(f'export const {prefix}_ODR = {{')
        odr_display = {}
        for name, val in sensor_spec['odr'].items():
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

    # Averaging
    if 'averaging' in sensor_spec:
        lines.append(f'export const {prefix}_AVG = {{')
        avg_items = list(sensor_spec['averaging'].items())
        for i, (name, val) in enumerate(avg_items):
            comma = ',' if i < len(avg_items) - 1 else ','
            lines.append(f"    {name}: {val}{comma}")
        lines.append('};')
        lines.append('')

    # OTP Addresses
    if 'otp_addresses' in sensor_spec:
        lines.append(f'export const {prefix}_OTP_ADDR = {{')
        otp_items = list(sensor_spec['otp_addresses'].items())
        for i, (name, val) in enumerate(otp_items):
            comma = ',' if i < len(otp_items) - 1 else ','
            lines.append(f"    {name}: {val}{comma}")
        lines.append('};')
        lines.append('')

    # Conversion Coefficients
    if 'conversion' in sensor_spec:
        conv = sensor_spec['conversion']
        lines.append(f'// ── {display_name} Conversion Coefficients (Bosch {display_name}_SensorAPI v{api_ver}) ────')
        lines.append('')
        if 'lsb_to_ut_xy' in conv:
            lines.append(f"export const {prefix}_LSB_TO_UT_XY = {conv['lsb_to_ut_xy']};  // uT/LSB for X,Y axes")
        if 'lsb_to_ut_z' in conv:
            lines.append(f"export const {prefix}_LSB_TO_UT_Z = {conv['lsb_to_ut_z']};   // uT/LSB for Z axis")
        if 'lsb_to_degc' in conv:
            lines.append(f"export const {prefix}_LSB_TO_DEGC = {conv['lsb_to_degc']};  // degC/LSB for temperature")
        if 'temp_offset_degc' in conv:
            lines.append(f"export const {prefix}_TEMP_OFFSET = {conv['temp_offset_degc']};  // degC offset")

    return '\n'.join(lines) + '\n'


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    spec = load_json(SPEC_PATH)

    # Generate board-level constants
    py_content = generate_board_py(spec)
    os.makedirs(os.path.dirname(PY_CONSTANTS_OUT), exist_ok=True)
    with open(PY_CONSTANTS_OUT, 'w') as f:
        f.write(py_content)
    print(f"✓ Generated {os.path.relpath(PY_CONSTANTS_OUT, REPO_ROOT)} ({len(py_content.splitlines())} lines)")

    js_content = generate_board_js(spec)
    os.makedirs(os.path.dirname(JS_CONSTANTS_OUT), exist_ok=True)
    with open(JS_CONSTANTS_OUT, 'w') as f:
        f.write(js_content)
    print(f"✓ Generated {os.path.relpath(JS_CONSTANTS_OUT, REPO_ROOT)} ({len(js_content.splitlines())} lines)")

    # Generate per-sensor constants
    sensor_files = sorted(glob.glob(os.path.join(SENSORS_DIR, '*.json')))
    if not sensor_files:
        print("\n  No sensor specs found in core/sensors/")
    else:
        print()
        for sensor_path in sensor_files:
            sensor_name = os.path.splitext(os.path.basename(sensor_path))[0]
            sensor_spec = load_json(sensor_path)

            # Python
            py_sensor_out = os.path.join(PY_DRIVERS_DIR, f'{sensor_name}_constants.py')
            py_sensor_content = generate_sensor_py(sensor_name, sensor_spec)
            os.makedirs(os.path.dirname(py_sensor_out), exist_ok=True)
            with open(py_sensor_out, 'w') as f:
                f.write(py_sensor_content)
            print(f"✓ Generated {os.path.relpath(py_sensor_out, REPO_ROOT)} ({len(py_sensor_content.splitlines())} lines)")

            # JavaScript
            js_sensor_out = os.path.join(JS_DRIVERS_DIR, f'{sensor_name}_constants.js')
            js_sensor_content = generate_sensor_js(sensor_name, sensor_spec)
            os.makedirs(os.path.dirname(js_sensor_out), exist_ok=True)
            with open(js_sensor_out, 'w') as f:
                f.write(js_sensor_content)
            print(f"✓ Generated {os.path.relpath(js_sensor_out, REPO_ROOT)} ({len(js_sensor_content.splitlines())} lines)")

    print(f"\n  Source: {os.path.relpath(SPEC_PATH, REPO_ROOT)}")
    print(f"  Sensors: {os.path.relpath(SENSORS_DIR, REPO_ROOT)}/")
    print(f"  → Python: {os.path.relpath(PY_CONSTANTS_OUT, REPO_ROOT)}")
    print(f"  → JavaScript: {os.path.relpath(JS_CONSTANTS_OUT, REPO_ROOT)}")


if __name__ == '__main__':
    main()