# COBRA: COines BRidge Access

Pure Python & JavaScript implementation of the Bosch COINES V3 Bridge Protocol for the Application Board 3.1 + BMM350 magnetometer.

## Project Structure

```
drpoom/cobra/
├── core/                   # Language-agnostic protocol specification
│   ├── PROTOCOL.md         # Human-readable COINES V3 reference
│   └── protocol_spec.json  # Machine-readable single source of truth ★
├── python/                 # COBRA Python (V1 sync / V2 async / V3 PRO)
│   ├── cobra_constants.py  # Constants loaded from protocol_spec.json
│   ├── cobra_core.py       # V1: CobraBridge — sync protocol over pyserial
│   ├── cobra_reader.py     # V2: CobraReader — background serial reader thread
│   ├── cobra_bridge_v2.py  # V2: AsyncBridge — CobraBridge + CobraReader
│   ├── bmm350.py           # V1: BMM350 blocking driver
│   ├── bmm350_v2.py        # V2: BMM350Async — non-blocking 400Hz driver
│   ├── bmm350_test.py      # V1: CLI test tool
│   ├── bmm350_test_v2.py   # V2: Async monitor with CSV/JSON logging
│   └── generate_constants_js.py  # Auto-generates JS constants from JSON
├── javascript/             # COBRA.js (V4 — WebSerial)
│   ├── cobra_constants.js  # Auto-generated from protocol_spec.json
│   ├── cobra_core.js       # CobraBridge — protocol over WebSerial
│   └── index.html          # One-page BMM350 dashboard
├── project_spec.md         # Technical specification & roadmap
└── LICENSE                 # MIT
```

## Design Philosophy

**`core/protocol_spec.json` is the single source of truth.** All protocol constants, command IDs, payload formats, and sensor register maps live there. Both Python and JavaScript derive from it — never hardcode.

- **Edit** `protocol_spec.json` to add/change any constant
- **Python** `cobra_constants.py` loads the JSON at import time
- **JavaScript** `cobra_constants.js` is auto-generated via `python generate_constants_js.py`
- **PROTOCOL.md** is the human-readable reference; if it disagrees with the JSON, the JSON wins

## Quick Start — Python V1 (Sync)

```bash
pip install pyserial
cd python

# Auto-detect AppBoard and read Chip ID
python bmm350_test.py

# Continuous monitoring at 200 Hz (blocking)
python bmm350_test.py --monitor --odr 200
```

### Python V1 Library

```python
from cobra_core import CobraBridge
from bmm350 import BMM350

bridge = CobraBridge(port='/dev/ttyACM0')
bridge.connect()

sensor = BMM350(bridge)
print(f"Chip ID: 0x{sensor.get_chip_id():02X}")  # 0x33

sensor.set_power_mode('continuous')
sensor.set_odr('100_HZ')

if sensor.is_data_ready():
    data = sensor.read_mag_data()
    print(f"X={data['x']:.2f} Y={data['y']:.2f} Z={data['z']:.2f} uT")

sensor.set_power_mode('suspend')
bridge.disconnect()
```

## Quick Start — Python V2 (Async, 400 Hz)

```bash
# Non-blocking 400 Hz monitor with CSV logging
python bmm350_test_v2.py --odr 400 --csv data.csv

# 200 Hz with JSON output
python bmm350_test_v2.py --odr 200 --json data.json
```

### Python V2 Library

```python
from cobra_bridge_v2 import AsyncBridge
from bmm350_v2 import BMM350Async

bridge = AsyncBridge(port='/dev/ttyACM0')
bridge.connect()  # Starts background reader thread

sensor = BMM350Async(bridge, stale_threshold=8)
sensor.start_continuous(odr='400_HZ')

# Non-blocking loop — never blocks main execution
while True:
    data = sensor.read_sensor()  # Returns dict or None
    if data:
        print(f"X={data['x']:.2f} Y={data['y']:.2f} Z={data['z']:.2f} uT")
    do_other_work()  # Your code runs freely

sensor.stop_continuous()
bridge.disconnect()
```

### V1 → V2 Key Differences

| Feature | V1 (CobraBridge) | V2 (AsyncBridge) |
|---------|-------------------|-------------------|
| Serial reads | Main thread (blocking) | Background thread |
| Max poll rate | ~100 Hz | 400 Hz |
| read_sensor() | Blocks until response | Non-blocking (returns None or data) |
| Stale data | No handling | Auto-evicts from queue |
| Thread safety | Single thread | Write lock + queue |
| Stats | None | Driver + reader stats |
| Logging | None | CSV/JSON built-in |

## Quick Start — JavaScript V4 (WebSerial)

Open `javascript/index.html` in Chrome/Edge (WebSerial required). Click **Connect AppBoard**, then **Start Monitor**.

## Termux (Android)

```bash
pkg install python && pip install pyserial
termux-usb -l
termux-usb -r -e python bmm350_test_v2.py /dev/bus/usb/001/002
```

## Roadmap

| Version | Mode | Features | Status |
|---------|------|----------|--------|
| V1 | Sync polling | I2C/SPI, BMM350 driver, CLI | ✅ |
| V2 | Async I/O | Threaded reads, 400Hz, stale eviction, CSV/JSON | ✅ |
| V3 (PRO) | Streaming | Binary streaming @ 6.4kHz, μs timestamps, sensor fusion | 🔜 |
| V4 | WebSerial | Browser dashboard, real-time plotting | ✅ |

## License

MIT