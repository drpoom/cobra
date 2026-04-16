"""
COBRA Async: BMM350Async — Non-Blocking Magnetometer Driver

High-rate sensor driver (up to 400 Hz) that uses the AsyncBridge
with background reader thread. Updated with official Bosch BMM350_SensorAPI
v1.10.0 conversion formulas (24-bit data, proper μT/°C coefficients, OTP compensation).

Key changes from V1:
  - 24-bit data reads (12 bytes: 3 bytes/axis × 3 axes + 3 bytes temp)
  - Official Bosch conversion coefficients (not 1/6 simplification)
  - Temperature readout with proper °C conversion
  - OTP calibration support (offset, sensitivity, TCO, TCS, cross-axis)
  - set_odr(frequency_hz) with user-friendly Hz input

Usage:
    from cobra_async import AsyncBridge
    from bmm350_async import BMM350Async

    bridge = AsyncBridge(port='/dev/ttyACM0')
    bridge.connect()

    sensor = BMM350Async(bridge)
    sensor.init()

    # Non-blocking 400 Hz loop
    sensor.start_continuous(odr=400)
    while True:
        data = sensor.read_sensor()  # Returns dict or None (never blocks)
        if data:
            print(f"X={data['x']:.2f} Y={data['y']:.2f} Z={data['z']:.2f} uT"
                  f" T={data['temperature']:.2f}°C")
        do_other_work()

    sensor.stop_continuous()
    bridge.disconnect()
"""

import struct
import time
from typing import Dict, Optional

from cobra_constants import (
    TYPE_GET, CMD_I2C_READ, CMD_I2C_WRITE,
    I2C_SPEED_400K, STATUS_OK,
    BMM350_I2C_ADDR, BMM350_CHIP_ID, BMM350_DATA_LEN,
    BMM350_REG, BMM350_PMU, BMM350_ODR, BMM350_AVG, BMM350_OTP_ADDR,
    BMM350_LSB_TO_UT_XY, BMM350_LSB_TO_UT_Z, BMM350_LSB_TO_DEGC, BMM350_TEMP_OFFSET,
)


# ── Sign Extension (mirrors Bosch fix_sign) ──────────────────────────────────

def fix_sign(value: int, bits: int) -> int:
    """Convert unsigned value to signed using two's complement (mirrors Bosch)."""
    power = {8: 128, 12: 2048, 16: 32768, 21: 1048576, 24: 8388608}.get(bits, 0)
    if value >= power:
        return value - (power * 2)
    return value


# ── ODR frequency mapping ────────────────────────────────────────────────────

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


