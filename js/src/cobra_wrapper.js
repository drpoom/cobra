/**
 * COBRA Wrapper — JavaScript
 *
 * Provides a drop-in replacement for coinespy-like API in JavaScript.
 * Supports synchronous and asynchronous operations by delegating to underlying
 * CobraBridge and Transport classes.
 */

import { CobraBridge } from './sync.js';
import { SerialTransport, BleTransport } from './transport.js';
import {
    CommInterface, ErrorCodes, PinDirection, PinValue,
    I2CBus, I2CMode, SPIMode, SPISpeed, MultiIOPin, I2CTransferBits, SPITransferBits,
    StreamingMode, StreamingState, TimerConfig, TimerStampConfig,
    PIN_IN, PIN_OUT, PIN_LOW, PIN_HIGH,
    I2C_SPEED_400K,
} from './constants.js';


class CobraTransportJs {
    constructor() {
        this._activeTransport = null;
    }

    async openInterface(interfaceType, serialComConfig = null, bleComConfig = null) {
        if (this._activeTransport && this._activeTransport.connected) {
            return ErrorCodes.COINES_E_COMM_ALREADY_OPEN;
        }

        if (interfaceType === CommInterface.USB.value) {
            if (!serialComConfig || !serialComConfig.comPortName) {
                return ErrorCodes.COINES_E_INVALID_ARGUMENT;
            }
            this._activeTransport = new SerialTransport(serialComConfig.baudRate);
        } else if (interfaceType === CommInterface.BLE.value) {
            if (!bleComConfig || !bleComConfig.address) {
                return ErrorCodes.COINES_E_INVALID_ARGUMENT;
            }
            this._activeTransport = new BleTransport(bleComConfig.address);
        } else if (interfaceType === CommInterface.VIRTUAL.value) {
            console.log('Virtual interface selected. No actual connection.');
            this._activeTransport = null; // Or a mock transport
            return ErrorCodes.COINES_SUCCESS;
        } else {
            return ErrorCodes.COINES_E_INVALID_ARGUMENT;
        }

        if (this._activeTransport) {
            try {
                await this._activeTransport.connect();
                return ErrorCodes.COINES_SUCCESS;
            } catch (e) {
                console.error(`Error opening transport interface: ${e}`);
                this._activeTransport = null;
                return ErrorCodes.COINES_E_COMM_INIT_FAILED;
            }
        }
        return ErrorCodes.COINES_E_COMM_INIT_FAILED;
    }

    async closeInterface(interfaceType) {
        if (this._activeTransport && this._activeTransport.connected) {
            try {
                await this._activeTransport.disconnect();
                this._activeTransport = null;
                return ErrorCodes.COINES_SUCCESS;
            } catch (e) {
                console.error(`Error closing transport interface: ${e}`);
                return ErrorCodes.COINES_E_FAILURE;
            }
        } else if (interfaceType === CommInterface.VIRTUAL.value) {
            console.log('Virtual interface closing. No actual disconnection.');
            this._activeTransport = null;
            return ErrorCodes.COINES_SUCCESS;
        }
        return ErrorCodes.COINES_E_UNABLE_OPEN_DEVICE;
    }

    async writeIntf(interfaceType, data) {
        if (this._activeTransport && this._activeTransport.connected) {
            await this._activeTransport.send(new Uint8Array(data));
        } else {
            console.log('No active transport to write to.');
        }
    }

    async readIntf(interfaceType, length) {
        if (this._activeTransport && this._activeTransport.connected) {
            const readBytes = await this._activeTransport.receive(length);
            return [Array.from(readBytes), readBytes.length];
        } else {
            console.log('No active transport to read from.');
            return [[], 0];
        }
    }
}


export class CobraBoardJs {
    constructor() {
        this._transport = new CobraTransportJs();
        this._bridge = new CobraBridge(this._transport);
        this.error_code = ErrorCodes.COINES_SUCCESS;
        this._sensorDrivers = {};
    }

    async open_comm_interface(interfaceType, serialComConfig = null, bleComConfig = null) {
        this.error_code = await this._transport.openInterface(interfaceType, serialComConfig, bleComConfig);
        return this.error_code;
    }

    async close_comm_interface(interfaceType) {
        this.error_code = await this._transport.closeInterface(interfaceType);
        return this.error_code;
    }

    get_version() {
        return "CobraBoardJs v0.1.0";
    }

    unload_library() {
        console.log("CobraBoardJs library unloaded.");
    }

    async write_intf(interfaceType, data) {
        await this._transport.writeIntf(interfaceType, data);
    }

