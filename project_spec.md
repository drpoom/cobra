# COBRA: COines BRidge Access

Developer: drpoom
Target Hardware: Bosch Application Board 3.1
Primary Sensor: BMM350 Magnetometer (via Shuttle Board)
Languages: Python 3.x, JavaScript (ES6+)
Transports: USB-Serial (pyserial/WebSerial), BLE (Bleak/WebBluetooth)

## 1. Project Vision

COBRA is a lightweight, transport-agnostic library for interfacing with the Bosch Sensortec AppBoard 3.1. By implementing the COINES Bridge Protocol (V3) in native Python and JavaScript, COBRA enables sensor testing on any platform — mobile (Android/Termux), desktop, or browser — over USB-Serial or BLE.

The architecture separates transport (I/O) from protocol (packet framing) from driver (sensor logic). Only the transport layer changes per backend; the packetizer and BMM350 driver remain identical.

## 2. Architecture

```
         ┌──────────────┐     ┌─────────────┐
         │  CobraBridge │────▶│  Transport  │  ← abstract base
         │  (Packetizer)│     │  (I/O)      │
         └──────────────┘     └─────────────┘
                                   │
                       ┌───────────┴───────────┐
                       │                       │
                 ┌─────┴─────┐          ┌──────┴──────┐
                 │  Serial   │          │    BLE      │
                 │ Transport │          │  Transport  │
                 │(pyserial/ │          │  (Bleak/    │
                 │ WebSerial)│          │ WebBluetooth)│
                 └───────────┘          └─────────────┘
```

## 3. Tiers

| Tier | Mode | Python | JavaScript | Features |
|------|------|--------|------------|----------|
| **Sync** | Request-response blocking | `cobra_sync.py` | `cobra_sync.js` | I2C/SPI, board control, BMM350 driver |
| **Async** | Non-blocking threaded reads | `cobra_async.py` | — | 400Hz polling, stale eviction, queue-based |
| **Streaming** | Binary streaming @ 6.4kHz | 🔜 | 🔜 | μs timestamps, sensor fusion |

## 4. Transport Backends

| Transport | Python | JavaScript |
|-----------|--------|------------|
| **USB-Serial** | `SerialTransport` (pyserial) | `SerialTransport` (WebSerial API) |
| **BLE** | `BleTransport` (Bleak) | `BleTransport` (WebBluetooth API) |

BLE uses Nordic UART Service (NUS):
- Service: `6e400001-b5a3-f393-e0a9-e50e24dcca9e`
- RX (write): `6e400002-b5a3-f393-e0a9-e50e24dcca9e`
- TX (notify): `6e400003-b5a3-f393-e0a9-e50e24dcca9e`
- GATT write chunk size: 20 bytes (safe default)

## 5. File Map

```
python/
├── cobra_constants.py       # Constants from protocol_spec.json
├── cobra_transport.py       # Transport ABC + SerialTransport + BleTransport
├── cobra_sync.py            # CobraBridge — sync protocol (any transport)
├── cobra_reader.py          # CobraReader — background serial reader thread
├── cobra_async.py           # AsyncBridge — CobraBridge + CobraReader/TransportReader
├── bmm350_sync.py           # BMM350 blocking driver
├── bmm350_async.py          # BMM350Async — non-blocking 400Hz driver
├── test_sync.py             # CLI test tool (sync)
├── test_async.py            # Async monitor with CSV/JSON logging
└── generate_constants_js.py # Auto-generates JS constants from JSON

javascript/
├── cobra_constants.js       # Auto-generated from protocol_spec.json
├── cobra_transport.js       # SerialTransport + BleTransport (Web APIs)
├── cobra_sync.js            # CobraBridge — sync protocol (any transport)
├── bmm350.js                # BMM350 driver (mirrors Python API)
└── index.html               # One-page BMM350 dashboard
```

## 6. COINES V3 Packet Structure

| Byte | Field      | Value / Description                              |
|------|-----------|--------------------------------------------------|
| 0    | Header    | 0xAA                                             |
| 1    | Type      | 0x01 (Get), 0x02 (Set)                           |
| 2    | Command ID | e.g., 0x0E (I2C Read), 0x0D (I2C Write)       |
| 3-4  | Length    | Payload length (Little Endian)                  |
| 5...N| Payload   | The raw I2C/SPI command data                     |
| N+1  | Checksum  | XOR sum of bytes 0 through N                     |

## 7. BMM350 Key Constants

- I2C Address: 0x14
- Chip ID: 0x33 (register 0x00)
- Data: 24-bit signed, 12 bytes (3 axes × 3 bytes + 3 bytes temp)
- Default conversion: X,Y = raw × 0.007069979 μT/LSB, Z = raw × 0.007174964 μT/LSB
- Temperature: raw × 0.000981282 − 25.49 °C
- ODR set via PMU_CMD_AGGR_SET (0x04), committed with PMU_CMD UPD_OAE (0x02 → 0x06)

## 8. Development Notes

- **Single source of truth**: `core/protocol_spec.json` — all constants derive from it
- **JSON wins** if it disagrees with PROTOCOL.md
- **Python loads JSON at import** (no build step)
- **JS constants auto-generated** via `python generate_constants_js.py`
- **Transport injection**: `CobraBridge(transport=...)` accepts any Transport instance
- **Backward compatible**: `CobraBridge(port='/dev/ttyACM0')` auto-creates SerialTransport
- **BLE async/sync bridge**: `BleTransport` uses asyncio.run() for sync API compatibility