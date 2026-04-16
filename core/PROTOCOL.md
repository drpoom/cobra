# COINES Bridge Protocol V3 — Language-Agnostic Specification

This directory defines the COBRA protocol layer. All implementations (Python, JavaScript, future bindings) MUST follow this specification exactly.

## 1. Packet Frame Format

All COINES V3 communication uses a binary frame with the following structure:

```
┌────────┬──────┬────────────┬────────────┬───────────┬───────────┐
│ Header │ Type │ Command ID │ Length (2) │ Payload   │ Checksum  │
│ 0xAA   │ 1 B  │ 1 B        │ LE uint16  │ N bytes   │ 1 B       │
└────────┴──────┴────────────┴────────────┴───────────┴───────────┘

Total: 5 + N + 1 = N + 6 bytes
```

| Offset | Size | Field       | Description                                      |
|--------|------|-------------|--------------------------------------------------|
| 0      | 1    | Header      | Always `0xAA`                                    |
| 1      | 1    | Type        | `0x01` = Get (read), `0x02` = Set (write)        |
| 2      | 1    | Command ID  | See §2 for command table                         |
| 3-4    | 2    | Length      | Payload length in bytes, **Little Endian** uint16 |
| 5..N   | N    | Payload     | Command-specific data                            |
| N+1    | 1    | Checksum    | XOR of all preceding bytes (offset 0 through N)  |

### Checksum Algorithm

```
checksum = 0
for each byte b in frame[0..N]:
    checksum = checksum XOR b
```

The checksum byte is appended after the payload. The receiver recalculates XOR over the full frame (excluding the checksum byte itself) and compares.

### Packet Building Algorithm (Pseudocode)

```
function build_packet(type, command, payload):
    length = len(payload)
    frame[0] = 0xAA                   // Header
    frame[1] = type                   // Type: 0x01 or 0x02
    frame[2] = command                // Command ID
    frame[3] = length & 0xFF          // Length low byte
    frame[4] = (length >> 8) & 0xFF   // Length high byte
    frame[5..5+length] = payload      // Payload bytes
    xor = 0
    for i = 0 to 4 + length:
        xor = xor XOR frame[i]
    frame[5 + length] = xor           // Checksum
    return frame
```

### Packet Parsing Algorithm (Pseudocode)

```
function parse_packet(stream):
    // 1. Wait for header byte
    wait until byte == 0xAA

    // 2. Read type, command, length (4 bytes)
    type     = read_byte()
    command  = read_byte()
    length_lo = read_byte()
    length_hi = read_byte()
    length   = length_lo | (length_hi << 8)

    // 3. Read payload
    payload = read_bytes(length)

    // 4. Read checksum
    received_xor = read_byte()

    // 5. Verify checksum
    frame = [0xAA, type, command, length_lo, length_hi] + payload
    expected_xor = XOR_reduce(frame)
    if expected_xor != received_xor:
        raise ChecksumError

    // 6. Extract status
    status = payload[0]     // First byte of response payload is status
    data   = payload[1:]    // Remaining bytes are command-specific data

    return {type, command, status, data}
```

## 2. Command Constants

These constants are shared across ALL implementations. Values are decimal with hex in parentheses.

### Packet Types

| Constant     | Value | Description        |
|-------------|-------|--------------------|
| TYPE_GET    | 1     | Read request       |
| TYPE_SET    | 2     | Write request      |

### System Commands

| Constant          | Value | Description               |
|------------------|-------|---------------------------|
| CMD_GET_BOARD_INFO | 1   | Read board identification |
| CMD_SET_PIN       | 5    | Configure GPIO pin        |
| CMD_SET_VDD       | 4    | Set VDD voltage (mV)      |
| CMD_SET_VDDIO     | 6    | Set VDDIO voltage (mV)    |
| CMD_INT_CONFIG    | 7    | Configure interrupts      |

### I2C Commands

| Constant          | Value | Description               |
|------------------|-------|---------------------------|
| CMD_I2C_WRITE    | 13    | I2C write transaction     |
| CMD_I2C_READ     | 14    | I2C read transaction      |

### SPI Commands

| Constant          | Value | Description               |
|------------------|-------|---------------------------|
| CMD_SPI_WRITE    | 19    | SPI write transaction     |
| CMD_SPI_READ     | 20    | SPI read transaction      |

### Response Status

| Constant     | Value | Description  |
|-------------|-------|-------------|
| STATUS_OK   | 0     | Success     |

## 3. I2C Command Payloads

### I2C Write (CMD_I2C_WRITE = 13)

**Request payload:**

| Offset | Size | Field     | Description                          |
|--------|------|-----------|--------------------------------------|
| 0      | 1    | DevAddr   | 7-bit I2C device address             |
| 1      | 1    | Speed     | 0 = 400 kHz, 1 = 1 MHz              |
| 2      | 1    | RegAddr   | Register address to write             |
| 3      | 1    | DataLen   | Number of data bytes following        |
| 4..N   | N    | Data      | Bytes to write to the register        |

