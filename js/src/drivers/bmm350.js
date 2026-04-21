/**
 * COBRA: BMM350Driver — Magnetometer Driver (JavaScript)
 *
 * Register-level driver for the Bosch BMM350 magnetometer.
 * Based on official Bosch BMM350_SensorAPI v1.10.0 conversion formulas.
 * Mirrors python/bmm350.py — same structure, same formulas, same API.
 *
 * Inherits from SensorDriver ABC for sensor-agnostic framework.
 *
 * Key features:
 *   - 24-bit data reads (12 bytes: 3 bytes/axis × 3 axes + 3 bytes temp)
 *   - Official Bosch conversion coefficients (not 1/6 simplification)
 *   - Temperature readout with proper °C conversion
 *   - OTP calibration support (offset, sensitivity, TCO, TCS, cross-axis)
 *   - setOdr(frequencyHz) with user-friendly Hz input
 *
 * Usage:
 *   import { BMM350Driver } from 'cobra-bridge/drivers/bmm350';
 *   const sensor = new BMM350Driver(board, { interface: 'i2c', bus: 0 });
 *   await sensor.setupBoard();
 *   await sensor.init();
 *   const data = await sensor.readData();
 *   console.log(`X=${data.x.toFixed(2)} Y=${data.y.toFixed(2)} Z=${data.z.toFixed(2)} μT`);
 *   console.log(`T=${data.temperature.toFixed(2)} °C`);
 */

import { SensorDriver, SensorData } from './base.js';
import { fixSign } from './utils.js';
import {
    BMM350_I2C_ADDR, BMM350_CHIP_ID, BMM350_DATA_LEN,
    BMM350_REG, BMM350_PMU, BMM350_ODR, BMM350_AVG, BMM350_OTP_ADDR,
    BMM350_LSB_TO_UT_XY, BMM350_LSB_TO_UT_Z, BMM350_LSB_TO_DEGC, BMM350_TEMP_OFFSET,
} from './bmm350_constants.js';
import {
    I2C_BUS_0, I2C_SPEED_STANDARD, I2C_SPEED_400K,
    SHUTTLE_PIN_7, PIN_OUT, PIN_LOW,
} from '../constants.js';


// ── BMM350Data ────────────────────────────────────────────────────────────

export class BMM350Data extends SensorData {
    /**
     * BMM350 magnetometer reading with physical units.
     * @param {number} x - X-axis magnetic field (μT)
     * @param {number} y - Y-axis magnetic field (μT)
     * @param {number} z - Z-axis magnetic field (μT)
     * @param {number} temperature - Die temperature (°C)
     * @param {Object} raw - Raw register values
     * @param {number|null} timestamp - Optional timestamp
     */
    constructor({ x = 0, y = 0, z = 0, temperature = 0, raw = {}, timestamp = null } = {}) {
        super(raw, timestamp);
        this.x = x;
        this.y = y;
        this.z = z;
        this.temperature = temperature;
    }
}


// ── ODR frequency mapping ────────────────────────────────────────────────

const ODR_HZ_MAP = {
    400:    BMM350_ODR[400],
    200:    BMM350_ODR[200],
    100:    BMM350_ODR[100],
    50:     BMM350_ODR[50],
    25:     BMM350_ODR[25],
    12.5:   BMM350_ODR['12.5'],
    6.25:   BMM350_ODR['6.25'],
    3.125:  BMM350_ODR['3.125'],
    1.5625: BMM350_ODR['1.5625'],
};

const ODR_AVG_LIMITS = {
    400: BMM350_AVG.NO_AVG,
    200: BMM350_AVG.AVG_2,
    100: BMM350_AVG.AVG_4,
};


// ── BMM350Driver ─────────────────────────────────────────────────────────

export class BMM350Driver extends SensorDriver {
    /**
     * BMM350 Magnetometer Driver over COBRA I2C bridge.
     *
     * Inherits from SensorDriver ABC. Uses CobraBoardJs board-level
     * methods for I2C communication, power control, and pin configuration.
     *
     * Supports two conversion modes:
     *   1. Default coefficients (no OTP) — simple raw × coefficient
     *   2. OTP compensated — full Bosch compensation chain with calibration data
     */

    // ── SensorDriver class-level metadata ────────────────────────────────

    static name = 'bmm350';
    static chipId = BMM350_CHIP_ID;
    static i2cAddr = BMM350_I2C_ADDR;
    static spiReadCmd = 0x80;
    static spiWriteCmd = 0x00;

