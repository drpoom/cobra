#!/usr/bin/env python3
"""
COBRA Test — BMM350 Chip ID Reader & Monitor

Usage:
    python bmm350_test.py                          # Auto-detect port
    python bmm350_test.py /dev/ttyACM0              # Specify port
    python bmm350_test.py --info                    # Board info
    python bmm350_test.py --monitor                 # Continuous readout
    python bmm350_test.py --monitor --odr 200       # Monitor at 200 Hz
"""

import sys
import time
import argparse


def auto_detect_port() -> str:
    """Try to auto-detect the AppBoard serial port."""
    import serial
    import platform

    candidates = {
        'Linux': ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyUSB0', '/dev/ttyUSB1'],
        'Darwin': ['/dev/cu.usbmodem101', '/dev/cu.usbmodem1101', '/dev/cu.usbserial-10'],
        'Windows': ['COM3', 'COM4', 'COM5', 'COM6'],
    }
    ports = candidates.get(platform.system(), candidates['Linux'])

    from cobra_sync import CobraBridge
    for port in ports:
        try:
            bridge = CobraBridge(port=port, timeout=1.0)
            bridge.connect()
            bridge.get_board_info()
            print(f"  ✓ AppBoard found on {port}")
            bridge.disconnect()
            return port
        except Exception:
            continue
    return None


def main():
    parser = argparse.ArgumentParser(description='COBRA — BMM350 Magnetometer Test')
    parser.add_argument('port', nargs='?', default=None, help='Serial port')
    parser.add_argument('--baud', type=int, default=115200, help='Baud rate')
    parser.add_argument('--info', action='store_true', help='Show board info')
    parser.add_argument('--monitor', action='store_true', help='Continuous readout')
    parser.add_argument('--odr', type=int, default=100, choices=[25, 50, 100, 200, 400])
    parser.add_argument('--count', type=int, default=0, help='Samples (0=infinite)')
    args = parser.parse_args()

    print("\n🐍 COBRA — COines BRidge Access v1.0")
    print("━" * 40)

    port = args.port
    if not port:
        print("  Auto-detecting AppBoard...")
        port = auto_detect_port()
        if not port:
            print("  ✗ No AppBoard found. Try: python bmm350_test.py /dev/ttyACM0")
            sys.exit(1)

    print(f"  Port: {port} @ {args.baud} baud")

    from cobra_sync import CobraBridge
    from bmm350_sync import BMM350
    from cobra_constants import BMM350_ODR

    bridge = CobraBridge(port=port, baudrate=args.baud)
    try:
        bridge.connect()
        print("  ✓ Connected")
    except Exception as e:
        print(f"  ✗ Connection failed: {e}")
        sys.exit(1)

    if args.info:
        print()
        info = bridge.get_board_info()
        for k, v in info.items():
            print(f"  {k}: {v.hex() if isinstance(v, bytes) else v}")

    # ── Chip ID ────────────────────────────────────────────────────────────
    print("\n  BMM350 Sensor:")
    sensor = BMM350(bridge)
    chip_id = sensor.get_chip_id()
    if chip_id == 0x33:
        print(f"  Chip ID: 0x{chip_id:02X} ✓ (BMM350 confirmed)")
    else:
        print(f"  Chip ID: 0x{chip_id:02X} ✗ (expected 0x33)")
    print(f"  Power Mode: {sensor.get_power_mode()}")

    # ── Monitor ───────────────────────────────────────────────────────────
    if args.monitor:
        odr_key_map = {400: '400_HZ', 200: '200_HZ', 100: '100_HZ', 50: '50_HZ', 25: '25_HZ'}
        sensor.set_power_mode('continuous')
        sensor.set_odr(odr_key_map.get(args.odr, '100_HZ'))
        time.sleep(0.05)
        print(f"\n  Monitoring @ {args.odr} Hz (Ctrl+C to stop):\n")
        print(f"  {'#':>7}  {'X(uT)':>10}  {'Y(uT)':>10}  {'Z(uT)':>10}")
        print(f"  {'─'*7}  {'─'*10}  {'─'*10}  {'─'*10}")
        n = 0
        try:
            while args.count == 0 or n < args.count:
                if sensor.is_data_ready():
                    d = sensor.read_mag_data()
                    n += 1
                    print(f"  {n:>7}  {d['x']:>10.2f}  {d['y']:>10.2f}  {d['z']:>10.2f}")
                else:
                    time.sleep(0.001)
        except KeyboardInterrupt:
            print(f"\n  Stopped after {n} samples")
        sensor.set_power_mode('suspend')

    bridge.disconnect()
    print("\n  Disconnected. 🐍\n")


if __name__ == '__main__':
    main()