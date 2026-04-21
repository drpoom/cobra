/**
 * COBRA.js — COines BRidge Access for JavaScript
 *
 * Transport-agnostic Bosch AppBoard protocol library.
 * Supports WebSerial (USB) and WebBluetooth (BLE).
 *
 * Quick start:
 *   import { SerialTransport, CobraBridge } from 'cobra-bridge';
 *   const transport = new SerialTransport();
 *   const bridge = new CobraBridge(transport);
 *   await bridge.connect();
 */

export { CobraBridge } from './sync.js';
export { SerialTransport, BleTransport } from './transport.js';
export * from './constants.js';

// ── Driver framework ─────────────────────────────────────────────────────

export { SensorDriver, SensorData } from './drivers/base.js';
export { fixSign } from './drivers/utils.js';
export { BMM350Driver, BMM350Data, BMM350 } from './drivers/bmm350.js';

/** Package version — kept in sync with package.json */
export const VERSION = '0.2.0';