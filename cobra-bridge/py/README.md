# cobra-bridge

**COines BRidge Access** — Bosch AppBoard protocol for Python

Transport-agnostic library for the Bosch Sensortec Application Board 3.1+.
Supports USB-Serial (pyserial) and BLE (Bleak) backends with identical protocol logic.

## Install

```bash
pip install cobra-bridge
```

For BLE support:

```bash
pip install cobra-bridge[ble]
```

## Quick Start

```python
from cobra_bridge.transport import SerialTransport
from cobra_bridge.sync import CobraBridge
from cobra_bridge.drivers.bmm350 import BMM350

# USB-Serial
transport = SerialTransport(port='/dev/ttyACM0')
bridge = CobraBridge(transport=transport)
bridge.connect()

sensor = BMM350(bridge)
sensor.init()
data = sensor.read_mag_data(compensated=True)
print(f"X={data['x']:.2f} Y={data['y']:.2f} Z={data['z']:.2f} uT")

bridge.disconnect()
```

## Platform-Specific Setup

### Linux

```bash
# Install
pip install cobra-bridge

# Serial port — typically /dev/ttyACM0 or /dev/ttyUSB0
# Add yourself to the dialout group to avoid sudo:
sudo usermod -aG dialout $USER
# Log out and back in for group changes to take effect

# Find your board:
ls /dev/ttyACM* /dev/ttyUSB*

# Usage
from cobra_bridge.transport import SerialTransport
transport = SerialTransport(port='/dev/ttyACM0')
```

### macOS

```bash
# Install
pip install cobra-bridge

# Serial port — typically /dev/cu.usbmodemXXXX
# List available ports:
ls /dev/cu.usbmodem*

# Usage
from cobra_bridge.transport import SerialTransport
transport = SerialTransport(port='/dev/cu.usbmodem1401')
```

### Windows

```bash
# Install
pip install cobra-bridge

# Serial port — typically COM3, COM4, etc.
# Check Device Manager → Ports (COM & LPT) to find your board

# Usage
from cobra_bridge.transport import SerialTransport
transport = SerialTransport(port='COM3')
```

## BLE (All Platforms)

```python
from cobra_bridge.transport import BleTransport

# Scan for devices
devices = await BleTransport.scan(timeout=5.0)

# Connect by address
transport = BleTransport(address='AA:BB:CC:DD:EE:FF')
bridge = CobraBridge(transport=transport)
bridge.connect()
```

> **Note:** BLE requires the `[ble]` extra: `pip install cobra-bridge[ble]`

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

## License

MIT