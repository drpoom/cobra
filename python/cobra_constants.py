"""
COBRA Protocol Constants — Loaded from core/protocol_spec.json

This module is the Python accessor for the single source of truth.
All constants are derived from core/protocol_spec.json so that
Python and JavaScript implementations stay in sync automatically.

Usage:
    from cobra_constants import HEADER, TYPE_GET, CMD_I2C_READ, ...
"""

import json
import os

# Resolve path to protocol_spec.json (core/ is sibling of python/)
_SPEC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'core', 'protocol_spec.json')

def _load_spec():
    with open(_SPEC_PATH, 'r') as f:
        return json.load(f)

_SPEC = _load_spec()

# ── Packet ──────────────────────────────────────────────────────────────────

HEADER = _SPEC['packet']['header']                    # 0xAA = 170

# Packet Types
TYPE_GET = _SPEC['packet']['types']['GET']             # 0x01
TYPE_SET = _SPEC['packet']['types']['SET']             # 0x02

# Response Status
STATUS_OK = _SPEC['packet']['status']['OK']            # 0x00

# ── System Commands ──────────────────────────────────────────────────────────

CMD_GET_BOARD_INFO = _SPEC['commands']['system']['GET_BOARD_INFO']
CMD_SET_VDD        = _SPEC['commands']['system']['SET_VDD']
CMD_SET_PIN        = _SPEC['commands']['system']['SET_PIN']
CMD_SET_VDDIO      = _SPEC['commands']['system']['SET_VDDIO']
CMD_INT_CONFIG     = _SPEC['commands']['system']['INT_CONFIG']

# ── I2C Commands ────────────────────────────────────────────────────────────

CMD_I2C_WRITE = _SPEC['commands']['i2c']['WRITE']     # 0x0D
CMD_I2C_READ  = _SPEC['commands']['i2c']['READ']       # 0x0E

# ── SPI Commands ────────────────────────────────────────────────────────────

CMD_SPI_WRITE = _SPEC['commands']['spi']['WRITE']      # 0x13
CMD_SPI_READ  = _SPEC['commands']['spi']['READ']       # 0x14

# ── I2C Speed ───────────────────────────────────────────────────────────────

I2C_SPEED_400K = _SPEC['i2c']['speed']['400K']
I2C_SPEED_1M   = _SPEC['i2c']['speed']['1M']

# ── SPI Speed & Mode ───────────────────────────────────────────────────────

SPI_SPEED_5MHZ  = _SPEC['spi']['speed']['5MHZ']
SPI_SPEED_10MHZ = _SPEC['spi']['speed']['10MHZ']
SPI_MODE_0 = _SPEC['spi']['mode']['MODE_0']
SPI_MODE_3 = _SPEC['spi']['mode']['MODE_3']

# ── BMM350 Constants ───────────────────────────────────────────────────────

_bmm350 = _SPEC['sensors']['bmm350']

BMM350_I2C_ADDR    = _bmm350['i2c_addr']              # 0x14 = 20
BMM350_CHIP_ID     = _bmm350['chip_id']               # 0x33 = 51
BMM350_SENSITIVITY = _bmm350['sensitivity_ut_per_lsb'] # 1/6

# BMM350 Register addresses
BMM350_REG = {name: entry['address'] for name, entry in _bmm350['registers'].items()}

# BMM350 PMU commands
BMM350_PMU = {name: val for name, val in _bmm350['pmu_commands'].items()}

# BMM350 PMU status values
BMM350_PMU_STATUS = {name: val for name, val in _bmm350['pmu_status'].items()}

# BMM350 ODR settings
BMM350_ODR = {name: val for name, val in _bmm350['odr'].items()}

# Convenience: flat ODR constants for Python (e.g. ODR_100HZ)
for _name, _val in _bmm350['odr'].items():
    globals()[f'ODR_{_name}'] = _val