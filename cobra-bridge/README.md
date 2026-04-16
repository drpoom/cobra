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

### Python — I2C (BMM350)

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

# init() now handles full board setup: I2C bus config, pin config,
# power cycle, soft reset, OTP, and magnetic reset
sensor = BMM350(bridge)
sensor.init()  # I2C bus 0, 400K, VDD/VDDIO 1800mV

data = sensor.read_mag_data(compensated=True)
print(f"X={data['x']:.2f} Y={data['y']:.2f} Z={data['z']:.2f} uT")

bridge.disconnect()
```

### Python — SPI (BMM350 on AppBoard3.1)

```python
from cobra_bridge.transport import SerialTransport
from cobra_bridge.sync import CobraBridge
from cobra_bridge.drivers.bmm350 import BMM350
from cobra_bridge.constants import (
    SPI_BUS_0, SPI_SPEED_5MHZ, SPI_MODE_0,
    SHUTTLE_PIN_7, PIN_OUT, PIN_LOW,
)

transport = SerialTransport(port='/dev/ttyACM0')
bridge = CobraBridge(transport=transport)
bridge.connect()

# SPI bus config (AppBoard3.1: bus 0, pin 7 = standard CS)
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

### JavaScript (Browser) — I2C

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

### JavaScript (Browser) — SPI (AppBoard3.1)

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