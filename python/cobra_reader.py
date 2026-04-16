"""
COBRA V2: CobraReader — Background Serial Reader Thread

Continuously monitors the serial port for incoming COINES V3 packets,
verifies checksums, and places decoded payloads into a thread-safe queue.

This enables non-blocking sensor polling at up to 400 Hz without
blocking the main execution loop.

Architecture:
    Main thread ──send_packet()──► Serial Port ──receive──► CobraReader thread
          ▲                                                           │
          │                                                       queue.put()
          └───────────────────queue.get()─────────────────────────────┘

Usage:
    from cobra_reader import CobraReader

    reader = CobraReader(serial_port)
    reader.start()

    # Send a request
    bridge.send_packet(TYPE_GET, CMD_I2C_READ, payload)

    # Non-blocking: check if response arrived
    result = reader.poll(timeout=0.05)

    # Blocking: wait for response
    result = reader.receive(timeout=2.0)

    reader.stop()
"""

import struct
import threading
import time
from queue import Queue, Full, Empty
from typing import Optional, Tuple

from cobra_constants import HEADER, STATUS_OK


class CobraReader(threading.Thread):
    """
    Background thread that reads COINES V3 packets from serial port.

    Continuously monitors the serial buffer, verifies checksums,
    and places decoded (ptype, command, status, data) tuples into
    a thread-safe queue. Supports stale-data eviction: if the queue
    exceeds max_queue_size, oldest entries are discarded.
    """

    def __init__(self, ser, max_queue_size: int = 64, read_timeout: float = 0.01):
        """
        Args:
            ser: Open pyserial Serial instance (must be already connected).
            max_queue_size: Max queue entries before eviction (default 64).
                            At 400Hz, 64 entries = 160ms buffer.
            read_timeout: Serial read timeout in seconds (short = responsive).
        """
        super().__init__(daemon=True, name='CobraReader')
        self._ser = ser
        self._max_queue = max_queue_size
        self._read_timeout = read_timeout
        self._queue: Queue = Queue(maxsize=max_queue_size + 16)  # overflow margin
        self._stop_event = threading.Event()
        self._lock = threading.Lock()  # protects serial writes from main thread

        # Stats
        self.packets_received = 0
        self.checksum_errors = 0
        self.overflows_dropped = 0

    # ── Thread Lifecycle ──────────────────────────────────────────────────

    def run(self):
        """Main reader loop — runs in background thread."""
        self._ser.timeout = self._read_timeout
        buf = bytearray()

        while not self._stop_event.is_set():
            try:
                # Read available bytes
                chunk = self._ser.read(256)
                if chunk:
                    buf.extend(chunk)

                # Try to parse complete packets from buffer
                while len(buf) >= 6:  # Minimum: header(1) + type(1) + cmd(1) + len(2) + xor(1)
                    # Find header
                    try:
                        idx = buf.index(HEADER)
                    except ValueError:
                        buf.clear()
                        break

                    if idx > 0:
                        del buf[:idx]  # Discard garbage before header

                    if len(buf) < 6:
                        break  # Not enough for minimum packet

                    # Parse header
                    ptype = buf[1]
                    command = buf[2]
                    length = buf[3] | (buf[4] << 8)
                    total_len = 5 + length + 1  # header(5) + payload + checksum(1)

                    if len(buf) < total_len:
                        break  # Incomplete packet, wait for more data

                    # Extract and verify
                    frame = bytes(buf[:5 + length])
                    received_xor = buf[5 + length]
                    expected_xor = self._xor_checksum(frame)

                    if expected_xor != received_xor:
                        self.checksum_errors += 1
                        # Discard header byte and resync
                        del buf[0]
                        continue

                    # Decode payload
                    payload = bytes(buf[5:5 + length])
                    status = payload[0] if len(payload) > 0 else STATUS_OK
                    data = payload[1:] if len(payload) > 1 else b''

                    # Enqueue with stale-data eviction
                    try:
                        self._queue.put_nowait((ptype, command, status, data))
                    except Full:
                        # Evict oldest entry to make room
                        try:
                            self._queue.get_nowait()
                            self.overflows_dropped += 1
                        except Empty:
                            pass
                        self._queue.put_nowait((ptype, command, status, data))

                    self.packets_received += 1
                    del buf[:total_len]

            except OSError as e:
                if not self._stop_event.is_set():
                    # Serial port error — might be disconnect
                    time.sleep(0.01)
            except Exception:
                if not self._stop_event.is_set():
                    time.sleep(0.001)

    def stop(self, timeout: float = 2.0):
        """Signal the reader thread to stop and wait for it."""
        self._stop_event.set()
        self.join(timeout=timeout)

    @property
    def is_running(self) -> bool:
        return self.is_alive()

    # ── Queue Access ─────────────────────────────────────────────────────

    def receive(self, timeout: float = 2.0) -> Tuple[int, int, int, bytes]:
        """
        Blocking read: wait for next decoded packet from queue.

        Returns:
            (ptype, command, status, data) tuple
        Raises:
            TimeoutError if no packet arrives within timeout.
        """
        try:
            return self._queue.get(timeout=timeout)
        except Empty:
            raise TimeoutError(f"No response within {timeout}s")

    def poll(self, timeout: float = 0.0) -> Optional[Tuple[int, int, int, bytes]]:
        """
        Non-blocking read: return next packet or None.

        Args:
            timeout: Seconds to wait (0 = instant check).
        """
        try:
            return self._queue.get(timeout=timeout) if timeout > 0 else self._queue.get_nowait()
        except Empty:
            return None

    def drain(self) -> list:
        """Remove and return all queued packets. Useful for discarding stale data."""
        packets = []
        while True:
            try:
                packets.append(self._queue.get_nowait())
            except Empty:
                break
        return packets

    def queue_size(self) -> int:
        """Current number of packets in queue."""
        return self._queue.qsize()

    def clear(self):
        """Drop all queued packets (stale data eviction)."""
        self.drain()

    # ── Serial Write Lock ────────────────────────────────────────────────

    def acquire_write(self):
        """Acquire the serial write lock (for main thread sends)."""
        self._lock.acquire()

    def release_write(self):
        """Release the serial write lock."""
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
        """Return reader statistics."""
        return {
            'packets_received': self.packets_received,
            'checksum_errors': self.checksum_errors,
            'overflows_dropped': self.overflows_dropped,
            'queue_size': self.queue_size(),
            'is_running': self.is_running,
        }