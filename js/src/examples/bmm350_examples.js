/**
 * COBRA BMM350 Examples — JavaScript port of Bosch BMM350_SensorAPI examples
 *
 * Mirrors the official C examples from:
 *   https://github.com/boschsensortec/BMM350_SensorAPI/tree/main/examples
 *
 * Each example is an async function. Call from browser console or the
 * companion dashboard (bmm350_examples.html).
 *
 * Usage (browser console):
 *   const ex = await BMM350Examples.connect();
 *   await ex.chipId();
 *   await ex.polling({ count: 20 });
 *   await ex.normalMode({ odr: 100, count: 30 });
 *   await ex.forcedMode({ count: 10 });
 *   await ex.selfTest();
 *   await ex.magneticReset({ count: 20 });
 *   await ex.configChanges({ count: 20 });
 *   await ex.disconnect();
 */

import { SerialTransport } from '../transport.js';
import { CobraBridge } from '../sync.js';
import { CobraBoardJs } from '../cobra_wrapper.js';
import { BMM350Driver } from '../drivers/bmm350.js';
import { BMM350_REG, BMM350_PMU } from '../drivers/bmm350_constants.js';


// ── Helpers ────────────────────────────────────────────────────────────────

function printHeader(title) {
    console.log(`\n${'━'.repeat(60)}`);
    console.log(`  ${title}`);
    console.log(`${'━'.repeat(60)}`);
}

function printRow(tMs, x, y, z, temp) {
    console.log(`${tMs}, ${x.toFixed(4)}, ${y.toFixed(4)}, ${z.toFixed(4)}, ${temp.toFixed(4)}`);
}

function calculateNoise(samples, avgX, avgY, avgZ) {
    const n = samples.length;
    if (n < 2) return;

    let varX = 0, varY = 0, varZ = 0;
    for (const s of samples) {
        varX += (s.x - avgX) ** 2;
        varY += (s.y - avgY) ** 2;
        varZ += (s.z - avgZ) ** 2;
    }
    varX /= (n - 1);
    varY /= (n - 1);
    varZ /= (n - 1);

    console.log(`\n  Noise (σ):  X=${Math.sqrt(varX).toFixed(4)}  Y=${Math.sqrt(varY).toFixed(4)}  Z=${Math.sqrt(varZ).toFixed(4)} μT`);
}

async function waitForDataReady(sensor, timeout = 1000) {
    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {
        if (await sensor.isDataReady()) return true;
        await new Promise(r => setTimeout(r, 1));
    }
    return false;
}

function delay(ms) {
    return new Promise(r => setTimeout(r, ms));
}


// ── BMM350Examples class ──────────────────────────────────────────────────

export class BMM350Examples {
    constructor() {
        this.board = null;
        this.sensor = null;
        this.bridge = null;
    }

    /**
     * Connect to AppBoard via WebSerial and initialize BMM350.
     * Must be called from a user gesture (click) context.
     */
    async connect() {
        printHeader('Connecting to AppBoard');

        const transport = new SerialTransport();
        this.bridge = new CobraBridge(transport);
        await this.bridge.connect();
        console.log('  ✓ Connected via WebSerial');

        this.board = new CobraBoardJs();
        // Wire up the transport for CobraBoardJs
        this.board._transport._activeTransport = transport;
        this.board._bridge = this.bridge;

        this.sensor = new BMM350Driver(this.board, { interface: 'i2c', bus: 0 });
        await this.sensor.setupBoard();
        await this.sensor.init();

        const chipId = await this.sensor.getChipId();
        console.log(`  Chip ID: 0x${chipId.toString(16).padStart(2, '0')} ${chipId === 0x33 ? '✓' : '✗'}`);

        return this;
    }

    async disconnect() {
        if (this.bridge) {
            await this.bridge.disconnect();
            console.log('  Disconnected');
        }
    }

    // ── chip-id ──────────────────────────────────────────────────────────

