#!/usr/bin/env python3
"""
COBRA BMM350 Examples — Python port of Bosch BMM350_SensorAPI examples

Mirrors the official C examples from:
  https://github.com/boschsensortec/BMM350_SensorAPI/tree/main/examples

Each example is a CLI subcommand. No C SDK, no compiled binaries —
just pure Python with cobra-bridge.

Usage:
    python -m cobra_bridge.examples.bmm350_examples chip-id
    python -m cobra_bridge.examples.bmm350_examples polling --count 20
    python -m cobra_bridge.examples.bmm350_examples normal-mode --odr 100 --count 30
    python -m cobra_bridge.examples.bmm350_examples forced-mode --count 10
    python -m cobra_bridge.examples.bmm350_examples self-test
    python -m cobra_bridge.examples.bmm350_examples magnetic-reset --count 20
    python -m cobra_bridge.examples.bmm350_examples config-changes --count 20
    python -m cobra_bridge.examples.bmm350_examples async-stream --odr 400 --count 100

Quick start (first use):
    python -m cobra_bridge.examples.bmm350_examples chip-id

Requires: cobra-bridge (pip install cobra-bridge)
Hardware: Bosch AppBoard 3.1+ with BMM350 shuttle board
"""

import argparse
import math
import sys
import time
from typing import List


# ── Helpers ────────────────────────────────────────────────────────────────


def auto_detect_port() -> str:
    """Try to auto-detect the AppBoard serial port."""
    import serial.tools.list_ports

    for port in serial.tools.list_ports.comports():
        # AppBoard 3.1 typically shows as USB ACM device
        if 'ACM' in port.device or 'usbmodem' in port.device or 'usbserial' in port.device:
            return port.device
    # Fallbacks by platform
    import platform
    candidates = {
        'Linux': ['/dev/ttyACM0', '/dev/ttyACM1'],
        'Darwin': ['/dev/cu.usbmodem101', '/dev/cu.usbmodem1101'],
        'Windows': ['COM3', 'COM4', 'COM5'],
    }
    for p in candidates.get(platform.system(), []):
        try:
            import serial
            s = serial.Serial(p, timeout=0.5)
            s.close()
            return p
        except Exception:
            continue
    return None


def create_board(port: str = None, baud: int = 115200):
    """Create and return a connected CobraBoard + BMM350Driver."""
    from cobra_bridge.cobra_wrapper import CobraBoard
    from cobra_bridge.drivers.bmm350 import BMM350Driver

    if port is None:
        port = auto_detect_port()
    if port is None:
        print("  ✗ No AppBoard found. Specify port with --port")
        sys.exit(1)

    board = CobraBoard()
    board.open_comm_interface(0)  # USB

    sensor = BMM350Driver(board, interface="i2c", bus=0)
    return board, sensor


def create_async_board(port: str = None, baud: int = 115200):
    """Create and return a connected AsyncCobraBoard + BMM350AsyncDriver."""
    from cobra_bridge.cobra_wrapper import AsyncCobraBoard
    from cobra_bridge.drivers.bmm350_async import BMM350AsyncDriver

    if port is None:
        port = auto_detect_port()
    if port is None:
        print("  ✗ No AppBoard found. Specify port with --port")
        sys.exit(1)

    board = AsyncCobraBoard()
    board.open_comm_interface(0)

    sensor = BMM350AsyncDriver(board, interface="i2c", bus=0)
    return board, sensor


def print_header(title: str):
    print(f"\n{'━' * 60}")
    print(f"  {title}")
    print(f"{'━' * 60}")


def print_data_row(t_ms: int, x: float, y: float, z: float, temp: float):
    """Print one CSV-style data row (mirrors Bosch printf format)."""
    print(f"{t_ms}, {x:.4f}, {y:.4f}, {z:.4f}, {temp:.4f}")


def calculate_noise(samples: List[dict], avg_x: float, avg_y: float, avg_z: float):
    """Calculate noise level (standard deviation) — mirrors Bosch calculate_noise()."""
    n = len(samples)
    if n < 2:
        return

    var_x = sum((s['x'] - avg_x) ** 2 for s in samples) / (n - 1)
    var_y = sum((s['y'] - avg_y) ** 2 for s in samples) / (n - 1)
    var_z = sum((s['z'] - avg_z) ** 2 for s in samples) / (n - 1)

    noise_x = math.sqrt(var_x)
    noise_y = math.sqrt(var_y)
    noise_z = math.sqrt(var_z)

    print(f"\n  Noise (σ):  X={noise_x:.4f}  Y={noise_y:.4f}  Z={noise_z:.4f} μT")


