# COBRA: COines BRidge Access

Bosch AppBoard protocol library — **Python** and **JavaScript** — over **USB-Serial** and **BLE**.

Implements the COINES V3 Bridge Protocol for Application Board 3.1+ with BMM350 magnetometer support. Transport-agnostic: only the I/O layer changes per backend; the packetizer and sensor drivers remain identical.

## Packages

| Package | Registry | Install |
|---------|----------|---------|
| **cobra-py** | [PyPI](https://pypi.org/project/cobra-py/) | `pip install cobra-py` |
| **cobra-js** | [npm](https://www.npmjs.com/package/cobra-js) | `npm install cobra-js` |

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
| **Sync** | Request-response blocking | `cobra_bridge.sync` | `cobra-js/sync` |
| **Async** | Non-blocking threaded reads | `cobra_bridge.async_` | 🔜 |
| **Streaming** | Binary streaming @ 6.4kHz | 🔜 | 🔜 |

## Platform × Transport

| Transport | Python | JavaScript |
|-----------|--------|------------|
| **USB-Serial** | `SerialTransport` (pyserial) | `SerialTransport` (WebSerial) |
| **BLE** | `BleTransport` (Bleak) | `BleTransport` (WebBluetooth) |

## Monorepo Structure

```
cobra/
├── core/                        # Language-agnostic protocol specification
│   ├── PROTOCOL.md              # Human-readable COINES V3 reference
│   └── protocol_spec.json       # Machine-readable single source of truth ★
│
├── cobra-py/                    ← pip install cobra-py
│   ├── pyproject.toml
│   ├── src/cobra_bridge/
│   │   ├── __init__.py
│   │   ├── constants.py         ← auto-generated from JSON
│   │   ├── transport.py         # Transport ABC + Serial + BLE
│   │   ├── sync.py              # CobraBridge (sync, any transport)
│   │   ├── reader.py            # Background serial reader thread
│   │   ├── async_.py            # AsyncBridge (non-blocking)
│   │   └── drivers/
│   │       ├── bmm350.py        # BMM350 sync driver
│   │       └── bmm350_async.py  # BMM350 async driver
│   └── tests/
│
├── cobra-js/                    ← npm install cobra-js
│   ├── package.json
│   ├── src/
│   │   ├── index.js             # Re-exports
│   │   ├── constants.js         ← auto-generated from JSON
│   │   ├── transport.js         # SerialTransport + BleTransport
│   │   ├── sync.js              # CobraBridge (sync, any transport)
│   │   └── drivers/
│   │       └── bmm350.js        # BMM350 driver (mirrors Python API)
│   └── dashboard.html           # Browser dashboard (USB + BLE)
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

# → cobra-py/src/cobra_bridge/constants.py
# → cobra-js/src/constants.js
```

The JSON never ships in published packages — generated constants are self-contained.

## Quick Start — Python

```bash
pip install cobra-py
```

```python
from cobra_bridge.transport import SerialTransport
from cobra_bridge.sync import CobraBridge
from cobra_bridge.drivers.bmm350 import BMM350

transport = SerialTransport(port='/dev/ttyACM0')
bridge = CobraBridge(transport=transport)
bridge.connect()

sensor = BMM350(bridge)
sensor.init()
data = sensor.read_mag_data(compensated=True)
print(f"X={data['x']:.2f} Y={data['y']:.2f} Z={data['z']:.2f} uT")

bridge.disconnect()
```

## Quick Start — JavaScript

```bash
npm install cobra-js
```

```javascript
import { SerialTransport, CobraBridge } from 'cobra-js';

const transport = new SerialTransport();
const bridge = new CobraBridge(transport);
await bridge.connect();

const chipId = await bridge.i2cRead(0x14, 0x00, 1);
console.log(`Chip ID: 0x${chipId[0].toString(16).padStart(2, '0')}`);

await bridge.disconnect();
```

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

## License

MIT