    async chipId() {
        printHeader('BMM350 Chip ID Verification');

        const chipId = await this.sensor.getChipId();
        console.log(`  Chip ID: 0x${chipId.toString(16).padStart(2, '0')}`);
        console.log(chipId === 0x33 ? '  ✓ BMM350 confirmed' : '  ✗ Expected 0x33');

        const pm = await this.sensor.getPowerMode();
        console.log(`  Power mode: ${pm}`);

        const err = await this.sensor.readErrorStatus();
        console.log(`  Error register: 0x${err.toString(16).padStart(2, '0')}`);

        console.log(`  OTP loaded: ${this.sensor.otpLoaded}`);
    }

    // ── polling ──────────────────────────────────────────────────────────

    async polling({ odr = 100, count = 10, compensated = false } = {}) {
        printHeader('BMM350 Polling Read');

        await this.sensor.enableAxes(true, true, true);
        await this.sensor.setOdr(odr, 'low_power');
        await this.sensor.setPowerMode('normal');
        await delay(50);

        // Phase 1: Delay-based polling
        console.log(`\n  Delay-based polling @ ${odr} Hz, ${count} samples`);
        console.log('  Timestamp(ms), Mag_X(uT), Mag_Y(uT), Mag_Z(uT), Temperature(degC)');

        let t0 = Date.now();
        for (let i = 0; i < count; i++) {
            await delay(1000 / odr);
            const data = await this.sensor.readData(compensated);
            printRow(Date.now() - t0, data.x, data.y, data.z, data.temperature);
        }

        // Phase 2: INT_STATUS polling
        console.log(`\n  INT_STATUS polling @ ${odr} Hz, ${count} samples`);
        console.log('  Timestamp(ms), Mag_X(uT), Mag_Y(uT), Mag_Z(uT), Temperature(degC)');

        t0 = Date.now();
        for (let i = 0; i < count; i++) {
            if (await waitForDataReady(this.sensor)) {
                const data = await this.sensor.readData(compensated);
                printRow(Date.now() - t0, data.x, data.y, data.z, data.temperature);
            }
        }
    }

    // ── normal-mode ──────────────────────────────────────────────────────

    async normalMode({ odr = 100, count = 50, compensated = false } = {}) {
        printHeader('BMM350 Normal Mode');

        const chipId = await this.sensor.getChipId();
        console.log(`\n  Chip ID: 0x${chipId.toString(16).padStart(2, '0')}`);

        // Show OTP coefficients
        if (this.sensor.otpLoaded) {
            console.log('\n  ── OTP Coefficients ──');
            console.log(`  Offset:  X=${this.sensor._offset.x.toFixed(4)}  Y=${this.sensor._offset.y.toFixed(4)}  Z=${this.sensor._offset.z.toFixed(4)}`);
            console.log(`  Sensitivity:  X=${this.sensor._sensit.x.toFixed(6)}  Y=${this.sensor._sensit.y.toFixed(6)}  Z=${this.sensor._sensit.z.toFixed(6)}`);
            console.log(`  TCO:  X=${this.sensor._tco.x.toFixed(4)}  Y=${this.sensor._tco.y.toFixed(4)}  Z=${this.sensor._tco.z.toFixed(4)}`);
            console.log(`  TCS:  X=${this.sensor._tcs.x.toFixed(6)}  Y=${this.sensor._tcs.y.toFixed(6)}  Z=${this.sensor._tcs.z.toFixed(6)}`);
            console.log(`  Cross:  XY=${this.sensor._cross.xY.toFixed(6)}  YX=${this.sensor._cross.yX.toFixed(6)}  ZX=${this.sensor._cross.zX.toFixed(6)}  ZY=${this.sensor._cross.zY.toFixed(6)}`);
            console.log(`  DUT T0: ${this.sensor._dutT0.toFixed(2)} °C`);
        }

        await this.sensor.enableAxes(true, true, true);
        await this.sensor.setOdr(odr, 'low_power');
        await this.sensor.setPowerMode('normal');
        await delay(50);

        // Phase 1: Raw data
        console.log(`\n  Raw magnetometer data @ ${odr} Hz, ${count} samples`);
        console.log('  mag_x_raw, mag_y_raw, mag_z_raw, temp_raw');

        for (let i = 0; i < count; i++) {
            if (await waitForDataReady(this.sensor)) {
                const raw = await this.sensor.readRawData();
                console.log(`  ${raw.xRaw}, ${raw.yRaw}, ${raw.zRaw}, ${raw.tRaw}`);
            }
        }

        // Phase 2: Compensated data
        console.log(`\n  Compensated magnetometer + temperature @ ${odr} Hz, ${count} samples`);
        console.log('  Timestamp(ms), Mag_X(uT), Mag_Y(uT), Mag_Z(uT), Temperature(degC)');

        const t0 = Date.now();
        for (let i = 0; i < count; i++) {
            if (await waitForDataReady(this.sensor)) {
                const data = await this.sensor.readData(compensated);
                printRow(Date.now() - t0, data.x, data.y, data.z, data.temperature);
            }
        }
    }

