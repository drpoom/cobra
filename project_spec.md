# COBRA: COines BRidge Access

Developer: drpoom
Target Hardware: Bosch Application Board 3.1
Primary Sensor: BMM350 Magnetometer (via Shuttle Board)
Language: Pure Python 3.x (No C-extensions)

## 1. Project Vision
COBRA is a lightweight, dependency-free Python library designed to interface with the Bosch Sensortec AppBoard 3.1. By implementing the COINES Bridge Protocol (V3) in native Python, COBRA enables sensor testing on mobile devices (Android/Termux) and embedded systems where the official Bosch SDK cannot be easily installed.

## 2. Technical Roadmap

### V1: Proof of Concept (Current Target)
- Mode: Synchronous Polling (Request-Response).
- Features:
  - Binary packetizer for COINES V3.
  - Support for I2C Read/Write commands.
  - Support for SPI Read/Write commands.
  - Basic BMM350 driver (Chip ID, Power Mode, Data Read).
- Connectivity: USB-Serial (via pyserial).

### V2: Performance Upgrade (Planned)
- Mode: Asynchronous Non-blocking IO.
- Features:
  - Threaded serial reading to prevent UI lag.
  - Higher Output Data Rates (ODR) up to 400Hz for BMM350.
  - Real-time data logging to CSV/JSON.

### PRO: High-Speed Streaming (Planned)
- Mode: Binary Streaming & Hardware Interrupts.
- Features:
  - Implementation of COINES Streaming Protocol (up to 6.4 kHz).
  - Support for microsecond (μs) hardware timestamps.
  - Advanced sensor fusion integration.

## 3. COINES V3 Packet Structure
The AI agent must implement the following binary frame for all communications:

| Byte | Field    | Value / Description                              |
|------|----------|--------------------------------------------------|
| 0    | Header   | 0xAA                                             |
| 1    | Type     | 0x01 (Get), 0x02 (Set)                           |
| 2    | Command ID | e.g., 0x0E (I2C Read), 0x0D (I2C Write)       |
| 3-4  | Length   | Payload length (Little Endian)                  |
| 5...N| Payload  | The raw I2C/SPI command data                     |
| N+1  | Checksum | XOR sum of bytes 0 through N                     |

## 4. BMM350 Initial Configuration (V1 Test)
- I2C Address: 0x14
- Chip ID Register: 0x00 (Expected Return: 0x33)
- Main Goal: Successfully read the Chip ID over USB-OTG on Android.

## 5. Development Instructions for OpenClaw/GLM 5.1
1. **Module cobra_core.py**: Create a class CobraBridge that handles serial port initialization and send_packet() / receive_packet() logic.
2. **Module bmm350.py**: Create a class BMM350 that inherits from or uses CobraBridge to perform register-level operations.
3. **CLI Tool cobra_test.py**: A simple script to scan for the AppBoard and print the BMM350 Chip ID.

## 6. Installation (Mobile/Termux)
```bash
pkg install python
pip install pyserial
# Grant USB permissions in Termux
termux-usb -l
python cobra_test.py
```

### Next Steps
- **Initialize the Repo:** Create the repository drpoom/cobra on GitHub.
- **Protocol Implementation:** Focus on the `struct.pack` and `struct.unpack` logic for the binary packets — that is the "heart" of COBRA.
- **BMM350 Logic:** Map BMM350 register addresses to the COBRA I2C_READ/WRITE commands.