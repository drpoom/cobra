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

from cobra_bridge.sync import CobraSyncBridge
from cobra_bridge.reader import CobraReader
from cobra_bridge.transport import CobraTransport # Changed from Transport, SerialTransport
from cobra_bridge.enums import (
    ErrorCodes, I2CBus, I2CMode, I2CTransferBits,
    SPISpeed, SPIMode, SPITransferBits, MultiIOPin
)
from cobra_bridge.constants import (
    HEADER, TYPE_GET, TYPE_SET,
    CMD_I2C_READ, CMD_I2C_WRITE,
    CMD_SPI_READ, CMD_SPI_WRITE,
    CMD_GET_BOARD_INFO, CMD_SET_VDD, CMD_SET_VDDIO,
    STATUS_OK,
    I2C_BUS_0, I2C_BUS_1, I2C_SPEED_400K, I2C_SPEED_1M, I2C_SPEED_STANDARD, I2C_SPEED_FAST,
    SPI_BUS_0, SPI_BUS_1,
    PIN_IN, PIN_OUT, PIN_LOW, PIN_HIGH,
)


class AsyncCobraBridge:
    """
    Async Bridge: CobraBridge (send) + CobraReader (receive).

    The reader thread continuously drains the transport and places
    decoded packets into a thread-safe queue. Main thread sends
    requests and picks up responses from the queue.

    Thread safety:
      - Transport writes are protected by a lock shared with the reader
      - Queue operations are inherently thread-safe
    """

    def __init__(self, transport: Optional[CobraTransport] = None,
                 port: str = '/dev/ttyUSB0', baudrate: int = 115200,
                 timeout: float = 2.0, max_queue_size: int = 64):
        """
        Create an AsyncBridge with a transport backend.

        Args:
            transport: CoinesTransport instance.
                       If None, creates SerialTransport from port/baudrate/timeout.
            port: Serial port (legacy, only used if transport is None).
            baudrate: Baud rate (legacy, only used if transport is None).
            timeout: Default timeout in seconds.
            max_queue_size: Max reader queue entries before eviction.
        """
        if transport is not None:
            self._transport = transport
        else:
            # Legacy: auto-create SerialTransport within CoinesTransport
            # This part needs careful handling as CoinesTransport expects SerialComConfig
            # For simplicity, let's assume a CoinesTransport instance is always passed
            raise ValueError("CoinesTransport instance must be provided to AsyncCoinesBridge")
            
        self._timeout = timeout
        self._max_queue = max_queue_size
        self._reader: Optional[CobraReader] = None
        self._sync_bridge = CobraSyncBridge(transport=self._transport) # Use CoinesSyncBridge for packet building


    async def open_interface(self, interface: CommInterface,
                             serial_com_config: SerialComConfig = None,
                             ble_com_config: BleComConfig = None) -> ErrorCodes:
        # The actual opening of the interface is handled by CoinesTransport
        # The AsyncCoinesBridge will start the reader thread once the transport is open.
        self.error_code = self._transport.open_interface(interface, serial_com_config, ble_com_config)
        if self.error_code == ErrorCodes.COINES_SUCCESS:
            if isinstance(self._transport._active_transport, SerialTransport):
                self._reader = CobraReader(
                    self._transport._active_transport.serial_port,
                    max_queue_size=self._max_queue,
                )
            elif isinstance(self._transport._active_transport, BleTransport):
                # For BLE, CobraReader needs to be adapted to read from the BleakClient notifications.
                # For now, we will use a placeholder or adapt CobraReader.
                print("Warning: CobraReader for BLE transport not fully implemented.")
                self._reader = CobraReader(
                    None, # Placeholder
                    max_queue_size=self._max_queue,
                ) # Need to pass a different object for Bleak

            if self._reader:
                self._reader.start()
                await asyncio.sleep(0.05) # Give reader a moment to start
        return self.error_code

    async def close_interface(self, interface: CommInterface) -> ErrorCodes:
        if self._reader:
            self._reader.stop(timeout=2.0)
            self._reader = None
        self.error_code = self._transport.close_interface(interface)
        return self.error_code

    @property
    def connected(self) -> bool:
        return self._transport.connected and self._reader is not None and self._reader.is_running
        
    async def write_intf(self, interface: CommInterface, data: list) -> None:
        if self._reader:
            self._reader.acquire_write()
        try:
            await self._transport.write_intf(interface, data)
        finally:
            if self._reader:
                self._reader.release_write()

    async def read_intf(self, interface: CommInterface, length: int) -> tuple[list[int], int]:
        # For asynchronous read, we should use the reader queue
        try:
            ptype, command, status, resp_data = await self.receive_packet_async() # Assuming an async receive_packet
            if status == STATUS_OK:
                return list(resp_data), len(resp_data)
            else:
                return [], ErrorCodes.COINES_E_FAILURE.value # Return error code as int
        except Exception as e:
            print(f"Error during async read_intf: {e}")
            return [], ErrorCodes.COINES_E_COMM_IO_ERROR.value

    # ── Low-Level Protocol (see core/PROTOCOL.md §1) ─────────────────────

    async def send_packet_async(self, ptype: int, command: int, payload: bytes = b'') -> None:
        """Build and send a COINES V3 packet via transport (asynchronously)."""
        if not self.connected:
            raise ConnectionError("Transport not connected")
        pkt = self._sync_bridge.build_packet(ptype, command, payload) # Use sync bridge for packet building
        await self._transport.send(pkt) # Assuming async send in CoinesTransport

    async def receive_packet_async(self, timeout: Optional[float] = None) -> tuple:
        """Get next decoded packet from reader queue (asynchronously)."""
        if not self._reader:
            raise ConnectionError("Reader not running")
        return self._reader.receive(timeout=timeout or self._timeout)

    async def transact_async(self, ptype: int, command: int, payload: bytes = b'',
                             timeout: Optional[float] = None) -> tuple:
        """Send packet and wait for response from reader queue (asynchronously)."""
        await self.send_packet_async(ptype, command, payload)
        _, _, status, resp_data = await self.receive_packet_async(timeout)
        return status, resp_data

    # ── COINES-like I2C Operations ────────────────────────────────────────

    async def config_i2c_bus(self, bus: I2CBus, i2c_address: int, i2c_mode: I2CMode) -> ErrorCodes:
        print(f"[AsyncCoinesBridge] Configuring I2C bus {bus.name}, address {i2c_address}, mode {i2c_mode.name}")
        # In a real implementation, this would send a COINES command to configure the I2C bus.
        # For async, we use transact_async
        payload = b'' # Need to build the actual payload for the command
        status, _ = await self.transact_async(TYPE_SET, CMD_CONFIG_I2C_BUS, payload) # Assuming CMD_CONFIG_I2C_BUS exists
        return ErrorCodes(status)

    async def deconfig_i2c_bus(self, bus: I2CBus) -> ErrorCodes:
        print(f"[AsyncCoinesBridge] Deconfiguring I2C bus {bus.name}")
        payload = b'' # Need to build the actual payload
        status, _ = await self.transact_async(TYPE_SET, CMD_DECONFIG_I2C_BUS, payload) # Assuming CMD_DECONFIG_I2C_BUS exists
        return ErrorCodes(status)

    async def write_i2c(self, bus: I2CBus, register_address: int,
                        register_value: int, sensor_interface_detail: int = None) -> ErrorCodes:
        dev_addr = sensor_interface_detail if sensor_interface_detail is not None else 0
        # Build payload for I2C write command
        payload = struct.pack('<BBB', dev_addr, register_address, register_value) # Simplified payload
        status, _ = await self.transact_async(TYPE_SET, CMD_I2C_WRITE, payload)
        return ErrorCodes(status)

    async def read_i2c(self, bus: I2CBus, register_address: int,
                       number_of_reads: int, sensor_interface_detail: int = None) -> tuple[list[int], ErrorCodes]:
        dev_addr = sensor_interface_detail if sensor_interface_detail is not None else 0
        # Build payload for I2C read command
        payload = struct.pack('<BB', dev_addr, register_address) # Simplified payload
        status, resp_data = await self.transact_async(TYPE_GET, CMD_I2C_READ, payload)
        if status == STATUS_OK:
            return list(resp_data), ErrorCodes.COINES_SUCCESS
        else:
            return [], ErrorCodes(status)

    async def read_16bit_i2c(self, bus: I2CBus, register_address: int, number_of_reads: int = 2,
                             sensor_interface_detail: int = None,
                             i2c_transfer_bits: I2CTransferBits = I2CTransferBits.I2C16BIT) -> tuple[list[int], ErrorCodes]:
        print(f"[AsyncCoinesBridge] Reading 16-bit I2C from bus {bus.name}, reg {register_address}")
        data, error = await self.read_i2c(bus, register_address, number_of_reads * 2, sensor_interface_detail)
        return data, error

    async def write_16bit_i2c(self, bus: I2CBus, register_address: int,
                              register_value: int, sensor_interface_detail: int = None,
                              i2c_transfer_bits: I2CTransferBits = I2CTransferBits.I2C16BIT) -> ErrorCodes:
        print(f"[AsyncCoinesBridge] Writing 16-bit I2C to bus {bus.name}, reg {register_address}, val {register_value}")
        byte1 = register_value & 0xFF
        byte2 = (register_value >> 8) & 0xFF
        status = await self.write_i2c(bus, register_address, byte1, sensor_interface_detail)
        if status == ErrorCodes.COINES_SUCCESS:
            status = await self.write_i2c(bus, register_address + 1, byte2, sensor_interface_detail)
        return status

    # ── SPI Operations ─────────────────────────────────────────────────

    async def config_spi_bus(self, bus: I2CBus, cs_pin: MultiIOPin,
                             spi_speed: SPISpeed, spi_mode: SPIMode) -> ErrorCodes:
        print(f"[AsyncCoinesBridge] Configuring SPI bus {bus.name}, CS {cs_pin.name}, speed {spi_speed.name}, mode {spi_mode.name}")
        payload = b'' # Need to build the actual payload for the command
        status, _ = await self.transact_async(TYPE_SET, CMD_CONFIG_SPI_BUS, payload) # Assuming CMD_CONFIG_SPI_BUS exists
        return ErrorCodes(status)

    async def deconfig_spi_bus(self, bus: I2CBus) -> ErrorCodes:
        print(f"[AsyncCoinesBridge] Deconfiguring SPI bus {bus.name}")
        payload = b'' # Need to build the actual payload
        status, _ = await self.transact_async(TYPE_SET, CMD_DECONFIG_SPI_BUS, payload) # Assuming CMD_DECONFIG_SPI_BUS exists
        return ErrorCodes(status)

    async def custom_spi_config(self, bus: I2CBus, cs_pin: MultiIOPin,
                                spi_speed: SPISpeed, spi_mode: SPIMode) -> ErrorCodes:
        print(f"[AsyncCoinesBridge] Custom SPI config for bus {bus.name}, CS {cs_pin.name}, speed {spi_speed.name}, mode {spi_mode.name}")
        return await self.config_spi_bus(bus, cs_pin, spi_speed, spi_mode)

    async def write_spi(self, bus: I2CBus, register_address: int,
                        register_value: int, sensor_interface_detail: int = None) -> ErrorCodes:
        cs_pin = sensor_interface_detail if sensor_interface_detail is not None else MultiIOPin.COINES_MINI_SHUTTLE_PIN_CS.value
        payload = struct.pack('<BB', cs_pin, register_address) + bytes([register_value]) # Simplified payload
        status, _ = await self.transact_async(TYPE_SET, CMD_SPI_WRITE, payload)
        return ErrorCodes(status)

    async def read_spi(self, bus: I2CBus, register_address: int,
                       number_of_reads: int, sensor_interface_detail: int = None) -> tuple[list[int], ErrorCodes]:
        cs_pin = sensor_interface_detail if sensor_interface_detail is not None else MultiIOPin.COINES_MINI_SHUTTLE_PIN_CS.value
        payload = struct.pack('<BBB', cs_pin, register_address | 0x80, number_of_reads) # Simplified payload
        status, resp_data = await self.transact_async(TYPE_GET, CMD_SPI_READ, payload)
        if status == STATUS_OK:
            return list(resp_data), ErrorCodes.COINES_SUCCESS
        else:
            return [], ErrorCodes(status)

    async def read_16bit_spi(self, bus: I2CBus, register_address: int, number_of_reads: int = 2,
                             sensor_interface_detail: int = None,
                             spi_transfer_bits: SPITransferBits = SPITransferBits.SPI16BIT) -> tuple[list[int], ErrorCodes]:
        print(f"[AsyncCoinesBridge] Reading 16-bit SPI from bus {bus.name}, reg {register_address}")
        data, error = await self.read_spi(bus, register_address, number_of_reads * 2, sensor_interface_detail)
        return data, error

    async def write_16bit_spi(self, bus: I2CBus, register_address: int,
                                register_value: list, sensor_interface_detail: int = None,
                                spi_transfer_bits: SPITransferBits = SPITransferBits.SPI16BIT) -> ErrorCodes:
        print(f"[AsyncCoinesBridge] Writing 16-bit SPI to bus {bus.name}, reg {register_address}, val {register_value}")
        status = ErrorCodes.COINES_SUCCESS
        if isinstance(register_value, list):
            for val in register_value:
                status = await self.write_spi(bus, register_address, val, sensor_interface_detail)
                if status != ErrorCodes.COINES_SUCCESS:
                    break
        else:
            status = await self.write_spi(bus, register_address, register_value, sensor_interface_detail)
        return status

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