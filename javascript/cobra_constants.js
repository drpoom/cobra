/**
 * COBRA Protocol Constants — JavaScript (WebSerial)
 *
 * AUTO-GENERATED from core/protocol_spec.json.
 * Do not edit manually — update protocol_spec.json and regenerate.
 *
 * To regenerate: python generate_constants_js.py
 */

export const HEADER = 0xAA;

// Packet Types
export const TYPE_GET = 0x01;
export const TYPE_SET = 0x02;

// System Commands
export const CMD_GET_BOARD_INFO = 0x01;
export const CMD_SET_VDD = 0x04;
export const CMD_SET_PIN = 0x05;
export const CMD_SET_VDDIO = 0x06;
export const CMD_INT_CONFIG = 0x07;

// I2C Commands
export const CMD_I2C_WRITE = 0x0D;
export const CMD_I2C_READ = 0x0E;

// SPI Commands
export const CMD_SPI_WRITE = 0x13;
export const CMD_SPI_READ = 0x14;

// Response Status
export const STATUS_OK = 0x00;

// I2C Speed
export const I2C_SPEED_400K = 0;
export const I2C_SPEED_1M = 1;

// SPI Speed & Mode
export const SPI_SPEED_5MHZ = 0;
export const SPI_SPEED_10MHZ = 1;
export const MODE_0 = 0;
export const MODE_3 = 3;

// ── BMM350 (from sensors.bmm350) ──────────────────────────────────────────

export const BMM350_I2C_ADDR  = 0x14;
export const BMM350_CHIP_ID   = 0x33;
export const BMM350_SENSITIVITY = 0.166667;

export const BMM350_REG = {
    CHIP_ID: 0x00,
    PMU_CMD: 0x02,
    PMU_STATUS: 0x03,
    ODR_AXIS: 0x21,
    AVERAGE: 0x22,
    REP_XY: 0x23,
    REP_Z: 0x24,
    OFC_CTRL: 0x25,
    OFC_X: 0x26,
    OFC_Y: 0x28,
    OFC_Z: 0x2A,
    INT_CTRL: 0x2D,
    INT_STATUS: 0x2E,
    DATA_X_LSB: 0x30,
    DATA_X_MSB: 0x31,
    DATA_Y_LSB: 0x32,
    DATA_Y_MSB: 0x33,
    DATA_Z_LSB: 0x34,
    DATA_Z_MSB: 0x35,
    SELF_TEST: 0x36,
    SELF_TEST_STATUS: 0x37,
    ERR_STAT: 0x3E,
    STATUS: 0x3F,
};

export const BMM350_PMU = {
    SUSPEND: 0x01,
    NORMAL: 0x02,
    FORCED: 0x03,
    CONTINUOUS: 0x04,
    SOFT_RESET: 0x80,
};

export const BMM350_ODR = {
    400_HZ: 0x00,
    200_HZ: 0x01,
    100_HZ: 0x02,
    50_HZ: 0x03,
    25_HZ: 0x04,
    12_5_HZ: 0x05,
    6_25_HZ: 0x06,
};
