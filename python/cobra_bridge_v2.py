"""
COBRA V2: AsyncBridge — CobraBridge + CobraReader

Combines the synchronous CobraBridge (for sends) with the background
CobraReader thread (for receives) to enable non-blocking, high-rate
sensor polling up to 400 Hz.

Key improvement over V1:
  - send_packet() is non-blocking (writes to serial, reader thread handles response)
  - transact() uses reader queue for responses (no blocking serial reads)
  - BMM350 read_sensor() is non-blocking with stale-data eviction

Usage:
    from cobra_bridge_v2 import AsyncBridge
    from bmm350_v2 import BMM350Async

    bridge = AsyncBridge(port='/dev/ttyACM0')
    bridge.connect()   # Opens serial + starts reader thread

    sensor = BMM350Async(bridge)
    sensor.start_continuous(odr='400_HZ')

    # Non-blocking polling loop at 400 Hz
    while True:
        data = sensor.read_sensor()  # Returns dict or None
        if data:
            process(data)
        do_other_work()

    sensor.stop_continuous()
    bridge.disconnect()  # Stops reader thread + closes serial
"""

import struct
import time
import threading
from typing import Optional

from cobra_core import CobraBridge
from cobra_reader import CobraReader
from cobra_constants import (
    HEADER, TYPE_GET, TYPE_SET,
    CMD_I2C_READ, CMD_I2C_WRITE,
    CMD_SPI_READ, CMD_SPI_WRITE,
    CMD_GET_BOARD_INFO, CMD_SET_VDD, CMD_SET_VDDIO,
    STATUS_OK,
    I2C_SPEED_400K, I2C_SPEED_1M,
    SPI_SPEED_5MHZ, SPI_SPEED_10MHZ,
    SPI_MODE_0, SPI_MODE_3,
)


class AsyncBridge:
    """
    V2 Async Bridge: CobraBridge (send) + CobraReader (receive).

    The reader thread continuously drains the serial port and places
    decoded packets into a thread-safe queue. Main thread sends
    requests and picks up responses from the queue.

    Thread safety:
      - Serial writes are protected by a lock shared with the reader
      - Queue operations are inherently thread-safe
    """

    def __init__(self, port: str = '/dev/ttyUSB0', baudrate: int = 115200,
                 timeout: float = 2.0, max_queue_size: int = 64):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._bridge = CobraBridge(port=port, baudrate=baudrate, timeout=timeout)
        self._reader: Optional[CobraReader] = None
        self._max_queue = max_queue_size

    # ── Connection ────────────────────────────────────────────────────────

    def connect(self):
        """Open serial port and start background reader thread."""
        self._bridge.connect()
        self._reader = CobraReader(
            self._bridge._ser,
            max_queue_size=self._max_queue,
        )
        self._reader.start()
        # Give reader a moment to start
        time.sleep(0.05)

    def disconnect(self):
        """Stop reader thread and close serial port."""
        if self._reader:
            self._reader.stop(timeout=2.0)
            self._reader = None
        self._bridge.disconnect()

    @property
    def connected(self) -> bool:
        return self._bridge.connected and self._reader is not None and self._reader.is_running

    # ── Send (main thread) ───────────────────────────────────────────────

    def send_packet(self, ptype: int, command: int, payload: bytes = b'') -> None:
        """Build and send a COINES V3 packet (non-blocking send)."""
        if self._reader:
            self._reader.acquire_write()
        try:
            self._bridge.send_packet(ptype, command, payload)
        finally:
            if self._reader:
                self._reader.release_write()

    # ── Receive (from reader queue) ──────────────────────────────────────

    def receive_packet(self, timeout: Optional[float] = None) -> tuple:
        """
        Get next decoded packet from reader queue.

        Args:
            timeout: Seconds to wait (None = use bridge default).
        Returns:
            (ptype, command, status, data) tuple.
        """
        if not self._reader:
            raise ConnectionError("Reader not running")
        return self._reader.receive(timeout=timeout or self.timeout)

    def poll_packet(self, timeout: float = 0.0) -> Optional[tuple]:
        """Non-blocking: return next packet or None."""
        if not self._reader:
            return None
        return self._reader.poll(timeout=timeout)

    def drain_queue(self) -> list:
        """Remove all queued packets (discard stale data)."""
        if not self._reader:
            return []
        return self._reader.drain()

    # ── Transaction (send + queue-receive) ───────────────────────────────

    def transact(self, ptype: int, command: int, payload: bytes = b'',
                 timeout: Optional[float] = None) -> tuple:
        """Send packet and wait for response from reader queue."""
        self.send_packet(ptype, command, payload)
        _, _, status, resp_data = self.receive_packet(timeout=timeout)
        return status, resp_data

    # ── I2C Operations (same API as V1) ──────────────────────────────────

    def i2c_write(self, dev_addr: int, reg_addr: int, data: bytes,
                  speed: int = I2C_SPEED_400K) -> int:
        payload = struct.pack('<BBBB', dev_addr, speed, reg_addr, len(data)) + data
        status, _ = self.transact(TYPE_SET, CMD_I2C_WRITE, payload)
        return status

    def i2c_read(self, dev_addr: int, reg_addr: int, length: int,
                 speed: int = I2C_SPEED_400K) -> bytes:
        payload = struct.pack('<BBBB', dev_addr, speed, reg_addr, length)
        status, resp_data = self.transact(TYPE_GET, CMD_I2C_READ, payload)
        if status != STATUS_OK:
            raise IOError(f"I2C read failed: 0x{status:02X}")
        return resp_data

    # ── SPI Operations ─────────────────────────────────────────────────

    def spi_write(self, cs_line: int, reg_addr: int, data: bytes,
                  speed: int = SPI_SPEED_5MHZ, mode: int = SPI_MODE_0) -> int:
        payload = struct.pack('<BBBBB', cs_line, speed, mode, reg_addr, len(data)) + data
        status, _ = self.transact(TYPE_SET, CMD_SPI_WRITE, payload)
        return status

    def spi_read(self, cs_line: int, reg_addr: int, length: int,
                 speed: int = SPI_SPEED_5MHZ, mode: int = SPI_MODE_0) -> bytes:
        payload = struct.pack('<BBBBB', cs_line, speed, mode, reg_addr, length)
        status, resp_data = self.transact(TYPE_GET, CMD_SPI_READ, payload)
        if status != STATUS_OK:
            raise IOError(f"SPI read failed: 0x{status:02X}")
        return resp_data

    # ── Board Control ──────────────────────────────────────────────────

    def get_board_info(self) -> dict:
        status, data = self.transact(TYPE_GET, CMD_GET_BOARD_INFO)
        if status != STATUS_OK:
            raise IOError(f"Get board info failed: 0x{status:02X}")
        info = {'raw': data}
        if len(data) >= 2:
            info['board_id'] = struct.unpack('<H', data[0:2])[0]
        if len(data) >= 6:
            info['software_ver'] = f"{data[2]}.{data[3]}"
            info['hardware_ver'] = f"{data[4]}.{data[5]}"
        return info

    def set_vdd(self, voltage_mv: int) -> int:
        status, _ = self.transact(TYPE_SET, CMD_SET_VDD, struct.pack('<H', voltage_mv))
        return status

    def set_vddio(self, voltage_mv: int) -> int:
        status, _ = self.transact(TYPE_SET, CMD_SET_VDDIO, struct.pack('<H', voltage_mv))
        return status

    # ── Stats ────────────────────────────────────────────────────────────

    def get_reader_stats(self) -> dict:
        """Return reader thread statistics."""
        if not self._reader:
            return {'is_running': False}
        return self._reader.get_stats()