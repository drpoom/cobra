/**
 * COBRA Protocol Constants — JavaScript
 *
 * AUTO-GENERATED from core/protocol_spec.json.
 * Do not edit manually — update protocol_spec.json and run:
 *     python tools/gen_constants.py
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
export const SPI_MODE_0 = 0;
export const SPI_MODE_3 = 3;

// ── BMM350 ──────────────────────────────────────────────────────────────

export const BMM350_I2C_ADDR = 0x14;
export const BMM350_CHIP_ID = 0x33;
export const BMM350_DATA_LEN = 12; // bytes per sample (24-bit x 4 channels)

export const BMM350_REG = {
    CHIP_ID: 0x00,  // Chip ID (expected 0x33)
    PMU_CMD_AGGR_SET: 0x04,  // ODR and averaging configuration
    PMU_CMD_AXIS_EN: 0x05,  // Axis enable/disable
    PMU_CMD: 0x06,  // Power mode command (SUS=0x00, NM=0x01, UPD_OAE=0x02, FORCED=0x03, NM_50HZ=0x04, FGR=0x05, FGR_FAST=0x06, BR=0x07, BR_FAST=0x08)
    PMU_CMD_STATUS_0: 0x08,  // PMU command status
    INT_CTRL: 0x11,  // Interrupt control
    INT_STATUS: 0x12,  // Interrupt status (bit 0 = DRDY)
    OTP_CMD_REG: 0x50,  // OTP command register
    OTP_DATA_MSB_REG: 0x52,  // OTP data MSB
    OTP_DATA_LSB_REG: 0x53,  // OTP data LSB
    OTP_STATUS_REG: 0x55,  // OTP status register
    CMD_REG: 0x24,  // Command register (soft-reset = 0xB6)
    MAG_X_XLSB: 0x31,  // Mag X 24-bit data (XLSB, LSB, MSB)
    MAG_Y_XLSB: 0x34,  // Mag Y 24-bit data (XLSB, LSB, MSB)
    MAG_Z_XLSB: 0x37,  // Mag Z 24-bit data (XLSB, LSB, MSB)
    TEMP_XLSB: 0x3A,  // Temperature 24-bit data (XLSB, LSB, MSB)
    ERR_STAT: 0x3F,  // Error status
};

export const BMM350_PMU = {
    SUS: 0x00,
    NM: 0x01,
    UPD_OAE: 0x02,
    FORCED: 0x03,
    NM_50HZ: 0x04,
    FGR: 0x05,
    FGR_FAST: 0x06,
    BR: 0x07,
    BR_FAST: 0x08,
    SOFT_RESET: 0xB6,
};

// ODR map: human Hz → register value
export const BMM350_ODR = {
    400: 0x02,
    200: 0x03,
    100: 0x04,
    50: 0x05,
    25: 0x06,
    '12.5': 0x07,
    '6.25': 0x08,
    '3.125': 0x09,
    '1.5625': 0x0A,
};

export const BMM350_AVG = {
    NO_AVG: 0,
    AVG_2: 1,
    AVG_4: 2,
    AVG_8: 3,
};

export const BMM350_OTP_ADDR = {
    TEMP_OFF_SENS: 13,
    MAG_OFFSET_X: 14,
    MAG_OFFSET_Y: 15,
    MAG_OFFSET_Z: 16,
    MAG_SENS_X: 16,
    MAG_SENS_Y: 17,
    MAG_SENS_Z: 17,
    MAG_TCO_X: 18,
    MAG_TCO_Y: 19,
    MAG_TCO_Z: 20,
    MAG_TCS_X: 18,
    MAG_TCS_Y: 19,
    MAG_TCS_Z: 20,
    MAG_DUT_T_0: 24,
    CROSS_X_Y: 21,
    CROSS_Y_X: 21,
    CROSS_Z_X: 22,
    CROSS_Z_Y: 22,
};

// ── BMM350 Conversion Coefficients (Bosch BMM350_SensorAPI v1.10.0) ────

export const BMM350_LSB_TO_UT_XY = 0.007069979;  // uT/LSB for X,Y axes
export const BMM350_LSB_TO_UT_Z = 0.007174964;   // uT/LSB for Z axis
export const BMM350_LSB_TO_DEGC = 0.000981282;  // degC/LSB for temperature
export const BMM350_TEMP_OFFSET = 25.49;  // degC offset