### I2C Read (CMD_I2C_READ = 14)

**Request payload:**

| Offset | Size | Field     | Description                          |
|--------|------|-----------|--------------------------------------|
| 0      | 1    | DevAddr   | 7-bit I2C device address             |
| 1      | 1    | Speed     | 0 = 400 kHz, 1 = 1 MHz              |
| 2      | 1    | RegAddr   | Register address to read from         |
| 3      | 1    | Length    | Number of bytes to read               |

**Response payload** (after status byte):

| Offset | Size | Field | Description        |
|--------|------|-------|--------------------|
| 0..N   | N    | Data  | Bytes read from register |

## 4. SPI Command Payloads

### SPI Write (CMD_SPI_WRITE = 19)

**Request payload:**

| Offset | Size | Field     | Description                          |
|--------|------|-----------|--------------------------------------|
| 0      | 1    | CS        | Chip-select line index               |
| 1      | 1    | Speed     | 0 = 5 MHz, 1 = 10 MHz              |
| 2      | 1    | Mode      | 0 = SPI_MODE_0, 3 = SPI_MODE_3      |
| 3      | 1    | RegAddr   | Register address to write            |
| 4      | 1    | DataLen   | Number of data bytes                 |
| 5..N   | N    | Data      | Bytes to write                       |

### SPI Read (CMD_SPI_READ = 20)

**Request payload:**

| Offset | Size | Field     | Description                          |
|--------|------|-----------|--------------------------------------|
| 0      | 1    | CS        | Chip-select line index               |
| 1      | 1    | Speed     | 0 = 5 MHz, 1 = 10 MHz              |
| 2      | 1    | Mode      | 0 = SPI_MODE_0, 3 = SPI_MODE_3      |
| 3      | 1    | RegAddr   | Register address to read from        |
| 4      | 1    | Length    | Number of bytes to read              |

**Response payload** (after status byte):

| Offset | Size | Field | Description        |
|--------|------|-------|--------------------|
| 0..N   | N    | Data  | Bytes read from register |

## 5. System Command Payloads

### Set VDD (CMD_SET_VDD = 4)

**Request payload:**

| Offset | Size | Field     | Description                     |
|--------|------|-----------|--------------------------------|
| 0-1    | 2    | Voltage   | Millivolts, LE uint16. 0=off   |

### Set VDDIO (CMD_SET_VDDIO = 6)

**Request payload:**

| Offset | Size | Field     | Description                     |
|--------|------|-----------|--------------------------------|
| 0-1    | 2    | Voltage   | Millivolts, LE uint16. 0=off   |

## 6. BMM350 Register Map

These registers are sensor-specific, not protocol-level. Included here for cross-language reference.

| Register   | Address | Access | Description              |
|-----------|---------|--------|--------------------------|
| CHIP_ID   | 0x00    | R      | Chip ID (expected: 0x33) |
| PMU_CMD   | 0x02    | W      | Power mode command       |
| PMU_STATUS| 0x03    | R      | Current power mode       |
| ODR_AXIS  | 0x21    | R/W    | ODR and axis enable      |
| DATA_X_LSB| 0x30    | R      | X-axis LSB               |
| DATA_X_MSB| 0x31    | R      | X-axis MSB               |
| DATA_Y_LSB| 0x32    | R      | Y-axis LSB               |
| DATA_Y_MSB| 0x33    | R      | Y-axis MSB               |
| DATA_Z_LSB| 0x34    | R      | Z-axis LSB               |
| DATA_Z_MSB| 0x35    | R      | Z-axis MSB               |
| ERR_STAT  | 0x3E    | R      | Error status             |
| STATUS    | 0x3F    | R      | Data ready flag          |

### BMM350 Constants

| Constant            | Value | Description             |
|--------------------|-------|-------------------------|
| BMM350_I2C_ADDR    | 0x14  | Default I2C address     |
| BMM350_CHIP_ID     | 0x33  | Expected chip ID value  |
| BMM350_SENSITIVITY  | 1/6   | uT per LSB              |

### Power Mode Commands (write to PMU_CMD)

| Mode        | Value |
|------------|-------|
| SUSPEND    | 0x01  |
| NORMAL     | 0x02  |
| FORCED     | 0x03  |
| CONTINUOUS | 0x04  |
| SOFT_RESET | 0x80  |

### ODR Settings (bits [6:4] of ODR_AXIS)

| ODR     | Value |
|--------|-------|
| 400 Hz | 0x00  |
| 200 Hz | 0x01  |
| 100 Hz | 0x02  |
| 50 Hz  | 0x03  |
| 25 Hz  | 0x04  |
| 12.5 Hz| 0x05  |
| 6.25 Hz| 0x06  |