# cobra-bridge

**COines BRidge Access** — Bosch AppBoard protocol for JavaScript

Transport-agnostic library for the Bosch Sensortec Application Board 3.1+.
Supports WebSerial (USB) and WebBluetooth (BLE) backends with identical protocol logic.

## Install

```bash
npm install cobra-bridge
```

## Quick Start

```javascript
import { SerialTransport, BleTransport, CobraBridge } from 'cobra-bridge';

// USB-Serial
const transport = new SerialTransport();
const bridge = new CobraBridge(transport);
await bridge.connect();

// BLE
// const transport = new BleTransport();
// const bridge = new CobraBridge(transport);
// await bridge.connect();

const chipId = await bridge.i2cRead(0x14, 0x00, 1);
console.log(`Chip ID: 0x${chipId[0].toString(16).padStart(2, '0')}`);

await bridge.disconnect();
```

## Platform-Specific Setup

### Linux (Chrome/Edge)

```bash
# WebSerial requires a browser — no system-level setup needed
# For Node.js, use the serialport package (see Advanced below)

# USB device permission (add yourself to dialout group):
sudo usermod -aG dialout $USER
# Log out and back in for changes to take effect
```

### macOS (Chrome/Edge)

```javascript
// WebSerial works out of the box
// macOS auto-detects USB-Serial devices
// No additional drivers needed for most boards
```

### Windows (Chrome/Edge)

```javascript
// WebSerial works out of the box
// If prompted, install the USB driver from Bosch or the CH340/CP210x driver
// Check Device Manager → Ports (COM & LPT) for the COM port number
```

## Browser Dashboard

Open `dashboard.html` in Chrome/Edge. Supports both USB (WebSerial) and BLE (WebBluetooth).

## License

MIT