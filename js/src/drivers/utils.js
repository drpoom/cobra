/**
 * COBRA Driver Utilities — JavaScript
 *
 * Shared utility functions for sensor drivers.
 * Avoids code duplication across driver implementations.
 */


// ── Sign Extension (mirrors Bosch fix_sign) ──────────────────────────────

export function fixSign(value, bits) {
    /**
     * Convert unsigned value to signed using two's complement.
     * Mirrors Bosch BMM350_SensorAPI fix_sign() exactly.
     *
     * @param {number} value - Unsigned integer from register read
     * @param {number} bits - Bit width (8, 12, 16, 21, or 24)
     * @returns {number} Signed integer
     *
     * Examples:
     *   fixSign(0x800000, 24) → -8388608
     *   fixSign(0x7FFFFF, 24) → 8388607
     *   fixSign(0x800, 12) → -2048
     *   fixSign(0xFF, 8) → -1
     */
    const powerMap = { 8: 128, 12: 2048, 16: 32768, 21: 1048576, 24: 8388608 };
    const power = powerMap[bits] || 0;
    if (value >= power) {
        return value - (power * 2);
    }
    return value;
}