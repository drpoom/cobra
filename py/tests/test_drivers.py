"""
Unit tests for COBRA sensor driver framework.

Tests SensorDriver ABC, SensorData, BMM350Driver class attributes,
BMM350Data, driver registry (attach_driver/get_driver), and utils.
No hardware required — uses mock board objects.
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import fields

from cobra_bridge.drivers.base import SensorDriver, SensorData
from cobra_bridge.drivers.utils import fix_sign
from cobra_bridge.drivers.bmm350 import BMM350Driver, BMM350Data
from cobra_bridge.drivers.bmm350_async import BMM350AsyncDriver


# ── SensorData ────────────────────────────────────────────────────────────


class TestSensorData:
    def test_default_construction(self):
        data = SensorData()
        assert data.raw == {}
        assert data.timestamp is None

    def test_with_raw_and_timestamp(self):
        data = SensorData(raw={'x': 42}, timestamp=1.23)
        assert data.raw == {'x': 42}
        assert data.timestamp == 1.23

    def test_is_dataclass(self):
        assert hasattr(SensorData, '__dataclass_fields__')
        field_names = {f.name for f in fields(SensorData)}
        assert 'raw' in field_names
        assert 'timestamp' in field_names


class TestBMM350Data:
    def test_default_construction(self):
        data = BMM350Data()
        assert data.x == 0
        assert data.y == 0
        assert data.z == 0
        assert data.temperature == 0
        assert data.raw == {}
        assert data.timestamp is None

    def test_with_values(self):
        data = BMM350Data(x=1.5, y=-2.3, z=0.8, temperature=25.0,
                          raw={'xRaw': 212}, timestamp=3.14)
        assert data.x == 1.5
        assert data.y == -2.3
        assert data.z == 0.8
        assert data.temperature == 25.0
        assert data.raw == {'xRaw': 212}
        assert data.timestamp == 3.14

    def test_inherits_sensor_data(self):
        assert issubclass(BMM350Data, SensorData)


# ── SensorDriver ABC ──────────────────────────────────────────────────────


class TestSensorDriverABC:
    def test_cannot_instantiate_directly(self):
        mock_board = MagicMock()
        with pytest.raises(TypeError):
            SensorDriver(mock_board)

    def test_subclass_must_implement_abstract_methods(self):
        """A minimal subclass that doesn't implement abstracts can't be instantiated."""

        class IncompleteDriver(SensorDriver):
            name = "test"
            chip_id = 0x00
            i2c_addr = 0x00

        mock_board = MagicMock()
        with pytest.raises(TypeError):
            IncompleteDriver(mock_board)

    def test_concrete_subclass_can_instantiate(self):
        """A subclass implementing all abstracts can be instantiated."""

        class ConcreteDriver(SensorDriver):
            name = "test"
            chip_id = 0xAB
            i2c_addr = 0x55

            def init(self, **kwargs):
                pass

            def soft_reset(self):
                return 0

            def get_chip_id(self):
                return self.chip_id

            def self_test(self):
                return True

            def configure(self, settings):
                pass

            def read_data(self):
                return SensorData()

        mock_board = MagicMock()
        driver = ConcreteDriver(mock_board)
        assert driver.name == "test"
        assert driver.chip_id == 0xAB
        assert driver.i2c_addr == 0x55
        assert driver.board is mock_board
        assert driver.interface == "i2c"
        assert driver.bus == 0

    def test_constructor_with_options(self):
        class ConcreteDriver(SensorDriver):
            name = "test"
            chip_id = 0x00
            i2c_addr = 0x10

            def init(self, **kwargs): pass
            def soft_reset(self): return 0
            def get_chip_id(self): return 0
            def self_test(self): return True
            def configure(self, settings): pass
            def read_data(self): return SensorData()

        mock_board = MagicMock()
        driver = ConcreteDriver(mock_board, interface="spi", bus=1, addr=0x20)
        assert driver.interface == "spi"
        assert driver.bus == 1
        assert driver.addr == 0x20

    def test_verify_chip_id(self):
        class ConcreteDriver(SensorDriver):
            name = "test"
            chip_id = 0xAB
            i2c_addr = 0x55

            def init(self, **kwargs): pass
            def soft_reset(self): return 0
            def get_chip_id(self): return 0xAB
            def self_test(self): return True
            def configure(self, settings): pass
            def read_data(self): return SensorData()

        mock_board = MagicMock()
        driver = ConcreteDriver(mock_board)
        assert driver.verify_chip_id() is True


# ── BMM350Driver ──────────────────────────────────────────────────────────


class TestBMM350DriverClassAttrs:
    def test_name(self):
        assert BMM350Driver.name == "bmm350"

    def test_chip_id(self):
        assert BMM350Driver.chip_id == 0x33

    def test_i2c_addr(self):
        assert BMM350Driver.i2c_addr == 0x14

    def test_inherits_sensor_driver(self):
        assert issubclass(BMM350Driver, SensorDriver)


class TestBMM350DriverConstruction:
    def _make_driver(self):
        mock_board = MagicMock()
        driver = BMM350Driver(mock_board)
        return driver, mock_board

    def test_default_addr(self):
        driver, _ = self._make_driver()
        assert driver.addr == 0x14

    def test_custom_addr(self):
        mock_board = MagicMock()
        driver = BMM350Driver(mock_board, addr=0x15)
        assert driver.addr == 0x15

    def test_board_reference(self):
        driver, mock_board = self._make_driver()
        assert driver.board is mock_board

    def test_otp_not_loaded_initially(self):
        driver, _ = self._make_driver()
        assert driver.otp_loaded is False


class TestBMM350DriverRegistry:
    def test_attach_and_get_driver(self):
        mock_board = MagicMock()
        mock_board._sensor_drivers = {}
        mock_board.attach_driver = MagicMock(
            side_effect=lambda d: mock_board._sensor_drivers.update({d.name: d})
        )
        mock_board.get_driver = MagicMock(
            side_effect=lambda n: mock_board._sensor_drivers.get(n)
        )

        driver = BMM350Driver(mock_board)
        mock_board.attach_driver(driver)
        mock_board.attach_driver.assert_called_once_with(driver)

        retrieved = mock_board.get_driver("bmm350")
        assert retrieved is driver


# ── BMM350AsyncDriver ─────────────────────────────────────────────────────


class TestBMM350AsyncDriverClassAttrs:
    def test_name(self):
        assert BMM350AsyncDriver.name == "bmm350"

    def test_chip_id(self):
        assert BMM350AsyncDriver.chip_id == 0x33

    def test_i2c_addr(self):
        assert BMM350AsyncDriver.i2c_addr == 0x14

    def test_inherits_sensor_driver(self):
        assert issubclass(BMM350AsyncDriver, SensorDriver)


class TestBMM350AsyncDriverConstruction:
    def test_default_construction(self):
        mock_board = MagicMock()
        driver = BMM350AsyncDriver(mock_board)
        assert driver.addr == 0x14
        assert driver.board is mock_board
        assert driver.otp_loaded is False
        assert driver.reads_sent == 0
        assert driver.reads_received == 0

    def test_stale_threshold(self):
        mock_board = MagicMock()
        driver = BMM350AsyncDriver(mock_board, stale_threshold=16)
        assert driver._stale_threshold == 16


# ── Backward-compatible aliases ───────────────────────────────────────────


class TestAliases:
    def test_bmm350_alias(self):
        from cobra_bridge.drivers.bmm350 import BMM350
        assert BMM350 is BMM350Driver

    def test_bmm350_async_alias(self):
        from cobra_bridge.drivers.bmm350_async import BMM350Async
        assert BMM350Async is BMM350AsyncDriver


# ── fix_sign utility ──────────────────────────────────────────────────────


class TestFixSign:
    def test_positive_8bit(self):
        assert fix_sign(0x7F, 8) == 127

    def test_negative_8bit(self):
        assert fix_sign(0xFF, 8) == -1

    def test_positive_24bit(self):
        assert fix_sign(0x7FFFFF, 24) == 8388607

    def test_negative_24bit(self):
        assert fix_sign(0x800000, 24) == -8388608

    def test_zero(self):
        assert fix_sign(0, 24) == 0

    def test_12bit(self):
        assert fix_sign(0x800, 12) == -2048
        assert fix_sign(0x7FF, 12) == 2047

    def test_16bit(self):
        assert fix_sign(0x8000, 16) == -32768
        assert fix_sign(0x7FFF, 16) == 32767


# ── BMM350 constants ─────────────────────────────────────────────────────


class TestBMM350Constants:
    def test_constants_importable(self):
        from cobra_bridge.drivers.bmm350_constants import (
            BMM350_I2C_ADDR, BMM350_CHIP_ID, BMM350_DATA_LEN,
            BMM350_REG, BMM350_PMU, BMM350_ODR, BMM350_AVG,
            BMM350_OTP_ADDR,
            BMM350_LSB_TO_UT_XY, BMM350_LSB_TO_UT_Z,
            BMM350_LSB_TO_DEGC, BMM350_TEMP_OFFSET,
        )
        assert BMM350_I2C_ADDR == 0x14
        assert BMM350_CHIP_ID == 0x33
        assert BMM350_DATA_LEN == 12

    def test_board_constants_no_bmm350(self):
        """Board-level constants should NOT contain BMM350 constants."""
        from cobra_bridge import constants as board_const
        assert not hasattr(board_const, 'BMM350_I2C_ADDR')
        assert not hasattr(board_const, 'BMM350_CHIP_ID')
        assert not hasattr(board_const, 'BMM350_REG')

    def test_shuttle_pin_no_double_prefix(self):
        """SHUTTLE_PIN constants should not have double prefix."""
        from cobra_bridge.constants import SHUTTLE_PIN_7
        # If the bug existed, we'd see SHUTTLE_PIN_SHUTTLE_PIN_7
        assert 'SHUTTLE_PIN_SHUTTLE_PIN' not in dir(
            __import__('cobra_bridge.constants', fromlist=['SHUTTLE_PIN_SHUTTLE_PIN_7'])
        )