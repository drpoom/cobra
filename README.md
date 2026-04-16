# COBRA: COines BRidge Access

Pure Python implementation of the Bosch COINES V3 Bridge Protocol for the Application Board 3.1, enabling sensor testing on Android/Termux and embedded systems.

## Features (V1)

- 🔌 USB-Serial connectivity via pyserial
- 📦 Binary COINES V3 packet framing with XOR checksums
- 📡 I2C Read/Write commands
- 📡 SPI Read/Write commands
- 🧲 BMM350 magnetometer driver (Chip ID, power modes, data readout)
- 🖥️ CLI test tool with auto-detection

## Quick Start

```bash
pip install pyserial

# Auto-detect AppBoard and read Chip ID
python cobra_test.py

# Specify port manually
python cobra_test.py /dev/ttyACM0

# Show board info
python cobra_test.py --info

# Continuous magnetic field monitoring
python cobra_test.py --monitor

# Monitor at 200 Hz
python cobra_test.py --monitor --odr 200
```

## Termux (Android)

```bash
pkg install python
pip install pyserial
termux-usb -l                              # List USB devices
termux-usb -r -e python cobra_test.py /dev/bus/usb/001/002
```

## Library Usage

```python
from cobra_core import CobraBridge
from bmm350 import BMM350

# Connect to AppBoard
bridge = CobraBridge(port='/dev/ttyACM0')
bridge.connect()

# Read BMM350 Chip ID
sensor = BMM350(bridge)
chip_id = sensor.get_chip_id()      # Expected: 0x33
print(f"Chip ID: 0x{chip_id:02X}")

# Configure and read data
sensor.set_power_mode('continuous')
sensor.set_odr(ODR_100HZ)

if sensor.is_data_ready():
    data = sensor.read_mag_data()
    print(f"Magnetic field: X={data['x']:.2f} Y={data['y']:.2f} Z={data['z']:.2f} uT")

# Cleanup
sensor.set_power_mode('suspend')
bridge.disconnect()
```

## COINES V3 Packet Structure

| Byte | Field      | Value / Description                    |
|------|------------|----------------------------------------|
| 0    | Header     | 0xAA                                   |
| 1    | Type       | 0x01 (Get), 0x02 (Set)                |
| 2    | Command ID | e.g., 0x0E (I2C Read), 0x0D (I2C Write) |
| 3-4  | Length     | Payload length (Little Endian)         |
| 5..N | Payload    | Raw I2C/SPI command data               |
| N+1  | Checksum   | XOR sum of bytes 0 through N           |

## BMM350 Configuration (V1 Test)

- I2C Address: 0x14
- Chip ID Register: 0x00 (Expected: 0x33)
- Power Modes: suspend, normal, forced, continuous
- ODR: 6.25, 12.5, 25, 50, 100, 200, 400 Hz

## Project Structure

```
cobra/
├── cobra_core.py    # COINES V3 protocol layer (CobraBridge class)
├── bmm350.py        # BMM350 magnetometer driver
├── cobra_test.py    # CLI test tool
├── project_spec.md   # Technical specification
└── README.md        # This file
```

## Roadmap

- **V1** — Synchronous polling, I2C/SPI, basic BMM350 driver ✓
- **V2** — Async I/O, higher ODR, CSV/JSON logging
- **PRO** — Binary streaming, hardware interrupts, sensor fusion

## License

MIT