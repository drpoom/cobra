# cobra-bridge

**COines BRidge Access** — Bosch AppBoard protocol for Python & JavaScript

Transport-agnostic library for the Bosch Sensortec Application Board 3.1+.
Identical protocol logic across Python and JS, supporting USB-Serial and BLE backends.

## Install

### Python

```bash
pip install cobra-bridge
```

With BLE support:

```bash
pip install cobra-bridge[ble]
```

### JavaScript

```bash
npm install cobra-bridge
```

## Quick Start

### Python

```python
from cobra_bridge.transport import SerialTransport
from cobra_bridge.sync import CobraBridge
from cobra_bridge.drivers.bmm350 import BMM350

# USB-Serial
transport = SerialTransport(port='/dev/ttyACM0')  # Linux
# transport = SerialTransport(port='/dev/cu.usbmodem1401')  # macOS
# transport = SerialTransport(port='COM3')  # Windows

bridge = CobraBridge(transport=transport)
bridge.connect()

sensor = BMM350(bridge)
sensor.init()
data = sensor.read_mag_data(compensated=True)
print(f"X={data['x']:.2f} Y={data['y']:.2f} Z={data['z']:.2f} uT")

bridge.disconnect()
```

### JavaScript (Browser)

```javascript
import { SerialTransport, CobraBridge } from 'cobra-bridge';

const transport = new SerialTransport();
const bridge = new CobraBridge(transport);
await bridge.connect();

const chipId = await bridge.i2cRead(0x14, 0x00, 1);
console.log(`Chip ID: 0x${chipId[0].toString(16).padStart(2, '0')}`);

await bridge.disconnect();
```

## Platform-Specific Setup

### Linux

```bash
# Python
pip install cobra-bridge

# Serial port — typically /dev/ttyACM0 or /dev/ttyUSB0
# Add yourself to the dialout group to avoid sudo:
sudo usermod -aG dialout $USER
# Log out and back in for group changes to take effect
```

### macOS

```bash
# Python
pip install cobra-bridge

# Serial port — typically /dev/cu.usbmodemXXXX
# No additional drivers needed for most boards
```

### Windows

```bash
# Python
pip install cobra-bridge

# Serial port — typically COM3, COM4, etc.
# Check Device Manager → Ports (COM & LPT) to find your board
```

## BLE (All Platforms)

### Python

```python
from cobra_bridge.transport import BleTransport

# Scan for devices
devices = await BleTransport.scan(timeout=5.0)

# Connect by address
transport = BleTransport(address='AA:BB:CC:DD:EE:FF')
bridge = CobraBridge(transport=transport)
bridge.connect()
```

> Requires `pip install cobra-bridge[ble]`

### JavaScript

```javascript
import { BleTransport, CobraBridge } from 'cobra-bridge';

const transport = new BleTransport();
const bridge = new CobraBridge(transport);
await bridge.connect();
```

## Architecture

```
         ┌──────────────┐     ┌─────────────┐
         │  CobraBridge │────▶│  Transport  │  ← abstract base
         │  (Packetizer)│     │  (I/O)      │
         └──────────────┘     └─────────────┘
                                   │
                       ┌───────────┴───────────┐
                       │                       │
                 Serial Transport        BLE Transport
                 (pyserial/WebSerial)   (Bleak/WebBluetooth)
```

## Packages

| Package | Registry | Install | Import |
|---------|----------|---------|--------|
| cobra-bridge | PyPI | `pip install cobra-bridge` | `from cobra_bridge import ...` |
| cobra-bridge | npm | `npm install cobra-bridge` | `import { ... } from 'cobra-bridge'` |

## Monorepo Structure

```
cobra-bridge/
├── py/               → pip package (src/cobra_bridge/)
│   ├── src/cobra_bridge/
│   ├── tests/
│   └── pyproject.toml
├── js/               → npm package (src/)
│   ├── src/
│   ├── dashboard.html
│   └── package.json
└── README.md         → this file
```

## Publishing

### Python

```bash
cd cobra-bridge/py
hatch build && hatch publish
```

### JavaScript

```bash
cd cobra-bridge/js
npm publish --access public
```

## License

MIT