class BMM350Async:
    """
    Non-blocking BMM350 driver for high-rate polling (up to 400 Hz).

    Updated with official Bosch BMM350_SensorAPI v1.10.0 conversion:
    24-bit data, proper μT/°C coefficients, OTP compensation.
    """

    def __init__(self, bridge, dev_addr: int = BMM350_I2C_ADDR,
                 stale_threshold: int = 8):
        self.bridge = bridge
        self.dev_addr = dev_addr
        self._stale_threshold = stale_threshold
        self._pending = False
        self._sample_count = 0
        self._compensated = False

        # OTP compensation coefficients
        self._otp_loaded = False
        self._offset = {'x': 0.0, 'y': 0.0, 'z': 0.0, 't_offs': 0.0}
        self._sensit = {'x': 0.0, 'y': 0.0, 'z': 0.0, 't_sens': 0.0}
        self._tco = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self._tcs = {'x': 0.0, 'y': 0.0, 'z': 0.0}
        self._cross = {'x_y': 0.0, 'y_x': 0.0, 'z_x': 0.0, 'z_y': 0.0}
        self._dut_t0 = 23.0

        # Stats
        self.reads_sent = 0
        self.reads_received = 0
        self.stale_dropped = 0

    # ── Chip ID (blocking) ───────────────────────────────────────────────

    def get_chip_id(self) -> int:
        """Read Chip ID (blocking). Expected: 0x33."""
        return self.bridge.i2c_read(self.dev_addr, BMM350_REG['CHIP_ID'], 1)[0]

    def verify_chip_id(self) -> bool:
        return self.get_chip_id() == BMM350_CHIP_ID

    # ── Power Mode (blocking) ────────────────────────────────────────────

    def set_power_mode(self, mode: str = 'normal') -> int:
        aliases = {'normal': 'nm', 'continuous': 'nm', 'suspend': 'sus'}
        mode_key = aliases.get(mode.lower(), mode.lower())
        cmd = BMM350_PMU.get(mode_key.upper())
        if cmd is None:
            raise ValueError(f"Invalid mode: {mode}")
        return self.bridge.i2c_write(self.dev_addr, BMM350_REG['PMU_CMD'], bytes([cmd]))

    def get_power_mode(self) -> str:
        pmu_names = {v: k.lower() for k, v in BMM350_PMU.items()
                     if k not in ('SOFT_RESET', 'UPD_OAE', 'FGR', 'FGR_FAST', 'BR', 'BR_FAST', 'NM_50HZ')}
        status = self.bridge.i2c_read(self.dev_addr, BMM350_REG['PMU_CMD_STATUS_0'], 1)[0] & 0x0F
        return pmu_names.get(status, f'unknown(0x{status:02X})')

    # ── ODR (official Bosch register sequence) ───────────────────────────

    def set_odr(self, frequency_hz: float = 100, averaging: str = 'low_power') -> int:
        """
        Set output data rate and averaging.

        Args:
            frequency_hz: ODR in Hz. Valid: 400, 200, 100, 50, 25, 12.5, 6.25, 3.125, 1.5625
            averaging: 'low_power', 'medium', 'high', 'ultra' (auto-clamped for high ODR)
        """
        odr_val = _ODR_HZ_MAP.get(frequency_hz)
        if odr_val is None:
            for hz, val in _ODR_HZ_MAP.items():
                if abs(frequency_hz - hz) < 0.01:
                    odr_val = val
                    break
        if odr_val is None:
            raise ValueError(f"Invalid ODR: {frequency_hz} Hz")

        avg_map = {
            'low_power': BMM350_AVG['NO_AVG'], 'medium': BMM350_AVG['AVG_2'],
            'high': BMM350_AVG['AVG_4'], 'ultra': BMM350_AVG['AVG_8'],
        }
        avg_val = avg_map.get(averaging, BMM350_AVG['NO_AVG'])
        if frequency_hz in _ODR_AVG_LIMITS:
            avg_val = min(avg_val, _ODR_AVG_LIMITS[frequency_hz])

        reg_data = (avg_val << 4) | (odr_val & 0x0F)
        self.bridge.i2c_write(self.dev_addr, BMM350_REG['PMU_CMD_AGGR_SET'], bytes([reg_data]))
        self.bridge.i2c_write(self.dev_addr, BMM350_REG['PMU_CMD'], bytes([BMM350_PMU['UPD_OAE']]))
        return 0

    # ── OTP Calibration ──────────────────────────────────────────────────

    def read_otp(self) -> None:
        """Read OTP and compute calibration coefficients (blocking)."""
        otp_data = []
        for addr in range(32):
            otp_cmd = 0x20 | (addr & 0x1F)
            self.bridge.i2c_write(self.dev_addr, BMM350_REG['OTP_CMD_REG'], bytes([otp_cmd]))
            time.sleep(0.0003)
            for _ in range(10):
                status = self.bridge.i2c_read(self.dev_addr, BMM350_REG['OTP_STATUS_REG'], 1)[0]
                if status & 0x01:
                    break
                time.sleep(0.0003)
            msb = self.bridge.i2c_read(self.dev_addr, BMM350_REG['OTP_DATA_MSB_REG'], 1)[0]
            lsb = self.bridge.i2c_read(self.dev_addr, BMM350_REG['OTP_DATA_LSB_REG'], 1)[0]
            otp_data.append((msb << 8) | lsb)
        self._otp_data = otp_data
        self._otp_loaded = True
        self._update_mag_off_sens()

    def _update_mag_off_sens(self) -> None:
        """Compute calibration coefficients from OTP data (mirrors Bosch)."""
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

    # ── Continuous Mode ──────────────────────────────────────────────────

    def start_continuous(self, odr: float = 100, compensated: bool = False) -> None:
        """
        Start continuous measurement mode.

        Args:
            odr: ODR in Hz (e.g. 100, 200, 400)
            compensated: Enable OTP compensation
        """
        self._compensated = compensated
        self.set_power_mode('nm')
        self.set_odr(odr)
        self._pending = False
        self._sample_count = 0
        self._send_read_request()

    def stop_continuous(self) -> None:
        """Stop continuous mode and return sensor to suspend."""
        self.set_power_mode('sus')
        self._pending = False
        self.bridge.drain_queue()

    # ── Non-Blocking Read ────────────────────────────────────────────────

    def _send_read_request(self) -> None:
        """Send I2C read for 12 bytes from MAG_X_XLSB (non-blocking send)."""
        payload = struct.pack('<BBBB', self.dev_addr, I2C_SPEED_400K,
                              BMM350_REG['MAG_X_XLSB'], BMM350_DATA_LEN)
        self.bridge.send_packet(TYPE_GET, CMD_I2C_READ, payload)
        self._pending = True
        self.reads_sent += 1

    def _poll_response(self) -> Optional[bytes]:
        """Check reader queue for a pending I2C response."""
        pkt = self.bridge.poll_packet(timeout=0.0)
        if pkt is None:
            return None
        _, _, status, data = pkt
        if status != STATUS_OK:
            return None
        if self.bridge.get_reader_stats().get('queue_size', 0) > self._stale_threshold:
            stale = self.bridge.drain_queue()
            self.stale_dropped += len(stale)
        self._pending = False
        self.reads_received += 1
        return data

    def _convert_raw(self, data: bytes) -> Dict[str, float]:
        """
        Convert 12 raw bytes to μT and °C using official Bosch formulas.
        Same math as bmm350.py — both drivers use identical formulas.
        """
        x_raw = data[0] | (data[1] << 8) | (data[2] << 16)
        y_raw = data[3] | (data[4] << 8) | (data[5] << 16)
        z_raw = data[6] | (data[7] << 8) | (data[8] << 16)
        t_raw = data[9] | (data[10] << 8) | (data[11] << 16)

        x_raw = fix_sign(x_raw, 24)
        y_raw = fix_sign(y_raw, 24)
        z_raw = fix_sign(z_raw, 24)
        t_raw = fix_sign(t_raw, 24)

        # Default coefficients
        x = x_raw * BMM350_LSB_TO_UT_XY
        y = y_raw * BMM350_LSB_TO_UT_XY
        z = z_raw * BMM350_LSB_TO_UT_Z
        temp = t_raw * BMM350_LSB_TO_DEGC - BMM350_TEMP_OFFSET

        if self._compensated and self._otp_loaded:
            temp = (1 + self._sensit['t_sens']) * temp + self._offset['t_offs']
            axes = [x, y, z]
            offset = [self._offset['x'], self._offset['y'], self._offset['z']]
            sensit = [self._sensit['x'], self._sensit['y'], self._sensit['z']]
            tco = [self._tco['x'], self._tco['y'], self._tco['z']]
            tcs = [self._tcs['x'], self._tcs['y'], self._tcs['z']]
            for i in range(3):
                axes[i] *= (1 + sensit[i])
                axes[i] += offset[i]
                axes[i] += tco[i] * (temp - self._dut_t0)
                axes[i] /= (1 + tcs[i] * (temp - self._dut_t0))
            x, y, z = axes
            cxy = self._cross['x_y']
            cyx = self._cross['y_x']
            czx = self._cross['z_x']
            czy = self._cross['z_y']
            det = 1 - cyx * cxy
            x_comp = (x - cxy * y) / det
            y_comp = (y - cyx * x) / det
            z_comp = z + (x * (cyx * czy - czx) - y * (czy - cxy * czx)) / det
            x, y, z = x_comp, y_comp, z_comp

        return {
            'x': x, 'y': y, 'z': z, 'temperature': temp,
            'x_raw': x_raw, 'y_raw': y_raw, 'z_raw': z_raw, 't_raw': t_raw,
        }

    def read_sensor(self) -> Optional[Dict[str, float]]:
        """
        Non-blocking sensor read. Returns magnetometer data or None.

        Pipeline: pick up previous response → send next request → return data.
        """
        result = None
        if self._pending:
            raw = self._poll_response()
            if raw and len(raw) >= BMM350_DATA_LEN:
                result = self._convert_raw(raw[:BMM350_DATA_LEN])
                self._sample_count += 1
        self._send_read_request()
        return result

    def read_sensor_blocking(self, timeout: float = 0.05) -> Optional[Dict[str, float]]:
        """Blocking sensor read with timeout."""
        self._send_read_request()
        pkt = self.bridge.poll_packet(timeout=timeout)
        if pkt is None:
            return None
        _, _, status, data = pkt
        if status != STATUS_OK or len(data) < BMM350_DATA_LEN:
            return None
        self._sample_count += 1
        self.reads_received += 1
        return self._convert_raw(data[:BMM350_DATA_LEN])

    # ── Utility ───────────────────────────────────────────────────────────

    def soft_reset(self) -> int:
        return self.bridge.i2c_write(self.dev_addr, BMM350_REG['CMD_REG'], bytes([0xB6]))

    def read_error_status(self) -> int:
        return self.bridge.i2c_read(self.dev_addr, BMM350_REG['ERR_STAT'], 1)[0]

    @property
    def sample_count(self) -> int:
        return self._sample_count

    @property
    def otp_loaded(self) -> bool:
        return self._otp_loaded

    def get_stats(self) -> dict:
        return {
            'reads_sent': self.reads_sent,
            'reads_received': self.reads_received,
            'stale_dropped': self.stale_dropped,
            'sample_count': self._sample_count,
            'pending': self._pending,
        }