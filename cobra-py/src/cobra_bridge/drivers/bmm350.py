"""
COBRA Sync: BMM350 Magnetometer Driver (Python)

Register-level driver for the Bosch BMM350 magnetometer.
Based on official Bosch BMM350_SensorAPI v1.10.0 conversion formulas.
All register addresses and constants come from core/protocol_spec.json
via cobra_constants — the single source of truth.

Key changes from V1:
  - 24-bit data reads (12 bytes: 3 bytes/axis × 3 axes + 3 bytes temp)
  - Official Bosch conversion coefficients (not 1/6 simplification)
  - Temperature readout with proper °C conversion
  - OTP calibration support (offset, sensitivity, TCO, TCS, cross-axis)
  - set_odr(frequency_hz) with user-friendly Hz input

Usage:
    from cobra_bridge.sync import CobraBridge
    from cobra_bridge.drivers.bmm350 import BMM350

    transport = SerialTransport(port='/dev/ttyACM0')
    bridge = CobraBridge(transport=transport)
    bridge.connect()

    sensor = BMM350(bridge)
    sensor.init()  # Soft reset + OTP read + magnetic reset

    # Simple read (default coefficients)
    data = sensor.read_mag_data()
    print(f"X={data['x']:.2f} Y={data['y']:.2f} Z={data['z']:.2f} uT")
    print(f"T={data['temperature']:.2f} °C")

    # With OTP compensation
    sensor.read_otp()  # Must call after init
    data = sensor.read_mag_data(compensated=True)

    # Set ODR
    sensor.set_odr(100)       # 100 Hz
    sensor.set_odr(400)       # 400 Hz

    bridge.disconnect()
"""

import struct
import time
from typing import Dict, Optional, Tuple

from cobra_bridge.constants import (
    BMM350_I2C_ADDR, BMM350_CHIP_ID, BMM350_DATA_LEN,
    BMM350_REG, BMM350_PMU, BMM350_ODR, BMM350_AVG, BMM350_OTP_ADDR,
    BMM350_LSB_TO_UT_XY, BMM350_LSB_TO_UT_Z, BMM350_LSB_TO_DEGC, BMM350_TEMP_OFFSET,
)


# ── Sign Extension (mirrors Bosch fix_sign) ──────────────────────────────────

def fix_sign(value: int, bits: int) -> int:
    """
    Convert unsigned value to signed using two's complement.
    Mirrors Bosch BMM350_SensorAPI fix_sign() exactly.

    Args:
        value: Unsigned integer from register read
        bits: Bit width (8, 12, 16, 21, or 24)

    Returns:
        Signed integer

    Examples:
        fix_sign(0x800000, 24) → -8388608
        fix_sign(0x7FFFFF, 24) → 8388607
        fix_sign(0x800, 12) → -2048
        fix_sign(0xFF, 8) → -1
    """
    power = {8: 128, 12: 2048, 16: 32768, 21: 1048576, 24: 8388608}.get(bits, 0)
    if value >= power:
        return value - (power * 2)
    return value


# ── ODR frequency mapping (Hz → register value) ──────────────────────────────

_ODR_HZ_MAP = {
    400:    BMM350_ODR['400_HZ'],     # 0x02
    200:    BMM350_ODR['200_HZ'],     # 0x03
    100:    BMM350_ODR['100_HZ'],     # 0x04
    50:     BMM350_ODR['50_HZ'],      # 0x05
    25:     BMM350_ODR['25_HZ'],      # 0x06
    12.5:   BMM350_ODR['12_5_HZ'],    # 0x07
    6.25:   BMM350_ODR['6_25_HZ'],    # 0x08
    3.125:  BMM350_ODR['3_125_HZ'],   # 0x09
    1.5625: BMM350_ODR['1_5625_HZ'],  # 0x0A
}

# Averaging constraints per ODR (from Bosch driver)
_ODR_AVG_LIMITS = {
    400:  BMM350_AVG['NO_AVG'],   # 400Hz → no averaging max
    200:  BMM350_AVG['AVG_2'],    # 200Hz → avg 2 max
    100:  BMM350_AVG['AVG_4'],    # 100Hz → avg 4 max
}


