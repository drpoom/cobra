# COBRA: COines BRidge Access

Bosch AppBoard protocol library — **Python** and **JavaScript** — over **USB-Serial** and **BLE**.

Implements the COINES V3 Bridge Protocol for Application Board 3.1+ with a **sensor-agnostic driver framework**. Transport-agnostic: only the I/O layer changes per backend; the packetizer and sensor drivers remain identical. Adding a new sensor = writing one driver class + one JSON spec.

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
                           │                    │
                    ┌──────┴──────┐    ┌────────┴────────┐
                    │  CobraBoard │    │ Serial Transport │
                    │  (High-level│    │  (pyserial /     │
                    │   API)      │    │   WebSerial)     │
                    └──────┬──────┘    └──────────────────┘
                           │           ┌──────────────────┐
                    ┌──────┴──────┐    │  BLE Transport   │
                    │ SensorDriver│    │  (Bleak /        │
                    │  (ABC)      │    │   WebBluetooth)  │
                    └──────┬──────┘    └──────────────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────┴─────┐ ┌───┴────┐ ┌────┴────┐
        │  BMM350   │ │ Future │ │ Future  │
        │  Driver   │ │ Driver │ │ Driver  │
        └───────────┘ └────────┘ └─────────┘
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
│   ├── protocol_spec.json       # Machine-readable single source of truth ★
│   └── sensors/                 # Per-sensor JSON specs (single source of truth)
│       └── bmm350.json          # BMM350 register map + coefficients
│
├── py/                          ← pip install cobra-bridge
│   ├── pyproject.toml
│   ├── src/cobra_bridge/
│   │   ├── __init__.py
│   │   ├── constants.py         ← auto-generated (board-level only)
│   │   ├── transport.py         # Transport ABC + Serial + BLE + CobraTransport
│   │   ├── sync.py              # CobraSyncBridge (sync, any transport)
│   │   ├── reader.py            # Background serial reader thread
│   │   ├── async_.py            # AsyncCobraBridge (non-blocking)
│   │   ├── cobra_wrapper.py     # CobraBoard / AsyncCobraBoard (coinespy-compatible)
│   │   └── drivers/
│   │       ├── __init__.py      # Driver framework exports
│   │       ├── base.py          # SensorDriver ABC + SensorData
│   │       ├── utils.py         # Shared utilities (fix_sign)
│   │       ├── bmm350.py        # BMM350Driver (sync)
│   │       ├── bmm350_async.py  # BMM350AsyncDriver (non-blocking)
│   │       └── bmm350_constants.py  ← auto-generated from bmm350.json
│   └── tests/
│       ├── test_sync.py
│       ├── test_async.py
│       ├── test_drivers.py      # Unit tests for driver framework
│       └── test_cobra_wrapper.py
│
├── js/                          ← npm install cobra-bridge
│   ├── package.json
│   ├── src/
│   │   ├── index.js             # Re-exports
│   │   ├── constants.js          ← auto-generated (board-level only)
│   │   ├── transport.js          # SerialTransport + BleTransport + CobraTransportJs
│   │   ├── sync.js               # CobraBridge (sync, any transport)
│   │   ├── cobra_wrapper.js      # CobraBoardJs (coinespy-compatible)
│   │   └── drivers/
│   │       ├── base.js           # SensorDriver base + SensorData
│   │       ├── utils.js          # Shared utilities (fixSign)
│   │       ├── bmm350.js         # BMM350Driver (mirrors Python API)
│   │       └── bmm350_constants.js  ← auto-generated from bmm350.json
│   └── dashboard.html            # Browser dashboard (USB + BLE)
│
└── tools/
    └── gen_constants.py          # Reads JSON → writes BOTH .py AND .js