def wait_for_data_ready(sensor, timeout: float = 1.0) -> bool:
    """Poll INT_STATUS until DRDY bit is set (mirrors Bosch polling loop)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if sensor.is_data_ready():
            return True
        time.sleep(0.001)
    return False


# ── Example: chip-id ──────────────────────────────────────────────────────


def cmd_chip_id(args):
    """Read and verify BMM350 chip ID.

    Mirrors: bmm350_interface_init + bmm350_init chip ID check.
    """
    print_header("BMM350 Chip ID Verification")
    board, sensor = create_board(args.port)

    try:
        sensor.setup_board()
        sensor.init()

        chip_id = sensor.get_chip_id()
        print(f"\n  Chip ID: 0x{chip_id:02X}")
        if chip_id == 0x33:
            print("  ✓ BMM350 confirmed")
        else:
            print(f"  ✗ Expected 0x33")

        # Show power mode (mirrors Bosch PMU status check)
        pm = sensor.get_power_mode()
        print(f"  Power mode: {pm}")

        # Show error status
        err = sensor.read_error_status()
        print(f"  Error register: 0x{err:02X}")

        # Show OTP status
        print(f"  OTP loaded: {sensor.otp_loaded}")

    finally:
        board.close_comm_interface()


# ── Example: polling ──────────────────────────────────────────────────────


def cmd_polling(args):
    """Read magnetometer data by polling INT_STATUS register.

    Mirrors: bmm350_polling.c — reads N samples in normal mode,
    first with delay-based polling, then with INT_STATUS check.
    """
    print_header("BMM350 Polling Read")
    board, sensor = create_board(args.port)

    try:
        sensor.setup_board()
        sensor.init()

        # Enable all axes
        sensor.enable_axes(x=True, y=True, z=True)

        # Set ODR and averaging
        sensor.set_odr(args.odr, 'low_power')
        sensor.set_power_mode('normal')
        time.sleep(0.05)

        count = args.count

        # ── Phase 1: Delay-based polling (mirrors Bosch first loop) ──────
        print(f"\n  Delay-based polling @ {args.odr} Hz, {count} samples")
        print("  Timestamp(ms), Mag_X(uT), Mag_Y(uT), Mag_Z(uT), Temperature(degC)")

        t0 = time.monotonic()
        for i in range(count):
            # Delay between reads (mirrors bmm350_delay_us)
            delay_s = 1.0 / args.odr
            time.sleep(delay_s)
            data = sensor.read_data(compensated=args.compensated)
            t_ms = int((time.monotonic() - t0) * 1000)
            print_data_row(t_ms, data.x, data.y, data.z, data.temperature)

        # ── Phase 2: INT_STATUS polling (mirrors Bosch second loop) ─────
        print(f"\n  INT_STATUS polling @ {args.odr} Hz, {count} samples")
        print("  Timestamp(ms), Mag_X(uT), Mag_Y(uT), Mag_Z(uT), Temperature(degC)")

        t0 = time.monotonic()
        for i in range(count):
            if wait_for_data_ready(sensor):
                data = sensor.read_data(compensated=args.compensated)
                t_ms = int((time.monotonic() - t0) * 1000)
                print_data_row(t_ms, data.x, data.y, data.z, data.temperature)

    finally:
        board.close_comm_interface()


# ── Example: normal-mode ──────────────────────────────────────────────────


def cmd_normal_mode(args):
    """Read magnetometer data in normal (continuous) mode.

    Mirrors: bmm350_normal_mode.c — reads raw + compensated data,
    shows OTP coefficients, reads with INT_STATUS check.
    """
    print_header("BMM350 Normal Mode")
    board, sensor = create_board(args.port)

    try:
        sensor.setup_board()
        sensor.init()

        chip_id = sensor.get_chip_id()
        print(f"\n  Chip ID: 0x{chip_id:02X}")

        # Show OTP coefficients (mirrors Bosch coefficient printout)
        if sensor.otp_loaded:
            print("\n  ── OTP Coefficients ──")
            print(f"  Offset:  X={sensor._offset['x']:.4f}  Y={sensor._offset['y']:.4f}  Z={sensor._offset['z']:.4f}")
            print(f"  Sensitivity:  X={sensor._sensit['x']:.6f}  Y={sensor._sensit['y']:.6f}  Z={sensor._sensit['z']:.6f}")
            print(f"  TCO:  X={sensor._tco['x']:.4f}  Y={sensor._tco['y']:.4f}  Z={sensor._tco['z']:.4f}")
            print(f"  TCS:  X={sensor._tcs['x']:.6f}  Y={sensor._tcs['y']:.6f}  Z={sensor._tcs['z']:.6f}")
            print(f"  Cross:  XY={sensor._cross['x_y']:.6f}  YX={sensor._cross['y_x']:.6f}  ZX={sensor._cross['z_x']:.6f}  ZY={sensor._cross['z_y']:.6f}")
            print(f"  DUT T0: {sensor._dut_t0:.2f} °C")

        # Enable all axes
        sensor.enable_axes(x=True, y=True, z=True)

        # Set ODR
        sensor.set_odr(args.odr, 'low_power')
        sensor.set_power_mode('normal')
        time.sleep(0.05)

        count = args.count

        # ── Phase 1: Raw data (mirrors Bosch raw data readout) ──────────
        print(f"\n  Raw magnetometer data @ {args.odr} Hz, {count} samples")
        print("  mag_x_raw, mag_y_raw, mag_z_raw, temp_raw")

        for i in range(count):
            if wait_for_data_ready(sensor):
                raw = sensor.read_raw_data()
                print(f"  {raw['xRaw']}, {raw['yRaw']}, {raw['zRaw']}, {raw['tRaw']}")

        # ── Phase 2: Compensated data (mirrors Bosch compensated readout) ─
        print(f"\n  Compensated magnetometer + temperature @ {args.odr} Hz, {count} samples")
        print("  Timestamp(ms), Mag_X(uT), Mag_Y(uT), Mag_Z(uT), Temperature(degC)")

        t0 = time.monotonic()
        for i in range(count):
            if wait_for_data_ready(sensor):
                data = sensor.read_data(compensated=args.compensated)
                t_ms = int((time.monotonic() - t0) * 1000)
                print_data_row(t_ms, data.x, data.y, data.z, data.temperature)

    finally:
        board.close_comm_interface()


# ── Example: forced-mode ──────────────────────────────────────────────────


def cmd_forced_mode(args):
    """Read magnetometer data in forced mode with various ODR/averaging combos.

    Mirrors: bmm350_forced_mode.c — tests multiple combinations of
    forced/forced-fast mode with different averaging settings,
    computes average and noise for each combination.
    """
    print_header("BMM350 Forced Mode")
    board, sensor = create_board(args.port)

    try:
        sensor.setup_board()
        sensor.init()

        # Enable all axes
        sensor.enable_axes(x=True, y=True, z=True)

        n = args.count  # samples per combination

        combinations = [
            ("Forced Fast + AVG_4",  'forced_fast', 'high'),
            ("Forced Fast + AVG_4 (loop)", 'forced_fast', 'high'),
            ("Forced + NO_AVG",     'forced',     'low_power'),
            ("Forced Fast + AVG_4 (batch)", 'forced_fast', 'high'),
            ("Forced + NO_AVG (batch)",     'forced',     'low_power'),
            ("Forced Fast + AVG_2 (batch)", 'forced_fast', 'medium'),
        ]

        for combo_idx, (label, mode, avg) in enumerate(combinations, 1):
            print(f"\n  COMBINATION {combo_idx}: {label}")

            sensor.set_odr(100, avg)

            print("  Timestamp(ms), Mag_X(uT), Mag_Y(uT), Mag_Z(uT), Temperature(degC)")

            samples = []
            t0 = time.monotonic()

            for i in range(n):
                # In forced mode, trigger measurement then read
                sensor.set_power_mode(mode)
                time.sleep(0.01)  # Wait for measurement

                if wait_for_data_ready(sensor, timeout=0.1):
                    data = sensor.read_data(compensated=args.compensated)
                    t_ms = int((time.monotonic() - t0) * 1000)
                    print_data_row(t_ms, data.x, data.y, data.z, data.temperature)
                    samples.append({'x': data.x, 'y': data.y, 'z': data.z})

            # Compute average and noise (mirrors Bosch mean + calculate_noise)
            if samples:
                avg_x = sum(s['x'] for s in samples) / len(samples)
                avg_y = sum(s['y'] for s in samples) / len(samples)
                avg_z = sum(s['z'] for s in samples) / len(samples)

                print(f"\n  ── Average ──")
                print(f"  Avg_Mag_X(uT), Avg_Mag_Y(uT), Avg_Mag_Z(uT)")
                print(f"  {avg_x:.4f}, {avg_y:.4f}, {avg_z:.4f}")

                calculate_noise(samples, avg_x, avg_y, avg_z)

    finally:
        board.close_comm_interface()


# ── Example: self-test ────────────────────────────────────────────────────


def cmd_self_test(args):
    """Run BMM350 built-in self test.

    Mirrors: bmm350_self_test.c — reads data before/after self-test,
    performs self-test in suspend mode, prints results.
    """
    print_header("BMM350 Self Test")
    board, sensor = create_board(args.port)

    try:
        sensor.setup_board()
        sensor.init()

        chip_id = sensor.get_chip_id()
        print(f"\n  Chip ID: 0x{chip_id:02X}")

        # Check PMU status
        pm = sensor.get_power_mode()
        print(f"  Power mode: {pm}")

        # Check error register
        err = sensor.read_error_status()
        print(f"  Error register: 0x{err:02X}")

        # Set ODR and enter normal mode
        sensor.set_odr(100, 'high')
        sensor.set_power_mode('normal')
        time.sleep(0.01)

        # Enable all axes
        sensor.enable_axes(x=True, y=True, z=True)

        # ── Before self-test: read some samples ─────────────────────────
        print(f"\n  ── BEFORE SELF TEST ──")
        print("  Timestamp(ms), Mag_X(uT), Mag_Y(uT), Mag_Z(uT), Temperature(degC)")

        t0 = time.monotonic()
        for i in range(10):
            time.sleep(0.1)
            if wait_for_data_ready(sensor, timeout=0.2):
                data = sensor.read_data(compensated=args.compensated)
                t_ms = int((time.monotonic() - t0) * 1000)
                print_data_row(t_ms, data.x, data.y, data.z, data.temperature)

        # ── Perform self-test ───────────────────────────────────────────
        print(f"\n  ── SELF TEST ──")
        print("  Running BMM350 built-in self test...")

        # Self-test in suspend mode (mirrors Bosch)
        sensor.set_power_mode('suspend')
        time.sleep(0.03)

        # Run self-test iterations (mirrors Bosch loop)
        print("\n  Iteration, Result")
        for i in range(20):
            result = sensor.self_test()
            status = "PASS" if result else "FAIL"
            print(f"  {i}, {status}")
            time.sleep(0.01)

        # ── After self-test: read some samples ──────────────────────────
        sensor.set_power_mode('normal')
        sensor.set_odr(100, 'high')
        time.sleep(0.01)

        print(f"\n  ── AFTER SELF TEST ──")
        print("  Timestamp(ms), Mag_X(uT), Mag_Y(uT), Mag_Z(uT), Temperature(degC)")

        t0 = time.monotonic()
        for i in range(20):
            time.sleep(0.01)
            if wait_for_data_ready(sensor, timeout=0.2):
                data = sensor.read_data(compensated=args.compensated)
                t_ms = int((time.monotonic() - t0) * 1000)
                print_data_row(t_ms, data.x, data.y, data.z, data.temperature)

    finally:
        board.close_comm_interface()


# ── Example: magnetic-reset ───────────────────────────────────────────────


def cmd_magnetic_reset(args):
    """Apply magnetic reset and read data before/after.

    Mirrors: bmm350_magnetic_reset.c — reads data, applies BR + FGR,
    then reads data again and shows magnitude change.
    """
    print_header("BMM350 Magnetic Reset")
    board, sensor = create_board(args.port)

    try:
        sensor.setup_board()
        sensor.init()

        # Enable all axes
        sensor.enable_axes(x=True, y=True, z=True)
        sensor.set_odr(100, 'low_power')
        sensor.set_power_mode('normal')
        time.sleep(0.05)

        count = args.count

        # ── Before reset: read samples ──────────────────────────────────
        print(f"\n  Before magnetic reset — {count} samples")
        print("  Timestamp(ms), Mag_X(uT), Mag_Y(uT), Mag_Z(uT), Temperature(degC)")

        samples_before = []
        t0 = time.monotonic()
        for i in range(count):
            if wait_for_data_ready(sensor):
                data = sensor.read_data(compensated=args.compensated)
                t_ms = int((time.monotonic() - t0) * 1000)
                print_data_row(t_ms, data.x, data.y, data.z, data.temperature)
                samples_before.append(data)

        if samples_before:
            avg_x = sum(d.x for d in samples_before) / len(samples_before)
            avg_y = sum(d.y for d in samples_before) / len(samples_before)
            avg_z = sum(d.z for d in samples_before) / len(samples_before)
            mag_before = math.sqrt(avg_x**2 + avg_y**2 + avg_z**2)
            print(f"\n  Magnitude before reset: {mag_before:.2f} μT")

        # ── Apply magnetic reset (BR → FGR) ─────────────────────────────
        print(f"\n  Applying magnetic reset (BR + FGR)...")
        sensor.set_power_mode('suspend')
        time.sleep(0.03)

        from cobra_bridge.drivers.bmm350_constants import BMM350_REG, BMM350_PMU
        sensor._write_reg(BMM350_REG['PMU_CMD'], bytes([BMM350_PMU['BR']]))
        time.sleep(0.003)
        sensor._write_reg(BMM350_REG['PMU_CMD'], bytes([BMM350_PMU['FGR']]))
        time.sleep(0.03)

        sensor.set_power_mode('normal')
        time.sleep(0.05)

        # ── After reset: read samples ───────────────────────────────────
        print(f"\n  After magnetic reset — {count} samples")
        print("  Timestamp(ms), Mag_X(uT), Mag_Y(uT), Mag_Z(uT), Temperature(degC)")

        samples_after = []
        t0 = time.monotonic()
        for i in range(count):
            if wait_for_data_ready(sensor):
                data = sensor.read_data(compensated=args.compensated)
                t_ms = int((time.monotonic() - t0) * 1000)
                print_data_row(t_ms, data.x, data.y, data.z, data.temperature)
                samples_after.append(data)

        if samples_after:
            avg_x = sum(d.x for d in samples_after) / len(samples_after)
            avg_y = sum(d.y for d in samples_after) / len(samples_after)
            avg_z = sum(d.z for d in samples_after) / len(samples_after)
            mag_after = math.sqrt(avg_x**2 + avg_y**2 + avg_z**2)
            print(f"\n  Magnitude after reset: {mag_after:.2f} μT")

    finally:
        board.close_comm_interface()


# ── Example: config-changes ───────────────────────────────────────────────


def cmd_config_changes(args):
    """Read data with different ODR/averaging configurations.

    Mirrors: bmm350_config_changes.c — changes ODR and averaging
    on-the-fly, reads samples at each config, computes noise.
    """
    print_header("BMM350 Configuration Changes")
    board, sensor = create_board(args.port)

    try:
        sensor.setup_board()
        sensor.init()

        # Enable all axes
        sensor.enable_axes(x=True, y=True, z=True)

        count = args.count

        configs = [
            (100, 'low_power', '100 Hz, NO_AVG'),
            (100, 'high',      '100 Hz, AVG_4'),
            (200, 'medium',    '200 Hz, AVG_2'),
            (400, 'low_power', '400 Hz, NO_AVG'),
            (50,  'ultra',     '50 Hz, AVG_8'),
        ]

        for odr, avg, label in configs:
            print(f"\n  ── Config: {label} ──")

            sensor.set_odr(odr, avg)
            sensor.set_power_mode('normal')
            time.sleep(0.05)

            print("  Timestamp(ms), Mag_X(uT), Mag_Y(uT), Mag_Z(uT), Temperature(degC)")

            samples = []
            t0 = time.monotonic()

            for i in range(count):
                if wait_for_data_ready(sensor, timeout=2.0):
                    data = sensor.read_data(compensated=args.compensated)
                    t_ms = int((time.monotonic() - t0) * 1000)
                    print_data_row(t_ms, data.x, data.y, data.z, data.temperature)
                    samples.append({'x': data.x, 'y': data.y, 'z': data.z})

            if samples:
                avg_x = sum(s['x'] for s in samples) / len(samples)
                avg_y = sum(s['y'] for s in samples) / len(samples)
                avg_z = sum(s['z'] for s in samples) / len(samples)
                calculate_noise(samples, avg_x, avg_y, avg_z)

            # Suspend between configs
            sensor.set_power_mode('suspend')
            time.sleep(0.03)

    finally:
        board.close_comm_interface()


# ── Example: async-stream ─────────────────────────────────────────────────


def cmd_async_stream(args):
    """High-rate non-blocking streaming with AsyncCobraBoard.

    Mirrors: bmm350_polling.c at high rate — uses background reader
    thread for pipelined I2C reads up to 400 Hz.
    """
    print_header("BMM350 Async Stream (Non-Blocking)")
    board, sensor = create_async_board(args.port)

    try:
        sensor.setup_board()
        sensor.init()

        # Enable all axes
        sensor.enable_axes(x=True, y=True, z=True)

        count = args.count
        odr = args.odr

        print(f"\n  Streaming @ {odr} Hz, {count} samples (non-blocking)")
        print("  Timestamp(ms), Mag_X(uT), Mag_Y(uT), Mag_Z(uT), Temperature(degC)")

        sensor.start_continuous(odr=odr, compensated=args.compensated)

        t0 = time.monotonic()
        received = 0

        try:
            while received < count:
                data = sensor.read_sensor()
                if data is not None:
                    t_ms = int((time.monotonic() - t0) * 1000)
                    print_data_row(t_ms, data['x'], data['y'], data['z'], data['temperature'])
                    received += 1
        except KeyboardInterrupt:
            print(f"\n  Interrupted after {received} samples")

        sensor.stop_continuous()

        # Print stats
        stats = sensor.get_stats()
        print(f"\n  ── Stats ──")
        print(f"  Reads sent:     {stats['reads_sent']}")
        print(f"  Reads received:  {stats['reads_received']}")
        print(f"  Stale dropped:   {stats['stale_dropped']}")
        print(f"  Sample count:    {stats['sample_count']}")

    finally:
        board.close_comm_interface()


# ── CLI ────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        prog='bmm350_examples',
        description='COBRA BMM350 Examples — Python port of Bosch BMM350_SensorAPI examples',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s chip-id                          Verify chip ID
  %(prog)s polling --count 20               Poll 20 samples
  %(prog)s normal-mode --odr 100 --count 30  Normal mode @ 100 Hz
  %(prog)s forced-mode --count 10            Forced mode with noise calc
  %(prog)s self-test                         Built-in self test
  %(prog)s magnetic-reset --count 20         Magnetic reset before/after
  %(prog)s config-changes --count 20        Multiple ODR/AVG configs
  %(prog)s async-stream --odr 400 --count 100  Non-blocking 400 Hz
        """,
    )
    parser.add_argument('--port', default=None, help='Serial port (auto-detect if omitted)')
    parser.add_argument('--compensated', action='store_true', help='Apply OTP compensation')

    sub = parser.add_subparsers(dest='command', required=True)

    # chip-id
    p_chip = sub.add_parser('chip-id', help='Read and verify chip ID')

    # polling
    p_poll = sub.add_parser('polling', help='Polling read (delay + INT_STATUS)')
    p_poll.add_argument('--odr', type=int, default=100, choices=[25, 50, 100, 200, 400])
    p_poll.add_argument('--count', type=int, default=10)

    # normal-mode
    p_norm = sub.add_parser('normal-mode', help='Normal (continuous) mode read')
    p_norm.add_argument('--odr', type=int, default=100, choices=[25, 50, 100, 200, 400])
    p_norm.add_argument('--count', type=int, default=50)

    # forced-mode
    p_force = sub.add_parser('forced-mode', help='Forced mode with multiple combos')
    p_force.add_argument('--count', type=int, default=10)

    # self-test
    sub.add_parser('self-test', help='Built-in self test')

    # magnetic-reset
    p_reset = sub.add_parser('magnetic-reset', help='Magnetic reset before/after')
    p_reset.add_argument('--count', type=int, default=20)

    # config-changes
    p_cfg = sub.add_parser('config-changes', help='Multiple ODR/AVG configurations')
    p_cfg.add_argument('--count', type=int, default=20)

    # async-stream
    p_async = sub.add_parser('async-stream', help='Non-blocking high-rate streaming')
    p_async.add_argument('--odr', type=int, default=400, choices=[25, 50, 100, 200, 400])
    p_async.add_argument('--count', type=int, default=100)

    args = parser.parse_args()

    print("\n🐍 COBRA — BMM350 Examples v0.2.0")
    print(f"  Port: {args.port or 'auto-detect'}")

    commands = {
        'chip-id':       cmd_chip_id,
        'polling':       cmd_polling,
        'normal-mode':   cmd_normal_mode,
        'forced-mode':   cmd_forced_mode,
        'self-test':     cmd_self_test,
        'magnetic-reset': cmd_magnetic_reset,
        'config-changes': cmd_config_changes,
        'async-stream':  cmd_async_stream,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()