    async read_intf(interfaceType, length) {
        const [data, n_bytes_read] = await this._transport.readIntf(interfaceType, length);
        return [data, n_bytes_read];
    }

    async config_i2c_bus(bus, i2c_address, i2c_mode) {
        // Delegate to CobraBridge after adapting parameters if necessary
        console.log(`[CobraBoardJs] Configuring I2C bus ${bus}, address ${i2c_address}, mode ${i2c_mode}`);
        // The underlying CobraBridge.i2c_write/read don't have explicit bus config methods.
        // This would require new commands in the COINES protocol for JS.
        // For now, simulate success.
        this.error_code = ErrorCodes.COINES_SUCCESS;
        return this.error_code;
    }

    async deconfig_i2c_bus(bus) {
        console.log(`[CobraBoardJs] Deconfiguring I2C bus ${bus}`);
        this.error_code = ErrorCodes.COINES_SUCCESS;
        return this.error_code;
    }

    async write_i2c(bus, register_address, register_value, sensor_interface_detail = null) {
        const dev_addr = sensor_interface_detail !== null ? sensor_interface_detail : 0; // Default if not provided
        const data = new Uint8Array([register_value]);
        // The existing CobraBridge.i2c_write uses speed as a parameter. Coinespy API doesn't.
        // We'll use a default speed for now, or assume it's configured globally.
        try {
            const status = await this._bridge.i2c_write(dev_addr, register_address, data, I2C_SPEED_400K);
            this.error_code = ErrorCodes.COINES_SUCCESS; // Assuming status is 0 for success
        } catch (e) {
            console.error(`Error in write_i2c: ${e}`);
            this.error_code = ErrorCodes.COINES_E_I2C_READ_WRITE_FAILED;
        }
        return this.error_code;
    }

    async read_i2c(bus, register_address, number_of_reads, sensor_interface_detail = null) {
        const dev_addr = sensor_interface_detail !== null ? sensor_interface_detail : 0; // Default if not provided
        try {
            const data = await this._bridge.i2c_read(dev_addr, register_address, number_of_reads, I2C_SPEED_400K);
            this.error_code = ErrorCodes.COINES_SUCCESS;
            return [Array.from(data), this.error_code];
        } catch (e) {
            console.error(`Error in read_i2c: ${e}`);
            this.error_code = ErrorCodes.COINES_E_I2C_READ_WRITE_FAILED;
            return [[], this.error_code];
        }
    }

    async read_16bit_i2c(bus, register_address, number_of_reads = 2,
                         sensor_interface_detail = null,
                         i2c_transfer_bits = I2CTransferBits.I2C16BIT) {
        console.log(`[CobraBoardJs] Reading 16-bit I2C from bus ${bus}, reg ${register_address}`);
        const [data, error] = await this.read_i2c(bus, register_address, number_of_reads * 2, sensor_interface_detail);
        return data;
    }

    async write_16bit_i2c(bus, register_address, register_value, sensor_interface_detail = null,
                          i2c_transfer_bits = I2CTransferBits.I2C16BIT) {
        console.log(`[CobraBoardJs] Writing 16-bit I2C to bus ${bus}, reg ${register_address}, val ${register_value}`);
        const byte1 = register_value & 0xFF;
        const byte2 = (register_value >> 8) & 0xFF;
        let status = await this.write_i2c(bus, register_address, byte1, sensor_interface_detail);
        if (status === ErrorCodes.COINES_SUCCESS) {
            status = await this.write_i2c(bus, register_address + 1, byte2, sensor_interface_detail);
        }
        return status;
    }

    async config_spi_bus(bus, cs_pin, spi_speed, spi_mode) {
        console.log(`[CobraBoardJs] Configuring SPI bus ${bus}, CS ${cs_pin}, speed ${spi_speed}, mode ${spi_mode}`);
        this.error_code = ErrorCodes.COINES_SUCCESS;
        return this.error_code;
    }

    async deconfig_spi_bus(bus) {
        console.log(`[CobraBoardJs] Deconfiguring SPI bus ${bus}`);
        this.error_code = ErrorCodes.COINES_SUCCESS;
        return this.error_code;
    }

    async custom_spi_config(bus, cs_pin, spi_speed, spi_mode) {
        console.log(`[CobraBoardJs] Custom SPI config for bus ${bus}, CS ${cs_pin}, speed ${spi_speed}, mode ${spi_mode}`);
        return await this.config_spi_bus(bus, cs_pin, spi_speed, spi_mode);
    }