    // ── Constructor ──────────────────────────────────────────────────────

    constructor(board, { interface: iface = 'i2c', bus = 0, addr } = {}) {
        super(board, { interface: iface, bus, addr });
        this._otpData = [];
        this._otpLoaded = false;
        this._axisEn = 0x07;  // XYZ enabled by default

        // OTP compensation coefficients (populated by readOtp)
        this._offset = { x: 0, y: 0, z: 0, tOffs: 0 };
        this._sensit = { x: 0, y: 0, z: 0, tSens: 0 };
        this._tco = { x: 0, y: 0, z: 0 };
        this._tcs = { x: 0, y: 0, z: 0 };
        this._cross = { xY: 0, yX: 0, zX: 0, zY: 0 };
        this._dutT0 = 23.0;
    }

    // ── Register I/O ────────────────────────────────────────────────────

    async _readReg(reg, length = 1) {
        return this.board.i2cReadReg(this.addr, reg, length);
    }

    async _writeReg(reg, data) {
        return this.board.i2cWriteReg(this.addr, reg, data);
    }

    // ── Board Setup ──────────────────────────────────────────────────────

    /**
     * Board-level setup: I2C bus config, pin config, power cycle.
     * Call this before init().
     *
     * @param {Object} [options]
     * @param {number} [options.bus=0] - I2C bus (0 or 1)
     * @param {number} [options.speed=0] - I2C speed: 0=400K, 1=1M, 2=3.4M
     * @param {number} [options.vddMv=1800] - VDD voltage in mV
     * @param {number} [options.vddioMv=1800] - VDDIO voltage in mV
     */
    async setupBoard({ bus = I2C_BUS_0, speed = I2C_SPEED_STANDARD,
                       vddMv = 1800, vddioMv = 1800 } = {}) {
        this.board.configI2cBus(bus, this.addr, 0);
        this.board.setPin(SHUTTLE_PIN_7, PIN_OUT, PIN_LOW);
        this.board.setVdd(0);
        this.board.setVddio(0);
        await this._delay(100);
        this.board.setVdd(vddMv);
        this.board.setVddio(vddioMv);
        await this._delay(100);
    }

    _delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // ── SensorDriver abstract method implementations ─────────────────────

    /**
     * Full sensor-level initialization sequence.
     * Mirrors the official Bosch COINES SDK init sequence.
     */
    async init() {
        await this.softReset();
        await this._delay(25);

        const chipId = await this.getChipId();
        if (chipId !== BMM350_CHIP_ID) {
            throw new Error(`BMM350 not found. Chip ID: 0x${chipId.toString(16).padStart(2, '0')}, expected 0x33`);
        }

        await this.readOtp();
        await this._writeReg(BMM350_REG.OTP_CMD_REG, new Uint8Array([0x80]));
        await this._delay(1);

        await this.setPowerMode('suspend');
        await this._delay(30);
        await this._writeReg(BMM350_REG.PMU_CMD, new Uint8Array([BMM350_PMU.BR]));
        await this._delay(3);
        await this._writeReg(BMM350_REG.PMU_CMD, new Uint8Array([BMM350_PMU.FGR]));
        await this._delay(30);
    }

    async softReset() {
        return this._writeReg(BMM350_REG.CMD_REG, new Uint8Array([0xB6]));
    }

    async getChipId() {
        const data = await this._readReg(BMM350_REG.CHIP_ID, 1);
        return data[0];
    }

    async selfTest() {
        return (await this.readErrorStatus()) === 0;
    }

    async configure(settings = {}) {
        if (settings.powerMode) {
            await this.setPowerMode(settings.powerMode);
        }
        if (settings.odrHz) {
            const avg = settings.averaging ?? 'low_power';
            await this.setOdr(settings.odrHz, avg);
        }
    }

    /**
     * Read 3-axis magnetic field in μT and temperature in °C.
     * Returns a BMM350Data instance.
     *
     * @param {boolean} [compensated=false] - If true and OTP loaded, apply full compensation
     * @returns {BMM350Data}
     */
    async readData(compensated = false) {
        const raw = await this._readReg(BMM350_REG.MAG_X_XLSB, BMM350_DATA_LEN);
        const converted = this._convertRaw(raw, compensated);
        return new BMM350Data({
            x: converted.x,
            y: converted.y,
            z: converted.z,
            temperature: converted.temperature,
            raw: { xRaw: converted.xRaw, yRaw: converted.yRaw, zRaw: converted.zRaw, tRaw: converted.tRaw },
        });
    }

