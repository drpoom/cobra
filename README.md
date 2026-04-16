# COBRA: COines BRidge Access

Pure Python & JavaScript implementation of the Bosch COINES V3 Bridge Protocol for the Application Board 3.1.

## Project Structure

```
drpoom/cobra/
├── core/               # Language-agnostic protocol specification
│   └── PROTOCOL.md     # COINES V3 packet format, commands, payloads
├── python/             # COBRA Python library (V1/V2/PRO)
│   ├── cobra_constants.py  # Shared command constants
│   ├── cobra_core.py      # CobraBridge — protocol over pyserial
│   ├── bmm350.py           # BMM350 magnetometer driver
│   └── bmm350_test.py      # CLI test tool
├── javascript/         # COBRA.js (V4 — WebSerial)
│   ├── cobra_constants.js  # Shared command constants
│   ├── cobra_core.js       # CobraBridge — protocol over WebSerial
│   └── index.html          # One-page BMM350 dashboard
├── project_spec.md     # Technical specification & roadmap
└── LICENSE             # MIT
```

## Design Philosophy

The COBRA core logic is **language-agnostic**. `core/protocol_spec.json` is the single source of truth for all protocol constants, command IDs, payload formats, and sensor register maps. Both Python and JavaScript implementations derive their constants from this JSON — never hardcode.

- **Edit** `core/protocol_spec.json` to add/change any constant
- **Python** `cobra_constants.py` loads the JSON at import time
- **JavaScript** `cobra_constants.js` is auto-generated via `python generate_constants_js.py`
- **PROTOCOL.md** is the human-readable reference; if it disagrees with the JSON, the JSON wins

## Quick Start — Python (V1)

```bash
pip install pyserial
cd python

# Auto-detect AppBoard and read Chip ID
python bmm350_test.py

# Specify port
python bmm350_test.py /dev/ttyACM0

# Continuous monitoring at 200 Hz
python bmm350_test.py --monitor --odr 200
```

### Termux (Android)

```bash
pkg install python && pip install pyserial
termux-usb -l
termux-usb -r -e python bmm350_test.py /dev/bus/usb/001/002
```

### Python Library Usage

```python
from cobra_core import CobraBridge
from bmm350 import BMM350, ODR_100HZ

bridge = CobraBridge(port='/dev/ttyACM0')
bridge.connect()

sensor = BMM350(bridge)
print(f"Chip ID: 0x{sensor.get_chip_id():02X}")  # 0x33

sensor.set_power_mode('continuous')
sensor.set_odr(ODR_100HZ)

if sensor.is_data_ready():
    data = sensor.read_mag_data()
    print(f"X={data['x']:.2f} Y={data['y']:.2f} Z={data['z']:.2f} uT")

sensor.set_power_mode('suspend')
bridge.disconnect()
```

## Quick Start — JavaScript (V4)

Open `javascript/index.html` in Chrome/Edge (WebSerial required). Click **Connect AppBoard**, then **Start Monitor**.

## Roadmap

| Version | Mode | Features |
|---------|------|----------|
| V1 ✓    | Sync polling | I2C/SPI, BMM350 driver, CLI |
| V2      | Async I/O | Threaded reads, 400Hz, CSV/JSON logging |
| V3 (PRO)| Streaming | Binary streaming @ 6.4kHz, μs timestamps, sensor fusion |
| V4 ✓    | WebSerial | Browser dashboard, real-time plotting |

## License

MIT