    // ── forced-mode ──────────────────────────────────────────────────────

    async forcedMode({ count = 10, compensated = false } = {}) {
        printHeader('BMM350 Forced Mode');

        await this.sensor.enableAxes(true, true, true);

        const combinations = [
            ['Forced Fast + AVG_4',          'forced_fast', 'high'],
            ['Forced Fast + AVG_4 (loop)',   'forced_fast', 'high'],
            ['Forced + NO_AVG',              'forced',      'low_power'],
            ['Forced Fast + AVG_4 (batch)',  'forced_fast', 'high'],
            ['Forced + NO_AVG (batch)',      'forced',      'low_power'],
            ['Forced Fast + AVG_2 (batch)',  'forced_fast', 'medium'],
        ];

        for (let ci = 0; ci < combinations.length; ci++) {
            const [label, mode, avg] = combinations[ci];
            console.log(`\n  COMBINATION ${ci + 1}: ${label}`);

            await this.sensor.setOdr(100, avg);
            console.log('  Timestamp(ms), Mag_X(uT), Mag_Y(uT), Mag_Z(uT), Temperature(degC)');

            const samples = [];
            const t0 = Date.now();

            for (let i = 0; i < count; i++) {
                await this.sensor.setPowerMode(mode);
                await delay(10);

                if (await waitForDataReady(this.sensor, 100)) {
                    const data = await this.sensor.readData(compensated);
                    printRow(Date.now() - t0, data.x, data.y, data.z, data.temperature);
                    samples.push({ x: data.x, y: data.y, z: data.z });
                }
            }

            if (samples.length > 0) {
                const avgX = samples.reduce((s, d) => s + d.x, 0) / samples.length;
                const avgY = samples.reduce((s, d) => s + d.y, 0) / samples.length;
                const avgZ = samples.reduce((s, d) => s + d.z, 0) / samples.length;

                console.log('\n  ── Average ──');
                console.log('  Avg_Mag_X(uT), Avg_Mag_Y(uT), Avg_Mag_Z(uT)');
                console.log(`  ${avgX.toFixed(4)}, ${avgY.toFixed(4)}, ${avgZ.toFixed(4)}`);

                calculateNoise(samples, avgX, avgY, avgZ);
            }
        }
    }

    // ── self-test ────────────────────────────────────────────────────────

