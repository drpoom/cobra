"""
COBRA V2: BMM350Async — Non-Blocking Magnetometer Driver

High-rate sensor driver (up to 400 Hz) that uses the V2 AsyncBridge
with background reader thread. The read_sensor() method is non-blocking:
it sends an I2C read request and immediately returns. On the next call,
it picks up the response from the reader queue.

This decouples sensor polling from the main execution loop, enabling
smooth 400 Hz data acquisition without blocking.

Usage:
    from cobra_bridge_v2 import AsyncBridge
    from bmm350_v2 import BMM350Async

    bridge = AsyncBridge(port='/dev/ttyACM0')
    bridge.connect()

    sensor = BMM350Async(bridge)
    sensor.start_continuous(odr='400_HZ')

    # Non-blocking 400 Hz loop
    while True:
        data = sensor.read_sensor()  # Returns dict or None (never blocks)
        if data:
            print(f"X={data['x']:.2f} Y={data['y']:.2f} Z={data['z']:.2f} uT")
        do_other_work()  # Main loop is never blocked

    sensor.stop_continuous()
    bridge.disconnect()
"""

import struct
import time
from typing import Dict, Optional

from cobra_constants import (
    TYPE_GET, CMD_I2C_READ, CMD_I2C_WRITE,
    I2C_SPEED_400K, STATUS_OK,
    BMM350_I2C_ADDR, BMM350_CHIP_ID, BMM350_SENSITIVITY,
    BMM350_REG, BMM350_PMU, BMM350_ODR,
)


