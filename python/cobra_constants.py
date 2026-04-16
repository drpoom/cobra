"""
COBRA Protocol Constants — Auto-generated from core/PROTOCOL.md

All implementations share these constants. This module is the
Python-specific export of the language-agnostic protocol spec.
"""

# ── Packet Types ────────────────────────────────────────────────────────────
TYPE_GET = 0x01  # Read request
TYPE_SET = 0x02  # Write request

# ── System Commands ─────────────────────────────────────────────────────────
CMD_GET_BOARD_INFO = 0x01
CMD_SET_VDD        = 0x04
CMD_SET_PIN        = 0x05
CMD_SET_VDDIO      = 0x06
CMD_INT_CONFIG     = 0x07

# ── I2C Commands ────────────────────────────────────────────────────────────
CMD_I2C_WRITE = 0x0D  # 13
CMD_I2C_READ  = 0x0E  # 14

# ── SPI Commands ────────────────────────────────────────────────────────────
CMD_SPI_WRITE = 0x13  # 19
CMD_SPI_READ  = 0x14  # 20

# ── Response Status ─────────────────────────────────────────────────────────
STATUS_OK = 0x00

# ── I2C Speed ───────────────────────────────────────────────────────────────
I2C_SPEED_400K = 0  # 400 kHz (default)
I2C_SPEED_1M   = 1  # 1 MHz

# ── SPI Speed ──────────────────────────────────────────────────────────────
SPI_SPEED_5MHZ  = 0
SPI_SPEED_10MHZ = 1

# ── SPI Mode ───────────────────────────────────────────────────────────────
SPI_MODE_0 = 0
SPI_MODE_3 = 3

# ── Packet Header ───────────────────────────────────────────────────────────
HEADER = 0xAA