    async selfTest({ compensated = false } = {}) {
        printHeader('BMM350 Self Test');

        const chipId = await this.sensor.getChipId();
        console.log(`\n  Chip ID: 0x${chipId.toString(16).padStart(2, '0')}`);

        const pm = await this.sensor.getPowerMode();
        console.log(`  Power mode: ${pm}`);

        const err = await this.sensor.readErrorStatus();
        console.log(`  Error register: 0x${err.toString(16).padStart(2, '0')}`);

        await this.sensor.setOdr(100, 'high');
        await this.sensor.setPowerMode('normal');
        await delay(10);

        await this.sensor.enableAxes(true, true, true);

        // Before self-test
        console.log('\n  ── BEFORE SELF TEST ──');
        console.log('  Timestamp(ms), Mag_X(uT), Mag_Y(uT), Mag_Z(uT), Temperature(degC)');

        let t0 = Date.now();
        for (let i = 0; i < 10; i++) {
            await delay(100);
            if (await waitForDataReady(this.sensor, 200)) {
                const data = await this.sensor.readData(compensated);
                printRow(Date.now() - t0, data.x, data.y, data.z, data.temperature);
            }
        }

        // Perform self-test
        console.log('\n  ── SELF TEST ──');
        console.log('  Running BMM350 built-in self test...');

        await this.sensor.setPowerMode('suspend');
        await delay(30);

        console.log('\n  Iteration, Result');
        for (let i = 0; i < 20; i++) {
            const result = await this.sensor.selfTest();
            console.log(`  ${i}, ${result ? 'PASS' : 'FAIL'}`);
            await delay(10);
        }

        // After self-test
        await this.sensor.setPowerMode('normal');
        await this.sensor.setOdr(100, 'high');
        await delay(10);

        console.log('\n  ── AFTER SELF TEST ──');
        console.log('  Timestamp(ms), Mag_X(uT), Mag_Y(uT), Mag_Z(uT), Temperature(degC)');

        t0 = Date.now();
        for (let i = 0; i < 20; i++) {
            await delay(10);
            if (await waitForDataReady(this.sensor, 200)) {
                const data = await this.sensor.readData(compensated);
                printRow(Date.now() - t0, data.x, data.y, data.z, data.temperature);
            }
        }
    }

    // ── magnetic-reset ───────────────────────────────────────────────────

    async magneticReset({ count = 20, compensated = false } = {}) {
        printHeader('BMM350 Magnetic Reset');

        await this.sensor.enableAxes(true, true, true);
        await this.sensor.setOdr(100, 'low_power');
        await this.sensor.setPowerMode('normal');
        await delay(50);

        // Before reset
        console.log(`\n  Before magnetic reset — ${count} samples`);
        console.log('  Timestamp(ms), Mag_X(uT), Mag_Y(uT), Mag_Z(uT), Temperature(degC)');

        const before = [];
        let t0 = Date.now();
        for (let i = 0; i < count; i++) {
            if (await waitForDataReady(this.sensor)) {
                const data = await this.sensor.readData(compensated);
                printRow(Date.now() - t0, data.x, data.y, data.z, data.temperature);
                before.push(data);
            }
        }

        if (before.length > 0) {
            const avgX = before.reduce((s, d) => s + d.x, 0) / before.length;
            const avgY = before.reduce((s, d) => s + d.y, 0) / before.length;
            const avgZ = before.reduce((s, d) => s + d.z, 0) / before.length;
            const mag = Math.sqrt(avgX ** 2 + avgY ** 2 + avgZ ** 2);
            console.log(`\n  Magnitude before reset: ${mag.toFixed(2)} μT`);
        }

        // Apply magnetic reset (BR → FGR)
        console.log('\n  Applying magnetic reset (BR + FGR)...');
        await this.sensor.setPowerMode('suspend');
        await delay(30);

        await this.sensor._writeReg(BMM350_REG.PMU_CMD, new Uint8Array([BMM350_PMU.BR]));
        await delay(3);
        await this.sensor._writeReg(BMM350_REG.PMU_CMD, new Uint8Array([BMM350_PMU.FGR]));
        await delay(30);

        await this.sensor.setPowerMode('normal');
        await delay(50);

        // After reset
        console.log(`\n  After magnetic reset — ${count} samples`);
        console.log('  Timestamp(ms), Mag_X(uT), Mag_Y(uT), Mag_Z(uT), Temperature(degC)');

        const after = [];
        t0 = Date.now();
        for (let i = 0; i < count; i++) {
            if (await waitForDataReady(this.sensor)) {
                const data = await this.sensor.readData(compensated);
                printRow(Date.now() - t0, data.x, data.y, data.z, data.temperature);
                after.push(data);
            }
        }

        if (after.length > 0) {
            const avgX = after.reduce((s, d) => s + d.x, 0) / after.length;
            const avgY = after.reduce((s, d) => s + d.y, 0) / after.length;
            const avgZ = after.reduce((s, d) => s + d.z, 0) / after.length;
            const mag = Math.sqrt(avgX ** 2 + avgY ** 2 + avgZ ** 2);
            console.log(`\n  Magnitude after reset: ${mag.toFixed(2)} μT`);
        }
    }

