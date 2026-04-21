"""
COBRA Sync: BMM350 Magnetometer Driver (Python)

Register-level driver for the Bosch BMM350 magnetometer.
Based on official Bosch BMM350_SensorAPI v1.10.0 conversion formulas.
All register addresses and constants come from core/sensors/bmm350.json
via cobra_bridge.drivers.bmm350_constants — the single source of truth.

Key features:
  - 24-bit data reads (12 bytes: 3 bytes/axis × 3 axes + 3 bytes temp)
  - Official Bosch conversion coefficients (not 1/6 simplification)
  - Temperature readout with proper °C conversion
  - OTP calibration support (offset, sensitivity, TCO, TCS, cross-axis)
  - set_odr(frequency_hz) with user-friendly Hz input
  - Inherits from SensorDriver ABC for sensor-agnostic framework

Usage:
    from cobra_bridge import CobraBoard, CommInterface
    from cobra_bridge.drivers.bmm350 import BMM350Driver

    board = CobraBoard()
    board.open_comm_interface(CommInterface.USB)

    sensor = BMM350Driver(board, interface="i2c", bus=0)
    sensor.setup_board()   # Board-level: VDD, I2C config, pins
    sensor.init()          # Sensor-level: reset, verify, OTP, magnetic reset

    # Read data (returns BMM350Data dataclass)
    data = sensor.read_data()
    print(f"X={data.x:.2f} Y={data.y:.2f} Z={data.z:.2f} uT")
    print(f"T={data.temperature:.2f} °C")

    # With OTP compensation
    data = sensor.read_data(compensated=True)

    # Set ODR
    sensor.set_odr(100)       # 100 Hz
    sensor.set_odr(400)       # 400 Hz

    board.close_comm_interface()

Legacy usage (backward compatible):
    from cobra_bridge.drivers.bmm350 import BMM350
    sensor = BMM350(board)
    data = sensor.read_mag_data()  # Returns dict
"""

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .base import SensorDriver, SensorData
from .utils import fix_sign
from .bmm350_constants import (
    BMM350_I2C_ADDR, BMM350_CHIP_ID, BMM350_DATA_LEN,
    BMM350_REG, BMM350_PMU, BMM350_ODR, BMM350_AVG, BMM350_OTP_ADDR,
    BMM350_LSB_TO_UT_XY, BMM350_LSB_TO_UT_Z, BMM350_LSB_TO_DEGC, BMM350_TEMP_OFFSET,
)
from cobra_bridge.constants import (
    I2C_BUS_0, I2C_SPEED_STANDARD,
    SHUTTLE_PIN_7, PIN_OUT, PIN_LOW,
)


# ── BMM350Data ───────────────────────────────────────────────────────────

@dataclass
class BMM350Data(SensorData):
    """BMM350 magnetometer data with physical units."""
    x: float = 0.0            # μT
    y: float = 0.0            # μT
    z: float = 0.0            # μT
    temperature: float = 0.0  # °C


# ── ODR frequency mapping (Hz → register value) ──────────────────────────

_ODR_HZ_MAP = {
    400:    BMM350_ODR['400_HZ'],
    200:    BMM350_ODR['200_HZ'],
    100:    BMM350_ODR['100_HZ'],
    50:     BMM350_ODR['50_HZ'],
    25:     BMM350_ODR['25_HZ'],
    12.5:   BMM350_ODR['12_5_HZ'],
    6.25:   BMM350_ODR['6_25_HZ'],
    3.125:  BMM350_ODR['3_125_HZ'],
    1.5625: BMM350_ODR['1_5625_HZ'],
}

_ODR_AVG_LIMITS = {
    400:  BMM350_AVG['NO_AVG'],
    200:  BMM350_AVG['AVG_2'],
    100:  BMM350_AVG['AVG_4'],
}


# ── BMM350Driver ─────────────────────────────────────────────────────────

