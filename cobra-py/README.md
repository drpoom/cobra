# cobra-py

COines BRidge Access — Bosch AppBoard protocol for Python.

## Install

```bash
pip install cobra-py
```

For BLE support:
```bash
pip install cobra-py[ble]
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

# BLE
# from cobra_bridge.transport import BleTransport
# transport = BleTransport(address='AA:BB:CC:DD:EE:FF')
# bridge = CobraBridge(transport=transport)
# bridge.connect()

sensor = BMM350(bridge)
sensor.init()
data = sensor.read_mag_data(compensated=True)
print(f"X={data['x']:.2f} Y={data['y']:.2f} Z={data['z']:.2f} uT")

bridge.disconnect()
```

## License

MIT