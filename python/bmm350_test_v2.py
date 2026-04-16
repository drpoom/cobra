#!/usr/bin/env python3
"""
COBRA V2 Test — Async BMM350 Monitor

Non-blocking high-rate magnetometer readout using CobraReader thread.

Usage:
    python bmm350_test_v2.py                          # Auto-detect, monitor @ 100 Hz
    python bmm350_test_v2.py /dev/ttyACM0              # Specify port
    python bmm350_test_v2.py --odr 400                 # 400 Hz
    python bmm350_test_v2.py --odr 400 --csv out.csv   # Log to CSV
    python bmm350_test_v2.py --json out.json            # Log to JSON
    python bmm350_test_v2.py --info                    # Board info only
"""

import sys
import time
import json
import csv
import argparse
from datetime import datetime


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

    from cobra_core import CobraBridge
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
    parser = argparse.ArgumentParser(description='COBRA V2 — Async BMM350 Monitor')
    parser.add_argument('port', nargs='?', default=None, help='Serial port')
    parser.add_argument('--baud', type=int, default=115200, help='Baud rate')
    parser.add_argument('--info', action='store_true', help='Show board info')
    parser.add_argument('--odr', type=int, default=100, choices=[25, 50, 100, 200, 400],
                        help='Output data rate (Hz)')
    parser.add_argument('--count', type=int, default=0, help='Samples (0=infinite)')
    parser.add_argument('--csv', type=str, default=None, help='Log to CSV file')
    parser.add_argument('--json', type=str, default=None, help='Log to JSON file')
    parser.add_argument('--stats-interval', type=float, default=5.0,
                        help='Print stats every N seconds (default 5)')
    args = parser.parse_args()

    print("\n🐍 COBRA V2 — Async COines BRidge Access")
    print("━" * 42)

    port = args.port
    if not port:
        print("  Auto-detecting AppBoard...")
        port = auto_detect_port()
        if not port:
            print("  ✗ No AppBoard found. Try: python bmm350_test_v2.py /dev/ttyACM0")
            sys.exit(1)

    print(f"  Port: {port} @ {args.baud} baud")

    from cobra_bridge_v2 import AsyncBridge
    from bmm350_v2 import BMM350Async

    bridge = AsyncBridge(port=port, baudrate=args.baud, max_queue_size=64)
    try:
        bridge.connect()
        print("  ✓ Connected (V2 async reader active)")
    except Exception as e:
        print(f"  ✗ Connection failed: {e}")
        sys.exit(1)

    # Board info
    if args.info:
        info = bridge.get_board_info()
        for k, v in info.items():
            print(f"  {k}: {v.hex() if isinstance(v, bytes) else v}")

    # Chip ID
    sensor = BMM350Async(bridge, stale_threshold=8)
    chip_id = sensor.get_chip_id()
    if chip_id == 0x33:
        print(f"  Chip ID: 0x{chip_id:02X} ✓ (BMM350 confirmed)")
    else:
        print(f"  Chip ID: 0x{chip_id:02X} ✗ (expected 0x33)")

    # Start monitoring
    odr_key_map = {400: '400_HZ', 200: '200_HZ', 100: '100_HZ',
                   50: '50_HZ', 25: '25_HZ'}
    odr_key = odr_key_map.get(args.odr, '100_HZ')

    print(f"\n  Starting continuous @ {args.odr} Hz...")
    sensor.start_continuous(odr=odr_key)
    time.sleep(0.05)

    # Setup logging
    csv_writer = None
    csv_file = None
    json_log = []

    if args.csv:
        csv_file = open(args.csv, 'w', newline='')
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(['timestamp', 'x_ut', 'y_ut', 'z_ut', 'x_raw', 'y_raw', 'z_raw'])

    # Monitor loop
    n = 0
    start_time = time.time()
    last_stats_time = start_time
    poll_sleep = 1.0 / (args.odr * 2)  # Poll at 2x ODR for responsiveness

    print(f"\n  {'#':>7}  {'X(uT)':>10}  {'Y(uT)':>10}  {'Z(uT)':>10}  {'Rate':>8}")
    print(f"  {'─'*7}  {'─'*10}  {'─'*10}  {'─'*10}  {'─'*8}")

    try:
        while args.count == 0 or n < args.count:
            data = sensor.read_sensor()
            if data is not None:
                n += 1
                elapsed = time.time() - start_time
                rate = n / elapsed if elapsed > 0 else 0

                # Console output (throttled to ~10 Hz for readability)
                if n % max(1, args.odr // 10) == 0 or n <= 5:
                    print(f"  {n:>7}  {data['x']:>10.2f}  {data['y']:>10.2f}  "
                          f"{data['z']:>10.2f}  {rate:>7.1f}Hz")

                # CSV logging
                if csv_writer:
                    csv_writer.writerow([
                        datetime.now().isoformat(),
                        f"{data['x']:.4f}", f"{data['y']:.4f}", f"{data['z']:.4f}",
                        data['x_raw'], data['y_raw'], data['z_raw'],
                    ])

                # JSON logging
                if args.json:
                    json_log.append({
                        't': datetime.now().isoformat(),
                        'x': data['x'], 'y': data['y'], 'z': data['z'],
                        'x_raw': data['x_raw'], 'y_raw': data['y_raw'], 'z_raw': data['z_raw'],
                    })
            else:
                time.sleep(poll_sleep)

            # Periodic stats
            now = time.time()
            if now - last_stats_time >= args.stats_interval:
                last_stats_time = now
                d_stats = sensor.get_stats()
                r_stats = bridge.get_reader_stats()
                print(f"\n  ── Stats (sample {n}) ──")
                print(f"  Driver: sent={d_stats['reads_sent']} recv={d_stats['reads_received']} "
                      f"stale={d_stats['stale_dropped']} pending={d_stats['pending']}")
                print(f"  Reader: pkts={r_stats.get('packets_received', 0)} "
                      f"cksum_err={r_stats.get('checksum_errors', 0)} "
                      f"overflow={r_stats.get('overflows_dropped', 0)} "
                      f"queue={r_stats.get('queue_size', 0)}\n")

    except KeyboardInterrupt:
        elapsed = time.time() - start_time
        rate = n / elapsed if elapsed > 0 else 0
        print(f"\n  Stopped after {n} samples ({rate:.1f} Hz avg)")

    sensor.stop_continuous()

    # Write JSON
    if args.json and json_log:
        with open(args.json, 'w') as f:
            json.dump({'odr': args.odr, 'samples': json_log}, f, indent=2)
        print(f"  JSON logged to {args.json}")

    if csv_file:
        csv_file.close()
        print(f"  CSV logged to {args.csv}")

    # Final stats
    d_stats = sensor.get_stats()
    r_stats = bridge.get_reader_stats()
    print(f"\n  Final Stats:")
    print(f"  Samples: {d_stats['sample_count']}")
    print(f"  Driver:  sent={d_stats['reads_sent']} recv={d_stats['reads_received']} "
          f"stale_dropped={d_stats['stale_dropped']}")
    print(f"  Reader:  pkts={r_stats.get('packets_received', 0)} "
          f"cksum_err={r_stats.get('checksum_errors', 0)} "
          f"overflow={r_stats.get('overflows_dropped', 0)}")

    bridge.disconnect()
    print("\n  Disconnected. 🐍\n")


if __name__ == '__main__':
    main()