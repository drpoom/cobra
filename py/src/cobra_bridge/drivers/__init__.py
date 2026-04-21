"""
COBRA sensor drivers.

Every sensor driver inherits from SensorDriver and implements
the abstract methods: init(), soft_reset(), get_chip_id(),
self_test(), configure(), read_data().

Available drivers:
    - BMM350Driver / BMM350AsyncDriver — Bosch BMM350 magnetometer
"""

from .base import SensorDriver, SensorData
from .utils import fix_sign
from .bmm350 import BMM350Driver, BMM350Data
from .bmm350_async import BMM350AsyncDriver

# Backward-compatible aliases
from .bmm350 import BMM350
from .bmm350_async import BMM350Async

__all__ = [
    'SensorDriver', 'SensorData',
    'fix_sign',
    'BMM350Driver', 'BMM350Data', 'BMM350',
    'BMM350AsyncDriver', 'BMM350Async',
]