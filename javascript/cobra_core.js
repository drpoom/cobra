/**
 * COBRA: COines BRidge Access — Core Protocol Layer (JavaScript/WebSerial)
 *
 * Implements the COINES V3 binary protocol over WebSerial API.
 * See ../core/PROTOCOL.md for the language-agnostic specification.
 *
 * Usage:
 *   const bridge = new CobraBridge();
 *   await bridge.connect();
 *   const chipId = await bridge.i2cRead(0x14, 0x00, 1);
 *   console.log(`Chip ID: 0x${chipId[0].toString(16).padStart(2, '0')}`);
 *   bridge.disconnect();
 */

import {
    HEADER, TYPE_GET, TYPE_SET,
    CMD_I2C_READ, CMD_I2C_WRITE,
    CMD_SPI_READ, CMD_SPI_WRITE,
    CMD_GET_BOARD_INFO, CMD_SET_VDD, CMD_SET_VDDIO,
    STATUS_OK,
    I2C_SPEED_400K, I2C_SPEED_1M,
    SPI_SPEED_5MHZ, SPI_SPEED_10MHZ,
    SPI_MODE_0, SPI_MODE_3,
} from './cobra_constants.js';


export class CobraBridge {
    constructor() {
        this.port = null;
        this.reader = null;
        this.writer = null;
        this.readableStream = null;
        this.writableStream = null;
    }

    // ── Connection ──────────────────────────────────────────────────────

    async connect(baudRate = 115200) {
        this.port = await navigator.serial.requestPort();
        await this.port.open({ baudRate });
        this.readableStream = this.port.readable.getReader();
        this.writableStream = this.port.writable.getWriter();
    }

    async disconnect() {
        if (this.readableStream) { await this.readableStream.cancel(); this.readableStream = null; }
        if (this.writableStream) { await this.writableStream.close(); this.writableStream = null; }
        if (this.port) { await this.port.close(); this.port = null; }
    }

    get connected() { return this.port !== null; }

    // ── Low-Level Protocol (core/PROTOCOL.md §1) ─────────────────────

    static checksum(data) {
        let xor = 0;
        for (const b of data) xor ^= b;
        return xor;
    }

    buildPacket(type, command, payload = new Uint8Array(0)) {
        const length = payload.length;
        const frame = new Uint8Array(5 + length + 1);
        frame[0] = HEADER;
        frame[1] = type;
        frame[2] = command;
        frame[3] = length & 0xFF;
        frame[4] = (length >> 8) & 0xFF;
        frame.set(payload, 5);
        let xor = 0;
        for (let i = 0; i < 5 + length; i++) xor ^= frame[i];
        frame[5 + length] = xor;
        return frame;
    }

    async sendPacket(type, command, payload = new Uint8Array(0)) {
        const pkt = this.buildPacket(type, command, payload);
        await this.writableStream.write(pkt);
    }

    async receivePacket(timeout = 2000) {
        const deadline = Date.now() + timeout;
        const buf = [];

        // 1. Wait for 0xAA
        while (Date.now() < deadline) {
            const { value } = await this.readableStream.read();
            if (!value) continue;
            for (const b of value) {
                buf.push(b);
                if (b === HEADER && buf.length === 1) break;
            }
            if (buf.length === 1 && buf[0] === HEADER) break;
        }
        if (buf.length === 0 || buf[0] !== HEADER) throw new Error('No header');

        // Helper: read N bytes
        const readN = async (n) => {
            while (buf.length < n + 1) { // +1 for header already read
                const { value } = await this.readableStream.read();
                if (value) for (const b of value) buf.push(b);
            }
            return buf.slice(1, 1 + n); // skip header
        };

        // 2. Read header rest
        const headerBytes = await readN(4);
        const ptype = headerBytes[0];
        const command = headerBytes[1];
        const length = headerBytes[2] | (headerBytes[3] << 8);

        // 3. Read payload + checksum
        while (buf.length < 5 + length + 2) { // header + 4 + payload + checksum
            const { value } = await this.readableStream.read();
            if (value) for (const b of value) buf.push(b);
        }

        const payload = new Uint8Array(buf.slice(5, 5 + length));
        const receivedXor = buf[5 + length];

        // 5. Verify checksum
        const frame = new Uint8Array(buf.slice(0, 5 + length));
        const expectedXor = CobraBridge.checksum(frame);
        if (expectedXor !== receivedXor) {
            throw new Error(`Checksum mismatch: 0x${expectedXor.toString(16)} vs 0x${receivedXor.toString(16)}`);
        }

        // 6. Extract status and data
        const status = payload.length > 0 ? payload[0] : STATUS_OK;
        const data = payload.length > 1 ? payload.slice(1) : new Uint8Array(0);

        // Clear buffer
        buf.length = 0;

        return { type: ptype, command, status, data };
    }

    async transact(type, command, payload = new Uint8Array(0), timeout = 2000) {
        await this.sendPacket(type, command, payload);
        const resp = await this.receivePacket(timeout);
        return { status: resp.status, data: resp.data };
    }

    // ── I2C Operations (core/PROTOCOL.md §3) ──────────────────────────

    async i2cWrite(devAddr, regAddr, data, speed = I2C_SPEED_400K) {
        const payload = new Uint8Array([devAddr, speed, regAddr, data.length, ...data]);
        const { status } = await this.transact(TYPE_SET, CMD_I2C_WRITE, payload);
        return status;
    }

    async i2cRead(devAddr, regAddr, length, speed = I2C_SPEED_400K) {
        const payload = new Uint8Array([devAddr, speed, regAddr, length]);
        const { status, data } = await this.transact(TYPE_GET, CMD_I2C_READ, payload);
        if (status !== STATUS_OK) throw new Error(`I2C read failed: 0x${status.toString(16)}`);
        return data;
    }

    // ── SPI Operations (core/PROTOCOL.md §4) ──────────────────────────

    async spiWrite(csLine, regAddr, data, speed = SPI_SPEED_5MHZ, mode = SPI_MODE_0) {
        const payload = new Uint8Array([csLine, speed, mode, regAddr, data.length, ...data]);
        const { status } = await this.transact(TYPE_SET, CMD_SPI_WRITE, payload);
        return status;
    }

    async spiRead(csLine, regAddr, length, speed = SPI_SPEED_5MHZ, mode = SPI_MODE_0) {
        const payload = new Uint8Array([csLine, speed, mode, regAddr, length]);
        const { status, data } = await this.transact(TYPE_GET, CMD_SPI_READ, payload);
        if (status !== STATUS_OK) throw new Error(`SPI read failed: 0x${status.toString(16)}`);
        return data;
    }

    // ── Board Control (core/PROTOCOL.md §5) ──────────────────────────

    async getBoardInfo() {
        const { status, data } = await this.transact(TYPE_GET, CMD_GET_BOARD_INFO);
        if (status !== STATUS_OK) throw new Error('Board info failed');
        return { raw: data, boardId: data[0] | (data[1] << 8) };
    }

    async setVdd(voltageMv) {
        const lo = voltageMv & 0xFF, hi = (voltageMv >> 8) & 0xFF;
        const { status } = await this.transact(TYPE_SET, CMD_SET_VDD, new Uint8Array([lo, hi]));
        return status;
    }

    async setVddio(voltageMv) {
        const lo = voltageMv & 0xFF, hi = (voltageMv >> 8) & 0xFF;
        const { status } = await this.transact(TYPE_SET, CMD_SET_VDDIO, new Uint8Array([lo, hi]));
        return status;
    }
}