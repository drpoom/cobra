"""
COBRA: BMM350 Magnetometer Driver (Python)

Register-level driver for the Bosch BMM350 magnetometer.
Register map defined in core/PROTOCOL.md §6.
Uses CobraBridge for I2C communication over COINES V3 protocol.

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

# ── BMM350 Register Map (core/PROTOCOL.md §6) ────────────────────────────

REG_CHIP_ID     = 0x00
REG_PMU_CMD     = 0x02
REG_PMU_STATUS  = 0x03
REG_ODR_AXIS    = 0x21
REG_DATA_X_LSB  = 0x30
REG_DATA_Z_MSB  = 0x35
REG_ERR_STAT    = 0x3E
REG_STATUS      = 0x3F

# ── Power Mode Commands (core/PROTOCOL.md §6) ────────────────────────────

PMU_SUSPEND    = 0x01
PMU_NORMAL     = 0x02
PMU_FORCED     = 0x03
PMU_CONTINUOUS = 0x04
PMU_SOFT_RESET = 0x80

# ── ODR Settings (core/PROTOCOL.md §6) ───────────────────────────────────

ODR_400HZ  = 0x00
ODR_200HZ  = 0x01
ODR_100HZ  = 0x02
ODR_50HZ   = 0x03
ODR_25HZ   = 0x04
ODR_12_5HZ = 0x05
ODR_6_25HZ = 0x06

# ── Constants ─────────────────────────────────────────────────────────────

BMM350_I2C_ADDR   = 0x14
BMM350_CHIP_ID    = 0x33
BMM350_SENSITIVITY = 1.0 / 6.0  # uT per LSB


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
        return self._read_reg(REG_CHIP_ID, 1)[0]

    def verify_chip_id(self) -> bool:
        """Verify BMM350 is present. Returns True if chip ID = 0x33."""
        return self.get_chip_id() == BMM350_CHIP_ID

    # ── Power Mode ────────────────────────────────────────────────────────

    def set_power_mode(self, mode: str = 'normal') -> int:
        """Set power mode: suspend, normal, forced, continuous."""
        modes = {'suspend': PMU_SUSPEND, 'normal': PMU_NORMAL,
                 'forced': PMU_FORCED, 'continuous': PMU_CONTINUOUS}
        cmd = modes.get(mode.lower())
        if cmd is None:
            raise ValueError(f"Invalid mode: {mode}")
        return self._write_reg(REG_PMU_CMD, bytes([cmd]))

    def get_power_mode(self) -> str:
        """Read current power mode."""
        status = self._read_reg(REG_PMU_STATUS, 1)[0] & 0x0F
        return {PMU_SUSPEND: 'suspend', PMU_NORMAL: 'normal',
                PMU_FORCED: 'forced', PMU_CONTINUOUS: 'continuous'}.get(status, f'unknown(0x{status:02X})')

    # ── ODR ───────────────────────────────────────────────────────────────

    def set_odr(self, odr: int = ODR_100HZ) -> int:
        """Set output data rate."""
        cur = self._read_reg(REG_ODR_AXIS, 1)
        return self._write_reg(REG_ODR_AXIS, bytes([(cur[0] & 0x8F) | ((odr & 0x07) << 4)]))

    # ── Data Readout ──────────────────────────────────────────────────────

    def is_data_ready(self) -> bool:
        return (self._read_reg(REG_STATUS, 1)[0] & 0x01) != 0

    def read_mag_data(self) -> Dict[str, float]:
        """Read 3-axis magnetic field data in uT."""
        raw = self._read_reg(REG_DATA_X_LSB, 6)
        x, y, z = struct.unpack('<hhh', raw)
        return {'x': x * BMM350_SENSITIVITY, 'y': y * BMM350_SENSITIVITY,
                'z': z * BMM350_SENSITIVITY, 'x_raw': x, 'y_raw': y, 'z_raw': z}

    # ── Utility ───────────────────────────────────────────────────────────

    def soft_reset(self) -> int:
        return self._write_reg(REG_PMU_CMD, bytes([PMU_SOFT_RESET]))

    def read_error_status(self) -> int:
        return self._read_reg(REG_ERR_STAT, 1)[0]