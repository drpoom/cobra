/**
 * COBRA Sync — Synchronous Protocol Bridge (JavaScript)
 *
 * Implements the COINES V3 binary protocol over any Transport backend.
 * Transport-agnostic: works with SerialTransport (WebSerial) or BleTransport (WebBluetooth).
 * Mirrors python cobra_bridge.sync — same packet building/parsing, same API.
 * See core/PROTOCOL.md for the language-agnostic specification.
 *
 * Usage:
 *   import { SerialTransport, BleTransport } from './transport.js';
 *   import { CobraBridge } from './sync.js';
 *
 *   // USB-Serial
 *   const transport = new SerialTransport();
 *   const bridge = new CobraBridge(transport);
 *   await bridge.connect();
 *
 *   // BLE
 *   const transport = new BleTransport();
 *   const bridge = new CobraBridge(transport);
 *   await bridge.connect();
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
} from './constants.js';


export class CobraBridge {
    /**
     * Create a CobraBridge with a transport backend.
     *
     * @param {Object} transport - A transport instance (SerialTransport or BleTransport)
     *   Must implement: connect(), disconnect(), send(data), receive(count, timeout), connected
     */
    constructor(transport) {
        if (!transport) {
            throw new Error('CobraBridge requires a transport. Use SerialTransport or BleTransport.');
        }
        this._transport = transport;
    }

    // ── Connection ──────────────────────────────────────────────────────

    async connect() {
        await this._transport.connect();
    }

    async disconnect() {
        await this._transport.disconnect();
    }

    get connected() { return this._transport.connected; }

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
        if (!this.connected) throw new Error('Not connected');
        const pkt = this.buildPacket(type, command, payload);
        await this._transport.send(pkt);
    }

    async receivePacket(timeout = 2000) {
        if (!this.connected) throw new Error('Not connected');

        const deadline = Date.now() + timeout;

        // 1. Find header 0xAA — skip garbage
        let found = false;
        while (Date.now() < deadline) {
            const buf = await this._transport.receive(1, deadline - Date.now());
            if (buf[0] === HEADER) {
                found = true;
                break;
            }
        }
        if (!found) {
            throw new Error('No header received within timeout');
        }

        // 2. Read rest of header (4 bytes: type, command, len_lo, len_hi)
        const headerRest = await this._transport.receive(4, deadline - Date.now());
        const ptype = headerRest[0];
        const command = headerRest[1];
        const length = headerRest[2] | (headerRest[3] << 8);

        // 3. Read payload + checksum
        const payloadAndXor = await this._transport.receive(length + 1, deadline - Date.now());
        const payload = payloadAndXor.slice(0, length);
        const receivedXor = payloadAndXor[length];

        // 4. Verify checksum
        const frame = new Uint8Array(5 + length);
        frame[0] = HEADER;
        frame[1] = ptype;
        frame[2] = command;
        frame[3] = length & 0xFF;
        frame[4] = (length >> 8) & 0xFF;
        frame.set(payload, 5);
        const expectedXor = CobraBridge.checksum(frame);
        if (expectedXor !== receivedXor) {
            throw new Error(`Checksum mismatch: 0x${expectedXor.toString(16)} vs 0x${receivedXor.toString(16)}`);
        }

        // 5. Extract status (first payload byte) and data
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