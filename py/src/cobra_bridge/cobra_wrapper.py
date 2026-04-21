"""
(c) Bosch Sensortec GmbH, Reutlingen, Germany
Open Source as per the BSD-3 Clause
"""

from .enums import CommInterface, ErrorCodes, PinDirection, PinValue, \
    I2CBus, I2CMode, SPIMode, SPISpeed, MultiIOPin, I2CTransferBits, SPITransferBits, \
    StreamingMode, StreamingState, StreamingBlocks, TimerConfig, TimerStampConfig, \
    SerialComConfig, BleComConfig
from .sync import CobraSyncBridge
from .async_ import AsyncCobraBridge
from .transport import CobraTransport, Transport, Transport
from .constants import (
    PIN_IN, PIN_OUT, PIN_LOW, PIN_HIGH,
    I2C_SPEED_400K,
)
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .drivers.base import SensorDriver


class CobraBoard:
    """
    API to utilize the functions of COINES_SDK header file through .dll/.so
    """

    def __init__(self, path_to_coines_lib=None):
        self._transport = CobraTransport()
        self._bridge = CobraSyncBridge(transport=self._transport._active_transport if self._transport._active_transport else None)
        self.error_code = ErrorCodes.COINES_SUCCESS
        self._sensor_drivers: dict[str, 'SensorDriver'] = {}


    def open_comm_interface(self, interface=CommInterface.USB,
                            serial_com_config: SerialComConfig = None,
                            ble_com_config: BleComConfig = None) -> ErrorCodes:
        # Map to the underlying transport layer
        self.error_code = self._transport.open_interface(interface, serial_com_config, ble_com_config)
        return self.error_code

    def close_comm_interface(self, interface=CommInterface.USB) -> ErrorCodes:
        self.error_code = self._transport.close_interface(interface)
        return self.error_code

    def get_version(self) -> str:
        """ Returns the version of the COINES_SDK library """
        return "CobraBoard v0.1.0"

    def unload_library(self) -> None:
        """
        Unloads the library
        """
        print("CobraBoard library unloaded.")

    def write_intf(self, interface: CommInterface, data: list) -> None:
        """ Write data to the communication interface """
        self._transport.write_intf(interface, data)

    def read_intf(self, interface: CommInterface, length: int) -> tuple[list[int], int]:
        """ Read data from the communication interface """
        return self._transport.read_intf(interface, length)

    def config_i2c_bus(self, bus: I2CBus, i2c_address: int, i2c_mode: I2CMode) -> ErrorCodes:
        self.error_code = self._bridge.config_i2c_bus(bus, i2c_address, i2c_mode)
        return self.error_code

    def deconfig_i2c_bus(self, bus: I2CBus) -> ErrorCodes:
        self.error_code = self._bridge.deconfig_i2c_bus(bus)
        return self.error_code

    def write_i2c(self, bus: I2CBus, register_address: int,
                  register_value: int, sensor_interface_detail: int | None = None) -> ErrorCodes:
        self.error_code = self._bridge.write_i2c(bus, register_address, register_value, sensor_interface_detail)
        return self.error_code

    def read_i2c(self, bus: I2CBus, register_address: int,
                 number_of_reads: int, sensor_interface_detail: int | None = None) -> tuple[list[int], ErrorCodes]:
        data, self.error_code = self._bridge.read_i2c(bus, register_address, number_of_reads, sensor_interface_detail)
        return data, self.error_code

    def read_16bit_i2c(self, bus: I2CBus, register_address: int, number_of_reads: int = 2,
                       sensor_interface_detail: int | None = None,
                       i2c_transfer_bits: I2CTransferBits = I2CTransferBits.I2C16BIT) -> tuple[list[int], ErrorCodes]:
        data, self.error_code = self._bridge.read_16bit_i2c(bus, register_address, number_of_reads,
                                                            sensor_interface_detail, i2c_transfer_bits)
        return data, self.error_code

    def write_16bit_i2c(self, bus: I2CBus, register_address: int,
                        register_value: int, sensor_interface_detail: int | None = None,
                        i2c_transfer_bits: I2CTransferBits = I2CTransferBits.I2C16BIT) -> ErrorCodes:
        self.error_code = self._bridge.write_16bit_i2c(bus, register_address, register_value,
                                                        sensor_interface_detail, i2c_transfer_bits)
        return self.error_code

    def config_spi_bus(self, bus: I2CBus, cs_pin: MultiIOPin,
                       spi_speed: SPISpeed, spi_mode: SPIMode) -> ErrorCodes:
        self.error_code = self._bridge.config_spi_bus(bus, cs_pin, spi_speed, spi_mode)
        return self.error_code

    def deconfig_spi_bus(self, bus: I2CBus) -> ErrorCodes:
        self.error_code = self._bridge.deconfig_spi_bus(bus)
        return self.error_code

    def custom_spi_config(self, bus: I2CBus, cs_pin: MultiIOPin,
                          spi_speed: SPISpeed, spi_mode: SPIMode) -> ErrorCodes:
        self.error_code = self._bridge.custom_spi_config(bus, cs_pin, spi_speed, spi_mode)
        return self.error_code

    def write_spi(self, bus: I2CBus, register_address: int,
                  register_value: int, sensor_interface_detail: int | None = None) -> ErrorCodes:
        self.error_code = self._bridge.write_spi(bus, register_address, register_value, sensor_interface_detail)
        return self.error_code

    def read_spi(self, bus: I2CBus, register_address: int,
                 number_of_reads: int, sensor_interface_detail: int | None = None) -> tuple[list[int], ErrorCodes]:
        data, self.error_code = self._bridge.read_spi(bus, register_address, number_of_reads, sensor_interface_detail)
        return data, self.error_code

    def read_16bit_spi(self, bus: I2CBus, register_address: int, number_of_reads: int = 2,
                       sensor_interface_detail: int | None = None,
                       spi_transfer_bits: SPITransferBits = SPITransferBits.SPI16BIT) -> tuple[list[int], ErrorCodes]:
        data, self.error_code = self._bridge.read_16bit_spi(bus, register_address, number_of_reads,
                                                            sensor_interface_detail, spi_transfer_bits)
        return data, self.error_code

    def write_16bit_spi(self, bus: I2CBus, register_address: int,
                        register_value: list, sensor_interface_detail: int | None = None,
                        spi_transfer_bits: SPITransferBits = SPITransferBits.SPI16BIT) -> ErrorCodes:
        self.error_code = self._bridge.write_16bit_spi(bus, register_address, register_value,
                                                        sensor_interface_detail, spi_transfer_bits)
        return self.error_code

    # ── Board Control (convenience methods for sensor drivers) ───────────

    def set_vdd(self, voltage_mv: int) -> int:
        """Set VDD voltage in millivolts (0 = off). Returns status code."""
        return self._bridge.set_vdd(voltage_mv)

    def set_vddio(self, voltage_mv: int) -> int:
        """Set VDDIO voltage in millivolts (0 = off). Returns status code."""
        return self._bridge.set_vddio(voltage_mv)

    def set_pin(self, pin: int, direction: int, value: int) -> int:
        """Configure a shuttle board pin. Returns status code."""
        return self._bridge.set_pin(pin, direction, value)

    # ── Sensor-Driver Convenience I/O ────────────────────────────────────

    def i2c_read_reg(self, dev_addr: int, reg_addr: int, length: int,
                      speed: int = I2C_SPEED_400K) -> list[int]:
        """
        Read `length` bytes from I2C register. Returns list of ints.

        Thin wrapper over CobraSyncBridge.i2c_read() for sensor drivers.
        """
        return self._bridge.i2c_read(dev_addr, reg_addr, length, speed)

    def i2c_write_reg(self, dev_addr: int, reg_addr: int, data: bytes,
                      speed: int = I2C_SPEED_400K) -> int:
        """
        Write data bytes to I2C register. Returns status byte.

        Thin wrapper over CobraSyncBridge.i2c_write() for sensor drivers.
        """
        return self._bridge.i2c_write(dev_addr, reg_addr, data, speed)

    def spi_read_reg(self, cs_pin: int, reg_addr: int, length: int,
                     speed: int = 1000000, mode: int = 0) -> list[int]:
        """
        Read `length` bytes from SPI register. Returns list of ints.

        Thin wrapper over CobraSyncBridge.spi_read() for sensor drivers.
        """
        return self._bridge.spi_read(cs_pin, reg_addr, length, speed, mode)

    def spi_write_reg(self, cs_pin: int, reg_addr: int, data: bytes,
                      speed: int = 1000000, mode: int = 0) -> int:
        """
        Write data bytes to SPI register. Returns status byte.

        Thin wrapper over CobraSyncBridge.spi_write() for sensor drivers.
        """
        return self._bridge.spi_write(cs_pin, reg_addr, data, speed, mode)

    # ── Sensor Driver Registry ──────────────────────────────────────────

    def attach_driver(self, driver: 'SensorDriver') -> None:
        """
        Register a sensor driver instance with this board.

        Args:
            driver: SensorDriver instance (e.g., BMM350Driver).
        """
        self._sensor_drivers[driver.name] = driver

    def get_driver(self, name: str) -> Optional['SensorDriver']:
        """
        Retrieve a previously attached sensor driver by name.

        Args:
            name: Sensor name (e.g., 'bmm350').

        Returns:
            SensorDriver instance, or None if not found.
        """
        return self._sensor_drivers.get(name)

    @property
    def drivers(self) -> dict[str, 'SensorDriver']:
        """All attached sensor drivers, keyed by name."""
        return dict(self._sensor_drivers)


