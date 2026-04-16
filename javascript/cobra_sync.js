/**
 * COBRA Sync — Synchronous Protocol Bridge (JavaScript/WebSerial)
 *
 * Implements the COINES V3 binary protocol over WebSerial API.
 * Transport-agnostic: works with SerialTransport (WebSerial) or BleTransport (WebBluetooth).
 * Mirrors python/cobra_sync.py — same packet building/parsing, same API.
 * See ../core/PROTOCOL.md for the language-agnostic specification.
 *
 * Usage:
 *   import { CobraBridge } from './cobra_sync.js';
 *   const bridge = new CobraBridge();
 *   await bridge.connect();
 *   const chipId = await bridge.i2cRead(0x14, 0x00, 1);
 *   console.log(`Chip ID: 0x${chipId[0].toString(16).padStart(2, '0')}`);
 *   await bridge.disconnect();
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
        this._reader = null;
        this._writer = null;
        this._readBuffer = new Uint8Array(0);
    }

    // ── Connection ──────────────────────────────────────────────────────

    async connect(baudRate = 115200) {
        if (!('serial' in navigator)) {
            throw new Error('WebSerial not supported. Use Chrome 89+ or Edge 89+.');
        }
        this.port = await navigator.serial.requestPort();
        await this.port.open({ baudRate });
        this._writer = this.port.writable.getWriter();
        // Don't grab reader yet — do it lazily to avoid locking issues
    }

    async disconnect() {
        if (this._reader) {
            await this._reader.cancel().catch(() => {});
            this._reader.releaseLock();
            this._reader = null;
        }
        if (this._writer) {
            await this._writer.close().catch(() => {});
            this._writer = null;
        }
        if (this.port) {
            await this.port.close().catch(() => {});
            this.port = null;
        }
        this._readBuffer = new Uint8Array(0);
    }

    get connected() { return this.port !== null; }

    // ── Internal: read bytes into buffer ───────────────────────────────

    async _ensureReader() {
        if (!this._reader && this.port?.readable) {
            this._reader = this.port.readable.getReader();
        }
        return this._reader;
    }

    async _fillBuffer(needed) {
        const reader = await this._ensureReader();
        while (this._readBuffer.length < needed) {
            const { value, done } = await reader.read();
            if (done) throw new Error('Serial stream closed');
            if (value && value.length > 0) {
                const prev = this._readBuffer;
                const next = new Uint8Array(prev.length + value.length);
                next.set(prev, 0);
                next.set(value, prev.length);
                this._readBuffer = next;
            }
        }
    }

    _consume(n) {
        const consumed = this._readBuffer.slice(0, n);
        this._readBuffer = this._readBuffer.slice(n);
        return consumed;
    }

    // ── Low-Level Protocol (core/PROTOCOL.md §1) ─────────────────────

    static checksum(data) {
        let xor = 0;
        for (let i = 0; i < data.length; i++) xor ^= data[i];
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
        if (!this._writer) throw new Error('Not connected');
        const pkt = this.buildPacket(type, command, payload);
        await this._writer.write(pkt);
    }

    async receivePacket(timeout = 2000) {
        if (!this.port) throw new Error('Not connected');

        const deadline = Date.now() + timeout;

        // 1. Find header 0xAA — skip garbage
        while (Date.now() < deadline) {
            await this._fillBuffer(this._readBuffer.length + 1);
            const idx = this._readBuffer.indexOf(HEADER);
            if (idx >= 0) {
                // Discard bytes before header
                this._consume(idx);
                break;
            }
            // Keep only last byte (might be partial header)
            if (this._readBuffer.length > 1) {
                this._readBuffer = this._readBuffer.slice(-1);
            }
        }
        if (this._readBuffer.length === 0 || this._readBuffer[0] !== HEADER) {
            throw new Error('No header received within timeout');
        }

        // 2. Read rest of header (4 bytes: type, command, len_lo, len_hi)
        await this._fillBuffer(5);
        const ptype = this._readBuffer[1];
        const command = this._readBuffer[2];
        const length = this._readBuffer[3] | (this._readBuffer[4] << 8);

        // 3. Read payload + checksum
        const totalLen = 5 + length + 1; // header(5) + payload(length) + xor(1)
        await this._fillBuffer(totalLen);

        const payload = this._readBuffer.slice(5, 5 + length);
        const receivedXor = this._readBuffer[5 + length];

        // 4. Verify checksum (over header + payload, NOT including xor byte)
        const frame = this._readBuffer.slice(0, 5 + length);
        const expectedXor = CobraBridge.checksum(frame);
        if (expectedXor !== receivedXor) {
            this._consume(1); // Skip bad header byte, try resync
            throw new Error(`Checksum mismatch: 0x${expectedXor.toString(16)} vs 0x${receivedXor.toString(16)}`);
        }

        // 5. Consume full packet from buffer
        this._consume(totalLen);

        // 6. Extract status (first payload byte) and data
        const status = payload.length > 0 ? payload[0] : STATUS_OK;
        const data = payload.length > 1 ? payload.slice(1) : new Uint8Array(0);

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
        const result = { raw: data };
        if (data.length >= 2) {
            result.boardId = data[0] | (data[1] << 8);
        }
        if (data.length >= 6) {
            result.softwareVer = `${data[2]}.${data[3]}`;
            result.hardwareVer = `${data[4]}.${data[5]}`;
        }
        return result;
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