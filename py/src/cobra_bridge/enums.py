"""
COBRA Enumerations — Python

Coinespy-compatible enums and data structures for COBRA.
These are NOT auto-generated — they are maintained manually.

This module provides drop-in replacements for coinespy enums:
    from cobra_bridge.enums import CommInterface, ErrorCodes, I2CBus, ...
"""

from enum import Enum


# ── Error Codes ──────────────────────────────────────────────────────────

class ErrorCodes(Enum):
    """Error codes matching coinespy ErrorCodes."""
    COINES_SUCCESS = 0
    COINES_E_FAILURE = -1
    COINES_E_COMM_IO_ERROR = -2
    COINES_E_COMM_INIT_FAILED = -3
    COINES_E_UNABLE_OPEN_DEVICE = -4
    COINES_E_DEVICE_NOT_FOUND = -5
    COINES_E_UNABLE_CLAIM_INTERFACE = -6
    COINES_E_MEMORY_ALLOCATION = -7
    COINES_E_NOT_SUPPORTED = -8
    COINES_E_NULL_PTR = -9
    COINES_E_INVALID_ARGUMENT = -10
    COINES_E_INVALID_PTR = -11
    COINES_E_SENSOR_INTF_INIT_FAILED = -12
    COINES_E_SPI_BUS_INIT_FAILED = -13
    COINES_E_I2C_BUS_INIT_FAILED = -14
    COINES_E_MAX_EXCEEDED = -15
    COINES_E_SPI_READ_WRITE_FAILED = -16
    COINES_E_I2C_READ_WRITE_FAILED = -17
    COINES_E_READ_WRITE_LENGTH_INVALID = -18
    COINES_E_COMM_ALREADY_OPEN = -19
    COINES_E_STREAM_NOT_ENABLED = -20
    COINES_E_STREAM_ALREADY_ENABLED = -21
    COINES_E_STREAM_REMAINING_SAMPLES = -22
    COINES_E_STREAM_SCAN_TIMEOUT = -23
    COINES_E_STREAM_READ_FAILED = -24
    COINES_E_BOARD_NOT_INITIALIZED = -25
    COINES_E_SHUTTLE_ID_UNKNOWN = -26
    COINES_E_INTERRUPT_NOT_CONFIGURED = -27
    COINES_E_GPIO_NOT_SUPPORTED = -28
    COINES_E_UNABLE_CLOSE_DEVICE = -29
    COINES_E_FW_LOAD_FAILED = -30
    COINES_E_NOT_FOUND = -31
    COINES_E_INVALID_SHUTTLE_ID = -32
    COINES_E_INVALID_SENSOR_ID = -33
    COINES_E_INSUFF_BUFFER_SIZE = -34
    COINES_E_ADAPTER_CHIP_FW_VERSION_MISMATCH = -35
    COINES_E_POLLING_TIMEOUT = -36


# ── Communication Interface ───────────────────────────────────────────────

class CommInterface(Enum):
    """Communication interfaces."""
    USB = 0
    BLE = 1
    VIRTUAL = 2


# ── GPIO ──────────────────────────────────────────────────────────────────

class PinDirection(Enum):
    """GPIO pin direction."""
    INPUT = 0
    OUTPUT = 1


class PinValue(Enum):
    """GPIO pin value."""
    LOW = 0
    HIGH = 1


class MultiIOPin(Enum):
    """Multi-I/O pin selection (coinespy compatible)."""
    COINES_MINI_SHUTTLE_PIN_CS = 0
    COINES_MINI_SHUTTLE_PIN_2_3 = 1
    COINES_MINI_SHUTTLE_PIN_2_4 = 2
    COINES_MINI_SHUTTLE_PIN_2_5 = 3
    COINES_MINI_SHUTTLE_PIN_1_6 = 4
    COINES_MINI_SHUTTLE_PIN_1_7 = 5
    COINES_MINI_SHUTTLE_PIN_1_8 = 6
    COINES_MINI_SHUTTLE_PIN_1_9 = 7


# ── I2C ───────────────────────────────────────────────────────────────────

class I2CBus(Enum):
    """I2C bus selection."""
    COINES_I2C_BUS_0 = 0
    COINES_I2C_BUS_1 = 1


class I2CMode(Enum):
    """I2C mode selection."""
    STANDARD_MODE = 0   # 100 kbps
    FAST_MODE = 1        # 400 kbps


class I2CTransferBits(Enum):
    """I2C transfer bits selection."""
    I2C8BIT = 0
    I2C16BIT = 1


# ── SPI ───────────────────────────────────────────────────────────────────

class SPIMode(Enum):
    """SPI mode selection."""
    MODE0 = 0   # CPOL=0, CPHA=0
    MODE1 = 1   # CPOL=0, CPHA=1
    MODE2 = 2   # CPOL=1, CPHA=0
    MODE3 = 3   # CPOL=1, CPHA=1


class SPISpeed(Enum):
    """SPI speed selection (Hz)."""
    SPI_50_KHZ = 50000
    SPI_100_KHZ = 100000
    SPI_250_KHZ = 250000
    SPI_500_KHZ = 500000
    SPI_1_MHZ = 1000000
    SPI_2_MHZ = 2000000
    SPI_4_MHZ = 4000000
    SPI_8_MHZ = 8000000
    SPI_10_MHZ = 10000000
    SPI_20_MHZ = 20000000


class SPITransferBits(Enum):
    """SPI transfer bits selection."""
    SPI8BIT = 0
    SPI16BIT = 1


# ── Streaming ─────────────────────────────────────────────────────────────

class StreamingMode(Enum):
    """Streaming modes."""
    STREAMING_MODE_FIFO = 0
    STREAMING_MODE_INTERRUPT = 1


class StreamingState(Enum):
    """Streaming states."""
    STREAMING_STOP = 0
    STREAMING_START = 1


class StreamingBlocks:
    """Streaming blocks configuration."""
    def __init__(self):
        self.sensor_id = 0
        self.feature_id = 0
        self.read_write_type = 0
        self.no_of_sensors = 0
        self.mem_page_info = 0
        self.int_array = [0] * 10
        self.address = [0] * 10
        self.no_of_data_bytes = [0] * 10
        self.enable_rw_blocks = 0
        self.block_type = [0] * 10
        self.wait_time_us = [0] * 10
        self.write_data = [[0] * 50 for _ in range(10)]


# ── Timer ─────────────────────────────────────────────────────────────────

class TimerConfig(Enum):
    """Timer configuration."""
    COINES_TIMER_STOP = 0
    COINES_TIMER_START = 1


class TimerStampConfig(Enum):
    """Timer stamp configuration."""
    COINES_TIMESTAMP_DISABLE = 0
    COINES_TIMESTAMP_ENABLE = 1


# ── Communication Config ──────────────────────────────────────────────────

class BleComConfig:
    """BLE communication configuration."""
    def __init__(self, address=None, identifier=None, timeout=0, rx_buffer_size=0):
        self.address = address
        self.identifier = identifier
        self.scan_timeout = timeout
        self.rx_buffer_size = rx_buffer_size


class SerialComConfig:
    """Serial communication configuration."""
    def __init__(self, baud_rate=0, vendor_id=0x00, product_id=0x00,
                 com_port_name: str = None, rx_buffer_size=0):
        self.baud_rate = baud_rate
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.com_port_name = com_port_name
        self.rx_buffer_size = rx_buffer_size