```

## Single Source of Truth

`core/protocol_spec.json` defines all **board-level** protocol constants. `core/sensors/*.json` defines per-sensor register maps and coefficients. **Never hardcode.**

```bash
# Edit the source of truth
vim core/protocol_spec.json          # Board-level constants
vim core/sensors/bmm350.json         # BMM350 register map + coefficients

# Regenerate constants for both packages
python tools/gen_constants.py

# → py/src/cobra_bridge/constants.py          (board-level only)
# → js/src/constants.js                        (board-level only)
# → py/src/cobra_bridge/drivers/bmm350_constants.py  (BMM350-specific)
# → js/src/drivers/bmm350_constants.js               (BMM350-specific)
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
from cobra_bridge.cobra_wrapper import CobraBoard
from cobra_bridge.drivers.bmm350 import BMM350Driver

# USB-Serial
transport = SerialTransport(port='/dev/ttyACM0')    # Linux
# transport = SerialTransport(port='/dev/cu.usbmodem1401')  # macOS
# transport = SerialTransport(port='COM3')           # Windows

bridge = CobraBridge(transport=transport)
bridge.connect()

# Board-level API (coinespy-compatible)
board = CobraBoard()
board.open_comm_interface(0)  # USB

# Sensor driver (sensor-agnostic framework)
sensor = BMM350Driver(board, interface="i2c", bus=0)
sensor.setup_board()  # I2C bus config, pin config, power cycle
sensor.init()         # Soft reset, chip ID verify, OTP, magnetic reset
data = sensor.read_data(compensated=True)
print(f"X={data.x:.2f} Y={data.y:.2f} Z={data.z:.2f} uT  T={data.temperature:.2f}°C")

# Backward-compatible alias still works:
# from cobra_bridge.drivers.bmm350 import BMM350
# sensor = BMM350(board)
# data = sensor.read_mag_data(compensated=True)  # Returns dict

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

// Backward-compatible alias still works:
// import { BMM350 } from 'cobra-bridge/drivers/bmm350.js';
// const sensor = new BMM350(bridge);
// const data = await sensor.readMagData(true);  // Returns plain object

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

## Sensor Driver Framework

COBRA v0.2 introduces a **sensor-agnostic driver framework** — adding a new sensor requires only:

1. **One JSON spec** in `core/sensors/{sensor}.json` (register map + coefficients)
2. **One driver class** inheriting `SensorDriver` (Python + JS)
3. **Run `gen_constants.py`** to generate per-sensor constants

### SensorDriver ABC

Every sensor driver inherits from `SensorDriver` and implements:

| Method | Description |
|--------|-------------|
| `init()` | Full sensor-level initialization |
| `soft_reset()` | Send soft reset command |
| `get_chip_id()` | Read and return chip ID |
| `self_test()` | Run built-in self test |
| `configure(settings)` | Apply sensor configuration |
| `read_data()` | Read sensor data (returns `SensorData` subclass) |

### Adding a New Sensor

```bash
# 1. Create sensor spec
vim core/sensors/bma456.json

# 2. Regenerate constants
python tools/gen_constants.py
# → py/src/cobra_bridge/drivers/bma456_constants.py
# → js/src/drivers/bma456_constants.js

# 3. Implement driver (Python)
# py/src/cobra_bridge/drivers/bma456.py
class BMA456Driver(SensorDriver):
    name = "bma456"
    chip_id = 0x46
    i2c_addr = 0x68
    # ... implement abstract methods

# 4. Implement driver (JavaScript)
# js/src/drivers/bma456.js
export class BMA456Driver extends SensorDriver {
    static name = 'bma456';
    static chipId = 0x46;
    static i2cAddr = 0x68;
    // ... implement abstract methods
```

### Board Convenience Methods

`CobraBoard` / `AsyncCobraBoard` / `CobraBoardJs` provide board-level methods that drivers use:

| Method | Description |
|--------|-------------|
| `set_vdd(mv)` / `setVdd(mv)` | Set VDD voltage (0 = off) |
| `set_vddio(mv)` / `setVddio(mv)` | Set VDDIO voltage (0 = off) |
| `set_pin(pin, dir, val)` / `setPin(...)` | Configure GPIO pin |
| `i2c_read_reg(addr, reg, len)` / `i2cReadReg(...)` | I2C register read |
| `i2c_write_reg(addr, reg, data)` / `i2cWriteReg(...)` | I2C register write |
| `spi_read_reg(cs, reg, len)` / `spiReadReg(...)` | SPI register read |
| `spi_write_reg(cs, reg, data)` / `spiWriteReg(...)` | SPI register write |
| `attach_driver(driver)` / `attachDriver(driver)` | Register a driver instance |
| `get_driver(name)` / `getDriver(name)` | Retrieve a driver by name |
| `drivers` | Dict of all attached drivers |

## Sync vs Async (Python)

| Feature | Sync (`CobraBridge`) | Async (`AsyncBridge`) |
|---------|---------------------|----------------------|
| Reads | Main thread (blocking) | Background thread |
| Max poll rate | ~100 Hz | 400 Hz |
| `read_sensor()` | Blocks until response | Non-blocking (None or data) |
| Stale data | No handling | Auto-evicts from queue |
| Thread safety | Single thread | Write lock + queue |

## Publishing

### Python — Build a Wheel

```bash
cd py
pip install build
python -m build
# Produces dist/cobra_bridge-0.1.2-py3-none-any.whl
# Install locally:
pip install dist/cobra_bridge-0.1.2-py3-none-any.whl
# Publish to PyPI:
pip install twine
twine upload dist/*
```

### JavaScript

```bash
cd js
npm publish --access public
```

## COBRA vs coinespy — Key Differences

COBRA is a **lightweight, transport-agnostic** drop-in replacement for [coinespy](https://github.com/boschsensortec/COINES_SDK/tree/main/coines-api/pc/python). It shares the same high-level API surface (`CobraBoard` mirrors `CoinesBoard`) but differs fundamentally in architecture:

| Aspect | coinespy | COBRA |
|--------|----------|-------|
| **Transport** | USB-only (wraps C `.dll`/`.so`) | USB-Serial + BLE (pure Python/JS) |
| **Dependencies** | Requires compiled C library | Pure Python (`pyserial`); optional BLE (`bleak`) |
| **Async support** | None | `AsyncCobraBoard` with background reader thread |
| **JavaScript** | None | Full JS mirror (`CobraBoardJs`) |
| **Protocol** | COINES V3 over USB | COINES V3 over Serial/BLE/NUS |
| **Streaming** | Built-in (C-level) | Planned (Python async tier) |
| **Board config** | `coines_config_i2c_bus`, `coines_config_spi_bus` | `config_i2c_bus`, `config_spi_bus` (same semantics) |
| **Error handling** | C error codes via ctypes | Python `ErrorCodes` enum |
| **Cross-platform** | Requires platform-specific binary | Runs anywhere Python/JS runs |

### API Mapping (coinespy → COBRA)

| coinespy (`CoinesBoard`) | COBRA (`CobraBoard`) | Notes |
|--------------------------|----------------------|-------|
| `open_comm_interface(USB)` | `open_comm_interface(CommInterface.USB)` | Same enum pattern |
| `close_comm_interface()` | `close_comm_interface()` | Identical |
| `config_i2c_bus(bus, addr, mode)` | `config_i2c_bus(bus, addr, mode)` | Same enums |
| `write_i2c(bus, reg, val)` | `write_i2c(bus, reg, val)` | Same signature |
| `read_i2c(bus, reg, n)` | `read_i2c(bus, reg, n)` | Same signature |
| `config_spi_bus(bus, cs, speed, mode)` | `config_spi_bus(bus, cs, speed, mode)` | Same enums |
| `write_spi(bus, reg, val)` | `write_spi(bus, reg, val)` | Same signature |
| `read_spi(bus, reg, n)` | `read_spi(bus, reg, n)` | Same signature |
| `read_16bit_i2c(...)` | `read_16bit_i2c(...)` | Same signature |
| `write_16bit_spi(...)` | `write_16bit_spi(...)` | Same signature |
| `scan_ble_devices(...)` | *(planned)* | BLE scanning via `BleTransport.scan()` |
| `config_streaming(...)` | *(planned)* | Streaming in async tier |
| `read_stream_sensor_data(...)` | *(planned)* | Streaming in async tier |

### Quick Migration

```python
# Before (coinespy)
import coinespy as cpy
board = cpy.CoinesBoard()
board.open_comm_interface(cpy.CommInterface.USB)

# After (COBRA — drop-in replacement)
from cobra_bridge.cobra_wrapper import CobraBoard
from cobra_bridge.constants import CommInterface
board = CobraBoard()
board.open_comm_interface(CommInterface.USB)
```

## License

MIT