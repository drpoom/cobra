"""
COBRA: COines BRidge Access — Core Protocol Layer

Implements the COINES V3 binary protocol over USB-Serial.
Handles packet framing, checksums, and I2C/SPI read/write commands.

Usage:
    from cobra_core import CobraBridge

    bridge = CobraBridge(port='/dev/ttyUSB0')
    bridge.connect()

    # I2C Write
    bridge.i2c_write(dev_addr=0x14, reg_addr=0x01, data=b'\\x00')

    # I2C Read
    chip_id = bridge.i2c_read(dev_addr=0x14, reg_addr=0x00, length=1)
    print(f"Chip ID: 0x{chip_id[0]:02X}")

    bridge.disconnect()
"""

import struct
import time
from typing import Optional

# ── COINES V3 Protocol Constants ─────────────────────────────────────────────

HEADER = 0xAA

# Packet Type
TYPE_GET = 0x01
TYPE_SET = 0x02

# Command IDs — I2C
CMD_I2C_READ  = 0x0E
CMD_I2C_WRITE = 0x0D

# Command IDs — SPI
CMD_SPI_READ  = 0x14
CMD_SPI_WRITE = 0x13

# Command IDs — System
CMD_GET_BOARD_INFO = 0x01
CMD_SET_VDD         = 0x04
CMD_SET_VDDIO       = 0x06
CMD_SET_PIN         = 0x05
CMD_INT_CONFIG      = 0x07

# Response Status
STATUS_OK = 0x00

# I2C Speed Modes
I2C_SPEED_400K = 0  # 400 kHz (default)
I2C_SPEED_1M   = 1  # 1 MHz

# SPI Speed Modes
SPI_SPEED_5MHZ  = 0
SPI_SPEED_10MHZ = 1

