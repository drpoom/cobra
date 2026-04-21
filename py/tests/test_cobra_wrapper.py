"""
(c) Bosch Sensortec GmbH, Reutlingen, Germany
Open Source as per the BSD-3 Clause
"""

import pytest
import asyncio
from cobra_bridge.cobra_wrapper import CobraBoard, AsyncCobraBoard
from cobra_bridge.enums import CommInterface, ErrorCodes, I2CBus, I2CMode, SPISpeed, SPIMode, MultiIOPin


@pytest.fixture
def sync_board():
    board = CobraBoard()
    yield board
    board.close_comm_interface(CommInterface.VIRTUAL)


@pytest.fixture
def async_board():
    board = AsyncCobraBoard()
    yield board
    # Note: async teardown requires pytest-asyncio; skip for now


class TestCobraBoard:
    def test_init(self, sync_board):
        assert sync_board.error_code == ErrorCodes.COINES_SUCCESS

    def test_open_close_comm_interface_virtual(self, sync_board):
        result = sync_board.open_comm_interface(CommInterface.VIRTUAL)
        assert result == ErrorCodes.COINES_SUCCESS
        result = sync_board.close_comm_interface(CommInterface.VIRTUAL)
        assert result == ErrorCodes.COINES_SUCCESS

    def test_get_version(self, sync_board):
        version = sync_board.get_version()
        assert isinstance(version, str)
        assert "CobraBoard" in version

    def test_write_read_intf_virtual(self, sync_board):
        sync_board.open_comm_interface(CommInterface.VIRTUAL)
        data_to_write = [0x01, 0x02, 0x03]
        sync_board.write_intf(CommInterface.VIRTUAL, data_to_write)
        # In virtual mode, read_intf will return dummy data
        read_data, num_bytes = sync_board.read_intf(CommInterface.VIRTUAL, 3)
        assert num_bytes == 3
        assert len(read_data) == 3
        sync_board.close_comm_interface(CommInterface.VIRTUAL)

    def test_i2c_config_deconfig(self, sync_board):
        sync_board.open_comm_interface(CommInterface.VIRTUAL)
        result = sync_board.config_i2c_bus(I2CBus.COINES_I2C_BUS_0, 0x14, I2CMode.FAST_MODE)
        assert result == ErrorCodes.COINES_SUCCESS
        result = sync_board.deconfig_i2c_bus(I2CBus.COINES_I2C_BUS_0)
        assert result == ErrorCodes.COINES_SUCCESS
        sync_board.close_comm_interface(CommInterface.VIRTUAL)

    def test_spi_config_deconfig(self, sync_board):
        sync_board.open_comm_interface(CommInterface.VIRTUAL)
        result = sync_board.config_spi_bus(I2CBus.COINES_I2C_BUS_0, MultiIOPin.COINES_MINI_SHUTTLE_PIN_CS, SPISpeed.SPI_1_MHZ, SPIMode.MODE0)
        assert result == ErrorCodes.COINES_SUCCESS
        result = sync_board.deconfig_spi_bus(I2CBus.COINES_I2C_BUS_0)
        assert result == ErrorCodes.COINES_SUCCESS
        sync_board.close_comm_interface(CommInterface.VIRTUAL)


class TestAsyncCobraBoard:
    def test_init(self, async_board):
        assert async_board.error_code == ErrorCodes.COINES_SUCCESS