    // ── Power Mode ────────────────────────────────────────────────────────

    async setPowerMode(mode = 'normal') {
        const aliases = { normal: 'nm', continuous: 'nm', suspend: 'sus', forced_fast: 'fgr_fast' };
        const modeKey = aliases[mode.toLowerCase()] || mode.toLowerCase();
        const cmd = BMM350_PMU[modeKey.toUpperCase()];
        if (cmd === undefined) {
            throw new Error(`Invalid mode: ${mode}`);
        }
        return this._writeReg(BMM350_REG.PMU_CMD, new Uint8Array([cmd]));
    }

    async getPowerMode() {
        const data = await this._readReg(BMM350_REG.PMU_CMD_STATUS_0, 1);
        const status = data[0] & 0x0F;
        const names = { 0: 'sus', 1: 'nm', 2: 'forced', 3: 'nm_50hz' };
        return names[status] || `unknown(0x${status.toString(16)})`;
    }

    // ── ODR ──────────────────────────────────────────────────────────────

    /**
     * Set output data rate and averaging.
     *
     * @param {number} frequencyHz - ODR in Hz. Valid: 400, 200, 100, 50, 25, 12.5, 6.25, 3.125, 1.5625
     * @param {string} [averaging='low_power'] - 'low_power', 'medium', 'high', 'ultra'
     * @returns {number} Status code
     */
    async setOdr(frequencyHz = 100, averaging = 'low_power') {
        let odrVal = ODR_HZ_MAP[frequencyHz];
        if (odrVal === undefined) {
            for (const [hz, val] of Object.entries(ODR_HZ_MAP)) {
                if (Math.abs(frequencyHz - Number(hz)) < 0.01) {
                    odrVal = val;
                    break;
                }
            }
        }
        if (odrVal === undefined) {
            const valid = Object.keys(ODR_HZ_MAP).map(Number).sort((a, b) => a - b);
            throw new Error(`Invalid ODR: ${frequencyHz} Hz. Valid: ${valid}`);
        }

        const avgMap = {
            low_power: BMM350_AVG.NO_AVG,
            medium: BMM350_AVG.AVG_2,
            high: BMM350_AVG.AVG_4,
            ultra: BMM350_AVG.AVG_8,
        };
        let avgVal = avgMap[averaging] ?? BMM350_AVG.NO_AVG;

        if (frequencyHz in ODR_AVG_LIMITS) {
            avgVal = Math.min(avgVal, ODR_AVG_LIMITS[frequencyHz]);
        }

        const regData = (avgVal << 4) | (odrVal & 0x0F);
        await this._writeReg(BMM350_REG.PMU_CMD_AGGR_SET, new Uint8Array([regData]));
        await this._writeReg(BMM350_REG.PMU_CMD, new Uint8Array([BMM350_PMU.UPD_OAE]));
        await this._delay(1);
        return 0;
    }

    // ── Axis Enable ───────────────────────────────────────────────────────

    async enableAxes(x = true, y = true, z = true) {
        let data = (x ? 0x01 : 0x00) | (y ? 0x02 : 0x00) | (z ? 0x04 : 0x00);
        if (data === 0) throw new Error('At least one axis must be enabled');
        this._axisEn = data;
        return this._writeReg(BMM350_REG.PMU_CMD_AXIS_EN, new Uint8Array([data]));
    }

    // ── OTP Calibration ───────────────────────────────────────────────────

    async readOtp() {
        this._otpData = [];
        for (let addr = 0; addr < 32; addr++) {
            const word = await this._readOtpWord(addr);
            this._otpData.push(word);
        }
        this._otpLoaded = true;
        this._updateMagOffSens();
    }

    async _readOtpWord(addr) {
        const otpCmd = 0x20 | (addr & 0x1F);
        await this._writeReg(BMM350_REG.OTP_CMD_REG, new Uint8Array([otpCmd]));
        await this._delay(0.3);

        for (let i = 0; i < 10; i++) {
            const status = (await this._readReg(BMM350_REG.OTP_STATUS_REG, 1))[0];
            if (status & 0x01) break;
            if (status & 0xE0) throw new Error(`OTP read error at addr ${addr}: 0x${status.toString(16)}`);
            await this._delay(0.3);
        }

        const msb = (await this._readReg(BMM350_REG.OTP_DATA_MSB_REG, 1))[0];
        const lsb = (await this._readReg(BMM350_REG.OTP_DATA_LSB_REG, 1))[0];
        return (msb << 8) | lsb;
    }

