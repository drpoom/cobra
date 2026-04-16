# COBRA: COines BRidge Access

Pure Python & JavaScript implementation of the Bosch COINES V3 Bridge Protocol for the Application Board 3.1 + BMM350 magnetometer.

Supports **USB-Serial** and **BLE** (Nordic UART Service) backends with identical protocol logic — only the transport layer changes.

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
                     │ Serial Transport  │              │  BLE Transport  │
                     │ (pyserial /       │              │  (Bleak /        │
                     │  WebSerial)       │              │   WebBluetooth)  │
                     └──────────────────┘              └─────────────────┘
```

COINES V3 packets travel identically over both transports — same framing, same checksums, same protocol. The packetizer (`CobraBridge`) and BMM350 driver are completely transport-agnostic.

## Project Structure

```
drpoom/cobra/
├── core/                        # Language-agnostic protocol specification
│   ├── PROTOCOL.md              # Human-readable COINES V3 reference
│   └── protocol_spec.json       # Machine-readable single source of truth ★
│
├── python/                      # COBRA Python
│   ├── cobra_constants.py       # Constants loaded from protocol_spec.json
│   ├── cobra_transport.py       # Transport ABC + SerialTransport + BleTransport
│   ├── cobra_sync.py            # CobraBridge — sync protocol (any transport)
│   ├── cobra_reader.py          # CobraReader — background serial reader thread
│   ├── cobra_async.py            # AsyncBridge — sync bridge + reader thread
│   ├── bmm350_sync.py           # BMM350 blocking driver
│   ├── bmm350_async.py          # BMM350Async — non-blocking 400Hz driver
│   ├── test_sync.py             # CLI test tool (sync)
│   ├── test_async.py            # Async monitor with CSV/JSON logging
│   └── generate_constants_js.py # Auto-generates JS constants from JSON
│
├── javascript/                  # COBRA.js
│   ├── cobra_constants.js       # Auto-generated from protocol_spec.json
│   ├── cobra_transport.js       # SerialTransport + BleTransport (Web APIs)
│   ├── cobra_sync.js            # CobraBridge — sync protocol (any transport)
│   ├── bmm350.js                # BMM350 driver (mirrors Python API)
│   └── index.html               # One-page BMM350 dashboard
│
├── project_spec.md              # Technical specification & roadmap
└── LICENSE                      # MIT
```

## Tiers

| Tier | Mode | Python | JavaScript | Features |
|------|------|--------|------------|----------|
| **Sync** | Request-response blocking | `cobra_sync.py` + `cobra_transport.py` | `cobra_sync.js` + `cobra_transport.js` | I2C/SPI, board control, BMM350 driver |
| **Async** | Non-blocking threaded reads | `cobra_async.py` + `cobra_reader.py` | — | 400Hz polling, stale eviction, queue-based |
| **Streaming** | Binary streaming @ 6.4kHz | 🔜 | 🔜 | μs timestamps, sensor fusion |

## Platform × Transport Matrix

| Transport | Python | JavaScript |
|-----------|--------|------------|
| **USB-Serial** | `SerialTransport` (pyserial) | `SerialTransport` (WebSerial) |
| **BLE** | `BleTransport` (Bleak) | `BleTransport` (WebBluetooth) |

## Quick Start — Python Sync (USB-Serial)

```bash
pip install pyserial
cd python

# Read BMM350 Chip ID
python test_sync.py --port /dev/ttyACM0

# Continuous monitoring at 200 Hz
python test_sync.py --port /dev/ttyACM0 --monitor --odr 200
```

### Python Sync Library

```python
from cobra_transport import SerialTransport
from cobra_sync import CobraBridge
from bmm350_sync import BMM350

transport = SerialTransport(port='/dev/ttyACM0')
bridge = CobraBridge(transport=transport)
bridge.connect()

sensor = BMM350(bridge)
print(f"Chip ID: 0x{sensor.get_chip_id():02X}")  # 0x33

sensor.set_power_mode('normal')
sensor.set_odr(100)

data = sensor.read_mag_data()
print(f"X={data['x']:.2f} Y={data['y']:.2f} Z={data['z']:.2f} uT")

sensor.set_power_mode('suspend')
bridge.disconnect()
```

## Quick Start — Python Sync (BLE)

```bash
pip install pyserial bleak
cd python

