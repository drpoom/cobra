"""
COBRA: BMM350 Magnetometer Driver

Register-level driver for the Bosch BMM350 magnetometer.
Uses CobraBridge for I2C communication over COINES V3 protocol.

BMM350 Datasheet Summary:
    - I2C Address: 0x14 (7-bit)
    - Chip ID:     0x33 at register 0x00
    - 3-axis magnetic field measurement
    - Power modes: suspend, normal, forced, continuous

Usage:
    from cobra_core import CobraBridge
    from bmm350 import BMM350

    bridge = CobraBridge(port='/dev/ttyUSB0')
    bridge.connect()

    sensor = BMM350(bridge)
    chip_id = sensor.get_chip_id()
    print(f"Chip ID: 0x{chip_id:02X}")  # Expected: 0x33

    sensor.set_power_mode('normal')
    data = sensor.read_mag_data()
    print(f"Magnetic field: X={data['x']:.2f} Y={data['y']:.2f} Z={data['z']:.2f} uT")

    bridge.disconnect()
"""

import struct
import time
from typing import Optional, Dict


# ── BMM350 Register Map ───────────────────────────────────────────────────────

REG_CHIP_ID      = 0x00   # Chip ID register (R): expected 0x33

REG_PMU_CMD      = 0x02   # PMU command register (W)
REG_PMU_STATUS   = 0x03   # PMU status register (R)

REG_CMD_CONFIG   = 0x20   # Command configuration
REG_ODR_AXIS     = 0x21   # Output data rate and axis enable
REG_AVERAGE      = 0x22   # Averaging configuration
REG_REP_XY       = 0x23   # Repetition count for X/Y
REG_REP_Z        = 0x24   # Repetition count for Z
REG_OFC_CTRL     = 0x25   # Offset correction control
REG_OFC_X        = 0x26   # Offset correction X
REG_OFC_Y        = 0x28   # Offset correction Y
REG_OFC_Z        = 0x2A   # Offset correction Z
REG_INT_CTRL     = 0x2D   # Interrupt control
REG_INT_STATUS   = 0x2E   # Interrupt status

REG_DATA_X_LSB   = 0x30   # X-axis data LSB
REG_DATA_X_MSB   = 0x31   # X-axis data MSB
REG_DATA_Y_LSB   = 0x32   # Y-axis data LSB
REG_DATA_Y_MSB   = 0x33   # Y-axis data MSB
REG_DATA_Z_LSB   = 0x34   # Z-axis data LSB
REG_DATA_Z_MSB   = 0x35   # Z-axis data MSB

REG_SELF_TEST    = 0x36   # Self-test configuration
REG_SELF_TEST_STATUS = 0x37  # Self-test status

REG_ERR_STAT     = 0x3E   # Error status
REG_STATUS       = 0x3F   # Status register (data ready)

# ── PMU Commands ──────────────────────────────────────────────────────────────

PMU_CMD_SUSPEND   = 0x01
PMU_CMD_NORMAL     = 0x02
PMU_CMD_FORCED     = 0x03
PMU_CMD_CONTINUOUS = 0x04

# ── PMU Status ────────────────────────────────────────────────────────────────

PMU_STATUS_SUSPEND   = 0x01
PMU_STATUS_NORMAL    = 0x02
PMU_STATUS_FORCED    = 0x03
PMU_STATUS_CONTINUOUS = 0x04

# ── ODR Settings ──────────────────────────────────────────────────────────────

ODR_400HZ = 0x00
ODR_200HZ = 0x01
ODR_100HZ = 0x02
ODR_50HZ  = 0x03
ODR_25HZ  = 0x04
ODR_12_5HZ = 0x05
ODR_6_25HZ = 0x06

# ── Sensitivity ───────────────────────────────────────────────────────────────
# BMM350 raw data is in LSB, sensitivity = 1/6 uT/LSB (from datasheet)
BMM350_SENSITIVITY = 1.0 / 6.0  # uT per LSB