    /**
     * Compute calibration coefficients from OTP data.
     * Mirrors official Bosch update_mag_off_sens() — float path.
     */
    _updateMagOffSens() {
        if (!this._otpLoaded || this._otpData.length < 32) return;

        const d = this._otpData;

        // ── Offsets ──
        const offX = d[BMM350_OTP_ADDR.MAG_OFFSET_X] & 0x0FFF;
        const offY = ((d[BMM350_OTP_ADDR.MAG_OFFSET_X] & 0xF000) >> 4) +
                     (d[BMM350_OTP_ADDR.MAG_OFFSET_Y] & 0x00FF);
        const offZ = (d[BMM350_OTP_ADDR.MAG_OFFSET_Y] & 0x0F00) +
                     (d[BMM350_OTP_ADDR.MAG_OFFSET_Z] & 0x00FF);
        const tOff = d[BMM350_OTP_ADDR.TEMP_OFF_SENS] & 0x00FF;

        this._offset.x = fixSign(offX, 12);
        this._offset.y = fixSign(offY, 12);
        this._offset.z = fixSign(offZ, 12);
        this._offset.tOffs = fixSign(tOff, 8) / 5.0;

        // ── Sensitivity ──
        const sensX = (d[BMM350_OTP_ADDR.MAG_SENS_X] & 0xFF00) >> 8;
        const sensY = d[BMM350_OTP_ADDR.MAG_SENS_Y] & 0x00FF;
        const sensZ = (d[BMM350_OTP_ADDR.MAG_SENS_Z] & 0xFF00) >> 8;
        const tSens = (d[BMM350_OTP_ADDR.TEMP_OFF_SENS] & 0xFF00) >> 8;

        this._sensit.x = fixSign(sensX, 8) / 256.0;
        this._sensit.y = fixSign(sensY, 8) / 256.0;
        this._sensit.z = fixSign(sensZ, 8) / 256.0;
        this._sensit.tSens = fixSign(tSens, 8) / 512.0;

        // ── TCO ──
        const tcoX = d[BMM350_OTP_ADDR.MAG_TCO_X] & 0x00FF;
        const tcoY = d[BMM350_OTP_ADDR.MAG_TCO_Y] & 0x00FF;
        const tcoZ = d[BMM350_OTP_ADDR.MAG_TCO_Z] & 0x00FF;

        this._tco.x = fixSign(tcoX, 8) / 32.0;
        this._tco.y = fixSign(tcoY, 8) / 32.0;
        this._tco.z = fixSign(tcoZ, 8) / 32.0;

        // ── TCS ──
        const tcsX = (d[BMM350_OTP_ADDR.MAG_TCS_X] & 0xFF00) >> 8;
        const tcsY = (d[BMM350_OTP_ADDR.MAG_TCS_Y] & 0xFF00) >> 8;
        const tcsZ = (d[BMM350_OTP_ADDR.MAG_TCS_Z] & 0xFF00) >> 8;

        this._tcs.x = fixSign(tcsX, 8) / 16384.0;
        this._tcs.y = fixSign(tcsY, 8) / 16384.0;
        this._tcs.z = fixSign(tcsZ, 8) / 16384.0;

        // ── Reference temperature T0 ──
        const t0Raw = d[BMM350_OTP_ADDR.MAG_DUT_T_0];
        this._dutT0 = fixSign(t0Raw, 16) / 512.0 + 23.0;

        // ── Cross-axis sensitivity ──
        const crossXY = d[BMM350_OTP_ADDR.CROSS_X_Y] & 0x00FF;
        const crossYX = (d[BMM350_OTP_ADDR.CROSS_Y_X] & 0xFF00) >> 8;
        const crossZX = d[BMM350_OTP_ADDR.CROSS_Z_X] & 0x00FF;
        const crossZY = (d[BMM350_OTP_ADDR.CROSS_Z_Y] & 0xFF00) >> 8;

        this._cross.xY = fixSign(crossXY, 8) / 800.0;
        this._cross.yX = fixSign(crossYX, 8) / 800.0;
        this._cross.zX = fixSign(crossZX, 8) / 800.0;
        this._cross.zY = fixSign(crossZY, 8) / 800.0;
    }

