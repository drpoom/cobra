# COBRA: COines BRidge Access

Developer: drpoom
Target Hardware: Bosch Application Board 3.1+
Primary Sensor: BMM350 Magnetometer (via Shuttle Board)
Packages: `cobra-py` (PyPI), `cobra-js` (npm)
Transports: USB-Serial (pyserial/WebSerial), BLE (Bleak/WebBluetooth)

## 1. Project Vision

COBRA is a lightweight, transport-agnostic library for the Bosch Sensortec AppBoard. Published as `cobra-py` on PyPI and `cobra-js` on npm, it supports USB-Serial and BLE backends with identical protocol logic.

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
| **Sync** | `cobra_bridge.sync` | `cobra-js/sync` |
| **Async** | `cobra_bridge.async_` | 🔜 |
| **Streaming** | 🔜 | 🔜 |

## 4. Packages

| Package | Registry | Install | Import |
|---------|----------|---------|--------|
| cobra-py | PyPI | `pip install cobra-py` | `from cobra_bridge import ...` |
| cobra-js | npm | `npm install cobra-js` | `import { ... } from 'cobra-js'` |

## 5. Monorepo Structure

```
core/               → protocol_spec.json (single source of truth)
cobra-py/           → pip package (src/cobra_bridge/)
cobra-js/           → npm package (src/)
tools/              → gen_constants.py (JSON → .py + .js)
```

## 6. Publishing

```bash
# Edit source of truth
vim core/protocol_spec.json
python tools/gen_constants.py

# Python
cd cobra-py && hatch build && hatch publish

# JavaScript
cd cobra-js && npm publish --access public
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