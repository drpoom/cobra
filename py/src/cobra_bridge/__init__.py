"""
COBRA — COines BRidge Access for Python

Transport-agnostic Bosch AppBoard protocol library.
Supports USB-Serial (pyserial) and BLE (Bleak).

Quick start:
    from cobra_bridge.transport import SerialTransport
    from cobra_bridge.sync import CobraBridge

    transport = SerialTransport(port='/dev/ttyACM0')
    bridge = CobraBridge(transport=transport)
    bridge.connect()
"""

from cobra_bridge.constants import (
    HEADER, TYPE_GET, TYPE_SET, STATUS_OK,
    CMD_GET_BOARD_INFO, CMD_SET_VDD, CMD_SET_PIN, CMD_SET_VDDIO, CMD_INT_CONFIG,
    CMD_CONFIG_I2C_BUS, CMD_CONFIG_SPI_BUS,
    CMD_I2C_WRITE, CMD_I2C_READ,
    CMD_SPI_WRITE, CMD_SPI_READ,
    I2C_BUS_0, I2C_BUS_1, I2C_SPEED_400K, I2C_SPEED_1M, I2C_SPEED_STANDARD, I2C_SPEED_FAST,
    SPI_BUS_0, SPI_BUS_1, SPI_SPEED_1MHZ, SPI_SPEED_10MHZ, SPI_MODE_0, SPI_MODE_3,
    SHUTTLE_PIN_7, SHUTTLE_PIN_8, SHUTTLE_PIN_9, SHUTTLE_PIN_14, SHUTTLE_PIN_15,
    SHUTTLE_PIN_16, SHUTTLE_PIN_19, SHUTTLE_PIN_20, SHUTTLE_PIN_21, SHUTTLE_PIN_22,
    PIN_IN, PIN_OUT, PIN_LOW, PIN_HIGH,
)

# ── Driver framework ─────────────────────────────────────────────────────

from cobra_bridge.drivers.base import SensorDriver, SensorData
from cobra_bridge.drivers.bmm350 import BMM350Driver, BMM350Data
from cobra_bridge.drivers.bmm350_async import BMM350AsyncDriver

# ── Backward-compatible aliases ──────────────────────────────────────────

from cobra_bridge.drivers.bmm350 import BMM350
from cobra_bridge.drivers.bmm350_async import BMM350Async

# ── Per-sensor constants (import explicitly when needed) ─────────────────

# from cobra_bridge.drivers.bmm350_constants import BMM350_REG, BMM350_PMU, ...

__version__ = '0.2.0'