class BMM350:
    """
    BMM350 Magnetometer Driver over COBRA I2C bridge.

    Supports two conversion modes:
      1. Default coefficients (no OTP) — simple raw × coefficient
      2. OTP compensated — full Bosch compensation chain with calibration data
    """

    def __init__(self, bridge, dev_addr: int = BMM350_I2C_ADDR):
        self.bridge = bridge
        self.dev_addr = dev_addr
        self._otp_data: list = []       # 32 OTP words (16-bit each)
        self._otp_loaded = False
        self._axis_en = 0x07            # XYZ enabled by default

        # OTP compensation coefficients (populated by read_otp)
        self._offset = {'x': 0.0, 'y': 0.0, 'z': 0.0, 't_offs': 0.0}
        self._sensit = {'x': 0.0, 'y': 0.0, 'z': 0.0, 't_sens': 0.0}
        self._tco = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self._tcs = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self._cross = {'x_y': 0.0, 'y_x': 0.0, 'z_x': 0.0, 'z_y': 0.0}
        self._dut_t0 = 23.0

    def _read_reg(self, reg: int, length: int = 1) -> bytes:
        return self.bridge.i2c_read(self.dev_addr, reg, length)

    def _write_reg(self, reg: int, data: bytes) -> int:
        return self.bridge.i2c_write(self.dev_addr, reg, data)

    # ── Initialization (mirrors Bosch bmm350_init) ───────────────────────

    def init(self) -> None:
        """
        Full initialization sequence (mirrors official Bosch bmm350_init):
          1. Soft reset
          2. Read chip ID
          3. OTP dump
          4. Power off OTP
          5. Magnetic reset (FGR + BR)
        """
        # Soft reset
        self.soft_reset()
        time.sleep(0.025)  # BMM350_SOFT_RESET_DELAY = 24ms

        # Verify chip ID
        chip_id = self.get_chip_id()
        if chip_id != BMM350_CHIP_ID:
            raise RuntimeError(f"BMM350 not found. Chip ID: 0x{chip_id:02X}, expected 0x33")

        # OTP dump
        self.read_otp()

        # Power off OTP
        self._write_reg(BMM350_REG['OTP_CMD_REG'], bytes([0x80]))
        time.sleep(0.001)

        # Magnetic reset: suspend → BR → FGR → normal
        self.set_power_mode('suspend')
        time.sleep(0.030)
        self._write_reg(BMM350_REG['PMU_CMD'], bytes([BMM350_PMU['BR']]))
        time.sleep(0.003)
        self._write_reg(BMM350_REG['PMU_CMD'], bytes([BMM350_PMU['FGR']]))
        time.sleep(0.030)

    # ── Chip ID ───────────────────────────────────────────────────────────

    def get_chip_id(self) -> int:
        """Read Chip ID. Expected: 0x33."""
        return self._read_reg(BMM350_REG['CHIP_ID'], 1)[0]

    def verify_chip_id(self) -> bool:
        """Verify BMM350 is present. Returns True if chip ID = 0x33."""
        return self.get_chip_id() == BMM350_CHIP_ID

    # ── Power Mode ────────────────────────────────────────────────────────

    _PMU_NAMES = {v: k.lower() for k, v in BMM350_PMU.items()
                  if k not in ('SOFT_RESET', 'UPD_OAE', 'FGR', 'FGR_FAST', 'BR', 'BR_FAST', 'NM_50HZ')}

    def set_power_mode(self, mode: str = 'normal') -> int:
        """
        Set power mode.

        Args:
            mode: 'suspend', 'nm', 'forced', 'nm_50hz'
        """
        mode_key = mode.lower()
        # Accept human-friendly aliases
        aliases = {'normal': 'nm', 'continuous': 'nm', 'suspend': 'sus'}
        mode_key = aliases.get(mode_key, mode_key)
        cmd = BMM350_PMU.get(mode_key.upper())
        if cmd is None:
            valid = [k.lower() for k in BMM350_PMU if k not in ('SOFT_RESET', 'UPD_OAE')]
            raise ValueError(f"Invalid mode: {mode}. Valid: {valid}")
        return self._write_reg(BMM350_REG['PMU_CMD'], bytes([cmd]))

    def get_power_mode(self) -> str:
        """Read current power mode from PMU_CMD_STATUS_0."""
        status = self._read_reg(BMM350_REG['PMU_CMD_STATUS_0'], 1)[0] & 0x0F
        return self._PMU_NAMES.get(status, f'unknown(0x{status:02X})')

    # ── ODR (official Bosch register sequence) ───────────────────────────

    def set_odr(self, frequency_hz: float = 100, averaging: str = 'low_power') -> int:
        """
        Set output data rate and averaging.

        Writes ODR+AVG to PMU_CMD_AGGR_SET (0x04), then commits with
        PMU_CMD UPD_OAE (0x02 → register 0x06). Mirrors official Bosch
        bmm350_set_odr_performance() exactly.

        Args:
            frequency_hz: ODR in Hz. Valid: 400, 200, 100, 50, 25, 12.5, 6.25, 3.125, 1.5625
            averaging: 'low_power' (no avg), 'medium' (avg 2), 'high' (avg 4), 'ultra' (avg 8).
                       Automatically clamped if incompatible with ODR.

        Returns:
            Status code from I2C write.

        Raises:
            ValueError: If frequency_hz is not a valid ODR.
        """
        # Map frequency to register value
        odr_val = _ODR_HZ_MAP.get(frequency_hz)
        if odr_val is None:
            # Try close match for float precision issues
            for hz, val in _ODR_HZ_MAP.items():
                if abs(frequency_hz - hz) < 0.01:
                    odr_val = val
                    break
        if odr_val is None:
            valid = sorted(_ODR_HZ_MAP.keys())
            raise ValueError(f"Invalid ODR: {frequency_hz} Hz. Valid: {valid}")

        # Map averaging string to register value
        avg_map = {
            'low_power': BMM350_AVG['NO_AVG'],
            'medium':    BMM350_AVG['AVG_2'],
            'high':      BMM350_AVG['AVG_4'],
            'ultra':     BMM350_AVG['AVG_8'],
        }
        avg_val = avg_map.get(averaging, BMM350_AVG['NO_AVG'])

        # Clamp averaging if ODR is too high (Bosch constraint)
        if frequency_hz in _ODR_AVG_LIMITS:
            max_avg = _ODR_AVG_LIMITS[frequency_hz]
            if avg_val > max_avg:
                avg_val = max_avg

        # Build register value: bits[7:4] = AVG, bits[3:0] = ODR
        reg_data = (avg_val << 4) | (odr_val & 0x0F)

        # Write to PMU_CMD_AGGR_SET
        self._write_reg(BMM350_REG['PMU_CMD_AGGR_SET'], bytes([reg_data]))

        # Commit with UPD_OAE command
        self._write_reg(BMM350_REG['PMU_CMD'], bytes([BMM350_PMU['UPD_OAE']]))
        time.sleep(0.001)  # BMM350_UPD_OAE_DELAY = 1ms

        return 0

    # ── Axis Enable ───────────────────────────────────────────────────────

    def enable_axes(self, x: bool = True, y: bool = True, z: bool = True) -> int:
        """Enable/disable individual axes. At least one must be enabled."""
        data = (0x01 if x else 0x00) | (0x02 if y else 0x00) | (0x04 if z else 0x00)
        if data == 0:
            raise ValueError("At least one axis must be enabled")
        self._axis_en = data
        return self._write_reg(BMM350_REG['PMU_CMD_AXIS_EN'], bytes([data]))

    # ── OTP Calibration (mirrors Bosch otp_dump_after_boot + update_mag_off_sens) ──

    def read_otp(self) -> None:
        """
        Read all 32 OTP words and compute calibration coefficients.

        Mirrors official Bosch otp_dump_after_boot() + update_mag_off_sens().
        After this, compensated=True can be used in read_mag_data().
        """
        self._otp_data = []
        for addr in range(32):  # BMM350_OTP_DATA_LENGTH = 32
            word = self._read_otp_word(addr)
            self._otp_data.append(word)
        self._otp_loaded = True
        self._update_mag_off_sens()

    def _read_otp_word(self, addr: int) -> int:
        """Read a single 16-bit OTP word at given address."""
        otp_cmd = 0x20 | (addr & 0x1F)  # BMM350_OTP_CMD_DIR_READ | addr
        self._write_reg(BMM350_REG['OTP_CMD_REG'], bytes([otp_cmd]))
        time.sleep(0.0003)  # 300µs per Bosch driver
        # Check OTP status for command done
        for _ in range(10):
            status = self._read_reg(BMM350_REG['OTP_STATUS_REG'], 1)[0]
            if status & 0x01:  # OTP_STATUS_CMD_DONE
                break
            if status & 0xE0:  # OTP error bits
                raise RuntimeError(f"OTP read error at addr {addr}: status 0x{status:02X}")
            time.sleep(0.0003)
        msb = self._read_reg(BMM350_REG['OTP_DATA_MSB_REG'], 1)[0]
        lsb = self._read_reg(BMM350_REG['OTP_DATA_LSB_REG'], 1)[0]
        return (msb << 8) | lsb

    def _update_mag_off_sens(self) -> None:
        """
        Compute calibration coefficients from OTP data.
        Mirrors official Bosch update_mag_off_sens() — float path.
        """
        if not self._otp_loaded or len(self._otp_data) < 32:
            return

        d = self._otp_data  # shorthand

        # ── Offsets ──
        off_x = d[BMM350_OTP_ADDR['MAG_OFFSET_X']] & 0x0FFF
        off_y = ((d[BMM350_OTP_ADDR['MAG_OFFSET_X']] & 0xF000) >> 4) + \
                (d[BMM350_OTP_ADDR['MAG_OFFSET_Y']] & 0x00FF)
        off_z = (d[BMM350_OTP_ADDR['MAG_OFFSET_Y']] & 0x0F00) + \
                (d[BMM350_OTP_ADDR['MAG_OFFSET_Z']] & 0x00FF)
        t_off = d[BMM350_OTP_ADDR['TEMP_OFF_SENS']] & 0x00FF

        self._offset['x'] = fix_sign(off_x, 12)
        self._offset['y'] = fix_sign(off_y, 12)
        self._offset['z'] = fix_sign(off_z, 12)
        self._offset['t_offs'] = fix_sign(t_off, 8) / 5.0

        # ── Sensitivity ──
        sens_x = (d[BMM350_OTP_ADDR['MAG_SENS_X']] & 0xFF00) >> 8
        sens_y = d[BMM350_OTP_ADDR['MAG_SENS_Y']] & 0x00FF
        sens_z = (d[BMM350_OTP_ADDR['MAG_SENS_Z']] & 0xFF00) >> 8
        t_sens = (d[BMM350_OTP_ADDR['TEMP_OFF_SENS']] & 0xFF00) >> 8

        self._sensit['x'] = fix_sign(sens_x, 8) / 256.0
        self._sensit['y'] = fix_sign(sens_y, 8) / 256.0
        self._sensit['z'] = fix_sign(sens_z, 8) / 256.0
        self._sensit['t_sens'] = fix_sign(t_sens, 8) / 512.0

        # ── TCO (temperature coefficient of offset) ──
        tco_x = d[BMM350_OTP_ADDR['MAG_TCO_X']] & 0x00FF
        tco_y = d[BMM350_OTP_ADDR['MAG_TCO_Y']] & 0x00FF
        tco_z = d[BMM350_OTP_ADDR['MAG_TCO_Z']] & 0x00FF

        self._tco['x'] = fix_sign(tco_x, 8) / 32.0
        self._tco['y'] = fix_sign(tco_y, 8) / 32.0
        self._tco['z'] = fix_sign(tco_z, 8) / 32.0

        # ── TCS (temperature coefficient of sensitivity) ──
        tcs_x = (d[BMM350_OTP_ADDR['MAG_TCS_X']] & 0xFF00) >> 8
        tcs_y = (d[BMM350_OTP_ADDR['MAG_TCS_Y']] & 0xFF00) >> 8
        tcs_z = (d[BMM350_OTP_ADDR['MAG_TCS_Z']] & 0xFF00) >> 8

        self._tcs['x'] = fix_sign(tcs_x, 8) / 16384.0
        self._tcs['y'] = fix_sign(tcs_y, 8) / 16384.0
        self._tcs['z'] = fix_sign(tcs_z, 8) / 16384.0

        # ── Reference temperature T0 ──
        t0_raw = d[BMM350_OTP_ADDR['MAG_DUT_T_0']]
        self._dut_t0 = fix_sign(t0_raw, 16) / 512.0 + 23.0

        # ── Cross-axis sensitivity ──
        cross_x_y = d[BMM350_OTP_ADDR['CROSS_X_Y']] & 0x00FF
        cross_y_x = (d[BMM350_OTP_ADDR['CROSS_Y_X']] & 0xFF00) >> 8
        cross_z_x = d[BMM350_OTP_ADDR['CROSS_Z_X']] & 0x00FF
        cross_z_y = (d[BMM350_OTP_ADDR['CROSS_Z_Y']] & 0xFF00) >> 8

        self._cross['x_y'] = fix_sign(cross_x_y, 8) / 800.0
        self._cross['y_x'] = fix_sign(cross_y_x, 8) / 800.0
        self._cross['z_x'] = fix_sign(cross_z_x, 8) / 800.0
        self._cross['z_y'] = fix_sign(cross_z_y, 8) / 800.0

    # ── Data Readout ─────────────────────────────────────────────────────

    def is_data_ready(self) -> bool:
        """Check if new data is available (INT_STATUS bit 0)."""
        return (self._read_reg(BMM350_REG['INT_STATUS'], 1)[0] & 0x01) != 0

    def read_raw_data(self) -> Dict[str, int]:
        """
        Read raw 24-bit magnetic + temperature data.

        Returns:
            {'x_raw': int, 'y_raw': int, 'z_raw': int, 't_raw': int}
            All values are signed 24-bit integers.
        """
        raw = self._read_reg(BMM350_REG['MAG_X_XLSB'], BMM350_DATA_LEN)  # 12 bytes
        x_raw = raw[0] | (raw[1] << 8) | (raw[2] << 16)
        y_raw = raw[3] | (raw[4] << 8) | (raw[5] << 16)
        z_raw = raw[6] | (raw[7] << 8) | (raw[8] << 16)
        t_raw = raw[9] | (raw[10] << 8) | (raw[11] << 16)

        return {
            'x_raw': fix_sign(x_raw, 24),
            'y_raw': fix_sign(y_raw, 24),
            'z_raw': fix_sign(z_raw, 24),
            't_raw': fix_sign(t_raw, 24),
        }

    def read_mag_data(self, compensated: bool = False) -> Dict[str, float]:
        """
        Read 3-axis magnetic field in μT and temperature in °C.

        Args:
            compensated: If True and OTP loaded, apply full Bosch compensation
                         chain (offset, sensitivity, TCO, TCS, cross-axis).
                         If False, use default coefficients (no OTP).

        Returns:
            {'x': float, 'y': float, 'z': float, 'temperature': float,
             'x_raw': int, 'y_raw': int, 'z_raw': int, 't_raw': int}
        """
        raw = self.read_raw_data()
        x_raw = raw['x_raw']
        y_raw = raw['y_raw']
        z_raw = raw['z_raw']
        t_raw = raw['t_raw']

        # Step 1: Convert raw to μT/°C using default coefficients
        x = x_raw * BMM350_LSB_TO_UT_XY
        y = y_raw * BMM350_LSB_TO_UT_XY  # Same as X
        z = z_raw * BMM350_LSB_TO_UT_Z
        temp = t_raw * BMM350_LSB_TO_DEGC - BMM350_TEMP_OFFSET

        if compensated and self._otp_loaded:
            # Step 2: Temperature compensation
            temp = (1 + self._sensit['t_sens']) * temp + self._offset['t_offs']

            # Step 3: Per-axis compensation (mirrors Bosch loop)
            axes = [x, y, z]
            offset = [self._offset['x'], self._offset['y'], self._offset['z']]
            sensit = [self._sensit['x'], self._sensit['y'], self._sensit['z']]
            tco    = [self._tco['x'],    self._tco['y'],    self._tco['z']]
            tcs    = [self._tcs['x'],    self._tcs['y'],    self._tcs['z']]

            for i in range(3):
                axes[i] *= (1 + sensit[i])
                axes[i] += offset[i]
                axes[i] += tco[i] * (temp - self._dut_t0)
                axes[i] /= (1 + tcs[i] * (temp - self._dut_t0))

            x, y, z = axes

            # Step 4: Cross-axis compensation (mirrors Bosch formula exactly)
            cxy = self._cross['x_y']
            cyx = self._cross['y_x']
            czx = self._cross['z_x']
            czy = self._cross['z_y']
            det = 1 - cyx * cxy

            x_comp = (x - cxy * y) / det
            y_comp = (y - cyx * x) / det
            z_comp = z + (
                x * (cyx * czy - czx) - y * (czy - cxy * czx)
            ) / det

            x, y, z = x_comp, y_comp, z_comp

        return {
            'x': x, 'y': y, 'z': z, 'temperature': temp,
            'x_raw': x_raw, 'y_raw': y_raw, 'z_raw': z_raw, 't_raw': t_raw,
        }

    # ── Utility ───────────────────────────────────────────────────────────

    def soft_reset(self) -> int:
        """Send soft reset command (0xB6 to CMD_REG 0x24)."""
        return self._write_reg(BMM350_REG['CMD_REG'], bytes([0xB6]))

    def read_error_status(self) -> int:
        """Read error status register."""
        return self._read_reg(BMM350_REG['ERR_STAT'], 1)[0]

    @property
    def otp_loaded(self) -> bool:
        """Whether OTP calibration data has been loaded."""
        return self._otp_loaded

    @property
    def otp_data(self) -> list:
        """Raw OTP data (32 × 16-bit words)."""
        return self._otp_data