# SPI Modes
SPI_MODE_0 = 0
SPI_MODE_3 = 3


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

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self):
        """Open the serial port."""
        import serial
        self._ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
            bytesize=8,
            parity='N',
            stopbits=1,
        )
        # Allow board to settle after port open
        time.sleep(0.1)
        # Flush any stale data
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

    # ── Low-Level Protocol ───────────────────────────────────────────────────

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

        Structure:
            [0xAA] [Type] [Command] [LenLo] [LenHi] [Payload...] [XOR]

        Args:
            ptype:   TYPE_GET (0x01) or TYPE_SET (0x02)
            command: Command ID (e.g., CMD_I2C_READ)
            payload: Raw payload bytes

        Returns:
            Complete packet as bytes including header, length, payload, and checksum.
        """
        length = len(payload)
        header_bytes = struct.pack('<BBBB', HEADER, ptype, command, length & 0xFF)
        # Length high byte
        length_hi = struct.pack('B', (length >> 8) & 0xFF)
        frame = header_bytes + length_hi + payload
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

        Returns:
            (ptype, command, status, payload) tuple.
            - ptype:   Response type byte
            - command: Command ID echoed back
            - status:  Status byte (0x00 = OK)
            - payload: Response payload bytes

        Raises:
            TimeoutError if no header found within timeout.
            ValueError if checksum fails.
        """
        if not self.connected:
            raise ConnectionError("Serial port not connected")

        t_out = timeout or self.timeout
        deadline = time.time() + t_out

        # 1. Wait for header byte 0xAA
        while time.time() < deadline:
            b = self._ser.read(1)
            if b == b'\xAA':
                break
        else:
            raise TimeoutError("No response header received")

        # 2. Read type, command, length_lo, length_hi (4 bytes)
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
        frame = struct.pack('<BBBB', HEADER, ptype, command, length_lo) + struct.pack('B', length_hi) + payload
        expected_xor = self._checksum(frame)
        received_xor = xor_byte[0]
        if expected_xor != received_xor:
            raise ValueError(
                f"Checksum mismatch: expected 0x{expected_xor:02X}, got 0x{received_xor:02X}"
            )

        # 6. Extract status from payload (first byte is status for responses)
        status = payload[0] if len(payload) > 0 else STATUS_OK
        resp_payload = payload[1:] if len(payload) > 1 else b''

        return (ptype, command, status, resp_payload)

    def transact(self, ptype: int, command: int, payload: bytes = b'', timeout: Optional[float] = None) -> tuple:
        """
        Send a packet and wait for the response.

        Returns:
            (status, payload) — status 0x00 means success.
        """
        self.send_packet(ptype, command, payload)
        _, _, status, resp_payload = self.receive_packet(timeout)
        return status, resp_payload

    # ── I2C Operations ────────────────────────────────────────────────────────

    def i2c_write(self, dev_addr: int, reg_addr: int, data: bytes,
                  speed: int = I2C_SPEED_400K) -> int:
        """
        Write data to an I2C register.

        Payload format (COINES V3 I2C Write):
            [DevAddr] [Speed] [RegAddr] [DataLen] [Data...]

        Args:
            dev_addr: 7-bit I2C device address (e.g., 0x14 for BMM350)
            reg_addr: Register address to write to
            data:     Bytes to write
            speed:    I2C_SPEED_400K or I2C_SPEED_1M

        Returns:
            Status byte (0x00 = success)
        """
        payload = struct.pack('<BBBB', dev_addr, speed, reg_addr, len(data)) + data
        status, _ = self.transact(TYPE_SET, CMD_I2C_WRITE, payload)
        return status

    def i2c_read(self, dev_addr: int, reg_addr: int, length: int,
                 speed: int = I2C_SPEED_400K) -> bytes:
        """
        Read data from an I2C register.

        Payload format (COINES V3 I2C Read request):
            [DevAddr] [Speed] [RegAddr] [Length]

        Args:
            dev_addr: 7-bit I2C device address (e.g., 0x14 for BMM350)
            reg_addr: Register address to read from
            length:   Number of bytes to read
            speed:    I2C_SPEED_400K or I2C_SPEED_1M

        Returns:
            Bytes read from the register
        """
        payload = struct.pack('<BBBB', dev_addr, speed, reg_addr, length)
        status, resp_data = self.transact(TYPE_GET, CMD_I2C_READ, payload)
        if status != STATUS_OK:
            raise IOError(f"I2C read failed with status 0x{status:02X}")
        return resp_data

    # ── SPI Operations ────────────────────────────────────────────────────────

    def spi_write(self, cs_line: int, reg_addr: int, data: bytes,
                  speed: int = SPI_SPEED_5MHZ, mode: int = SPI_MODE_0) -> int:
        """
        Write data to an SPI register.

        Payload format (COINES V3 SPI Write):
            [CS] [Speed] [Mode] [RegAddr] [DataLen] [Data...]

        Args:
            cs_line:  Chip-select line index
            reg_addr: Register address to write to
            data:     Bytes to write
            speed:    SPI_SPEED_5MHZ or SPI_SPEED_10MHZ
            mode:     SPI_MODE_0 or SPI_MODE_3

        Returns:
            Status byte (0x00 = success)
        """
        payload = struct.pack('<BBBBB', cs_line, speed, mode, reg_addr, len(data)) + data
        status, _ = self.transact(TYPE_SET, CMD_SPI_WRITE, payload)
        return status

    def spi_read(self, cs_line: int, reg_addr: int, length: int,
                 speed: int = SPI_SPEED_5MHZ, mode: int = SPI_MODE_0) -> bytes:
        """
        Read data from an SPI register.

        Payload format (COINES V3 SPI Read request):
            [CS] [Speed] [Mode] [RegAddr] [Length]

        Args:
            cs_line:  Chip-select line index
            reg_addr: Register address to read from
            length:   Number of bytes to read
            speed:    SPI_SPEED_5MHZ or SPI_SPEED_10MHZ
            mode:     SPI_MODE_0 or SPI_MODE_3

        Returns:
            Bytes read from the register
        """
        payload = struct.pack('<BBBBB', cs_line, speed, mode, reg_addr, length)
        status, resp_data = self.transact(TYPE_GET, CMD_SPI_READ, payload)
        if status != STATUS_OK:
            raise IOError(f"SPI read failed with status 0x{status:02X}")
        return resp_data

    # ── Board Info ────────────────────────────────────────────────────────────

    def get_board_info(self) -> dict:
        """
        Get board identification information.

        Returns:
            Dict with keys: board, software_ver, hardware_ver
        """
        status, data = self.transact(TYPE_GET, CMD_GET_BOARD_INFO)
        if status != STATUS_OK:
            raise IOError(f"Get board info failed with status 0x{status:02X}")

        # Parse board info response
        # Format: Board name (variable), SW version, HW version
        info = {}
        if len(data) >= 4:
            # Board info starts with a variable-length name
            # Try to extract what we can
            try:
                info['raw'] = data
                # First 2 bytes are often board ID
                info['board_id'] = struct.unpack('<H', data[0:2])[0]
                if len(data) >= 6:
                    info['software_ver'] = f"{data[2]}.{data[3]}"
                    info['hardware_ver'] = f"{data[4]}.{data[5]}"
            except Exception:
                info['raw'] = data
        return info

    def set_vdd(self, voltage_mv: int) -> int:
        """Set VDD voltage in millivolts (0 = off, e.g., 1800 = 1.8V, 3300 = 3.3V)."""
        payload = struct.pack('<H', voltage_mv)
        status, _ = self.transact(TYPE_SET, CMD_SET_VDD, payload)
        return status

    def set_vddio(self, voltage_mv: int) -> int:
        """Set VDDIO voltage in millivolts (0 = off, e.g., 1800 = 1.8V, 3300 = 3.3V)."""
        payload = struct.pack('<H', voltage_mv)
        status, _ = self.transact(TYPE_SET, CMD_SET_VDDIO, payload)
        return status