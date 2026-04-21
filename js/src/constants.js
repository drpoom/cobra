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
export const CMD_CONFIG_I2C_BUS = 0x08;
export const CMD_CONFIG_SPI_BUS = 0x09;
export const CMD_DECONFIG_I2C_BUS = 0x24;
export const CMD_DECONFIG_SPI_BUS = 0x25;

// I2C Commands
export const CMD_I2C_WRITE = 0x0D;
export const CMD_I2C_READ = 0x0E;

// SPI Commands
export const CMD_SPI_WRITE = 0x13;
export const CMD_SPI_READ = 0x14;

// Response Status
export const STATUS_OK = 0x00;

// I2C Bus
export const I2C_BUS_0 = 0;
export const I2C_BUS_1 = 1;

// I2C Speed
export const I2C_SPEED_STANDARD = 0;
export const I2C_SPEED_FAST = 1;
export const I2C_SPEED_HIGH = 2;
export const I2C_SPEED_400K = 0;
export const I2C_SPEED_1M = 1;

// SPI Bus
export const SPI_BUS_0 = 0;
export const SPI_BUS_1 = 1;

// SPI Speed & Mode
export const SPI_SPEED_50KHZ = 50000;
export const SPI_SPEED_100KHZ = 100000;
export const SPI_SPEED_250KHZ = 250000;
export const SPI_SPEED_500KHZ = 500000;
export const SPI_SPEED_1MHZ = 1000000;
export const SPI_SPEED_2MHZ = 2000000;
export const SPI_SPEED_4MHZ = 4000000;
export const SPI_SPEED_8MHZ = 8000000;
export const SPI_SPEED_10MHZ = 10000000;
export const SPI_SPEED_20MHZ = 20000000;
export const SPI_MODE_0 = 0;
export const SPI_MODE_1 = 1;
export const SPI_MODE_2 = 2;
export const SPI_MODE_3 = 3;

// Shuttle Board Pins
export const SHUTTLE_PIN_7 = 9;
export const SHUTTLE_PIN_8 = 5;
export const SHUTTLE_PIN_9 = 0;
export const SHUTTLE_PIN_14 = 1;
export const SHUTTLE_PIN_15 = 2;
export const SHUTTLE_PIN_16 = 3;
export const SHUTTLE_PIN_19 = 8;
export const SHUTTLE_PIN_20 = 6;
export const SHUTTLE_PIN_21 = 7;
export const SHUTTLE_PIN_22 = 4;

// Pin Direction & Value
export const PIN_IN = 0;
export const PIN_OUT = 1;
export const PIN_LOW = 0;
export const PIN_HIGH = 1;

// ── Coinespy-compatible Enums ──────────────────────────────────────────

export const CommInterface = {
    USB: { value: 0, name: 'USB' },
    BLE: { value: 1, name: 'BLE' },
    VIRTUAL: { value: 2, name: 'VIRTUAL' },
};

export const ErrorCodes = {
    COINES_SUCCESS: 0,
    COINES_E_FAILURE: -1,
    COINES_E_COMM_ALREADY_OPEN: -2,
    COINES_E_COMM_INIT_FAILED: -3,
    COINES_E_INVALID_ARGUMENT: -4,
    COINES_E_UNABLE_OPEN_DEVICE: -5,
    COINES_E_I2C_READ_WRITE_FAILED: -6,
    COINES_E_SPI_READ_WRITE_FAILED: -7,
};

export const PinDirection = { IN: 0, OUT: 1 };
export const PinValue = { LOW: 0, HIGH: 1 };

export const I2CBus = { BUS_0: 0, BUS_1: 1 };
export const I2CMode = { STANDARD: 0, FAST: 1, HIGH: 2 };

export const SPIMode = { MODE_0: 0, MODE_1: 1, MODE_2: 2, MODE_3: 3 };
export const SPISpeed = {
    SPEED_50KHZ: 50000, SPEED_100KHZ: 100000, SPEED_250KHZ: 250000,
    SPEED_500KHZ: 500000, SPEED_1MHZ: 1000000, SPEED_2MHZ: 2000000,
    SPEED_4MHZ: 4000000, SPEED_8MHZ: 8000000, SPEED_10MHZ: 10000000,
    SPEED_20MHZ: 20000000,
};

export const MultiIOPin = {
    COINES_MINI_SHUTTLE_PIN_CS: { value: 7 },
    COINES_MINI_SHUTTLE_PIN_1_6: { value: 16 },
    COINES_MINI_SHUTTLE_PIN_1_7: { value: 17 },
    COINES_MINI_SHUTTLE_PIN_1_8: { value: 18 },
    COINES_MINI_SHUTTLE_PIN_1_9: { value: 19 },
    COINES_MINI_SHUTTLE_PIN_1_10: { value: 20 },
    COINES_MINI_SHUTTLE_PIN_1_11: { value: 21 },
    COINES_MINI_SHUTTLE_PIN_1_12: { value: 22 },
};

export const I2CTransferBits = { I2C16BIT: 16 };
export const SPITransferBits = { SPI16BIT: 16 };

export const StreamingMode = { DMA: 0, INTERRUPT: 1 };
export const StreamingState = { STOP: 0, START: 1 };

export const TimerConfig = { TIMER_0: 0, TIMER_1: 1 };
export const TimerStampConfig = { STAMP_0: 0, STAMP_1: 1 };

