"""
COBRA Async — AsyncBridge + TransportReader

Combines the synchronous CobraBridge (for sends) with the background
CobraReader thread (for receives) to enable non-blocking, high-rate
sensor polling up to 400 Hz.

Now transport-agnostic: works with SerialTransport or BleTransport.
The reader thread reads from transport.receive() instead of directly
from pyserial.

Key improvements over Sync tier:
  - send_packet() is non-blocking (writes to transport, reader thread handles response)
  - transact() uses reader queue for responses (no blocking transport reads)
  - BMM350 read_sensor() is non-blocking with stale-data eviction

Usage:
    from cobra_bridge.transport import SerialTransport, BleTransport
    from cobra_bridge.async_ import AsyncBridge
    from cobra_bridge.drivers.bmm350_async import BMM350Async

    # USB-Serial
    transport = SerialTransport(port='/dev/ttyACM0')
    bridge = AsyncBridge(transport=transport)

    # BLE
    transport = BleTransport(address='AA:BB:CC:DD:EE:FF')
    bridge = AsyncBridge(transport=transport)

    bridge.connect()
    sensor = BMM350Async(bridge)
    sensor.start_continuous(odr='400_HZ')

    while True:
        data = sensor.read_sensor()
        if data:
            process(data)

    sensor.stop_continuous()
    bridge.disconnect()

Legacy (backward-compatible) usage:
    bridge = AsyncBridge(port='/dev/ttyACM0')  # Creates SerialTransport internally
"""

import struct
import time
import threading
from typing import Optional

