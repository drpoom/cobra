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

from cobra_bridge.enums import (
    ErrorCodes, I2CBus, I2CMode, I2CTransferBits,
    SPISpeed, SPIMode, SPITransferBits, MultiIOPin
)
from cobra_bridge.constants import (
    HEADER, TYPE_GET, TYPE_SET,
    CMD_I2C_READ, CMD_I2C_WRITE,
    CMD_SPI_READ, CMD_SPI_WRITE,
    CMD_GET_BOARD_INFO, CMD_SET_VDD, CMD_SET_VDDIO, CMD_SET_PIN,
    CMD_CONFIG_I2C_BUS, CMD_CONFIG_SPI_BUS, CMD_INT_CONFIG,
    STATUS_OK,
    I2C_BUS_0, I2C_BUS_1, I2C_SPEED_400K, I2C_SPEED_1M, I2C_SPEED_STANDARD, I2C_SPEED_FAST,
    SPI_BUS_0, SPI_BUS_1,
    PIN_IN, PIN_OUT, PIN_LOW, PIN_HIGH,
)
from cobra_bridge.transport import Transport, SerialTransport


class CobraSyncBridge:
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

    # ── Board Control ────────────────────────────────────────────────────

    def set_vdd(self, voltage_mv: int) -> int:
        """Set VDD voltage in millivolts (0 = off). Returns status byte."""
        status, _ = self.transact(TYPE_SET, CMD_SET_VDD, struct.pack('<H', voltage_mv))
        return status

    def set_vddio(self, voltage_mv: int) -> int:
        """Set VDDIO voltage in millivolts (0 = off). Returns status byte."""
        status, _ = self.transact(TYPE_SET, CMD_SET_VDDIO, struct.pack('<H', voltage_mv))
        return status

    def set_pin(self, pin: int, direction: int, value: int) -> int:
        """Configure a shuttle board pin. Returns status byte."""
        payload = struct.pack('<BBB', pin, direction, value)
        status, _ = self.transact(TYPE_SET, CMD_SET_PIN, payload)
        return status

    def get_board_info(self) -> dict:
        """Read board information (board ID, software/hardware version)."""
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

    # ── I2C Operations (see core/PROTOCOL.md §3) ─────────────────────────

    def i2c_write(self, dev_addr: int, reg_addr: int, data: bytes,
                  speed: int = I2C_SPEED_400K) -> int:
        """Write data to an I2C register. Returns status byte."""
        payload = struct.pack('<BBBB', dev_addr, speed, reg_addr, len(data)) + data
        status, _ = self.transact(TYPE_SET, CMD_I2C_WRITE, payload)
        return status

    def i2c_read(self, dev_addr: int, reg_addr: int, length: int,
                 speed: int = I2C_SPEED_400K) -> list[int]:
        """Read `length` bytes from `reg_addr` on `dev_addr` via I2C."""
        payload = struct.pack('<BBB', dev_addr, reg_addr, length)
        status, data = self.transact(TYPE_GET, CMD_I2C_READ, payload)
        if status != STATUS_OK:
            raise IOError(f"I2C read failed with status 0x{status:02X}")
        return list(data)

    # ── COINES-like I2C Operations ────────────────────────────────────────

    def config_i2c_bus(self, bus: I2CBus, i2c_address: int, i2c_mode: I2CMode) -> ErrorCodes:
        # The existing CobraBridge i2c_write and i2c_read don't explicitly configure the bus
        # for a specific address or mode in this way. This will be a new command.
        # For now, we will simulate success.
        print(f"[CoinesSyncBridge] Configuring I2C bus {bus.name}, address {i2c_address}, mode {i2c_mode.name}")
        # In a real implementation, this would send a COINES command to configure the I2C bus.
        return ErrorCodes.COINES_SUCCESS

    def deconfig_i2c_bus(self, bus: I2CBus) -> ErrorCodes:
        print(f"[CoinesSyncBridge] Deconfiguring I2C bus {bus.name}")
        # In a real implementation, this would send a COINES command to deconfigure the I2C bus.
        return ErrorCodes.COINES_SUCCESS

    def write_i2c(self, bus: I2CBus, register_address: int,
                  register_value: int, sensor_interface_detail: int = None) -> ErrorCodes:
        # Adapt existing i2c_write to use new parameters
        # Assuming sensor_interface_detail is the device address
        dev_addr = sensor_interface_detail if sensor_interface_detail is not None else 0 # Default if not provided
        data = bytes([register_value])
        status = self.i2c_write(dev_addr, register_address, data)
        return ErrorCodes(status)

    def read_i2c(self, bus: I2CBus, register_address: int,
                 number_of_reads: int, sensor_interface_detail: int = None) -> tuple[list[int], ErrorCodes]:
        # Adapt existing i2c_read to use new parameters
        dev_addr = sensor_interface_detail if sensor_interface_detail is not None else 0 # Default if not provided
        try:
            data = self.i2c_read(dev_addr, register_address, number_of_reads)
            return data, ErrorCodes.COINES_SUCCESS
        except IOError as e:
            print(f"Error in read_i2c: {e}")
            return [], ErrorCodes.COINES_E_I2C_READ_WRITE_FAILED

    def read_16bit_i2c(self, bus: I2CBus, register_address: int, number_of_reads: int = 2,
                       sensor_interface_detail: int = None,
                       i2c_transfer_bits: I2CTransferBits = I2CTransferBits.I2C16BIT) -> tuple[list[int], ErrorCodes]:
        # This would require specific COINES commands for 16-bit I2C reads.
        # For now, simulate by reading 2 bytes for each "16-bit" read.
        print(f"[CoinesSyncBridge] Reading 16-bit I2C from bus {bus.name}, reg {register_address}")
        # Assuming each 16-bit read corresponds to 2 bytes
        data, error = self.read_i2c(bus, register_address, number_of_reads * 2, sensor_interface_detail)
        # If needed, convert 8-bit bytes to 16-bit integers here
        return data, error

    def write_16bit_i2c(self, bus: I2CBus, register_address: int,
                        register_value: int, sensor_interface_detail: int = None,
                        i2c_transfer_bits: I2CTransferBits = I2CTransferBits.I2C16BIT) -> ErrorCodes:
        # This would require specific COINES commands for 16-bit I2C writes.
        print(f"[CoinesSyncBridge] Writing 16-bit I2C to bus {bus.name}, reg {register_address}, val {register_value}")
        # Simulate by writing 2 bytes for a "16-bit" write.
        # Need to split register_value into two 8-bit bytes.
        byte1 = register_value & 0xFF
        byte2 = (register_value >> 8) & 0xFF
        # The existing write_i2c only takes one register_value. This needs to be adapted.
        # For now, calling it twice for simulation. Real implementation needs a different COINES command.
        status = self.write_i2c(bus, register_address, byte1, sensor_interface_detail)
        if status == ErrorCodes.COINES_SUCCESS:
            status = self.write_i2c(bus, register_address + 1, byte2, sensor_interface_detail)
        return status

    # ── SPI Operations (see core/PROTOCOL.md §4) ─────────────────────────

    def spi_write(self, cs_pin: int, reg_addr: int, data: bytes,
                  speed: int = SPISpeed.SPI_10_MHZ.value, mode: int = SPIMode.MODE0.value) -> int:
        """Write data to an SPI register. Returns status byte."""
        payload = struct.pack('<BB', cs_pin, reg_addr) + data
        status, _ = self.transact(TYPE_SET, CMD_SPI_WRITE, payload)
        return status

    def spi_read(self, cs_pin: int, reg_addr: int, length: int,
                 speed: int = SPISpeed.SPI_10_MHZ.value, mode: int = SPIMode.MODE0.value) -> list[int]:
        """Read `length` bytes from `reg_addr` on `cs_pin` via SPI."""
        payload = struct.pack('<BBB', cs_pin, reg_addr | 0x80, length)
        status, data = self.transact(TYPE_GET, CMD_SPI_READ, payload)
        if status != STATUS_OK:
            raise IOError(f"SPI read failed with status 0x{status:02X}")
        return list(data)

    # ── COINES-like SPI Operations ────────────────────────────────────────

    def config_spi_bus(self, bus: I2CBus, cs_pin: MultiIOPin,
                       spi_speed: SPISpeed, spi_mode: SPIMode) -> ErrorCodes:
        # Similar to I2C bus config, this would be a new COINES command.
        print(f"[CoinesSyncBridge] Configuring SPI bus {bus.name}, CS {cs_pin.name}, speed {spi_speed.name}, mode {spi_mode.name}")
        return ErrorCodes.COINES_SUCCESS

    def deconfig_spi_bus(self, bus: I2CBus) -> ErrorCodes:
        print(f"[CoinesSyncBridge] Deconfiguring SPI bus {bus.name}")
        return ErrorCodes.COINES_SUCCESS

    def custom_spi_config(self, bus: I2CBus, cs_pin: MultiIOPin,
                          spi_speed: SPISpeed, spi_mode: SPIMode) -> ErrorCodes:
        # This might involve calculating custom speed values for the COINES firmware.
        print(f"[CoinesSyncBridge] Custom SPI config for bus {bus.name}, CS {cs_pin.name}, speed {spi_speed.name}, mode {spi_mode.name}")
        return self.config_spi_bus(bus, cs_pin, spi_speed, spi_mode) # Delegate to regular config for now

    def write_spi(self, bus: I2CBus, register_address: int,
                  register_value: int, sensor_interface_detail: int = None) -> ErrorCodes:
        # Adapt existing spi_write. Assuming sensor_interface_detail is the CS pin.
        cs_pin = sensor_interface_detail if sensor_interface_detail is not None else MultiIOPin.COINES_MINI_SHUTTLE_PIN_CS.value
        data = bytes([register_value])
        status = self.spi_write(cs_pin, register_address, data)
        return ErrorCodes(status)

    def read_spi(self, bus: I2CBus, register_address: int,
                 number_of_reads: int, sensor_interface_detail: int = None) -> tuple[list[int], ErrorCodes]:
        # Adapt existing spi_read.
        cs_pin = sensor_interface_detail if sensor_interface_detail is not None else MultiIOPin.COINES_MINI_SHUTTLE_PIN_CS.value
        try:
            data = self.spi_read(cs_pin, register_address, number_of_reads)
            return data, ErrorCodes.COINES_SUCCESS
        except IOError as e:
            print(f"Error in read_spi: {e}")
            return [], ErrorCodes.COINES_E_SPI_READ_WRITE_FAILED

    def read_16bit_spi(self, bus: I2CBus, register_address: int, number_of_reads: int = 2,
                       sensor_interface_detail: int = None,
                       spi_transfer_bits: SPITransferBits = SPITransferBits.SPI16BIT) -> tuple[list[int], ErrorCodes]:
        # This would require specific COINES commands for 16-bit SPI reads.
        print(f"[CoinesSyncBridge] Reading 16-bit SPI from bus {bus.name}, reg {register_address}")
        data, error = self.read_spi(bus, register_address, number_of_reads * 2, sensor_interface_detail)
        return data, error

    def write_16bit_spi(self, bus: I2CBus, register_address: int,
                        register_value: list, sensor_interface_detail: int = None,
                        spi_transfer_bits: SPITransferBits = SPITransferBits.SPI16BIT) -> ErrorCodes:
        # This would require specific COINES commands for 16-bit SPI writes.
        print(f"[CoinesSyncBridge] Writing 16-bit SPI to bus {bus.name}, reg {register_address}, val {register_value}")
        # Simulate by writing 2 bytes for a "16-bit" write.
        # The existing write_spi only takes one register_value. This needs to be adapted.
        # For now, if register_value is a list, write each element as a byte.
        status = ErrorCodes.COINES_SUCCESS
        if isinstance(register_value, list):
            for val in register_value:
                status = self.write_spi(bus, register_address, val, sensor_interface_detail)
                if status != ErrorCodes.COINES_SUCCESS:
                    break
        else:
            status = self.write_spi(bus, register_address, register_value, sensor_interface_detail)
        return status