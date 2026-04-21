/**
 * COBRA Sensor Driver Base — JavaScript
 *
 * Abstract base class for all Bosch sensor drivers.
 * Every sensor driver must extend SensorDriver and implement
 * the abstract methods: init(), softReset(), getChipId(),
 * selfTest(), configure(), and readData().
 *
 * SensorData is the base class for sensor readings — subclasses
 * add sensor-specific fields (e.g., BMM350Data adds x, y, z, temperature).
 *
 * Usage:
 *   import { SensorDriver, SensorData } from 'cobra-bridge/drivers/base';
 *   const sensor = new BMM350Driver(board, { interface: 'i2c', bus: 0 });
 *   await sensor.setupBoard();
 *   await sensor.init();
 *   const data = await sensor.readData();
 *   console.log(`X=${data.x.toFixed(2)} Y=${data.y.toFixed(2)} Z=${data.z.toFixed(2)} μT`);
 */


// ── SensorData ────────────────────────────────────────────────────────────

export class SensorData {
    /**
     * Base sensor data container.
     *
     * Subclasses add sensor-specific fields:
     *   class BMM350Data extends SensorData {
     *     x = 0; y = 0; z = 0; temperature = 0;
     *   }
     *
     * @param {Object} raw - Raw register values (e.g., { xRaw: 123, yRaw: -456 })
     * @param {number|null} timestamp - Optional timestamp in seconds
     */
    constructor(raw = {}, timestamp = null) {
        this.raw = raw;
        this.timestamp = timestamp;
    }
}


// ── SensorDriver ───────────────────────────────────────────────────────────

export class SensorDriver {
    /**
     * Abstract base class for all Bosch sensor drivers.
     *
     * Subclasses must define:
     *   - Static properties: name, chipId, i2cAddr (minimum)
     *   - Methods: init(), softReset(), getChipId(), selfTest(),
     *     configure(), readData()
     *
     * The driver receives a CobraBoardJs instance and uses its
     * board-level methods for I2C/SPI communication, power control,
     * and pin configuration.
     *
     * @param {Object} board - CobraBoardJs instance
     * @param {Object} [options]
     * @param {string} [options.interface='i2c'] - 'i2c' or 'spi'
     * @param {number} [options.bus=0] - Bus number (0 or 1)
     * @param {number} [options.addr] - Device address. If omitted, uses class default.
     */

    // ── Class-level metadata (override in subclass) ─────────────────────

    static name = '';
    /** Sensor name (e.g., 'bmm350', 'bma456'). */

    static chipId = 0;
    /** Expected chip ID value (e.g., 0x33 for BMM350). */

    static i2cAddr = 0;
    /** Default I2C address (7-bit, e.g., 0x14 for BMM350). */

    static spiReadCmd = 0x80;
    /** SPI read bit mask (sensor-specific). */

    static spiWriteCmd = 0x00;
    /** SPI write bit mask (sensor-specific). */

    // ── Constructor ──────────────────────────────────────────────────────

    constructor(board, { interface: iface = 'i2c', bus = 0, addr } = {}) {
        if (new.target === SensorDriver) {
            throw new TypeError('SensorDriver is abstract and cannot be instantiated directly');
        }
        this.board = board;
        this.interface = iface;
        this.bus = bus;
        this.addr = addr ?? this.constructor.i2cAddr;
    }

    // ── Abstract methods (must be implemented by subclass) ───────────────

    async init(/** ...kwargs */) {
        /**
         * Full sensor-level initialization sequence.
         * Typically: soft reset → verify chip ID → read OTP → configure defaults.
         * @abstract
         */
        throw new Error('init() must be implemented by subclass');
    }

    async softReset() {
        /** Send soft reset command. @abstract @returns {number} Status code (0 = success) */
        throw new Error('softReset() must be implemented by subclass');
    }

    async getChipId() {
        /** Read and return chip ID register. @abstract @returns {number} Chip ID value */
        throw new Error('getChipId() must be implemented by subclass');
    }

    async selfTest() {
        /** Run built-in self test. @abstract @returns {boolean} True if passed */
        throw new Error('selfTest() must be implemented by subclass');
    }

    async configure(/** settings */) {
        /** Apply sensor configuration (ODR, range, averaging, etc.). @abstract */
        throw new Error('configure() must be implemented by subclass');
    }

    async readData() {
        /** Read sensor data and return parsed result. @abstract @returns {SensorData} */
        throw new Error('readData() must be implemented by subclass');
    }

    // ── Concrete methods ─────────────────────────────────────────────────

    async verifyChipId() {
        /**
         * Verify sensor is present by checking chip ID.
         * @returns {boolean} True if chip ID matches expected value.
         */
        return (await this.getChipId()) === this.constructor.chipId;
    }

    toString() {
        const cls = this.constructor;
        return `${cls.name}(name=${cls.name}, addr=0x${this.addr.toString(16).padStart(2, '0')}, interface=${this.interface}, bus=${this.bus})`;
    }
}