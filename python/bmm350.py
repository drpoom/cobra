"""
COBRA: BMM350 Magnetometer Driver (Python)

Register-level driver for the Bosch BMM350 magnetometer.
All register addresses and constants come from core/protocol_spec.json
via cobra_constants — the single source of truth.

Usage:
    from cobra_core import CobraBridge
    from bmm350 import BMM350

    bridge = CobraBridge(port='/dev/ttyACM0')
    bridge.connect()

    sensor = BMM350(bridge)
    chip_id = sensor.get_chip_id()
    print(f"Chip ID: 0x{chip_id:02X}")  # Expected: 0x33

    sensor.set_power_mode('continuous')
    data = sensor.read_mag_data()
    print(f"X={data['x']:.2f} Y={data['y']:.2f} Z={data['z']:.2f} uT")

    bridge.disconnect()
"""

import struct
import time
from typing import Dict

from cobra_constants import BMM350_I2C_ADDR, BMM350_CHIP_ID, BMM350_SENSITIVITY
from cobra_constants import BMM350_REG, BMM350_PMU, BMM350_PMU_STATUS, BMM350_ODR


class BMM350:
    """BMM350 Magnetometer Driver over COBRA I2C bridge."""

    def __init__(self, bridge, dev_addr: int = BMM350_I2C_ADDR):
        self.bridge = bridge
        self.dev_addr = dev_addr

    def _read_reg(self, reg: int, length: int = 1) -> bytes:
        return self.bridge.i2c_read(self.dev_addr, reg, length)

    def _write_reg(self, reg: int, data: bytes) -> int:
        return self.bridge.i2c_write(self.dev_addr, reg, data)

    # ── Chip ID ───────────────────────────────────────────────────────────

    def get_chip_id(self) -> int:
        """Read Chip ID. Expected: 0x33."""
        return self._read_reg(BMM350_REG['CHIP_ID'], 1)[0]

    def verify_chip_id(self) -> bool:
        """Verify BMM350 is present. Returns True if chip ID = 0x33."""
        return self.get_chip_id() == BMM350_CHIP_ID

    # ── Power Mode ────────────────────────────────────────────────────────

    _PMU_NAMES = {v: k.lower() for k, v in BMM350_PMU.items() if k != 'SOFT_RESET'}

    def set_power_mode(self, mode: str = 'normal') -> int:
        """Set power mode: suspend, normal, forced, continuous."""
        mode_map = {k.lower(): v for k, v in BMM350_PMU.items() if k != 'SOFT_RESET'}
        cmd = mode_map.get(mode.lower())
        if cmd is None:
            raise ValueError(f"Invalid mode: {mode}. Valid: {list(mode_map.keys())}")
        return self._write_reg(BMM350_REG['PMU_CMD'], bytes([cmd]))

    def get_power_mode(self) -> str:
        """Read current power mode."""
        status = self._read_reg(BMM350_REG['PMU_STATUS'], 1)[0] & 0x0F
        return self._PMU_NAMES.get(status, f'unknown(0x{status:02X})')

    # ── ODR ───────────────────────────────────────────────────────────────

    def set_odr(self, odr_key: str = '100_HZ') -> int:
        """
        Set output data rate.

        Args:
            odr_key: Key from protocol_spec (e.g. '100_HZ', '400_HZ', '25_HZ')
        """
        odr_val = BMM350_ODR.get(odr_key)
        if odr_val is None:
            raise ValueError(f"Invalid ODR: {odr_key}. Valid: {list(BMM350_ODR.keys())}")
        cur = self._read_reg(BMM350_REG['ODR_AXIS'], 1)
        return self._write_reg(BMM350_REG['ODR_AXIS'], bytes([(cur[0] & 0x8F) | ((odr_val & 0x07) << 4)]))

    # ── Data Readout ──────────────────────────────────────────────────────

    def is_data_ready(self) -> bool:
        return (self._read_reg(BMM350_REG['STATUS'], 1)[0] & 0x01) != 0

    def read_mag_data(self) -> Dict[str, float]:
        """Read 3-axis magnetic field data in uT."""
        raw = self._read_reg(BMM350_REG['DATA_X_LSB'], 6)
        x, y, z = struct.unpack('<hhh', raw)
        return {'x': x * BMM350_SENSITIVITY, 'y': y * BMM350_SENSITIVITY,
                'z': z * BMM350_SENSITIVITY, 'x_raw': x, 'y_raw': y, 'z_raw': z}

    # ── Utility ───────────────────────────────────────────────────────────

    def soft_reset(self) -> int:
        return self._write_reg(BMM350_REG['PMU_CMD'], bytes([BMM350_PMU['SOFT_RESET']]))

    def read_error_status(self) -> int:
        return self._read_reg(BMM350_REG['ERR_STAT'], 1)[0]