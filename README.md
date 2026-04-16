# COBRA: COines BRidge Access

Bosch AppBoard protocol library — **Python** and **JavaScript** — over **USB-Serial** and **BLE**.

Implements the COINES V3 Bridge Protocol for Application Board 3.1+ with BMM350 magnetometer support. Transport-agnostic: only the I/O layer changes per backend; the packetizer and sensor drivers remain identical.

## Packages

| Package | Registry | Install | Import |
|---------|----------|---------|--------|
| **cobra-bridge** | [PyPI](https://pypi.org/project/cobra-bridge/) | `pip install cobra-bridge` | `from cobra_bridge import ...` |
| **cobra-bridge** | [npm](https://www.npmjs.com/package/cobra-bridge) | `npm install cobra-bridge` | `import { ... } from 'cobra-bridge'` |

> **Unified name:** Both packages share the name `cobra-bridge`. The Python module is `cobra_bridge` (underscore, per PEP 8).

## Architecture

```
                    ┌──────────────┐     ┌─────────────┐
                    │  CobraBridge │────▶│  Transport  │  ← abstract base
                    │  (Packetizer)│     │  (I/O)      │
                    └──────────────┘     └─────────────┘
                                              │
                              ┌────────────────┴────────────────┐
                              │                                  │
                     ┌────────┴────────┐              ┌────────┴────────┐
                     │ Serial Transport │              │  BLE Transport  │
                     │ (pyserial /      │              │  (Bleak /        │
                     │  WebSerial)      │              │   WebBluetooth)  │
                     └──────────────────┘              └─────────────────┘
```

## Tiers

| Tier | Mode | Python | JavaScript |
|------|------|--------|------------|
| **Sync** | Request-response blocking | `cobra_bridge.sync` | `cobra-bridge/sync` |
| **Async** | Non-blocking threaded reads | `cobra_bridge.async_` | 🔜 |
| **Streaming** | Binary streaming @ 6.4kHz | 🔜 | 🔜 |

## Platform × Transport

| Transport | Python | JavaScript |
|-----------|--------|------------|
| **USB-Serial** | `SerialTransport` (pyserial) | `SerialTransport` (WebSerial) |
| **BLE** | `BleTransport` (Bleak) | `BleTransport` (WebBluetooth) |

## Platform-Specific Setup

### Linux

```bash
pip install cobra-bridge
# Serial port: /dev/ttyACM0 or /dev/ttyUSB0
# Add yourself to the dialout group:
sudo usermod -aG dialout $USER
# Log out and back in for group changes to take effect
```

### macOS

```bash
pip install cobra-bridge
# Serial port: /dev/cu.usbmodemXXXX
# No additional drivers needed for most boards
```

### Windows

```bash
pip install cobra-bridge
# Serial port: COM3, COM4, etc.
# Check Device Manager → Ports (COM & LPT) to find your board
```

## Monorepo Structure

```
cobra/
├── core/                        # Language-agnostic protocol specification
│   ├── PROTOCOL.md              # Human-readable COINES V3 reference
│   └── protocol_spec.json       # Machine-readable single source of truth ★
│
├── cobra-bridge/                ← unified package directory
│   ├── py/                      ← pip install cobra-bridge
│   │   ├── pyproject.toml
│   │   ├── src/cobra_bridge/
│   │   │   ├── __init__.py
│   │   │   ├── constants.py     ← auto-generated from JSON
│   │   │   ├── transport.py     # Transport ABC + Serial + BLE
│   │   │   ├── sync.py          # CobraBridge (sync, any transport)
│   │   │   ├── reader.py        # Background serial reader thread
│   │   │   ├── async_.py        # AsyncBridge (non-blocking)
│   │   │   └── drivers/
│   │   │       ├── bmm350.py    # BMM350 sync driver
│   │   │       └── bmm350_async.py  # BMM350 async driver
│   │   └── tests/
│   │       ├── test_sync.py
│   │       └── test_async.py
│   │
│   ├── js/                      ← npm install cobra-bridge
│   │   ├── package.json
│   │   ├── src/
│   │   │   ├── index.js         # Re-exports
│   │   │   ├── constants.js     ← auto-generated from JSON
│   │   │   ├── transport.js     # SerialTransport + BleTransport
│   │   │   ├── sync.js          # CobraBridge (sync, any transport)
│   │   │   └── drivers/
│   │   │       └── bmm350.js    # BMM350 driver (mirrors Python API)
│   │   └── dashboard.html       # Browser dashboard (USB + BLE)
│   │
│   └── README.md                # Package-level docs
│
└── tools/
    └── gen_constants.py         # Reads JSON → writes BOTH .py AND .js
```

## Single Source of Truth

`core/protocol_spec.json` defines all protocol constants, register maps, and conversion coefficients. **Never hardcode.**

```bash
# Edit the source of truth
vim core/protocol_spec.json

# Regenerate constants for both packages
python tools/gen_constants.py

# → cobra-bridge/py/src/cobra_bridge/constants.py
# → cobra-bridge/js/src/constants.js
```

The JSON never ships in published packages — generated constants are self-contained.

## Quick Start — Python

```bash
pip install cobra-bridge
```

```python
from cobra_bridge.transport import SerialTransport
from cobra_bridge.sync import CobraBridge
from cobra_bridge.drivers.bmm350 import BMM350

# USB-Serial
transport = SerialTransport(port='/dev/ttyACM0')    # Linux
# transport = SerialTransport(port='/dev/cu.usbmodem1401')  # macOS
# transport = SerialTransport(port='COM3')           # Windows

bridge = CobraBridge(transport=transport)
bridge.connect()

sensor = BMM350(bridge)
sensor.init()
data = sensor.read_mag_data(compensated=True)
print(f"X={data['x']:.2f} Y={data['y']:.2f} Z={data['z']:.2f} uT")

bridge.disconnect()
```

### BLE (Python)

```python
from cobra_bridge.transport import BleTransport

# Scan for nearby AppBoard BLE devices
devices = await BleTransport.scan(timeout=5.0)

# Connect by address
transport = BleTransport(address='AA:BB:CC:DD:EE:FF')
bridge = CobraBridge(transport=transport)
bridge.connect()
```

> Requires `pip install cobra-bridge[ble]`

## Quick Start — JavaScript

```bash
npm install cobra-bridge
```

```javascript
import { SerialTransport, CobraBridge } from 'cobra-bridge';

const transport = new SerialTransport();
const bridge = new CobraBridge(transport);
await bridge.connect();

const chipId = await bridge.i2cRead(0x14, 0x00, 1);
console.log(`Chip ID: 0x${chipId[0].toString(16).padStart(2, '0')}`);

await bridge.disconnect();
```

### Browser Dashboard

Open `cobra-bridge/js/dashboard.html` in Chrome/Edge for a visual interface with USB and BLE support.

## BLE Protocol

AppBoard 3.1 uses **Nordic UART Service (NUS)** over BLE:

| Characteristic | UUID | Direction |
|---------------|------|-----------|
| NUS Service | `6e400001-b5a3-f393-e0a9-e50e24dcca9e` | — |
| RX (write) | `6e400002-b5a3-f393-e0a9-e50e24dcca9e` | Host → AppBoard |
| TX (notify) | `6e400003-b5a3-f393-e0a9-e50e24dcca9e` | AppBoard → Host |

Same COINES V3 packets over NUS — identical framing and checksums.

## Sync vs Async (Python)

| Feature | Sync (`CobraBridge`) | Async (`AsyncBridge`) |
|---------|---------------------|----------------------|
| Reads | Main thread (blocking) | Background thread |
| Max poll rate | ~100 Hz | 400 Hz |
| `read_sensor()` | Blocks until response | Non-blocking (None or data) |
| Stale data | No handling | Auto-evicts from queue |
| Thread safety | Single thread | Write lock + queue |

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