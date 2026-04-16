#!/usr/bin/env python3
"""
COBRA Test — BMM350 Chip ID Reader

Scans for the Bosch AppBoard 3.1 over USB-Serial,
establishes a COINES V3 connection, and reads the BMM350 Chip ID.

Usage:
    python cobra_test.py                          # Auto-detect port
    python cobra_test.py /dev/ttyUSB0              # Specify port
    python cobra_test.py /dev/ttyACM0              # AppBoard ACM port
    python cobra_test.py --info                     # Show board info
    python cobra_test.py --monitor                  # Continuous data readout
    python cobra_test.py --monitor --odr 100        # Monitor at 100 Hz

Termux (Android):
    termux-usb -l                                  # List USB devices
    termux-usb -r -e python cobra_test.py /dev/bus/usb/001/002
"""

import sys
import time
import argparse


def auto_detect_port() -> str:
    """
    Try to auto-detect the AppBoard serial port.

    Checks common port names in order of likelihood.
    Returns first port that responds to COINES V3, or None.
    """
    import serial

    # Common port patterns for AppBoard 3.1
    candidates = [
        '/dev/ttyACM0',     # AppBoard USB-Serial (ACM)
        '/dev/ttyACM1',
        '/dev/ttyUSB0',     # USB-Serial adapter
        '/dev/ttyUSB1',
        '/dev/ttyAMA0',    # Raspberry Pi serial
    ]

    # On macOS
    import platform
    if platform.system() == 'Darwin':
        candidates = ['/dev/cu.usbmodem101', '/dev/cu.usbmodem1101',
                      '/dev/cu.usbserial-10', '/dev/tty.usbmodem101']

    # On Windows
    if platform.system() == 'Windows':
        candidates = ['COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8']

    from cobra_core import CobraBridge

    for port in candidates:
        try:
            bridge = CobraBridge(port=port, timeout=1.0)
            bridge.connect()
            # Try to read board info as connectivity test
            info = bridge.get_board_info()
            if info:
                print(f"✓ AppBoard found on {port}")
                bridge.disconnect()
                return port
            bridge.disconnect()
        except Exception:
            continue

    return None


def print_chip_id(bridge) -> None:
    """Read and display the BMM350 Chip ID."""
    from bmm350 import BMM350

    sensor = BMM350(bridge)
    chip_id = sensor.get_chip_id()
    expected = 0x33

    if chip_id == expected:
        print(f"  Chip ID: 0x{chip_id:02X} ✓ (BMM350 confirmed)")
    else:
        print(f"  Chip ID: 0x{chip_id:02X} ✗ (expected 0x{expected:02X})")
        print(f"  ⚠ Sensor may not be connected or address wrong")


def print_power_mode(bridge) -> None:
    """Read and display current power mode."""
    from bmm350 import BMM350

    sensor = BMM350(bridge)
    mode = sensor.get_power_mode()
    print(f"  Power Mode: {mode}")


def print_board_info(bridge) -> None:
    """Read and display board information."""
    try:
        info = bridge.get_board_info()
        print("  Board Info:")
        for key, val in info.items():
            if key == 'raw':
                print(f"    Raw bytes: {val.hex() if isinstance(val, bytes) else val}")
            else:
                print(f"    {key}: {val}")
    except Exception as e:
        print(f"  Board Info: unavailable ({e})")


def monitor_data(bridge, odr: int = 100, count: int = 0) -> None:
    """
    Continuous magnetic field data readout.

    Args:
        bridge: Connected CobraBridge instance
        odr:    Output data rate in Hz (25, 50, 100, 200, 400)
        count:  Number of samples (0 = infinite until Ctrl+C)
    """
    from bmm350 import BMM350, ODR_100HZ, ODR_200HZ, ODR_50HZ, ODR_25HZ, ODR_400HZ

    odr_map = {400: ODR_400HZ, 200: ODR_200HZ, 100: ODR_100HZ, 50: ODR_50HZ, 25: ODR_25HZ}
    odr_val = odr_map.get(odr, ODR_100HZ)

    sensor = BMM350(bridge)

    print(f"\n  Setting power mode to continuous @ {odr} Hz...")
    sensor.set_power_mode('continuous')
    sensor.set_odr(odr_val)
    time.sleep(0.05)

    print(f"  Reading magnetic field data (Ctrl+C to stop):\n")
    print(f"  {'Sample':>7}  {'X (uT)':>10}  {'Y (uT)':>10}  {'Z (uT)':>10}")
    print(f"  {'─'*7}  {'─'*10}  {'─'*10}  {'─'*10}")

    n = 0
    try:
        while count == 0 or n < count:
            if sensor.is_data_ready():
                data = sensor.read_mag_data()
                n += 1
                print(f"  {n:>7}  {data['x']:>10.2f}  {data['y']:>10.2f}  {data['z']:>10.2f}")
            else:
                time.sleep(0.001)
    except KeyboardInterrupt:
        print(f"\n  Stopped after {n} samples")

    sensor.set_power_mode('suspend')
    print("  Sensor suspended")


def main():
    parser = argparse.ArgumentParser(
        description='COBRA Test — BMM350 Magnetometer Reader',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('port', nargs='?', default=None,
                        help='Serial port (auto-detect if omitted)')
    parser.add_argument('--baud', type=int, default=115200,
                        help='Baud rate (default: 115200)')
    parser.add_argument('--info', action='store_true',
                        help='Show board information')
    parser.add_argument('--monitor', action='store_true',
                        help='Continuous data readout')
    parser.add_argument('--odr', type=int, default=100, choices=[25, 50, 100, 200, 400],
                        help='Output data rate in Hz for monitor mode (default: 100)')
    parser.add_argument('--count', type=int, default=0,
                        help='Number of samples in monitor mode (0=infinite)')

    args = parser.parse_args()

    # ── Header ─────────────────────────────────────────────────────────────
    print()
    print("🐍 COBRA — COines BRidge Access v1.0")
    print("━" * 40)

    # ── Port Detection ─────────────────────────────────────────────────────
    port = args.port
    if not port:
        print("  Auto-detecting AppBoard...")
        port = auto_detect_port()
        if not port:
            print("  ✗ No AppBoard found. Connect the board and try again.")
            print("  Specify port manually: python cobra_test.py /dev/ttyACM0")
            sys.exit(1)

    print(f"  Port: {port} @ {args.baud} baud")

    # ── Connect ─────────────────────────────────────────────────────────────
    from cobra_core import CobraBridge

    bridge = CobraBridge(port=port, baudrate=args.baud)
    try:
        bridge.connect()
        print("  ✓ Connected")
    except Exception as e:
        print(f"  ✗ Connection failed: {e}")
        sys.exit(1)

    # ── Board Info ───────────────────────────────────────────────────────────
    if args.info:
        print()
        print_board_info(bridge)

    # ── Chip ID ────────────────────────────────────────────────────────────
    print()
    print("  BMM350 Sensor:")
    print_chip_id(bridge)
    print_power_mode(bridge)

    # ── Monitor Mode ────────────────────────────────────────────────────────
    if args.monitor:
        monitor_data(bridge, odr=args.odr, count=args.count)

    # ── Cleanup ─────────────────────────────────────────────────────────────
    bridge.disconnect()
    print()
    print("  Disconnected. Bye! 🐍")


if __name__ == '__main__':
    main()