class BMM350Async:
    """
    Non-blocking BMM350 driver for high-rate polling (up to 400 Hz).

    How read_sensor() works:
      1. Check reader queue for any pending response from previous request
      2. If found, decode it → return magnetometer data dict
      3. Send a new I2C read request for the next sample
      4. Return the previous data (or None if no pending response)

    This pipelined approach means the I2C request is in-flight while
    the main loop does other work. At 400 Hz, the 2.5ms sensor ODR
    interval overlaps with serial round-trip time.
    """

    def __init__(self, bridge, dev_addr: int = BMM350_I2C_ADDR,
                 stale_threshold: int = 8):
        """
        Args:
            bridge: AsyncBridge instance (must be connected).
            dev_addr: BMM350 I2C address (default 0x14).
            stale_threshold: Max queued responses before eviction (default 8).
                             At 400Hz, 8 = 20ms of stale data.
        """
        self.bridge = bridge
        self.dev_addr = dev_addr
        self._stale_threshold = stale_threshold
        self._pending = False  # True if we have an I2C read in flight
        self._sample_count = 0

        # Stats
        self.reads_sent = 0
        self.reads_received = 0
        self.stale_dropped = 0

    # ── Chip ID (blocking — used once at init) ───────────────────────────

    def get_chip_id(self) -> int:
        """Read Chip ID (blocking). Expected: 0x33."""
        return self.bridge.i2c_read(self.dev_addr, BMM350_REG['CHIP_ID'], 1)[0]

    def verify_chip_id(self) -> bool:
        return self.get_chip_id() == BMM350_CHIP_ID

    # ── Power Mode (blocking — used once at start/stop) ──────────────────

    def set_power_mode(self, mode: str = 'normal') -> int:
        mode_map = {k.lower(): v for k, v in BMM350_PMU.items() if k != 'SOFT_RESET'}
        cmd = mode_map.get(mode.lower())
        if cmd is None:
            raise ValueError(f"Invalid mode: {mode}")
        return self.bridge.i2c_write(self.dev_addr, BMM350_REG['PMU_CMD'], bytes([cmd]))

    def get_power_mode(self) -> str:
        pmu_names = {v: k.lower() for k, v in BMM350_PMU.items() if k != 'SOFT_RESET'}
        status = self.bridge.i2c_read(self.dev_addr, BMM350_REG['PMU_STATUS'], 1)[0] & 0x0F
        return pmu_names.get(status, f'unknown(0x{status:02X})')

    # ── ODR ───────────────────────────────────────────────────────────────

    def set_odr(self, odr_key: str = '100_HZ') -> int:
        odr_val = BMM350_ODR.get(odr_key)
        if odr_val is None:
            raise ValueError(f"Invalid ODR: {odr_key}")
        cur = self.bridge.i2c_read(self.dev_addr, BMM350_REG['ODR_AXIS'], 1)
        return self.bridge.i2c_write(
            self.dev_addr, BMM350_REG['ODR_AXIS'],
            bytes([(cur[0] & 0x8F) | ((odr_val & 0x07) << 4)])
        )

    # ── Continuous Mode ──────────────────────────────────────────────────

    def start_continuous(self, odr: str = '100_HZ') -> None:
        """
        Start continuous measurement mode.

        Args:
            odr: ODR key from protocol_spec ('400_HZ', '200_HZ', etc.)
        """
        self.set_power_mode('continuous')
        self.set_odr(odr)
        self._pending = False
        self._sample_count = 0
        # Prime the pipeline: send first read request
        self._send_read_request()

    def stop_continuous(self) -> None:
        """Stop continuous mode and return sensor to suspend."""
        self.set_power_mode('suspend')
        self._pending = False
        # Drain any remaining queued responses
        self.bridge.drain_queue()

    # ── Non-Blocking Read ────────────────────────────────────────────────

    def _send_read_request(self) -> None:
        """Send an I2C read for 6 bytes from DATA_X_LSB (non-blocking send)."""
        payload = struct.pack('<BBBB', self.dev_addr, I2C_SPEED_400K,
                              BMM350_REG['DATA_X_LSB'], 6)
        self.bridge.send_packet(TYPE_GET, CMD_I2C_READ, payload)
        self._pending = True
        self.reads_sent += 1

    def _poll_response(self) -> Optional[bytes]:
        """
        Check reader queue for a pending I2C response.

        Returns:
            Data bytes if response available, None otherwise.
        """
        pkt = self.bridge.poll_packet(timeout=0.0)
        if pkt is None:
            return None

        ptype, command, status, data = pkt
        if status != STATUS_OK:
            return None

        # Evict stale data if queue is backing up
        if self.bridge.get_reader_stats().get('queue_size', 0) > self._stale_threshold:
            stale = self.bridge.drain_queue()
            self.stale_dropped += len(stale)

        self._pending = False
        self.reads_received += 1
        return data

    def read_sensor(self) -> Optional[Dict[str, float]]:
        """
        Non-blocking sensor read. Returns magnetometer data or None.

        Pipeline:
          1. If a previous request is pending, check queue for its response
          2. If response found, decode it
          3. Send next read request (fire-and-forget)
          4. Return decoded data (or None if no response yet)

        This method NEVER blocks the main loop. Call it in a tight loop
        for maximum throughput, or at your desired rate for controlled sampling.

        Returns:
            {'x': float, 'y': float, 'z': float, 'x_raw': int, ...} or None
        """
        # 1. Try to pick up previous response
        data = None
        if self._pending:
            raw = self._poll_response()
            if raw and len(raw) >= 6:
                x, y, z = struct.unpack('<hhh', raw[:6])
                data = {
                    'x': x * BMM350_SENSITIVITY,
                    'y': y * BMM350_SENSITIVITY,
                    'z': z * BMM350_SENSITIVITY,
                    'x_raw': x, 'y_raw': y, 'z_raw': z,
                }
                self._sample_count += 1

        # 2. Send next request (pipelined)
        self._send_read_request()

        return data

    # ── Blocking Read (for convenience) ──────────────────────────────────

    def read_sensor_blocking(self, timeout: float = 0.05) -> Optional[Dict[str, float]]:
        """
        Blocking sensor read with timeout.

        Same as read_sensor() but waits up to `timeout` seconds for response.
        """
        self._send_read_request()
        pkt = self.bridge.poll_packet(timeout=timeout)
        if pkt is None:
            return None

        _, _, status, data = pkt
        if status != STATUS_OK or len(data) < 6:
            return None

        x, y, z = struct.unpack('<hhh', data[:6])
        self._sample_count += 1
        self.reads_received += 1
        return {
            'x': x * BMM350_SENSITIVITY,
            'y': y * BMM350_SENSITIVITY,
            'z': z * BMM350_SENSITIVITY,
            'x_raw': x, 'y_raw': y, 'z_raw': z,
        }

    # ── Utility ───────────────────────────────────────────────────────────

    def soft_reset(self) -> int:
        return self.bridge.i2c_write(
            self.dev_addr, BMM350_REG['PMU_CMD'],
            bytes([BMM350_PMU['SOFT_RESET']])
        )

    def read_error_status(self) -> int:
        return self.bridge.i2c_read(self.dev_addr, BMM350_REG['ERR_STAT'], 1)[0]

    @property
    def sample_count(self) -> int:
        return self._sample_count

    def get_stats(self) -> dict:
        """Return driver statistics."""
        return {
            'reads_sent': self.reads_sent,
            'reads_received': self.reads_received,
            'stale_dropped': self.stale_dropped,
            'sample_count': self._sample_count,
            'pending': self._pending,
        }