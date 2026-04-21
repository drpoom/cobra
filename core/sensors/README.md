# COBRA Sensor Specifications

This directory contains per-sensor JSON specifications — the **single source of truth** for sensor register maps, PMU commands, ODR settings, and conversion coefficients.

Each JSON file is consumed by `tools/gen_constants.py` to produce language-specific constant files:

```
core/sensors/bmm350.json
    → py/src/cobra_bridge/drivers/bmm350_constants.py
    → js/src/drivers/bmm350_constants.js
```

## JSON Schema

Each sensor JSON must follow this structure:

```json
{
  "_meta": {
    "name": "bmm350",
    "sensor_type": "magnetometer",
    "family": "bmm",
    "manufacturer": "Bosch Sensortec",
    "api_version": "1.10.0"
  },
  "i2c_addr": 20,
  "chip_id": 51,
  "data_len": 12,
  "spi_read_cmd": 128,
  "spi_write_cmd": 0,
  "registers": { ... },
  "pmu_commands": { ... },
  "pmu_status": { ... },
  "odr": { ... },
  "averaging": { ... },
  "otp_addr": { ... },
  "coefficients": { ... }
}
```

## Adding a New Sensor

1. Create `core/sensors/{sensor}.json` following the schema above
2. Run `python tools/gen_constants.py` from the repo root
3. Implement the driver class inheriting `SensorDriver` (Python + JS)
4. Import from the generated `{sensor}_constants` module

## Existing Sensors

| Sensor | Type | JSON | Driver |
|--------|------|------|--------|
| BMM350 | Magnetometer | `bmm350.json` | `BMM350Driver` / `BMM350AsyncDriver` |