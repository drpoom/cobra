"""
COBRA Sync — Synchronous Protocol Bridge (Python)

Implements the COINES V3 binary protocol over any Transport backend.
See ../core/PROTOCOL.md for the language-agnostic specification.

The CobraBridge class is now transport-agnostic: it accepts any
Transport instance (SerialTransport, BleTransport, or custom) and
uses only transport.send() and transport.receive() for I/O.
Packet building, parsing, checksums, and the I2C/SPI/board API
remain identical regardless of connection type.

Usage:
    from cobra_bridge.transport import SerialTransport, BleTransport
    from cobra_bridge.sync import CobraBridge

    # USB-Serial
    transport = SerialTransport(port='/dev/ttyACM0')
    bridge = CobraBridge(transport=transport)

    # BLE
    transport = BleTransport(address='AA:BB:CC:DD:EE:FF')
    bridge = CobraBridge(transport=transport)

    bridge.connect()
    chip_id = bridge.i2c_read(dev_addr=0x14, reg_addr=0x00, length=1)
    print(f"Chip ID: 0x{chip_id[0]:02X}")
    bridge.disconnect()

Legacy (backward-compatible) usage:
    bridge = CobraBridge(port='/dev/ttyUSB0')  # Creates SerialTransport internally
    bridge.connect()
    ...
    bridge.disconnect()
"""

import struct
import time
from typing import Optional

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
from cobra_bridge.transport import Transport, SerialTransport


