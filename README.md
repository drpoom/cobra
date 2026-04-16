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

### I2C (BMM350)

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

# init() now handles full board setup: I2C bus config, pin config,
# power cycle, soft reset, OTP, and magnetic reset
sensor = BMM350(bridge)
sensor.init()  # I2C bus 0, 400K, VDD/VDDIO 1800mV
data = sensor.read_mag_data(compensated=True)
print(f"X={data['x']:.2f} Y={data['y']:.2f} Z={data['z']:.2f} uT")

bridge.disconnect()
```

### SPI (AppBoard3.1)

```python
from cobra_bridge.transport import SerialTransport
from cobra_bridge.sync import CobraBridge
from cobra_bridge.constants import (
    SPI_BUS_0, SPI_SPEED_5MHZ, SPI_MODE_0,
    SHUTTLE_PIN_7, PIN_OUT, PIN_LOW,
)

transport = SerialTransport(port='/dev/ttyACM0')
bridge = CobraBridge(transport=transport)
bridge.connect()

# SPI bus config (AppBoard3.1: bus 0, CS pin 7)
bridge.config_spi_bus(bus=SPI_BUS_0, mode=SPI_MODE_0, speed=SPI_SPEED_5MHZ)
bridge.set_pin(SHUTTLE_PIN_7, PIN_OUT, PIN_LOW)

# Power cycle
bridge.set_vdd(0); bridge.set_vddio(0)
import time; time.sleep(0.1)
bridge.set_vdd(1800); bridge.set_vddio(1800)
time.sleep(0.1)

# Read chip ID over SPI (CS line 7)
chip_id = bridge.spi_read(cs_line=7, reg_addr=0x00, length=1,
                          speed=SPI_SPEED_5MHZ, mode=SPI_MODE_0)
print(f"Chip ID: 0x{chip_id[0]:02X}")  # Expected: 0x33

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

### I2C (Browser)

```bash
npm install cobra-bridge
```

```javascript
import { SerialTransport, CobraBridge } from 'cobra-bridge';
import { BMM350 } from 'cobra-bridge/drivers/bmm350.js';

const transport = new SerialTransport();
const bridge = new CobraBridge(transport);
await bridge.connect();

// init() handles full board setup automatically
const sensor = new BMM350(bridge);
await sensor.init();  // I2C bus 0, 400K, 1800mV

const data = await sensor.readMagData(true);
console.log(`X=${data.x.toFixed(2)} Y=${data.y.toFixed(2)} Z=${data.z.toFixed(2)} μT`);

await bridge.disconnect();
```

### SPI (AppBoard3.1)

```javascript
import { SerialTransport, CobraBridge } from 'cobra-bridge';
import {
    SPI_BUS_0, SPI_SPEED_5MHZ, SPI_MODE_0,
    SHUTTLE_PIN_7, PIN_OUT, PIN_LOW,
} from 'cobra-bridge';

const transport = new SerialTransport();
const bridge = new CobraBridge(transport);
await bridge.connect();

// SPI bus config (AppBoard3.1: bus 0, CS pin 7)
await bridge.configSpiBus(SPI_BUS_0, SPI_MODE_0, SPI_SPEED_5MHZ);
await bridge.setPin(SHUTTLE_PIN_7, PIN_OUT, PIN_LOW);

// Power cycle
await bridge.setVdd(0); await bridge.setVddio(0);
await new Promise(r => setTimeout(r, 100));
await bridge.setVdd(1800); await bridge.setVddio(1800);
await new Promise(r => setTimeout(r, 100));

// Read chip ID over SPI (CS line 7)
const chipId = await bridge.spiRead(7, 0x00, 1, SPI_SPEED_5MHZ, SPI_MODE_0);
console.log(`Chip ID: 0x${chipId[0].toString(16).padStart(2, '0')}`);  // 0x33

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