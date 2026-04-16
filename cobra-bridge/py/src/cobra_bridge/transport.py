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

from abc import ABC, abstractmethod
from typing import Optional


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
        """Whether the transport connection is active."""
        ...

    @property
    def transport_type(self) -> str:
        """Human-readable transport type name."""
        return self.__class__.__name__


class SerialTransport(Transport):
    """
    USB-Serial transport using pyserial.

    Wraps an existing pyserial.Serial port or creates one from
    port/baudrate parameters. This is the default (legacy) transport.

    Usage:
        transport = SerialTransport(port='/dev/ttyACM0')
        transport.connect()
        # ... use with CobraBridge ...
        transport.disconnect()
    """

    def __init__(self, port: str = '/dev/ttyUSB0', baudrate: int = 115200,
                 timeout: float = 2.0, serial_instance=None):
        """
        Args:
            port: Serial port path (e.g., '/dev/ttyACM0', 'COM3').
            baudrate: Baud rate (default 115200 for AppBoard 3.1).
            timeout: Default read timeout in seconds.
            serial_instance: Pre-connected pyserial.Serial object.
                             If provided, port/baudrate are ignored.
        """
        self._port = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._ser = serial_instance
        self._owns_serial = serial_instance is None  # Only close if we created it

    def connect(self) -> None:
        """Open the serial port."""
        import serial
        if self._ser is not None and self._ser.is_open:
            return  # Already connected
        self._ser = serial.Serial(
            port=self._port,
            baudrate=self._baudrate,
            timeout=self._timeout,
            bytesize=8, parity='N', stopbits=1,
        )
        import time
        time.sleep(0.1)
        self._ser.reset_input_buffer()
        self._ser.reset_output_buffer()

    def disconnect(self) -> None:
        """Close the serial port."""
        if self._ser and self._ser.is_open and self._owns_serial:
            self._ser.close()
        if self._owns_serial:
            self._ser = None

    def send(self, data: bytes) -> None:
        """Send raw bytes over serial."""
        if not self.connected:
            raise ConnectionError("Serial transport not connected")
        self._ser.write(data)
        self._ser.flush()

    def receive(self, count: int, timeout: Optional[float] = None) -> bytes:
        """Read exactly `count` bytes from serial."""
        if not self.connected:
            raise ConnectionError("Serial transport not connected")
        old_timeout = self._ser.timeout
        if timeout is not None:
            self._ser.timeout = timeout
        try:
            data = self._ser.read(count)
            if len(data) < count:
                raise TimeoutError(
                    f"Serial read timeout: wanted {count}, got {len(data)}"
                )
            return data
        finally:
            if timeout is not None:
                self._ser.timeout = old_timeout

    @property
    def connected(self) -> bool:
        return self._ser is not None and self._ser.is_open

    @property
    def serial_port(self):
        """Access to underlying pyserial.Serial object (for CobraReader compatibility)."""
        return self._ser


