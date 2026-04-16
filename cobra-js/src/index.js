/**
 * COBRA.js — COines BRidge Access for JavaScript
 *
 * Transport-agnostic Bosch AppBoard protocol library.
 * Supports WebSerial (USB) and WebBluetooth (BLE).
 *
 * Quick start:
 *   import { SerialTransport, CobraBridge } from 'cobra-js';
 *   const transport = new SerialTransport();
 *   const bridge = new CobraBridge(transport);
 *   await bridge.connect();
 */

export { CobraBridge } from './sync.js';
export { SerialTransport, BleTransport } from './transport.js';
export * from './constants.js';