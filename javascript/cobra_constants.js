/**
 * COBRA Protocol Constants — JavaScript (WebSerial)
 *
 * Mirrors core/PROTOCOL.md and python/cobra_constants.py
 * Shared across all JS implementations.
 */

export const HEADER = 0xAA;

// Packet Types
export const TYPE_GET = 0x01;
export const TYPE_SET = 0x02;

// System Commands
export const CMD_GET_BOARD_INFO = 0x01;
export const CMD_SET_VDD  = 0x04;
export const CMD_SET_PIN  = 0x05;
export const CMD_SET_VDDIO = 0x06;
export const CMD_INT_CONFIG = 0x07;

// I2C Commands
export const CMD_I2C_WRITE = 0x0D;
export const CMD_I2C_READ  = 0x0E;

// SPI Commands
export const CMD_SPI_WRITE = 0x13;
export const CMD_SPI_READ  = 0x14;

// Response Status
export const STATUS_OK = 0x00;

// I2C Speed
export const I2C_SPEED_400K = 0;
export const I2C_SPEED_1M   = 1;

// SPI Speed
export const SPI_SPEED_5MHZ  = 0;
export const SPI_SPEED_10MHZ = 1;

// SPI Mode
export const SPI_MODE_0 = 0;
export const SPI_MODE_3 = 3;

// BMM350 Register Map (core/PROTOCOL.md §6)
export const BMM350_I2C_ADDR  = 0x14;
export const BMM350_CHIP_ID   = 0x33;
export const BMM350_SENSITIVITY = 1 / 6; // uT per LSB

export const BMM350_REG = {
    CHIP_ID:    0x00,
    PMU_CMD:    0x02,
    PMU_STATUS: 0x03,
    ODR_AXIS:   0x21,
    DATA_X_LSB: 0x30,
    DATA_Z_MSB: 0x35,
    ERR_STAT:   0x3E,
    STATUS:     0x3F,
};

export const BMM350_PMU = {
    SUSPEND:    0x01,
    NORMAL:     0x02,
    FORCED:     0x03,
    CONTINUOUS: 0x04,
    SOFT_RESET: 0x80,
};

export const BMM350_ODR = {
    400: 0x00,
    200: 0x01,
    100: 0x02,
    50:  0x03,
    25:  0x04,
    12:  0x05,
    6:   0x06,
};