class AsyncCobraBoard:
    """
    Asynchronous API to utilize the functions of COINES_SDK header file through .dll/.so
    """

    def __init__(self, path_to_coines_lib=None):
        self._transport = CobraTransport()
        self._async_bridge = AsyncCobraBridge(transport=self._transport)
        self.error_code = ErrorCodes.COINES_SUCCESS
        self._sensor_drivers: dict[str, 'SensorDriver'] = {}

    async def open_comm_interface(self, interface=CommInterface.USB,
                                  serial_com_config=None,
                                  ble_com_config=None) -> ErrorCodes:
        self.error_code = await self._async_bridge.open_interface(interface, serial_com_config, ble_com_config)
        return self.error_code

    async def close_comm_interface(self, interface=CommInterface.USB) -> ErrorCodes:
        self.error_code = await self._async_bridge.close_interface(interface)
        return self.error_code

    async def write_intf(self, interface: CommInterface, data: list) -> None:
        await self._async_bridge.write_intf(interface, data)

    async def read_intf(self, interface: CommInterface, length: int) -> tuple[list[int], int]:
        data, n_bytes_read = await self._async_bridge.read_intf(interface, length)
        return data, n_bytes_read

    async def config_i2c_bus(self, bus: I2CBus, i2c_address: int, i2c_mode: I2CMode) -> ErrorCodes:
        self.error_code = await self._async_bridge.config_i2c_bus(bus, i2c_address, i2c_mode)
        return self.error_code

    async def deconfig_i2c_bus(self, bus: I2CBus) -> ErrorCodes:
        self.error_code = await self._async_bridge.deconfig_i2c_bus(bus)
        return self.error_code

    async def write_i2c(self, bus: I2CBus, register_address: int,
                        register_value: int, sensor_interface_detail: int | None = None) -> ErrorCodes:
        self.error_code = await self._async_bridge.write_i2c(bus, register_address, register_value, sensor_interface_detail)
        return self.error_code

    async def read_i2c(self, bus: I2CBus, register_address: int,
                       number_of_reads: int, sensor_interface_detail: int | None = None) -> tuple[list[int], ErrorCodes]:
        data, self.error_code = await self._async_bridge.read_i2c(bus, register_address, number_of_reads, sensor_interface_detail)
        return data, self.error_code

    async def read_16bit_i2c(self, bus: I2CBus, register_address: int, number_of_reads: int = 2,
                             sensor_interface_detail: int | None = None,
                             i2c_transfer_bits: I2CTransferBits = I2CTransferBits.I2C16BIT) -> tuple[list[int], ErrorCodes]:
        data, self.error_code = await self._async_bridge.read_16bit_i2c(bus, register_address, number_of_reads,
                                                                        sensor_interface_detail, i2c_transfer_bits)
        return data, self.error_code

    async def write_16bit_i2c(self, bus: I2CBus, register_address: int,
                              register_value: int, sensor_interface_detail: int | None = None,
                              i2c_transfer_bits: I2CTransferBits = I2CTransferBits.I2C16BIT) -> ErrorCodes:
        self.error_code = await self._async_bridge.write_16bit_i2c(bus, register_address, register_value,
                                                                    sensor_interface_detail, i2c_transfer_bits)
        return self.error_code

    async def config_spi_bus(self, bus: I2CBus, cs_pin: MultiIOPin,
                             spi_speed: SPISpeed, spi_mode: SPIMode) -> ErrorCodes:
        self.error_code = await self._async_bridge.config_spi_bus(bus, cs_pin, spi_speed, spi_mode)
        return self.error_code

    async def deconfig_spi_bus(self, bus: I2CBus) -> ErrorCodes:
        self.error_code = await self._async_bridge.deconfig_spi_bus(bus)
        return self.error_code

    async def custom_spi_config(self, bus: I2CBus, cs_pin: MultiIOPin,
                                spi_speed: SPISpeed, spi_mode: SPIMode) -> ErrorCodes:
        self.error_code = await self._async_bridge.custom_spi_config(bus, cs_pin, spi_speed, spi_mode)
        return self.error_code

    async def write_spi(self, bus: I2CBus, register_address: int,
                        register_value: int, sensor_interface_detail: int | None = None) -> ErrorCodes:
        self.error_code = await self._async_bridge.write_spi(bus, register_address, register_value, sensor_interface_detail)
        return self.error_code

    async def read_spi(self, bus: I2CBus, register_address: int,
                       number_of_reads: int, sensor_interface_detail: int | None = None) -> tuple[list[int], ErrorCodes]:
        data, self.error_code = await self._async_bridge.read_spi(bus, register_address, number_of_reads, sensor_interface_detail)
        return data, self.error_code

    async def read_16bit_spi(self, bus: I2CBus, register_address: int, number_of_reads: int = 2,
                             sensor_interface_detail: int | None = None,
                             spi_transfer_bits: SPITransferBits = SPITransferBits.SPI16BIT) -> tuple[list[int], ErrorCodes]:
        data, self.error_code = await self._async_bridge.read_16bit_spi(bus, register_address, number_of_reads,
                                                                        sensor_interface_detail, spi_transfer_bits)
        return data, self.error_code

    async def write_16bit_spi(self, bus: I2CBus, register_address: int,
                                register_value: list, sensor_interface_detail: int | None = None,
                                spi_transfer_bits: SPITransferBits = SPITransferBits.SPI16BIT) -> ErrorCodes:
        self.error_code = await self._async_bridge.write_16bit_spi(bus, register_address, register_value,
                                                                    sensor_interface_detail, spi_transfer_bits)
        return self.error_code

    # ── Board Control (convenience methods for sensor drivers) ───────────

    def set_vdd(self, voltage_mv: int) -> int:
        """Set VDD voltage in millivolts (0 = off). Returns status code."""
        return self._async_bridge.set_vdd(voltage_mv)

    def set_vddio(self, voltage_mv: int) -> int:
        """Set VDDIO voltage in millivolts (0 = off). Returns status code."""
        return self._async_bridge.set_vddio(voltage_mv)

    def set_pin(self, pin: int, direction: int, value: int) -> int:
        """Configure a shuttle board pin. Returns status code."""
        return self._async_bridge.set_pin(pin, direction, value)

    # ── Sensor-Driver Convenience I/O ────────────────────────────────────

    async def i2c_read_reg(self, dev_addr: int, reg_addr: int, length: int,
                           speed: int = I2C_SPEED_400K) -> list[int]:
        """Read `length` bytes from I2C register. Returns list of ints."""
        return await self._async_bridge.i2c_read(dev_addr, reg_addr, length, speed)

    async def i2c_write_reg(self, dev_addr: int, reg_addr: int, data: bytes,
                            speed: int = I2C_SPEED_400K) -> int:
        """Write data bytes to I2C register. Returns status byte."""
        return await self._async_bridge.i2c_write(dev_addr, reg_addr, data, speed)

    async def spi_read_reg(self, cs_pin: int, reg_addr: int, length: int,
                           speed: int = 1000000, mode: int = 0) -> list[int]:
        """Read `length` bytes from SPI register. Returns list of ints."""
        return await self._async_bridge.spi_read(cs_pin, reg_addr, length, speed, mode)

    async def spi_write_reg(self, cs_pin: int, reg_addr: int, data: bytes,
                            speed: int = 1000000, mode: int = 0) -> int:
        """Write data bytes to SPI register. Returns status byte."""
        return await self._async_bridge.spi_write(cs_pin, reg_addr, data, speed, mode)

    # ── Sensor Driver Registry ──────────────────────────────────────────

    def attach_driver(self, driver: 'SensorDriver') -> None:
        """Register a sensor driver instance with this board."""
        self._sensor_drivers[driver.name] = driver

    def get_driver(self, name: str) -> Optional['SensorDriver']:
        """Retrieve a previously attached sensor driver by name."""
        return self._sensor_drivers.get(name)

    @property
    def drivers(self) -> dict[str, 'SensorDriver']:
        """All attached sensor drivers, keyed by name."""
        return dict(self._sensor_drivers)