    async write_spi(bus, register_address, register_value, sensor_interface_detail = null) {
        const cs_pin = sensor_interface_detail !== null ? sensor_interface_detail : MultiIOPin.COINES_MINI_SHUTTLE_PIN_CS.value;
        const data = new Uint8Array([register_value]);
        try {
            const status = await this._bridge.spi_write(cs_pin, register_address, data, SPI_SPEED_10MHZ, SPI_MODE_0);
            this.error_code = ErrorCodes.COINES_SUCCESS; // Assuming status is 0 for success
        } catch (e) {
            console.error(`Error in write_spi: ${e}`);
            this.error_code = ErrorCodes.COINES_E_SPI_READ_WRITE_FAILED;
        }
        return this.error_code;
    }

    async read_spi(bus, register_address, number_of_reads, sensor_interface_detail = null) {
        const cs_pin = sensor_interface_detail !== null ? sensor_interface_detail : MultiIOPin.COINES_MINI_SHUTTLE_PIN_CS.value;
        try {
            const data = await this._bridge.spi_read(cs_pin, register_address, number_of_reads, SPI_SPEED_10MHZ, SPI_MODE_0);
            this.error_code = ErrorCodes.COINES_SUCCESS;
            return [Array.from(data), this.error_code];
        } catch (e) {
            console.error(`Error in read_spi: ${e}`);
            this.error_code = ErrorCodes.COINES_E_SPI_READ_WRITE_FAILED;
            return [[], this.error_code];
        }
    }

    async read_16bit_spi(bus, register_address, number_of_reads = 2,
                         sensor_interface_detail = null,
                         spi_transfer_bits = SPITransferBits.SPI16BIT) {
        console.log(`[CobraBoardJs] Reading 16-bit SPI from bus ${bus}, reg ${register_address}`);
        const [data, error] = await this.read_spi(bus, register_address, number_of_reads * 2, sensor_interface_detail);
        return data;
    }

    async write_16bit_spi(bus, register_address, register_value, sensor_interface_detail = null,
                           spi_transfer_bits = SPITransferBits.SPI16BIT) {
        console.log(`[CobraBoardJs] Writing 16-bit SPI to bus ${bus}, reg ${register_address}, val ${register_value}`);
        let status = ErrorCodes.COINES_SUCCESS;
        if (Array.isArray(register_value)) {
            for (const val of register_value) {
                status = await this.write_spi(bus, register_address, val, sensor_interface_detail);
                if (status !== ErrorCodes.COINES_SUCCESS) {
                    break;
                }
            }
        } else {
            status = await this.write_spi(bus, register_address, register_value, sensor_interface_detail);
        }
        return status;
    }

    // ── Board Control (convenience methods for sensor drivers) ───────────

    async setVdd(voltageMv) {
        /** Set VDD voltage in millivolts (0 = off). Returns status code. */
        return await this._bridge.setVdd(voltageMv);
    }

    async setVddio(voltageMv) {
        /** Set VDDIO voltage in millivolts (0 = off). Returns status code. */
        return await this._bridge.setVddio(voltageMv);
    }

    async setPin(pin, direction, value) {
        /** Configure a shuttle board pin. Returns status code. */
        return await this._bridge.setPin(pin, direction, value);
    }

    // ── Sensor-Driver Convenience I/O ────────────────────────────────────

    async i2cReadReg(devAddr, regAddr, length, speed = I2C_SPEED_400K) {
        /** Read `length` bytes from I2C register. Returns Uint8Array. */
        return await this._bridge.i2c_read(devAddr, regAddr, length, speed);
    }

    async i2cWriteReg(devAddr, regAddr, data, speed = I2C_SPEED_400K) {
        /** Write data bytes to I2C register. Returns status byte. */
        return await this._bridge.i2c_write(devAddr, regAddr, data, speed);
    }

    async spiReadReg(csPin, regAddr, length, speed = 1000000, mode = 0) {
        /** Read `length` bytes from SPI register. Returns Uint8Array. */
        return await this._bridge.spi_read(csPin, regAddr, length, speed, mode);
    }

    async spiWriteReg(csPin, regAddr, data, speed = 1000000, mode = 0) {
        /** Write data bytes to SPI register. Returns status byte. */
        return await this._bridge.spi_write(csPin, regAddr, data, speed, mode);
    }

    // ── Sensor Driver Registry ──────────────────────────────────────────

    attachDriver(driver) {
        /** Register a sensor driver instance with this board. */
        this._sensorDrivers[driver.constructor.name] = driver;
    }

    getDriver(name) {
        /** Retrieve a previously attached sensor driver by name. */
        return this._sensorDrivers[name] || null;
    }

    get drivers() {
        /** All attached sensor drivers, keyed by name. */
        return { ...this._sensorDrivers };
    }
}

export { CobraBoardJs as CobraBoard };
export { CobraTransportJs as CobraTransport };