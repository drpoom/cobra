"""
COBRA: Transport Abstraction Layer (Python)

Provides a unified interface for Serial (USB) and BLE backends.
Only send() and receive() change based on connection type;
packet framing (CobraBridge.build_packet / receive_packet) and
BMM350 driver logic remain identical regardless of transport.

Architecture:
    ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
    │  BMM350     │────▶│  CobraBridge │────▶│  Transport  │
    │  Driver     │     │  (Packetizer)│     │  (I/O)      │
    └─────────────┘     └──────────────┘     └─────────────┘
                                                │
                                    ┌───────────┴───────────┐
                                    │                       │
                              ┌─────┴─────┐          ┌──────┴──────┐
                              │  Serial   │          │    BLE      │
                              │ Transport │          │  Transport  │
                              │ (pyserial)│          │   (Bleak)   │
                              └───────────┘          └─────────────┘

The AppBoard 3.1 uses Nordic UART Service (NUS) over BLE:
  - Service UUID: 6e400001-b5a3-f393-e0a9-e50e24dcca9e
  - RX Characteristic (write): 6e400002-b5a3-f393-e0a9-e50e24dcca9e
  - TX Characteristic (notify): 6e400003-b5a3-f393-e0a9-e50e24dcca9e

COINES V3 packets travel as raw bytes over NUS — same framing,
same checksums, same protocol. Only the transport layer differs.

Usage:
    from cobra_bridge.transport import SerialTransport, BleTransport
    from cobra_bridge.sync import CobraBridge

    # USB-Serial
    transport = SerialTransport(port='/dev/ttyACM0')
    bridge = CobraBridge(transport=transport)
    bridge.connect()

    # BLE
    transport = BleTransport(address='AA:BB:CC:DD:EE:FF')
    bridge = CobraBridge(transport=transport)
    bridge.connect()

See ../core/PROTOCOL.md for the language-agnostic specification.
"""

import time
from abc import ABC, abstractmethod
from typing import Optional
import serial # Uncomment and install pyserial if needed
import asyncio
from bleak import BleakClient # Uncomment and install bleak if needed
from .enums import CommInterface, ErrorCodes, SerialComConfig, BleComConfig


class Transport(ABC):
    """
    Abstract base class for COBRA transport backends.

    All transports must implement:
      - connect(): Establish connection
      - disconnect(): Close connection
      - send(data: bytes): Send raw bytes
      - receive(count: int, timeout: float): Read exactly count bytes
      - connected property: Whether transport is active
    """

    @abstractmethod
    def connect(self) -> None:
        """Establish the connection. Must be called before send/receive."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Close the connection and release resources."""
        ...

    @abstractmethod
    def send(self, data: bytes) -> None:
        """
        Send raw bytes over the transport.

        Args:
            data: Complete COINES V3 packet bytes to send.
        """
        ...

    @abstractmethod
    def receive(self, count: int, timeout: Optional[float] = None) -> bytes:
        """
        Read exactly `count` bytes from the transport.

        Args:
            count: Number of bytes to read.
            timeout: Seconds to wait (None = use default, 0 = non-blocking).

        Returns:
            bytes: Exactly `count` bytes.

        Raises:
            TimeoutError: If bytes not received within timeout.
            ConnectionError: If transport is disconnected.
        """
        ...

    @property
    @abstractmethod
    def connected(self) -> bool:
        """True if the transport is connected, False otherwise."""
        ...


class SerialTransport(Transport):
    """
    Serial port implementation of the Transport interface.
    """
    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 1.0):
        self.port = port
        self.baudrate = baudrate
        self._timeout = timeout
        self._serial = None # type: Optional[serial.Serial]

    @property
    def connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def connect(self) -> None:
        if self.connected:
            return
        try:
            # self._serial = serial.Serial(self.port, self.baudrate, timeout=self._timeout)
            print(f"[SerialTransport] Connecting to {self.port}...")
            # Placeholder for actual serial connection
            self._serial = True # Simulate connection
        except Exception as e:
            raise ConnectionError(f"Failed to connect to serial port {self.port}: {e}") from e

    def disconnect(self) -> None:
        if self.connected:
            print(f"[SerialTransport] Disconnecting from {self.port}...")
            # self._serial.close()
            self._serial = None

    def send(self, data: bytes) -> None:
        if not self.connected:
            raise ConnectionError("Serial port not connected.")
        # self._serial.write(data)
        print(f"[SerialTransport] Sent {len(data)} bytes: {data}")

    def receive(self, count: int, timeout: Optional[float] = None) -> bytes:
        if not self.connected:
            raise ConnectionError("Serial port not connected.")
        # read_timeout = timeout if timeout is not None else self._timeout
        # data = self._serial.read(count)
        # if len(data) != count:
        #     raise TimeoutError(f"Expected {count} bytes, received {len(data)}.")
        # return data
        print(f"[SerialTransport] Receiving {count} bytes (simulated).")
        return b'\x00' * count # Simulate receiving data