class BMM350:
    """
    BMM350 Magnetometer Driver over COBRA I2C bridge.

    Provides register-level access to the BMM350 sensor including
    chip identification, power mode control, and data readout.
    """

    I2C_ADDR = 0x14

    def __init__(self, bridge, dev_addr: int = None):
        """
        Initialize BMM350 driver.

        Args:
            bridge:   CobraBridge instance (must be connected)
            dev_addr: I2C address override (default: 0x14)
        """
        self.bridge = bridge
        self.dev_addr = dev_addr or self.I2C_ADDR

    # ── Register Access ───────────────────────────────────────────────────────

    def _read_reg(self, reg_addr: int, length: int = 1) -> bytes:
        """Read bytes from a register."""
        return self.bridge.i2c_read(self.dev_addr, reg_addr, length)

    def _write_reg(self, reg_addr: int, data: bytes) -> int:
        """Write bytes to a register."""
        return self.bridge.i2c_write(self.dev_addr, reg_addr, data)

    # ── Chip Identification ───────────────────────────────────────────────────

    def get_chip_id(self) -> int:
        """
        Read the BMM350 Chip ID.

        Returns:
            Chip ID byte (expected: 0x33)
        """
        data = self._read_reg(REG_CHIP_ID, 1)
        return data[0]

    def verify_chip_id(self) -> bool:
        """
        Verify the BMM350 is present and responsive.

        Returns:
            True if chip ID matches 0x33, False otherwise
        """
        chip_id = self.get_chip_id()
        return chip_id == 0x33

    # ── Power Mode ────────────────────────────────────────────────────────────

    def set_power_mode(self, mode: str = 'normal') -> int:
        """
        Set the BMM350 power mode.

        Args:
            mode: One of 'suspend', 'normal', 'forced', 'continuous'

        Returns:
            Status byte (0x00 = success)
        """
        mode_map = {
            'suspend':    PMU_CMD_SUSPEND,
            'normal':    PMU_CMD_NORMAL,
            'forced':    PMU_CMD_FORCED,
            'continuous': PMU_CMD_CONTINUOUS,
        }
        cmd = mode_map.get(mode.lower())
        if cmd is None:
            raise ValueError(f"Invalid power mode: {mode}. Use: suspend, normal, forced, continuous")
        return self._write_reg(REG_PMU_CMD, bytes([cmd]))

    def get_power_mode(self) -> str:
        """
        Read the current BMM350 power mode.

        Returns:
            Power mode string: 'suspend', 'normal', 'forced', or 'continuous'
        """
        data = self._read_reg(REG_PMU_STATUS, 1)
        status = data[0] & 0x0F  # Lower nibble is PMU state
        status_map = {
            PMU_STATUS_SUSPEND:    'suspend',
            PMU_STATUS_NORMAL:    'normal',
            PMU_STATUS_FORCED:    'forced',
            PMU_STATUS_CONTINUOUS: 'continuous',
        }
        return status_map.get(status, f'unknown (0x{status:02X})')

    # ── ODR Configuration ─────────────────────────────────────────────────────

    def set_odr(self, odr: int = ODR_100HZ) -> int:
        """
        Set the output data rate.

        Args:
            odr: ODR constant (ODR_400HZ, ODR_200HZ, ODR_100HZ, etc.)

        Returns:
            Status byte (0x00 = success)
        """
        # Read current ODR/AXIS register, set ODR bits [6:4], keep axis enabled
        current = self._read_reg(REG_ODR_AXIS, 1)
        new_val = (current[0] & 0x8F) | ((odr & 0x07) << 4)
        return self._write_reg(REG_ODR_AXIS, bytes([new_val]))

    # ── Data Readout ──────────────────────────────────────────────────────────

    def read_status(self) -> int:
        """
        Read the status register.

        Returns:
            Status byte (bit 0 = data ready)
        """
        data = self._read_reg(REG_STATUS, 1)
        return data[0]

    def is_data_ready(self) -> bool:
        """
        Check if new magnetic field data is available.

        Returns:
            True if data ready bit is set
        """
        return (self.read_status() & 0x01) != 0

    def read_mag_data(self) -> Dict[str, float]:
        """
        Read 3-axis magnetic field data.

        Returns:
            Dict with keys 'x', 'y', 'z' in micro-Tesla (uT)

        Note:
            BMM350 returns 16-bit signed values for each axis.
            Sensitivity: 1/6 uT per LSB.
        """
        # Read all 6 data bytes in one burst (X_LSB through Z_MSB)
        data = self._read_reg(REG_DATA_X_LSB, 6)

        # Unpack three signed 16-bit little-endian values
        x_raw, y_raw, z_raw = struct.unpack('<hhh', data)

        return {
            'x': x_raw * BMM350_SENSITIVITY,
            'y': y_raw * BMM350_SENSITIVITY,
            'z': z_raw * BMM350_SENSITIVITY,
            'x_raw': x_raw,
            'y_raw': y_raw,
            'z_raw': z_raw,
        }

    def read_raw_data(self) -> tuple:
        """
        Read raw 16-bit magnetic field data.

        Returns:
            (x_raw, y_raw, z_raw) as signed 16-bit integers
        """
        data = self._read_reg(REG_DATA_X_LSB, 6)
        return struct.unpack('<hhh', data)

    # ── Error Status ──────────────────────────────────────────────────────────

    def read_error_status(self) -> int:
        """
        Read the error status register.

        Returns:
            Error status byte
        """
        data = self._read_reg(REG_ERR_STAT, 1)
        return data[0]

    # ── Self Test ─────────────────────────────────────────────────────────────

    def run_self_test(self) -> bool:
        """
        Trigger and verify BMM350 self-test.

        Returns:
            True if self-test passed
        """
        # Enable self-test
        self._write_reg(REG_SELF_TEST, bytes([0x01]))
        # Wait for completion
        time.sleep(0.1)
        # Read result
        status = self._read_reg(REG_SELF_TEST_STATUS, 1)
        return (status[0] & 0x01) != 0

    # ── Soft Reset ────────────────────────────────────────────────────────────

    def soft_reset(self) -> int:
        """
        Perform a soft reset of the BMM350.

        Returns:
            Status byte (0x00 = success)
        """
        # Write reset command to PMU_CMD
        return self._write_reg(REG_PMU_CMD, bytes([0x80]))