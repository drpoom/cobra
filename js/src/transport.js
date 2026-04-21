/**
 * COBRA: Transport Abstraction Layer (JavaScript)
 *
 * Provides a unified interface for Serial (WebSerial) and BLE (WebBluetooth)
 * backends. Only send() and receive() change based on connection type;
 * packet framing (CobraBridge.buildPacket / receivePacket) and BMM350
 * driver logic remain identical regardless of transport.
 *
 * Architecture:
 *     ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
 *     │  BMM350     │────▶│  CobraBridge │────▶│  Transport  │
 *     │  Driver     │     │  (Packetizer)│     │  (I/O)      │
 *     └─────────────┘     └──────────────┘     └─────────────┘
 *                                                 │
 *                                     ┌───────────┴───────────┐
 *                                     │                       │
 *                               ┌─────┴─────┐          ┌──────┴──────┐
 *                               │  Serial   │          │    BLE      │
 *                               │ Transport │          │  Transport  │
 *                               │(WebSerial)│          │(WebBluetooth)│
 *                               └───────────┘          └─────────────┘
 *
 * The AppBoard 3.1 uses Nordic UART Service (NUS) over BLE:
 *   - Service UUID:    6e400001-b5a3-f393-e0a9-e50e24dcca9e
 *   - RX (write):      6e400002-b5a3-f393-e0a9-e50e24dcca9e
 *   - TX (notify):     6e400003-b5a3-f393-e0a9-e50e24dcca9e
 *
 * COINES V3 packets travel as raw bytes over NUS — same framing,
 * same checksums, same protocol. Only the transport layer differs.
 */

// ── Nordic UART Service UUIDs ──────────────────────────────────────────

export const NUS_SERVICE_UUID  = '6e400001-b5a3-f393-e0a9-e50e24dcca9e';
export const NUS_RX_CHAR_UUID  = '6e400002-b5a3-f393-e0a9-e50e24dcca9e';
export const NUS_TX_CHAR_UUID  = '6e400003-b5a3-f393-e0a9-e50e24dcca9e';
export const GATT_WRITE_LEN    = 20;  // Safe BLE GATT write chunk size


// ── Serial Transport (WebSerial API) ────────────────────────────────────

export class SerialTransport {
    constructor(baudRate = 115200) {
        this.baudRate = baudRate;
        this.port = null;
        this._reader = null;
        this._writer = null;
        this._readBuffer = new Uint8Array(0);
        this._type = 'serial';
    }

    get transportType() { return 'serial'; }

