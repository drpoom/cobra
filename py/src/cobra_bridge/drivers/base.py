"""
COBRA Sensor Driver Base — Python

Abstract base class for all Bosch sensor drivers.
Every sensor driver must inherit from SensorDriver and implement
the abstract methods: init(), soft_reset(), get_chip_id(),
self_test(), configure(), and read_data().

SensorData is the base dataclass for sensor readings — subclasses
add sensor-specific fields (e.g., BMM350Data adds x, y, z, temperature).

Usage:
    from cobra_bridge.drivers.base import SensorDriver, SensorData
    from cobra_bridge import CobraBoard

    board = CobraBoard()
    board.open_comm_interface(CommInterface.USB)

    sensor = BMM350Driver(board, interface="i2c", bus=0)
    sensor.setup_board()   # Board-level: VDD, I2C config, pins
    sensor.init()          # Sensor-level: reset, verify, OTP
    data = sensor.read_data()
    print(f"X={data.x:.2f} Y={data.y:.2f} Z={data.z:.2f} μT")
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Union


@dataclass
class SensorData:
    """
    Base sensor data container.

    Subclasses add sensor-specific fields:
        @dataclass
        class BMM350Data(SensorData):
            x: float = 0.0
            y: float = 0.0
            z: float = 0.0
            temperature: float = 0.0

    Attributes:
        raw: Raw register values as a dict (e.g., {'x_raw': 123, 'y_raw': -456})
        timestamp: Optional timestamp in seconds (from board timer or time.time())
    """
    raw: Dict[str, int] = field(default_factory=dict)
    timestamp: Optional[float] = None


class SensorDriver(ABC):
    """
    Abstract base class for all Bosch sensor drivers.

    Subclasses must define:
        - Class attributes: name, chip_id, i2c_addr (minimum)
        - Abstract methods: init(), soft_reset(), get_chip_id(),
          self_test(), configure(), read_data()

    The driver receives a CobraBoard (or AsyncCobraBoard) instance and
    uses its board-level methods for I2C/SPI communication, power control,
    and pin configuration.

    Args:
        board: CobraBoard or AsyncCobraBoard instance
        interface: "i2c" or "spi"
        bus: Bus number (0 or 1)
        addr: Device address (I2C addr or SPI CS index). If None, uses class default.
    """

    # ── Class-level metadata (override in subclass) ───────────────────────

    name: str = ""
    """Sensor name (e.g., 'bmm350', 'bma456')."""

    chip_id: int = 0
    """Expected chip ID value (e.g., 0x33 for BMM350)."""

    i2c_addr: int = 0
    """Default I2C address (7-bit, e.g., 0x14 for BMM350)."""

    spi_read_cmd: int = 0x80
    """SPI read bit mask (sensor-specific, e.g., 0x80 for most Bosch sensors)."""

    spi_write_cmd: int = 0x00
    """SPI write bit mask (sensor-specific, typically 0x00)."""

    # ── Constructor ───────────────────────────────────────────────────────

    def __init__(self, board, interface: str = "i2c", bus: int = 0,
                 addr: Optional[int] = None):
        self.board = board
        self.interface = interface
        self.bus = bus
        self.addr = addr if addr is not None else self.i2c_addr

    # ── Abstract methods (must be implemented by subclass) ────────────────

    @abstractmethod
    def init(self, **kwargs) -> None:
        """
        Full sensor-level initialization sequence.

        Typically: soft reset → verify chip ID → read OTP → configure defaults.
        Board-level setup (VDD, I2C/SPI bus config, pins) should be done
        in setup_board() or by the user before calling init().

        Args:
            **kwargs: Sensor-specific initialization parameters.
        """
        ...

    @abstractmethod
    def soft_reset(self) -> int:
        """
        Send soft reset command to the sensor.

        Returns:
            Status code (0 = success).
        """
        ...

    @abstractmethod
    def get_chip_id(self) -> int:
        """
        Read and return the sensor's chip ID register.

        Returns:
            Chip ID value (e.g., 0x33 for BMM350).
        """
        ...

    @abstractmethod
    def self_test(self) -> bool:
        """
        Run the sensor's built-in self test.

        Returns:
            True if self test passed, False otherwise.
        """
        ...

    @abstractmethod
    def configure(self, settings: Dict[str, Any]) -> None:
        """
        Apply sensor configuration (ODR, range, averaging, etc.).

        Args:
            settings: Sensor-specific configuration dict.
                      Example: {'odr_hz': 100, 'averaging': 'low_power'}
        """
        ...

    @abstractmethod
    def read_data(self) -> SensorData:
        """
        Read sensor data and return parsed result.

        Returns:
            SensorData subclass instance with sensor-specific fields.
        """
        ...

    # ── Concrete methods ─────────────────────────────────────────────────

    def verify_chip_id(self) -> bool:
        """
        Verify sensor is present by checking chip ID.

        Returns:
            True if chip ID matches expected value.
        """
        return self.get_chip_id() == self.chip_id

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"name={self.name!r}, addr=0x{self.addr:02X}, "
            f"interface={self.interface!r}, bus={self.bus})"
        )