# Scan for BLE devices
python -c "from cobra_transport import BleTransport; import asyncio; print(asyncio.run(BleTransport.scan()))"

# Connect by MAC address
python test_sync.py --ble AA:BB:CC:DD:EE:FF
```

### Python Sync Library (BLE)

```python
from cobra_transport import BleTransport
from cobra_sync import CobraBridge
from bmm350_sync import BMM350

transport = BleTransport(address='AA:BB:CC:DD:EE:FF')
bridge = CobraBridge(transport=transport)
bridge.connect()

sensor = BMM350(bridge)
sensor.init()
data = sensor.read_mag_data(compensated=True)
print(f"X={data['x']:.2f} Y={data['y']:.2f} Z={data['z']:.2f} uT")

bridge.disconnect()
```

## Quick Start — Python Async (400 Hz)

```bash
# Non-blocking 400 Hz monitor with CSV logging
python test_async.py --port /dev/ttyACM0 --odr 400 --csv data.csv
```

### Python Async Library

```python
from cobra_transport import SerialTransport
from cobra_async import AsyncBridge
from bmm350_async import BMM350Async

transport = SerialTransport(port='/dev/ttyACM0')
bridge = AsyncBridge(transport=transport)
bridge.connect()  # Starts background reader thread

sensor = BMM350Async(bridge, stale_threshold=8)
sensor.start_continuous(odr='400_HZ')

while True:
    data = sensor.read_sensor()  # Returns dict or None (non-blocking)
    if data:
        print(f"X={data['x']:.2f} Y={data['y']:.2f} Z={data['z']:.2f} uT")
    do_other_work()

sensor.stop_continuous()
bridge.disconnect()
```

## Quick Start — JavaScript (Browser)

Open `javascript/index.html` in Chrome/Edge. Click **Connect AppBoard** (WebSerial) or **Connect BLE** (WebBluetooth), then **Start Monitor**.

### JavaScript Library

```javascript
import { SerialTransport, BleTransport } from './cobra_transport.js';
import { CobraBridge } from './cobra_sync.js';

// USB-Serial
const transport = new SerialTransport();
await transport.connect();

// BLE
// const transport = new BleTransport();
// await transport.connect();

const bridge = new CobraBridge(transport);
await bridge.connect();

const chipId = await bridge.i2cRead(0x14, 0x00, 1);
console.log(`Chip ID: 0x${chipId[0].toString(16).padStart(2, '0')}`);

await bridge.disconnect();
```

## BLE Protocol Details

The AppBoard 3.1 uses **Nordic UART Service (NUS)** over BLE:

| Characteristic | UUID | Direction |
|---------------|------|-----------|
| NUS Service | `6e400001-b5a3-f393-e0a9-e50e24dcca9e` | — |
| RX (write) | `6e400002-b5a3-f393-e0a9-e50e24dcca9e` | Host → AppBoard |
| TX (notify) | `6e400003-b5a3-f393-e0a9-e50e24dcca9e` | AppBoard → Host |

COINES V3 packets travel as raw bytes over NUS — identical framing and checksums. BLE writes are chunked to 20 bytes (safe GATT MTU default).

## Design Philosophy

**`core/protocol_spec.json` is the single source of truth.** All protocol constants, command IDs, payload formats, and sensor register maps derive from it. Never hardcode.

- **Edit** `protocol_spec.json` to add/change constants
- **Python** `cobra_constants.py` loads the JSON at import time
- **JavaScript** `cobra_constants.js` is auto-generated via `python generate_constants_js.py`
- **PROTOCOL.md** is the human-readable reference; JSON wins if they disagree

## Sync vs Async Comparison

| Feature | Sync (CobraBridge) | Async (AsyncBridge) |
|---------|-------------------|---------------------|
| Reads | Main thread (blocking) | Background thread |
| Max poll rate | ~100 Hz | 400 Hz |
| read_sensor() | Blocks until response | Non-blocking (returns None or data) |
| Stale data | No handling | Auto-evicts from queue |
| Thread safety | Single thread | Write lock + queue |
| Stats | None | Driver + reader stats |
| Logging | None | CSV/JSON built-in |
| Transport | Any (Serial/BLE) | Serial (CobraReader) or any (TransportReader) |

## Termux (Android)

```bash
pkg install python && pip install pyserial
termux-usb -l
termux-usb -r -e python test_sync.py /dev/bus/usb/001/002
```

## License

MIT