    async connect() {
        if (!('serial' in navigator)) {
            throw new Error('WebSerial not supported. Use Chrome 89+ or Edge 89+.');
        }
        this.port = await navigator.serial.requestPort();
        await this.port.open({ baudRate: this.baudRate });
        this._writer = this.port.writable.getWriter();
        this._readBuffer = new Uint8Array(0);
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

    async send(data) {
        if (!this._writer) throw new Error('SerialTransport: not connected');
        await this._writer.write(data);
    }

    async receive(count, timeout = 2000) {
        if (!this.port) throw new Error('SerialTransport: not connected');
        const deadline = Date.now() + timeout;

        while (this._readBuffer.length < count && Date.now() < deadline) {
            const reader = await this._ensureReader();
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

        if (this._readBuffer.length < count) {
            throw new Error(`SerialTransport: read timeout (wanted ${count}, got ${this._readBuffer.length})`);
        }

        const result = this._readBuffer.slice(0, count);
        this._readBuffer = this._readBuffer.slice(count);
        return result;
    }

    async _ensureReader() {
        if (!this._reader && this.port?.readable) {
            this._reader = this.port.readable.getReader();
        }
        return this._reader;
    }
}


// ── BLE Transport (WebBluetooth API) ────────────────────────────────────

export class BleTransport {
    /**
     * BLE transport using Nordic UART Service (NUS).
     *
     * The AppBoard 3.1 exposes COINES V3 protocol over BLE NUS.
     * Packets are identical — only the transport changes.
     *
     * Usage:
     *   const transport = new BleTransport();
     *   await transport.connect();  // Opens WebBluetooth picker
     *   // ... use with CobraBridge ...
     *   await transport.disconnect();
     */

    constructor() {
        this.device = null;
        this.server = null;
        this._rxChar = null;   // Write characteristic
        this._txChar = null;   // Notify characteristic
        this._readBuffer = new Uint8Array(0);
        this._type = 'ble';
    }

    get transportType() { return 'ble'; }

    async connect() {
        if (!('bluetooth' in navigator)) {
            throw new Error('WebBluetooth not supported. Use Chrome 56+ with flags enabled.');
        }

        // Request device with NUS service filter
        this.device = await navigator.bluetooth.requestDevice({
            filters: [{ services: [NUS_SERVICE_UUID] }],
            optionalServices: [NUS_SERVICE_UUID]
        });

        // Connect to GATT server
        this.server = await this.device.gatt.connect();

        // Get NUS service and characteristics
        const service = await this.server.getPrimaryService(NUS_SERVICE_UUID);
        this._rxChar = await service.getCharacteristic(NUS_RX_CHAR_UUID);
        this._txChar = await service.getCharacteristic(NUS_TX_CHAR_UUID);

        // Subscribe to TX notifications
        await this._txChar.startNotifications();
        this._txChar.addEventListener('characteristicvaluechanged', (event) => {
            const value = event.target.value;
            const data = new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
            const prev = this._readBuffer;
            const next = new Uint8Array(prev.length + data.length);
            next.set(prev, 0);
            next.set(data, prev.length);
            this._readBuffer = next;
        });

        this._readBuffer = new Uint8Array(0);
    }

    async disconnect() {
        if (this._txChar) {
            try { await this._txChar.stopNotifications(); } catch (e) { /* ignore */ }
            this._txChar = null;
        }
        if (this.server) {
            this.server.disconnect();
            this.server = null;
        }
        this._rxChar = null;
        this.device = null;
        this._readBuffer = new Uint8Array(0);
    }

    get connected() { return this.server !== null && this.server.connected; }

    async send(data) {
        if (!this._rxChar) throw new Error('BleTransport: not connected');

        // BLE GATT has limited MTU — chunk writes to 20 bytes
        for (let i = 0; i < data.length; i += GATT_WRITE_LEN) {
            const chunk = data.slice(i, Math.min(i + GATT_WRITE_LEN, data.length));
            await this._rxChar.writeValue(chunk);
        }
    }

    async receive(count, timeout = 2000) {
        if (!this.connected) throw new Error('BleTransport: not connected');

        const deadline = Date.now() + timeout;

        // Wait until we have enough bytes or timeout
        while (this._readBuffer.length < count && Date.now() < deadline) {
            await new Promise(resolve => setTimeout(resolve, 5)); // 5ms poll
        }

        if (this._readBuffer.length < count) {
            throw new Error(`BleTransport: read timeout (wanted ${count}, got ${this._readBuffer.length})`);
        }

        const result = this._readBuffer.slice(0, count);
        this._readBuffer = this._readBuffer.slice(count);
        return result;
    }

    /**
     * Check if WebBluetooth is available in the current browser.
     */
    static isAvailable() {
        return 'bluetooth' in navigator;
    }

    /**
     * Scan for AppBoard BLE devices (optional pre-filter).
     * Returns array of { name, id } objects.
     */
    static async scan() {
        if (!('bluetooth' in navigator)) {
            throw new Error('WebBluetooth not supported');
        }
        const device = await navigator.bluetooth.requestDevice({
            filters: [{ services: [NUS_SERVICE_UUID] }],
            optionalServices: [NUS_SERVICE_UUID]
        });
        return { name: device.name, id: device.id };
    }
}