    // ── Data Readout ─────────────────────────────────────────────────────

    async isDataReady() {
        const data = await this._readReg(BMM350_REG.INT_STATUS, 1);
        return (data[0] & 0x01) !== 0;
    }

    /**
     * Read raw 24-bit magnetic + temperature data.
     * @returns {{ xRaw: number, yRaw: number, zRaw: number, tRaw: number }}
     */
    async readRawData() {
        const raw = await this._readReg(BMM350_REG.MAG_X_XLSB, BMM350_DATA_LEN);
        return this._parseRaw(raw);
    }

    _parseRaw(raw) {
        const xRaw = raw[0] | (raw[1] << 8) | (raw[2] << 16);
        const yRaw = raw[3] | (raw[4] << 8) | (raw[5] << 16);
        const zRaw = raw[6] | (raw[7] << 8) | (raw[8] << 16);
        const tRaw = raw[9] | (raw[10] << 8) | (raw[11] << 16);

        return {
            xRaw: fixSign(xRaw, 24),
            yRaw: fixSign(yRaw, 24),
            zRaw: fixSign(zRaw, 24),
            tRaw: fixSign(tRaw, 24),
        };
    }

    /**
     * Convert raw bytes to μT and °C.
     * @param {Uint8Array} raw - 12 bytes from MAG_X_XLSB
     * @param {boolean} [compensated=false] - Apply OTP compensation
     * @returns {{ x: number, y: number, z: number, temperature: number, xRaw: number, ... }}
     */
    _convertRaw(raw, compensated = false) {
        const { xRaw, yRaw, zRaw, tRaw } = this._parseRaw(raw);

        let x = xRaw * BMM350_LSB_TO_UT_XY;
        let y = yRaw * BMM350_LSB_TO_UT_XY;
        let z = zRaw * BMM350_LSB_TO_UT_Z;
        let temp = tRaw * BMM350_LSB_TO_DEGC - BMM350_TEMP_OFFSET;

        if (compensated && this._otpLoaded) {
            temp = (1 + this._sensit.tSens) * temp + this._offset.tOffs;

            let axes = [x, y, z];
            const offset = [this._offset.x, this._offset.y, this._offset.z];
            const sensit = [this._sensit.x, this._sensit.y, this._sensit.z];
            const tco    = [this._tco.x,    this._tco.y,    this._tco.z];
            const tcs    = [this._tcs.x,    this._tcs.y,    this._tcs.z];

            for (let i = 0; i < 3; i++) {
                axes[i] *= (1 + sensit[i]);
                axes[i] += offset[i];
                axes[i] += tco[i] * (temp - this._dutT0);
                axes[i] /= (1 + tcs[i] * (temp - this._dutT0));
            }

            x = axes[0]; y = axes[1]; z = axes[2];

            const cxy = this._cross.xY;
            const cyx = this._cross.yX;
            const czx = this._cross.zX;
            const czy = this._cross.zY;
            const det = 1 - cyx * cxy;

            const xComp = (x - cxy * y) / det;
            const yComp = (y - cyx * x) / det;
            const zComp = z + (
                x * (cyx * czy - czx) - y * (czy - cxy * czx)
            ) / det;

            x = xComp; y = yComp; z = zComp;
        }

        return { x, y, z, temperature: temp, xRaw, yRaw, zRaw, tRaw };
    }

    /**
     * Backward-compatible readMagData — returns plain dict.
     * Prefer readData() which returns BMM350Data.
     *
     * @param {boolean} [compensated=false]
     * @returns {{ x: number, y: number, z: number, temperature: number, xRaw: number, ... }}
     */
    async readMagData(compensated = false) {
        const raw = await this._readReg(BMM350_REG.MAG_X_XLSB, BMM350_DATA_LEN);
        return this._convertRaw(raw, compensated);
    }

    // ── Utility ───────────────────────────────────────────────────────────

    async readErrorStatus() {
        const data = await this._readReg(BMM350_REG.ERR_STAT, 1);
        return data[0];
    }

    get otpLoaded() { return this._otpLoaded; }
    get otpData() { return this._otpData; }
}


// ── Backward-compatible alias ─────────────────────────────────────────────

export const BMM350 = BMM350Driver;
/** Alias for backward compatibility. Prefer BMM350Driver in new code. */