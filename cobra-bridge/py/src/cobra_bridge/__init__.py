"""
COBRA — COines BRidge Access for Python

Transport-agnostic Bosch AppBoard protocol library.
Supports USB-Serial (pyserial) and BLE (Bleak).

Quick start:
    from cobra_bridge.transport import SerialTransport
    from cobra_bridge.sync import CobraBridge

    transport = SerialTransport(port='/dev/ttyACM0')
    bridge = CobraBridge(transport=transport)
    bridge.connect()
"""

from cobra_bridge.constants import (
    HEADER, TYPE_GET, TYPE_SET, STATUS_OK,
    CMD_GET_BOARD_INFO, CMD_SET_VDD, CMD_SET_PIN, CMD_SET_VDDIO, CMD_INT_CONFIG,
    CMD_I2C_WRITE, CMD_I2C_READ,
    CMD_SPI_WRITE, CMD_SPI_READ,
    I2C_SPEED_400K, I2C_SPEED_1M,
    SPI_SPEED_5MHZ, SPI_SPEED_10MHZ, SPI_MODE_0, SPI_MODE_3,
    BMM350_I2C_ADDR, BMM350_CHIP_ID, BMM350_DATA_LEN,
    BMM350_REG, BMM350_PMU, BMM350_PMU_STATUS, BMM350_ODR, BMM350_AVG, BMM350_OTP_ADDR,
    BMM350_LSB_TO_UT_XY, BMM350_LSB_TO_UT_Z, BMM350_LSB_TO_DEGC, BMM350_TEMP_OFFSET,
)

__version__ = '0.1.0'