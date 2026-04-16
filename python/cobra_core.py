"""
COBRA: COines BRidge Access — Core Protocol Layer (Python)

Implements the COINES V3 binary protocol over USB-Serial.
See ../core/PROTOCOL.md for the language-agnostic specification.

Usage:
    from cobra_core import CobraBridge

    bridge = CobraBridge(port='/dev/ttyUSB0')
    bridge.connect()
    chip_id = bridge.i2c_read(dev_addr=0x14, reg_addr=0x00, length=1)
    print(f"Chip ID: 0x{chip_id[0]:02X}")
    bridge.disconnect()
"""

import struct
import time
from typing import Optional

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


class CobraBridge:
    """
    Synchronous COINES V3 bridge over USB-Serial.

    Provides send_packet / receive_packet primitives plus
    convenience methods for I2C and SPI register access.
    """

    def __init__(self, port: str = '/dev/ttyUSB0', baudrate: int = 115200, timeout: float = 2.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._ser = None

    # ── Connection ────────────────────────────────────────────────────────

    def connect(self):
        """Open the serial port."""
        import serial
        self._ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
            bytesize=8, parity='N', stopbits=1,
        )
        time.sleep(0.1)
        self._ser.reset_input_buffer()
        self._ser.reset_output_buffer()

    def disconnect(self):
        """Close the serial port."""
        if self._ser and self._ser.is_open:
            self._ser.close()
        self._ser = None

    @property
    def connected(self) -> bool:
        return self._ser is not None and self._ser.is_open

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
        """Build and send a COINES V3 packet."""
        pkt = self.build_packet(ptype, command, payload)
        if not self.connected:
            raise ConnectionError("Serial port not connected")
        self._ser.write(pkt)
        self._ser.flush()

    def receive_packet(self, timeout: Optional[float] = None) -> tuple:
        """
        Read and parse a COINES V3 response packet.

        Implements the packet parsing algorithm from core/PROTOCOL.md §1.
        Returns (ptype, command, status, data) tuple.
        """
        if not self.connected:
            raise ConnectionError("Serial port not connected")

        t_out = timeout or self.timeout
        deadline = time.time() + t_out

        # 1. Wait for header 0xAA
        while time.time() < deadline:
            b = self._ser.read(1)
            if b == b'\xAA':
                break
        else:
            raise TimeoutError("No response header received")

        # 2. Read type, command, length_lo, length_hi
        header_rest = self._ser.read(4)
        if len(header_rest) < 4:
            raise TimeoutError("Incomplete response header")
        ptype, command, length_lo, length_hi = struct.unpack('<BBBB', header_rest)
        length = length_lo | (length_hi << 8)

        # 3. Read payload
        payload = b''
        if length > 0:
            payload = self._ser.read(length)
            if len(payload) < length:
                raise TimeoutError(f"Incomplete payload: expected {length}, got {len(payload)}")

        # 4. Read checksum
        xor_byte = self._ser.read(1)
        if len(xor_byte) < 1:
            raise TimeoutError("Missing checksum byte")

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