class BMM350Driver(SensorDriver):
    """
    BMM350 Magnetometer Driver — inherits from SensorDriver ABC.

    Supports two conversion modes:
      1. Default coefficients (no OTP) — simple raw × coefficient
      2. OTP compensated — full Bosch compensation chain with calibration data
    """

    # ── SensorDriver class attributes ────────────────────────────────────
    name: str = "bmm350"
    chip_id: int = BMM350_CHIP_ID
    i2c_addr: int = BMM350_I2C_ADDR
    spi_read_cmd: int = 0x80
    spi_write_cmd: int = 0x00

    def __init__(self, board, interface: str = "i2c", bus: int = 0,
                 addr: Optional[int] = None):
        super().__init__(board, interface, bus, addr)
        self._otp_data: list = []
        self._otp_loaded = False
        self._axis_en = 0x07

        # OTP compensation coefficients (populated by read_otp)
        self._offset = {'x': 0.0, 'y': 0.0, 'z': 0.0, 't_offs': 0.0}
        self._sensit = {'x': 0.0, 'y': 0.0, 'z': 0.0, 't_sens': 0.0}
        self._tco = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self._tcs = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self._cross = {'x_y': 0.0, 'y_x': 0.0, 'z_x': 0.0, 'z_y': 0.0}
        self._dut_t0 = 23.0

    # ── Register I/O ────────────────────────────────────────────────────

    def _read_reg(self, reg: int, length: int = 1) -> list[int]:
        return self.board.i2c_read_reg(self.addr, reg, length)

    def _write_reg(self, reg: int, data: bytes) -> int:
        return self.board.i2c_write_reg(self.addr, reg, data)

    # ── Board Setup (board-level concerns) ────────────────────────────────

    def setup_board(self, bus: int = I2C_BUS_0, speed: int = I2C_SPEED_STANDARD,
                    vdd_mv: int = 1800, vddio_mv: int = 1800) -> None:
        """
        Board-level setup: I2C bus config, pin config, power cycle.

        Call this before init() or do board setup manually.

        Args:
            bus: I2C bus number (0 or 1). Default: 0.
            speed: I2C speed mode. 0=standard/400K, 1=fast/1M.
            vdd_mv: VDD voltage in mV. Default: 1800.
            vddio_mv: VDDIO voltage in mV. Default: 1800.
        """
        # Configure I2C bus
        self.board.config_i2c_bus(bus=bus, i2c_address=self.addr,
                                  i2c_mode=0)  # TODO: use proper I2CMode enum

        # Set shuttle pin 7 (standard CS/address pin for AppBoard3.1)
        self.board.set_pin(SHUTTLE_PIN_7, PIN_OUT, PIN_LOW)

        # Power cycle
        self.board.set_vdd(0)
        self.board.set_vddio(0)
        time.sleep(0.100)

        self.board.set_vdd(vdd_mv)
        self.board.set_vddio(vddio_mv)
        time.sleep(0.100)

    # ── SensorDriver abstract method implementations ─────────────────────

    def init(self, **kwargs) -> None:
        """
        Full sensor-level initialization sequence.

        Mirrors the official Bosch COINES SDK init sequence:
          1. Soft reset
          2. Verify chip ID
          3. OTP dump
          4. Power off OTP
          5. Magnetic reset (suspend → BR → FGR)

        Board-level setup (VDD, I2C config, pins) should be done
        via setup_board() or manually before calling init().
        """
        # Step 1: Soft reset
        self.soft_reset()
        time.sleep(0.025)  # BMM350_SOFT_RESET_DELAY = 24ms

        # Step 2: Verify chip ID
        chip_id = self.get_chip_id()
        if chip_id != BMM350_CHIP_ID:
            raise RuntimeError(f"BMM350 not found. Chip ID: 0x{chip_id:02X}, expected 0x33")

        # Step 3: OTP dump
        self.read_otp()

        # Step 4: Power off OTP
        self._write_reg(BMM350_REG['OTP_CMD_REG'], bytes([0x80]))
        time.sleep(0.001)

        # Step 5: Magnetic reset: suspend → BR → FGR
        self.set_power_mode('suspend')
        time.sleep(0.030)
        self._write_reg(BMM350_REG['PMU_CMD'], bytes([BMM350_PMU['BR']]))
        time.sleep(0.003)
        self._write_reg(BMM350_REG['PMU_CMD'], bytes([BMM350_PMU['FGR']]))
        time.sleep(0.030)

    def soft_reset(self) -> int:
        """Send soft reset command (0xB6 to CMD_REG 0x24)."""
        return self._write_reg(BMM350_REG['CMD_REG'], bytes([0xB6]))

    def get_chip_id(self) -> int:
        """Read Chip ID. Expected: 0x33."""
        return self._read_reg(BMM350_REG['CHIP_ID'], 1)[0]

    def self_test(self) -> bool:
        """Run built-in self test by reading error status register."""
        err = self.read_error_status()
        return err == 0

    def configure(self, settings: Dict[str, Any]) -> None:
        """
        Apply sensor configuration.

        Args:
            settings: Dict with optional keys:
                - 'odr_hz': Output data rate in Hz
                - 'averaging': 'low_power', 'medium', 'high', 'ultra'
                - 'power_mode': 'normal', 'suspend', 'forced'
        """
        if 'power_mode' in settings:
            self.set_power_mode(settings['power_mode'])
        if 'odr_hz' in settings:
            avg = settings.get('averaging', 'low_power')
            self.set_odr(settings['odr_hz'], avg)

    def read_data(self, compensated: bool = False) -> BMM350Data:
        """
        Read 3-axis magnetic field in μT and temperature in °C.

        Args:
            compensated: If True and OTP loaded, apply full Bosch compensation.

        Returns:
            BMM350Data instance with x, y, z (μT), temperature (°C).
        """
        raw = self.read_raw_data()
        x_raw = raw['x_raw']
        y_raw = raw['y_raw']
        z_raw = raw['z_raw']
        t_raw = raw['t_raw']

        # Step 1: Convert raw to μT/°C using default coefficients
        x = x_raw * BMM350_LSB_TO_UT_XY
        y = y_raw * BMM350_LSB_TO_UT_XY
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

        return BMM350Data(
            raw={'x_raw': x_raw, 'y_raw': y_raw, 'z_raw': z_raw, 't_raw': t_raw},
            x=x, y=y, z=z, temperature=temp,
        )

    # ── Power Mode ──────────────────────────────────────────────────────

    _PMU_NAMES = {v: k.lower() for k, v in BMM350_PMU.items()
                  if k not in ('SOFT_RESET', 'UPD_OAE', 'FGR', 'FGR_FAST', 'BR', 'BR_FAST', 'NM_50HZ')}

    def set_power_mode(self, mode: str = 'normal') -> int:
        """Set power mode.

        Supported modes: 'suspend'/'sus', 'normal'/'nm'/'continuous',
        'forced', 'forced_fast', 'nm_50hz'.
        """
        mode_key = mode.lower()
        aliases = {
            'normal': 'nm', 'continuous': 'nm', 'suspend': 'sus',
            'forced_fast': 'fgr_fast',
        }
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

    # ── ODR ──────────────────────────────────────────────────────────────

    def set_odr(self, frequency_hz: float = 100, averaging: str = 'low_power') -> int:
        """Set output data rate and averaging. Mirrors official Bosch bmm350_set_odr_performance()."""
        odr_val = _ODR_HZ_MAP.get(frequency_hz)
        if odr_val is None:
            for hz, val in _ODR_HZ_MAP.items():
                if abs(frequency_hz - hz) < 0.01:
                    odr_val = val
                    break
        if odr_val is None:
            valid = sorted(_ODR_HZ_MAP.keys())
            raise ValueError(f"Invalid ODR: {frequency_hz} Hz. Valid: {valid}")

        avg_map = {
            'low_power': BMM350_AVG['NO_AVG'],
            'medium':    BMM350_AVG['AVG_2'],
            'high':      BMM350_AVG['AVG_4'],
            'ultra':     BMM350_AVG['AVG_8'],
        }
        avg_val = avg_map.get(averaging, BMM350_AVG['NO_AVG'])

        if frequency_hz in _ODR_AVG_LIMITS:
            max_avg = _ODR_AVG_LIMITS[frequency_hz]
            if avg_val > max_avg:
                avg_val = max_avg

        reg_data = (avg_val << 4) | (odr_val & 0x0F)
        self._write_reg(BMM350_REG['PMU_CMD_AGGR_SET'], bytes([reg_data]))
        self._write_reg(BMM350_REG['PMU_CMD'], bytes([BMM350_PMU['UPD_OAE']]))
        time.sleep(0.001)
        return 0

    # ── Axis Enable ──────────────────────────────────────────────────────

    def enable_axes(self, x: bool = True, y: bool = True, z: bool = True) -> int:
        """Enable/disable individual axes. At least one must be enabled."""
        data = (0x01 if x else 0x00) | (0x02 if y else 0x00) | (0x04 if z else 0x00)
        if data == 0:
            raise ValueError("At least one axis must be enabled")
        self._axis_en = data
        return self._write_reg(BMM350_REG['PMU_CMD_AXIS_EN'], bytes([data]))

    # ── OTP Calibration ─────────────────────────────────────────────────

    def read_otp(self) -> None:
        """Read all 32 OTP words and compute calibration coefficients."""
        self._otp_data = []
        for addr in range(32):
            word = self._read_otp_word(addr)
            self._otp_data.append(word)
        self._otp_loaded = True
        self._update_mag_off_sens()

    def _read_otp_word(self, addr: int) -> int:
        """Read a single 16-bit OTP word at given address."""
        otp_cmd = 0x20 | (addr & 0x1F)
        self._write_reg(BMM350_REG['OTP_CMD_REG'], bytes([otp_cmd]))
        time.sleep(0.0003)
        for _ in range(10):
            status = self._read_reg(BMM350_REG['OTP_STATUS_REG'], 1)[0]
            if status & 0x01:
                break
            if status & 0xE0:
                raise RuntimeError(f"OTP read error at addr {addr}: status 0x{status:02X}")
            time.sleep(0.0003)
        msb = self._read_reg(BMM350_REG['OTP_DATA_MSB_REG'], 1)[0]
        lsb = self._read_reg(BMM350_REG['OTP_DATA_LSB_REG'], 1)[0]
        return (msb << 8) | lsb

    def _update_mag_off_sens(self) -> None:
        """Compute calibration coefficients from OTP data. Mirrors Bosch update_mag_off_sens()."""
        if not self._otp_loaded or len(self._otp_data) < 32:
            return
        d = self._otp_data

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

        sens_x = (d[BMM350_OTP_ADDR['MAG_SENS_X']] & 0xFF00) >> 8
        sens_y = d[BMM350_OTP_ADDR['MAG_SENS_Y']] & 0x00FF
        sens_z = (d[BMM350_OTP_ADDR['MAG_SENS_Z']] & 0xFF00) >> 8
        t_sens = (d[BMM350_OTP_ADDR['TEMP_OFF_SENS']] & 0xFF00) >> 8

        self._sensit['x'] = fix_sign(sens_x, 8) / 256.0
        self._sensit['y'] = fix_sign(sens_y, 8) / 256.0
        self._sensit['z'] = fix_sign(sens_z, 8) / 256.0
        self._sensit['t_sens'] = fix_sign(t_sens, 8) / 512.0

        tco_x = d[BMM350_OTP_ADDR['MAG_TCO_X']] & 0x00FF
        tco_y = d[BMM350_OTP_ADDR['MAG_TCO_Y']] & 0x00FF
        tco_z = d[BMM350_OTP_ADDR['MAG_TCO_Z']] & 0x00FF

        self._tco['x'] = fix_sign(tco_x, 8) / 32.0
        self._tco['y'] = fix_sign(tco_y, 8) / 32.0
        self._tco['z'] = fix_sign(tco_z, 8) / 32.0

        tcs_x = (d[BMM350_OTP_ADDR['MAG_TCS_X']] & 0xFF00) >> 8
        tcs_y = (d[BMM350_OTP_ADDR['MAG_TCS_Y']] & 0xFF00) >> 8
        tcs_z = (d[BMM350_OTP_ADDR['MAG_TCS_Z']] & 0xFF00) >> 8

        self._tcs['x'] = fix_sign(tcs_x, 8) / 16384.0
        self._tcs['y'] = fix_sign(tcs_y, 8) / 16384.0
        self._tcs['z'] = fix_sign(tcs_z, 8) / 16384.0

        t0_raw = d[BMM350_OTP_ADDR['MAG_DUT_T_0']]
        self._dut_t0 = fix_sign(t0_raw, 16) / 512.0 + 23.0

        cross_x_y = d[BMM350_OTP_ADDR['CROSS_X_Y']] & 0x00FF
        cross_y_x = (d[BMM350_OTP_ADDR['CROSS_Y_X']] & 0xFF00) >> 8
        cross_z_x = d[BMM350_OTP_ADDR['CROSS_Z_X']] & 0x00FF
        cross_z_y = (d[BMM350_OTP_ADDR['CROSS_Z_Y']] & 0xFF00) >> 8

        self._cross['x_y'] = fix_sign(cross_x_y, 8) / 800.0
        self._cross['y_x'] = fix_sign(cross_y_x, 8) / 800.0
        self._cross['z_x'] = fix_sign(cross_z_x, 8) / 800.0
        self._cross['z_y'] = fix_sign(cross_z_y, 8) / 800.0

    # ── Data Readout ────────────────────────────────────────────────────

    def is_data_ready(self) -> bool:
        """Check if new data is available (INT_STATUS bit 0)."""
        return (self._read_reg(BMM350_REG['INT_STATUS'], 1)[0] & 0x01) != 0

    def read_raw_data(self) -> Dict[str, int]:
        """Read raw 24-bit magnetic + temperature data."""
        raw = self._read_reg(BMM350_REG['MAG_X_XLSB'], BMM350_DATA_LEN)
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

        Backward-compatible method returning a dict.
        For new code, prefer read_data() which returns BMM350Data.
        """
        data = self.read_data(compensated=compensated)
        return {
            'x': data.x, 'y': data.y, 'z': data.z,
            'temperature': data.temperature,
            'x_raw': data.raw.get('x_raw', 0),
            'y_raw': data.raw.get('y_raw', 0),
            'z_raw': data.raw.get('z_raw', 0),
            't_raw': data.raw.get('t_raw', 0),
        }

    # ── Utility ─────────────────────────────────────────────────────────

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


# ── Backward-compatible alias ────────────────────────────────────────────

BMM350 = BMM350Driver
"""Alias for backward compatibility. Prefer BMM350Driver in new code."""