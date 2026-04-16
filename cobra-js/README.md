# cobra-js

COines BRidge Access — Bosch AppBoard protocol for JavaScript.

## Install

```bash
npm install cobra-js
```

## Quick Start

```javascript
import { SerialTransport, BleTransport, CobraBridge } from 'cobra-js';

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

## Browser Dashboard

Open `dashboard.html` in Chrome/Edge. Supports both USB (WebSerial) and BLE (WebBluetooth).

## License

MIT