class BleTransport(Transport):
    """
    Bluetooth Low Energy (BLE) implementation of the Transport interface using Bleak.
    """
    NUS_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
    NUS_RX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
    NUS_TX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

    def __init__(self, address: str):
        self.address = address
        self._client = None # type: Optional[BleakClient]
        self._rx_buffer = bytearray()
        self._notification_event = asyncio.Event()

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    async def connect(self) -> None:
        if self.connected:
            return
        try:
            # self._client = BleakClient(self.address)
            # await self._client.connect()
            # await self._client.start_notify(self.NUS_TX_CHAR_UUID, self._notification_handler)
            print(f"[BleTransport] Connecting to {self.address}...")
            self._client = True # Simulate connection
        except Exception as e:
            raise ConnectionError(f"Failed to connect to BLE device {self.address}: {e}") from e

    async def disconnect(self) -> None:
        if self.connected:
            print(f"[BleTransport] Disconnecting from {self.address}...")
            # await self._client.stop_notify(self.NUS_TX_CHAR_UUID, self._notification_handler)
            # await self._client.disconnect()
            self._client = None

    async def send(self, data: bytes) -> None:
        if not self.connected:
            raise ConnectionError("BLE device not connected.")
        # await self._client.write_gatt_char(self.NUS_RX_CHAR_UUID, data)
        print(f"[BleTransport] Sent {len(data)} bytes: {data}")

    async def receive(self, count: int, timeout: Optional[float] = None) -> bytes:
        if not self.connected:
            raise ConnectionError("BLE device not connected.")
        # self._rx_buffer.clear() # Clear buffer for new read
        # try:
        #     await asyncio.wait_for(self._notification_event.wait(), timeout)
        # except asyncio.TimeoutError:
        #     raise TimeoutError(f"Timeout waiting for {count} bytes.")
        # finally:
        #     self._notification_event.clear()
        #
        # received_data = bytes(self._rx_buffer[:count])
        # self._rx_buffer = self._rx_buffer[count:]
        # return received_data
        print(f"[BleTransport] Receiving {count} bytes (simulated).")
        return b'\x00' * count # Simulate receiving data

    def _notification_handler(self, sender, data):
        self._rx_buffer.extend(data)
        if len(self._rx_buffer) >= 0: # This condition might need adjustment based on packet structure
            self._notification_event.set()


class VirtualTransport(Transport):
    """
    Virtual (null) transport for testing without hardware.
    Accepts sends (discards), returns zeroes on receive.
    """
    def __init__(self):
        self._connected = False
        self._write_buffer = bytearray()

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def send(self, data: bytes) -> None:
        if not self._connected:
            raise ConnectionError("Virtual transport not connected.")
        self._write_buffer.extend(data)

    def receive(self, count: int, timeout: Optional[float] = None) -> bytes:
        if not self._connected:
            raise ConnectionError("Virtual transport not connected.")
        return bytes(self._write_buffer[:count]) if self._write_buffer else b'\x00' * count


class CobraTransport:
    """
    Manages and abstracts different COINES communication interfaces (USB, BLE).
    """
    def __init__(self):
        self._active_transport: Optional[Transport] = None

    def open_interface(self, interface: CommInterface,
                       serial_com_config: SerialComConfig = None,
                       ble_com_config: BleComConfig = None) -> ErrorCodes:
        if self._active_transport and self._active_transport.connected:
            return ErrorCodes.COINES_E_COMM_ALREADY_OPEN

        if interface == CommInterface.USB:
            if serial_com_config is None or serial_com_config.com_port_name is None:
                return ErrorCodes.COINES_E_INVALID_ARGUMENT
            self._active_transport = SerialTransport(port=serial_com_config.com_port_name,
                                                     baudrate=serial_com_config.baud_rate)
        elif interface == CommInterface.BLE:
            if ble_com_config is None or ble_com_config.address is None:
                return ErrorCodes.COINES_E_INVALID_ARGUMENT
            self._active_transport = BleTransport(address=ble_com_config.address)
        elif interface == CommInterface.VIRTUAL:
            self._active_transport = VirtualTransport()
            self._active_transport.connect()
            return ErrorCodes.COINES_SUCCESS
        else:
            return ErrorCodes.COINES_E_INVALID_ARGUMENT

        if self._active_transport:
            try:
                if interface == CommInterface.BLE:
                    asyncio.run(self._active_transport.connect())
                else:
                    self._active_transport.connect()
                return ErrorCodes.COINES_SUCCESS
            except Exception as e:
                print(f"Error opening transport interface: {e}")
                self._active_transport = None
                return ErrorCodes.COINES_E_COMM_INIT_FAILED
        return ErrorCodes.COINES_E_COMM_INIT_FAILED

    def close_interface(self, interface: CommInterface) -> ErrorCodes:
        if self._active_transport and self._active_transport.connected:
            try:
                if interface == CommInterface.BLE:
                    asyncio.run(self._active_transport.disconnect())
                else:
                    self._active_transport.disconnect()
                self._active_transport = None
                return ErrorCodes.COINES_SUCCESS
            except Exception as e:
                print(f"Error closing transport interface: {e}")
                return ErrorCodes.COINES_E_FAILURE
        elif interface == CommInterface.VIRTUAL:
            if self._active_transport:
                self._active_transport.disconnect()
            self._active_transport = None
            return ErrorCodes.COINES_SUCCESS
        return ErrorCodes.COINES_E_UNABLE_OPEN_DEVICE  # Or a more appropriate error

    def write_intf(self, interface: CommInterface, data: list) -> None:
        if self._active_transport and self._active_transport.connected:
            # Convert list of ints to bytes
            self._active_transport.send(bytes(data))
        else:
            raise ConnectionError("No active transport to write to.")

    def read_intf(self, interface: CommInterface, length: int) -> tuple[list[int], int]:
        if self._active_transport and self._active_transport.connected:
            read_bytes = self._active_transport.receive(count=length)
            return list(read_bytes), len(read_bytes)
        else:
            raise ConnectionError("No active transport to read from.")