from cobra_bridge.sync import CobraBridge
from cobra_bridge.reader import CobraReader
from cobra_bridge.transport import Transport, SerialTransport
from cobra_bridge.constants import (
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
    Async Bridge: CobraBridge (send) + CobraReader (receive).

    The reader thread continuously drains the transport and places
    decoded packets into a thread-safe queue. Main thread sends
    requests and picks up responses from the queue.

    Thread safety:
      - Transport writes are protected by a lock shared with the reader
      - Queue operations are inherently thread-safe
    """

    def __init__(self, transport: Optional[Transport] = None,
                 port: str = '/dev/ttyUSB0', baudrate: int = 115200,
                 timeout: float = 2.0, max_queue_size: int = 64):
        """
        Create an AsyncBridge with a transport backend.

        Args:
            transport: Transport instance (Serial, BLE, or custom).
                       If None, creates SerialTransport from port/baudrate/timeout.
            port: Serial port (legacy, only used if transport is None).
            baudrate: Baud rate (legacy, only used if transport is None).
            timeout: Default timeout in seconds.
            max_queue_size: Max reader queue entries before eviction.
        """
        if transport is not None:
            self._transport = transport
        else:
            self._transport = SerialTransport(
                port=port, baudrate=baudrate, timeout=timeout
            )
        self._timeout = timeout
        self._max_queue = max_queue_size
        self._bridge = CobraBridge(transport=self._transport)
        self._reader: Optional[CobraReader] = None

    @property
    def transport(self) -> Transport:
        """Access the underlying transport backend."""
        return self._transport

    # ── Connection ────────────────────────────────────────────────────────

    def connect(self):
        """Open transport and start background reader thread."""
        self._transport.connect()
        # For serial transport, pass the underlying serial port to reader
        # For BLE transport, use transport-based reader
        if isinstance(self._transport, SerialTransport):
            self._reader = CobraReader(
                self._transport.serial_port,
                max_queue_size=self._max_queue,
            )
        else:
            # Generic transport reader — reads from transport.receive()
            self._reader = TransportReader(
                self._transport,
                max_queue_size=self._max_queue,
            )
        self._reader.start()
        time.sleep(0.05)

    def disconnect(self):
        """Stop reader thread and close transport."""
        if self._reader:
            self._reader.stop(timeout=2.0)
            self._reader = None
        self._transport.disconnect()

    @property
    def connected(self) -> bool:
        return self._transport.connected and self._reader is not None and self._reader.is_running

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
        """Get next decoded packet from reader queue."""
        if not self._reader:
            raise ConnectionError("Reader not running")
        return self._reader.receive(timeout=timeout or self._timeout)

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

    # ── Transaction (send + queue-receive) ────────────────────────────────

    def transact(self, ptype: int, command: int, payload: bytes = b'',
                 timeout: Optional[float] = None) -> tuple:
        """Send packet and wait for response from reader queue."""
        self.send_packet(ptype, command, payload)
        _, _, status, resp_data = self.receive_packet(timeout=timeout)
        return status, resp_data

    # ── I2C Operations (same API as sync) ──────────────────────────────────

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


class TransportReader(threading.Thread):
    """
    Background thread that reads COINES V3 packets from a generic Transport.

    This is the transport-agnostic equivalent of CobraReader — instead of
    reading directly from a pyserial Serial object, it reads from
    transport.receive() which works with any backend (BLE, etc.).

    Continuously reads from the transport, verifies checksums,
    and places decoded (ptype, command, status, data) tuples into
    a thread-safe queue.
    """

    def __init__(self, transport: Transport, max_queue_size: int = 64,
                 poll_interval: float = 0.001):
        """
        Args:
            transport: Connected Transport instance.
            max_queue_size: Max queue entries before eviction (default 64).
            poll_interval: Seconds between transport reads when idle (default 1ms).
        """
        super().__init__(daemon=True, name='TransportReader')
        self._transport = transport
        self._max_queue = max_queue_size
        self._poll_interval = poll_interval
        self._queue = __import__('queue').Queue(maxsize=max_queue_size + 16)
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # Stats
        self.packets_received = 0
        self.checksum_errors = 0
        self.overflows_dropped = 0

    def run(self):
        """Main reader loop — runs in background thread."""
        buf = bytearray()

        while not self._stop_event.is_set():
            try:
                # Read available bytes from transport
                try:
                    chunk = self._transport.receive(1, timeout=self._poll_interval)
                    buf.extend(chunk)

                    # Drain any additional available bytes
                    while True:
                        try:
                            extra = self._transport.receive(256, timeout=0)
                            buf.extend(extra)
                        except (TimeoutError, TimeoutError):
                            break
                        except Exception:
                            break
                except TimeoutError:
                    pass
                except Exception:
                    if not self._stop_event.is_set():
                        time.sleep(0.01)
                    continue

                # Try to parse complete packets from buffer
                while len(buf) >= 6:  # Minimum: header(1) + type(1) + cmd(1) + len(2) + xor(1)
                    try:
                        idx = buf.index(HEADER)
                    except ValueError:
                        buf.clear()
                        break

                    if idx > 0:
                        del buf[:idx]

                    if len(buf) < 6:
                        break

                    ptype = buf[1]
                    command = buf[2]
                    length = buf[3] | (buf[4] << 8)
                    total_len = 5 + length + 1

                    if len(buf) < total_len:
                        break

                    frame = bytes(buf[:5 + length])
                    received_xor = buf[5 + length]
                    expected_xor = self._xor_checksum(frame)

                    if expected_xor != received_xor:
                        self.checksum_errors += 1
                        del buf[0]
                        continue

                    payload = bytes(buf[5:5 + length])
                    status = payload[0] if len(payload) > 0 else STATUS_OK
                    data = payload[1:] if len(payload) > 1 else b''

                    try:
                        self._queue.put_nowait((ptype, command, status, data))
                    except __import__('queue').Full:
                        try:
                            self._queue.get_nowait()
                            self.overflows_dropped += 1
                        except __import__('queue').Empty:
                            pass
                        self._queue.put_nowait((ptype, command, status, data))

                    self.packets_received += 1
                    del buf[:total_len]

            except Exception:
                if not self._stop_event.is_set():
                    time.sleep(0.001)

    def stop(self, timeout: float = 2.0):
        self._stop_event.set()
        self.join(timeout=timeout)

    @property
    def is_running(self) -> bool:
        return self.is_alive()

    # ── Queue Access (same interface as CobraReader) ─────────────────────

    def receive(self, timeout: float = 2.0):
        from queue import Empty
        try:
            return self._queue.get(timeout=timeout)
        except Empty:
            raise TimeoutError(f"No response within {timeout}s")

    def poll(self, timeout: float = 0.0):
        from queue import Empty
        try:
            return self._queue.get(timeout=timeout) if timeout > 0 else self._queue.get_nowait()
        except Empty:
            return None

    def drain(self) -> list:
        packets = []
        from queue import Empty
        while True:
            try:
                packets.append(self._queue.get_nowait())
            except Empty:
                break
        return packets

    def queue_size(self) -> int:
        return self._queue.qsize()

    def clear(self):
        self.drain()

    # ── Write Lock (same interface as CobraReader) ───────────────────────

    def acquire_write(self):
        self._lock.acquire()

    def release_write(self):
        self._lock.release()

    # ── Checksum ─────────────────────────────────────────────────────────

    @staticmethod
    def _xor_checksum(data: bytes) -> int:
        xor = 0
        for b in data:
            xor ^= b
        return xor

    # ── Stats ────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        return {
            'packets_received': self.packets_received,
            'checksum_errors': self.checksum_errors,
            'overflows_dropped': self.overflows_dropped,
            'queue_size': self.queue_size(),
            'is_running': self.is_running,
            'transport_type': self._transport.transport_type,
        }