class CobraBridge:
    """
    COINES V3 protocol bridge — transport-agnostic.

    Takes a Transport backend (Serial, BLE, or custom) and provides
    send_packet / receive_packet / transact primitives plus convenience
    methods for I2C, SPI, and board control.

    The packetizer (build_packet, receive_packet) and all higher-level
    API methods are identical regardless of transport type. Only
    transport.send() and transport.receive() change.
    """

    def __init__(self, transport: Optional[Transport] = None,
                 port: str = '/dev/ttyUSB0', baudrate: int = 115200,
                 timeout: float = 2.0):
        """
        Create a CobraBridge with a transport backend.

        Args:
            transport: Transport instance (SerialTransport, BleTransport, etc.)
                       If None, creates a SerialTransport from port/baudrate/timeout.
            port: Serial port (only used if transport is None).
            baudrate: Baud rate (only used if transport is None).
            timeout: Default timeout in seconds.
        """
        if transport is not None:
            self._transport = transport
        else:
            # Legacy: auto-create SerialTransport
            self._transport = SerialTransport(
                port=port, baudrate=baudrate, timeout=timeout
            )
        self._timeout = timeout

    @property
    def transport(self) -> Transport:
        """Access the underlying transport backend."""
        return self._transport

    # ── Connection ────────────────────────────────────────────────────────

    def connect(self):
        """Open the transport connection."""
        self._transport.connect()

    def disconnect(self):
        """Close the transport connection."""
        self._transport.disconnect()

    @property
    def connected(self) -> bool:
        return self._transport.connected

    # ── Low-Level Protocol (see core/PROTOCOL.md §1) ─────────────────────

    @staticmethod
    def _checksum(data: bytes) -> int:
        """XOR checksum of all bytes in data."""
        xor = 0
        for b in data:
            xor ^= b
        return xor

    def build_packet(self, ptype: int, command: int, payload: bytes = b'') -> bytes:
        """
        Build a COINES V3 packet.

        Implements the packet building algorithm from core/PROTOCOL.md §1:
            frame = [0xAA, type, command, length_lo, length_hi, payload...]
            checksum = XOR_reduce(frame)
            return frame + [checksum]
        """
        length = len(payload)
        frame = struct.pack('<BBBB', HEADER, ptype, command, length & 0xFF)
        frame += struct.pack('B', (length >> 8) & 0xFF)
        frame += payload
        xor = self._checksum(frame)
        return frame + struct.pack('B', xor)

    def send_packet(self, ptype: int, command: int, payload: bytes = b'') -> None:
        """Build and send a COINES V3 packet via transport."""
        if not self.connected:
            raise ConnectionError("Transport not connected")
        pkt = self.build_packet(ptype, command, payload)
        self._transport.send(pkt)

    def receive_packet(self, timeout: Optional[float] = None) -> tuple:
        """
        Read and parse a COINES V3 response packet via transport.

        Returns (ptype, command, status, data) tuple.
        """
        if not self.connected:
            raise ConnectionError("Transport not connected")

        t_out = timeout or self._timeout

        # 1. Wait for header 0xAA
        while True:
            b = self._transport.receive(1, timeout=t_out)
            if b == b'\xAA':
                break
            # Non-header byte — skip and keep looking

        # 2. Read type, command, length_lo, length_hi
        header_rest = self._transport.receive(4, timeout=t_out)
        ptype, command, length_lo, length_hi = struct.unpack('<BBBB', header_rest)
        length = length_lo | (length_hi << 8)

        # 3. Read payload
        payload = b''
        if length > 0:
            payload = self._transport.receive(length, timeout=t_out)

        # 4. Read checksum
        xor_byte = self._transport.receive(1, timeout=t_out)

        # 5. Verify checksum
        frame = struct.pack('<BBBB', HEADER, ptype, command, length_lo)
        frame += struct.pack('B', length_hi) + payload
        expected_xor = self._checksum(frame)
        if expected_xor != xor_byte[0]:
            raise ValueError(
                f"Checksum mismatch: expected 0x{expected_xor:02X}, got 0x{xor_byte[0]:02X}"
            )

        # 6. Extract status (first byte) and data
        status = payload[0] if len(payload) > 0 else STATUS_OK
        resp_data = payload[1:] if len(payload) > 1 else b''

        return (ptype, command, status, resp_data)

    def transact(self, ptype: int, command: int, payload: bytes = b'',
                 timeout: Optional[float] = None) -> tuple:
        """Send a packet and wait for the response. Returns (status, data)."""
        self.send_packet(ptype, command, payload)
        _, _, status, resp_data = self.receive_packet(timeout)
        return status, resp_data

    # ── I2C Operations (see core/PROTOCOL.md §3) ─────────────────────────

    def i2c_write(self, dev_addr: int, reg_addr: int, data: bytes,
                  speed: int = I2C_SPEED_400K) -> int:
        """Write data to an I2C register. Returns status byte."""
        payload = struct.pack('<BBBB', dev_addr, speed, reg_addr, len(data)) + data
        status, _ = self.transact(TYPE_SET, CMD_I2C_WRITE, payload)
        return status

    def i2c_read(self, dev_addr: int, reg_addr: int, length: int,
                 speed: int = I2C_SPEED_400K) -> bytes:
        """Read data from an I2C register. Returns bytes read."""
        payload = struct.pack('<BBBB', dev_addr, speed, reg_addr, length)
        status, resp_data = self.transact(TYPE_GET, CMD_I2C_READ, payload)
        if status != STATUS_OK:
            raise IOError(f"I2C read failed with status 0x{status:02X}")
        return resp_data

    # ── SPI Operations (see core/PROTOCOL.md §4) ─────────────────────────

    def spi_write(self, cs_line: int, reg_addr: int, data: bytes,
                  speed: int = SPI_SPEED_5MHZ, mode: int = SPI_MODE_0) -> int:
        """Write data to an SPI register. Returns status byte."""
        payload = struct.pack('<BBBBB', cs_line, speed, mode, reg_addr, len(data)) + data
        status, _ = self.transact(TYPE_SET, CMD_SPI_WRITE, payload)
        return status

    def spi_read(self, cs_line: int, reg_addr: int, length: int,
                 speed: int = SPI_SPEED_5MHZ, mode: int = SPI_MODE_0) -> bytes:
        """Read data from an SPI register. Returns bytes read."""
        payload = struct.pack('<BBBBB', cs_line, speed, mode, reg_addr, length)
        status, resp_data = self.transact(TYPE_GET, CMD_SPI_READ, payload)
        if status != STATUS_OK:
            raise IOError(f"SPI read failed with status 0x{status:02X}")
        return resp_data

    # ── Board Control (see core/PROTOCOL.md §5) ──────────────────────────

    def get_board_info(self) -> dict:
        """Get board identification information."""
        status, data = self.transact(TYPE_GET, CMD_GET_BOARD_INFO)
        if status != STATUS_OK:
            raise IOError(f"Get board info failed with status 0x{status:02X}")
        info = {'raw': data}
        if len(data) >= 2:
            info['board_id'] = struct.unpack('<H', data[0:2])[0]
        if len(data) >= 6:
            info['software_ver'] = f"{data[2]}.{data[3]}"
            info['hardware_ver'] = f"{data[4]}.{data[5]}"
        return info

    def set_vdd(self, voltage_mv: int) -> int:
        """Set VDD voltage in millivolts (0 = off)."""
        status, _ = self.transact(TYPE_SET, CMD_SET_VDD, struct.pack('<H', voltage_mv))
        return status

    def set_vddio(self, voltage_mv: int) -> int:
        """Set VDDIO voltage in millivolts (0 = off)."""
        status, _ = self.transact(TYPE_SET, CMD_SET_VDDIO, struct.pack('<H', voltage_mv))
        return status