"""
COBRA Driver Utilities — Python

Shared utility functions for sensor drivers.
Avoids code duplication across driver implementations.
"""


def fix_sign(value: int, bits: int) -> int:
    """
    Convert unsigned value to signed using two's complement.
    Mirrors Bosch BMM350_SensorAPI fix_sign() exactly.

    Args:
        value: Unsigned integer from register read
        bits: Bit width (8, 12, 16, 21, or 24)

    Returns:
        Signed integer

    Examples:
        fix_sign(0x800000, 24) → -8388608
        fix_sign(0x7FFFFF, 24) → 8388607
        fix_sign(0x800, 12) → -2048
        fix_sign(0xFF, 8) → -1
    """
    power = {8: 128, 12: 2048, 16: 32768, 21: 1048576, 24: 8388608}.get(bits, 0)
    if value >= power:
        return value - (power * 2)
    return value