class BleTransport(Transport):
    """
    BLE transport using Bleak (Nordic UART Service).

    The Bosch AppBoard 3.1 exposes the COINES protocol over BLE
    using the Nordic UART Service (NUS). COINES V3 packets travel
    as raw bytes — same framing, same checksums.

    BLE NUS characteristics:
      - Service:    6e400001-b5a3-f393-e0a9-e50e24dcca9e
      - RX (write): 6e400002-b5a3-f393-e0a9-e50e24dcca9e
      - TX (notify):6e400003-b5a3-f393-e0a9-e50e24dcca9e

    Usage:
        transport = BleTransport(address='AA:BB:CC:DD:EE:FF')
        transport.connect()
        # ... use with CobraBridge ...
        transport.disconnect()

    Or scan first:
        devices = await BleTransport.scan()
        transport = BleTransport(address=device.address)
    """

    NUS_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
    NUS_RX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
    NUS_TX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

    # BLE GATT MTU limit for writes (safe default; can be negotiated higher)
    GATT_WRITE_LEN = 20

    def __init__(self, address: str, timeout: float = 5.0):
        """
        Args:
            address: BLE device MAC address (e.g., 'AA:BB:CC:DD:EE:FF').
            timeout: Default timeout for read operations in seconds.
        """
        self._address = address
        self._timeout = timeout
        self._client = None
        self._rx_buffer = bytearray()
        self._notify_event = None

    @staticmethod
    async def scan(timeout: float = 5.0):
        """
        Scan for nearby BLE devices advertising NUS service.

        Args:
            timeout: Scan duration in seconds.

        Returns:
            List of BleakScanner discoveries with NUS service.
        """
        from bleak import BleakScanner

        devices = await BleakScanner.discover(timeout=timeout)
        nus_devices = []
        for d in devices:
            # Check if device advertises NUS service
            if hasattr(d, 'metadata') and 'uuids' in d.metadata:
                if BleTransport.NUS_SERVICE_UUID.lower() in \
                   [u.lower() for u in d.metadata['uuids']]:
                    nus_devices.append(d)
        return nus_devices

    def connect(self) -> None:
        """
        Connect to BLE device and subscribe to NUS TX notifications.

        Note: This is a synchronous wrapper around the async Bleak connect.
        For async usage, use connect_async() instead.
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an async context — use run_coroutine_threadsafe
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = asyncio.run_coroutine_threadsafe(
                        self.connect_async(), loop
                    )
                    future.result(timeout=self._timeout + 5)
            else:
                loop.run_until_complete(self.connect_async())
        except RuntimeError:
            # No event loop — create one
            asyncio.run(self.connect_async())

    async def connect_async(self) -> None:
        """Async version of connect(). Use in async contexts."""
        from bleak import BleakClient

        self._client = BleakClient(
            self._address,
            timeout=self._timeout,
        )
        await self._client.connect()

        # Subscribe to NUS TX notifications
        self._notify_event = asyncio.Event()
        await self._client.start_notify(
            self.NUS_TX_CHAR_UUID,
            self._notification_handler
        )

        self._rx_buffer = bytearray()

    def disconnect(self) -> None:
        """Disconnect from BLE device."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = asyncio.run_coroutine_threadsafe(
                        self.disconnect_async(), loop
                    )
                    future.result(timeout=self._timeout + 5)
            else:
                loop.run_until_complete(self.disconnect_async())
        except RuntimeError:
            asyncio.run(self.disconnect_async())

    async def disconnect_async(self) -> None:
        """Async version of disconnect()."""
        if self._client and self._client.is_connected:
            try:
                await self._client.stop_notify(self.NUS_TX_CHAR_UUID)
            except Exception:
                pass
            await self._client.disconnect()
        self._client = None
        self._rx_buffer = bytearray()

    def _notification_handler(self, sender, data: bytearray):
        """
        BLE notification callback — called when NUS TX characteristic
        receives data. Appends to internal buffer.
        """
        self._rx_buffer.extend(data)
        if self._notify_event:
            self._notify_event.set()

    def send(self, data: bytes) -> None:
        """
        Send raw bytes over BLE NUS RX characteristic.

        Automatically chunks data into GATT write-sized pieces (20 bytes)
        since BLE has limited MTU.
        """
        if not self.connected:
            raise ConnectionError("BLE transport not connected")
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = asyncio.run_coroutine_threadsafe(
                        self.send_async(data), loop
                    )
                    future.result(timeout=self._timeout + 5)
            else:
                loop.run_until_complete(self.send_async(data))
        except RuntimeError:
            asyncio.run(self.send_async(data))

    async def send_async(self, data: bytes) -> None:
        """Async version of send(). Chunks data for BLE GATT write limit."""
        if not self._client or not self._client.is_connected:
            raise ConnectionError("BLE transport not connected")

        # Chunk writes to fit BLE GATT MTU (default 20 bytes for write without response)
        for i in range(0, len(data), self.GATT_WRITE_LEN):
            chunk = bytes(data[i:i + self.GATT_WRITE_LEN])
            await self._client.write_gatt_char(
                self.NUS_RX_CHAR_UUID,
                chunk,
                response=False  # Write without response for speed
            )

    def receive(self, count: int, timeout: Optional[float] = None) -> bytes:
        """
        Read exactly `count` bytes from BLE NUS TX buffer.

        Blocks until enough data has been received via notifications
        or timeout expires.

        Args:
            count: Number of bytes to read.
            timeout: Seconds to wait (None = default).

        Returns:
            bytes: Exactly `count` bytes.
        """
        if not self.connected:
            raise ConnectionError("BLE transport not connected")

        import asyncio
        t_out = timeout if timeout is not None else self._timeout

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Synchronous wait with event loop integration
                import time
                deadline = time.time() + t_out
                while len(self._rx_buffer) < count:
                    remaining = deadline - time.time()
                    if remaining <= 0:
                        raise TimeoutError(
                            f"BLE read timeout: wanted {count}, got {len(self._rx_buffer)}"
                        )
                    time.sleep(0.005)  # 5ms poll interval
            else:
                loop.run_until_complete(self._receive_async(count, t_out))
        except RuntimeError:
            asyncio.run(self._receive_async(count, t_out))

        result = bytes(self._rx_buffer[:count])
        self._rx_buffer = self._rx_buffer[count:]
        return result

    async def _receive_async(self, count: int, timeout: float) -> None:
        """Async: wait until buffer has `count` bytes or timeout."""
        import asyncio
        deadline = asyncio.get_event_loop().time() + timeout
        while len(self._rx_buffer) < count:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise TimeoutError(
                    f"BLE read timeout: wanted {count}, got {len(self._rx_buffer)}"
                )
            if self._notify_event:
                self._notify_event.clear()
                try:
                    await asyncio.wait_for(self._notify_event.wait(), timeout=remaining)
                except asyncio.TimeoutError:
                    pass
            else:
                await asyncio.sleep(0.005)

    @property
    def connected(self) -> bool:
        return self._client is not None and self._client.is_connected

    @property
    def address(self) -> str:
        return self._address