    // ── config-changes ───────────────────────────────────────────────────

    async configChanges({ count = 20, compensated = false } = {}) {
        printHeader('BMM350 Configuration Changes');

        await this.sensor.enableAxes(true, true, true);

        const configs = [
            [100, 'low_power', '100 Hz, NO_AVG'],
            [100, 'high',      '100 Hz, AVG_4'],
            [200, 'medium',    '200 Hz, AVG_2'],
            [400, 'low_power', '400 Hz, NO_AVG'],
            [50,  'ultra',     '50 Hz, AVG_8'],
        ];

        for (const [odr, avg, label] of configs) {
            console.log(`\n  ── Config: ${label} ──`);

            await this.sensor.setOdr(odr, avg);
            await this.sensor.setPowerMode('normal');
            await delay(50);

            console.log('  Timestamp(ms), Mag_X(uT), Mag_Y(uT), Mag_Z(uT), Temperature(degC)');

            const samples = [];
            const t0 = Date.now();

            for (let i = 0; i < count; i++) {
                if (await waitForDataReady(this.sensor, 2000)) {
                    const data = await this.sensor.readData(compensated);
                    printRow(Date.now() - t0, data.x, data.y, data.z, data.temperature);
                    samples.push({ x: data.x, y: data.y, z: data.z });
                }
            }

            if (samples.length > 0) {
                const avgX = samples.reduce((s, d) => s + d.x, 0) / samples.length;
                const avgY = samples.reduce((s, d) => s + d.y, 0) / samples.length;
                const avgZ = samples.reduce((s, d) => s + d.z, 0) / samples.length;
                calculateNoise(samples, avgX, avgY, avgZ);
            }

            await this.sensor.setPowerMode('suspend');
            await delay(30);
        }
    }
}


// ── Convenience: one-liner usage ──────────────────────────────────────────

/**
 * Quick connect + run a single example.
 *
 * @param {string} example - 'chip-id', 'polling', 'normal-mode', 'forced-mode',
 *                            'self-test', 'magnetic-reset', 'config-changes'
 * @param {Object} [opts] - Example-specific options
 * @returns {BMM350Examples} The connected instance (call .disconnect() when done)
 *
 * @example
 *   // In browser console (must be triggered by user gesture):
 *   const ex = await BMM350Examples.run('chip-id');
 *   await ex.disconnect();
 *
 *   const ex = await BMM350Examples.run('polling', { odr: 100, count: 20 });
 *   await ex.disconnect();
 */
BMM350Examples.run = async function(example, opts = {}) {
    const ex = new BMM350Examples();
    await ex.connect();

    const map = {
        'chip-id':        () => ex.chipId(),
        'polling':        () => ex.polling(opts),
        'normal-mode':    () => ex.normalMode(opts),
        'forced-mode':    () => ex.forcedMode(opts),
        'self-test':      () => ex.selfTest(opts),
        'magnetic-reset': () => ex.magneticReset(opts),
        'config-changes': () => ex.configChanges(opts),
    };

    const fn = map[example];
    if (fn) {
        await fn();
    } else {
        console.error(`Unknown example: ${example}. Valid: ${Object.keys(map).join(', ')}`);
    }

    return ex;
};