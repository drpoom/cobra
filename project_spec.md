# COBRA: COines BRidge Access

Developer: drpoom
Target Hardware: Bosch Application Board 3.1+
Primary Sensor: BMM350 Magnetometer (via Shuttle Board)
Packages: `cobra-bridge` (PyPI + npm, unified name)
Transports: USB-Serial (pyserial/WebSerial), BLE (Bleak/WebBluetooth)

## 1. Project Vision

COBRA is a lightweight, transport-agnostic library for the Bosch Sensortec AppBoard.
Published as `cobra-bridge` on both PyPI and npm, it supports USB-Serial and BLE backends with identical protocol logic.

## 2. Architecture

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

## 3. Tiers

| Tier | Python | JavaScript |
|------|--------|------------|
| **Sync** | `cobra_bridge.sync` | `cobra-bridge/sync` |
| **Async** | `cobra_bridge.async_` | 🔜 |
| **Streaming** | 🔜 | 🔜 |

## 4. Packages

| Package | Registry | Install | Import |
|---------|----------|---------|--------|
| cobra-bridge | PyPI | `pip install cobra-bridge` | `from cobra_bridge import ...` |
| cobra-bridge | npm | `npm install cobra-bridge` | `import { ... } from 'cobra-bridge'` |

## 5. Monorepo Structure

```
core/               → protocol_spec.json (single source of truth)
cobra-bridge/
├── py/             → pip package (src/cobra_bridge/)
│   ├── src/cobra_bridge/
│   ├── tests/
│   └── pyproject.toml
├── js/             → npm package (src/)
│   ├── src/
│   ├── dashboard.html
│   └── package.json
└── README.md       → unified README
tools/              → gen_constants.py (JSON → .py + .js)
```

## 6. Publishing

```bash
# Edit source of truth
vim core/protocol_spec.json
python tools/gen_constants.py

# Python
cd cobra-bridge/py && hatch build && hatch publish

# JavaScript
cd cobra-bridge/js && npm publish --access public
```

## 7. COINES V3 Packet Structure

| Byte | Field      | Value / Description                              |
|------|-----------|--------------------------------------------------|
| 0    | Header    | 0xAA                                             |
| 1    | Type      | 0x01 (Get), 0x02 (Set)                           |
| 2    | Command ID | e.g., 0x0E (I2C Read), 0x0D (I2C Write)       |
| 3-4  | Length    | Payload length (Little Endian)                  |
| 5...N| Payload   | The raw I2C/SPI command data                     |
| N+1  | Checksum  | XOR sum of bytes 0 through N                     |

## 8. BMM350 Key Constants

- I2C Address: 0x14
- Chip ID: 0x33 (register 0x00)
- Data: 24-bit signed, 12 bytes (3 axes × 3 bytes + 3 bytes temp)
- Default conversion: X,Y = raw × 0.007069979 μT/LSB, Z = raw × 0.007174964 μT/LSB
- Temperature: raw × 0.000981282 − 25.49 °C