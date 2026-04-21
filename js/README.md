# cobra-bridge

**COines BRidge Access** — Bosch AppBoard protocol for JavaScript

Transport-agnostic library for the Bosch Sensortec Application Board 3.1+.
Supports WebSerial (USB) and WebBluetooth (BLE) backends with identical protocol logic.
Features a **sensor-agnostic driver framework** — add new sensors with just a JSON spec + driver class.

## Install

```bash
npm install cobra-bridge
```

## Quick Start

```javascript
import { SerialTransport, CobraBridge } from 'cobra-bridge';
import { BMM350Driver } from 'cobra-bridge/drivers/bmm350.js';

const transport = new SerialTransport();
const bridge = new CobraBridge(transport);
await bridge.connect();

// Sensor driver (sensor-agnostic framework)
const sensor = new BMM350Driver(bridge, { interface: 'i2c', bus: 0 });
await sensor.setupBoard();
await sensor.init();

const data = await sensor.readData(true);  // compensated
console.log(`X=${data.x.toFixed(2)} Y=${data.y.toFixed(2)} Z=${data.z.toFixed(2)} μT`);

// Backward-compatible alias:
// import { BMM350 } from 'cobra-bridge/drivers/bmm350.js';
// const sensor = new BMM350(bridge);

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