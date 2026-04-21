# COBRA: COines BRidge Access

Developer: drpoom
Target Hardware: Bosch Application Board 3.1+
Sensor Framework: SensorDriver ABC — pluggable, sensor-agnostic
Primary Sensor: BMM350 Magnetometer (via Shuttle Board)
Packages: `cobra-bridge` (PyPI + npm, unified name)
Transports: USB-Serial (pyserial/WebSerial), BLE (Bleak/WebBluetooth)

## 1. Project Vision

COBRA is a lightweight, transport-agnostic library for the Bosch Sensortec AppBoard.
Published as `cobra-bridge` on both PyPI and npm, it supports USB-Serial and BLE backends with identical protocol logic. Since v0.2, COBRA features a **sensor-agnostic driver framework** — adding a new sensor requires only a JSON spec + one driver class per language.

## 2. Architecture

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
         ┌──────┴──────┐    │  BLE Transport  │
         │ SensorDriver │    │  (Bleak /       │
         │  (ABC)       │    │   WebBluetooth) │
         └──────┬──────┘    └──────────────────┘
                │
     ┌──────────┼──────────┐
     │          │          │
  BMM350    Future      Future
  Driver    Driver      Driver
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
core/               → protocol_spec.json (board-level constants)
                    → sensors/*.json (per-sensor specs — single source of truth)
cobra-bridge/
├── py/             → pip package (src/cobra_bridge/)
│   ├── src/cobra_bridge/
│   │   ├── drivers/
│   │   │   ├── base.py          # SensorDriver ABC + SensorData
│   │   │   ├── utils.py         # Shared utilities (fix_sign)
│   │   │   ├── bmm350.py        # BMM350Driver (sync)
│   │   │   ├── bmm350_async.py  # BMM350AsyncDriver (non-blocking)
│   │   │   └── bmm350_constants.py  ← auto-generated
│   │   ├── constants.py         ← auto-generated (board-level only)
│   │   ├── cobra_wrapper.py     # CobraBoard / AsyncCobraBoard
│   │   └── ...
│   ├── tests/
│   └── pyproject.toml
├── js/             → npm package (src/)
│   ├── src/
│   │   ├── drivers/
│   │   │   ├── base.js          # SensorDriver + SensorData
│   │   │   ├── utils.js         # Shared utilities (fixSign)
│   │   │   ├── bmm350.js        # BMM350Driver
│   │   │   └── bmm350_constants.js  ← auto-generated
│   │   ├── constants.js         ← auto-generated (board-level only)
│   │   └── ...
│   ├── dashboard.html
│   └── package.json
└── README.md       → unified README
tools/              → gen_constants.py (JSON → .py + .js, board + per-sensor)
```

## 6. Publishing

```bash
# Edit source of truth
vim core/protocol_spec.json          # Board-level constants
vim core/sensors/bmm350.json        # Per-sensor register map + coefficients
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

## 8. Sensor Driver Framework (v0.2)

### Architecture

- **SensorDriver ABC** (`drivers/base.py` / `drivers/base.js`): Abstract base class with class attrs `name`, `chip_id`, `i2c_addr` and abstract methods `init()`, `soft_reset()`, `get_chip_id()`, `self_test()`, `configure()`, `read_data()`.
- **SensorData** dataclass: Base container with `raw: dict` and `timestamp: Optional[float]`. Subclasses add sensor-specific fields (e.g., `BMM350Data` adds `x, y, z, temperature`).
- **Per-sensor JSON specs** (`core/sensors/*.json`): Single source of truth for register maps, PMU commands, ODR settings, conversion coefficients.
- **gen_constants.py**: Generates board-only `constants.py`/`constants.js` + per-sensor `{sensor}_constants.py`/`{sensor}_constants.js`.
- **Board convenience methods**: `CobraBoard`/`CobraBoardJs` provide `set_vdd()`, `set_vddio()`, `set_pin()`, `i2c_read_reg()`, `i2c_write_reg()`, `spi_read_reg()`, `spi_write_reg()`, `attach_driver()`, `get_driver()`, `drivers`.
- **Driver registry**: `board.attach_driver(sensor)` / `board.get_driver("bmm350")`.

### Adding a New Sensor

1. Create `core/sensors/{sensor}.json` with register map + coefficients
2. Run `python tools/gen_constants.py` → generates per-sensor constants
3. Implement `{sensor}.py` / `{sensor}.js` inheriting `SensorDriver`
4. Update `__init__.py` / `index.js` exports

### Backward Compatibility

- `BMM350 = BMM350Driver` alias (Python + JS)
- `BMM350Async = BMM350AsyncDriver` alias (Python)
- `read_mag_data()` kept as dict-returning wrapper around `read_data()`

## 9. BMM350 Key Constants

- I2C Address: 0x14
- Chip ID: 0x33 (register 0x00)
- Data: 24-bit signed, 12 bytes (3 axes × 3 bytes + 3 bytes temp)
- Default conversion: X,Y = raw × 0.007069979 μT/LSB, Z = raw × 0.007174964 μT/LSB
- Temperature: raw × 0.000981282 − 25.49 °C