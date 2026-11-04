#!/usr/bin/env python3
"""Record MPU-6050 x,y,z rows directly from serial. Use PlatformIO's Python."""
import argparse
import math
from pathlib import Path
import sys
import time


def csv_row(raw):
    """Require one complete, finite three-number row; preserve sensor precision."""
    try:
        values = raw.decode('ascii').strip().split(',')
        if len(values) != 3 or not all(math.isfinite(float(v)) for v in values):
            raise ValueError
    except (UnicodeError, ValueError):
        raise ValueError('expected three finite numbers (x,y,z)') from None
    return ','.join(v.strip() for v in values) + '\n'


class Lines:
    """Keep partial reads across timeouts, with a bound on unframed input."""
    def __init__(self, port):
        self.port = port
        self.pending = b''

    def read(self):
        self.pending += self.port.read_until(b'\n', 1024)
        if len(self.pending) > 1024:
            self.pending = b''
            raise ValueError('serial line exceeds 1024 bytes; check baud rate/sketch')
        if not self.pending.endswith(b'\n'):
            return None
        raw, self.pending = self.pending, b''
        return raw


def choose_port(ports, requested):
    if requested:
        return requested
    usb = [p.device for p in ports if p.vid is not None]
    if len(usb) == 1:
        return usb[0]
    raise ValueError('Cannot choose one USB serial port. Run --list-ports, then add '
                     '--port COM3 (Windows) or --port /dev/cu.usbserial-... (Mac).')


def capture(port, output, seconds, countdown=3, startup_timeout=8):
    """Ignore startup text before GO; reject errors during the actual take."""
    if output.exists():
        raise ValueError(f'{output} already exists. Use a new take number; nothing overwritten.')
    lines = Lines(port)
    print('Waiting for x,y,z readings (upload session02_mpu_read.cpp first)...', flush=True)
    deadline = time.monotonic() + startup_timeout
    last_text = ''
    while time.monotonic() < deadline:
        raw = None
        try:
            raw = lines.read()
            if raw is not None:
                csv_row(raw)
                break
        except ValueError as exc:
            last_text = repr(raw[:100]) if raw is not None else str(exc)
    else:
        raise ValueError('No valid readings. Check sketch, UART cable and 115200 baud. '
                         + ('Last input: ' + last_text if last_text else 'No complete rows received.'))
    # Drain incoming rows throughout the countdown so old motion is not buffered.
    for remaining in range(countdown, 0, -1):
        print(f'Get ready: {remaining}...', flush=True)
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            lines.read()
    # The take begins at the next complete row, not in the middle of a number.
    if lines.pending:
        deadline = time.monotonic() + 1
        while lines.read() is None:
            if time.monotonic() >= deadline:
                raise ValueError('Serial stream stopped before recording.')
    count = 0
    # Exclusive creation protects previous takes, including empty failed redirects.
    with output.open('x', encoding='utf-8', newline='\n') as target:
        try:
            print(f'GO! Perform the activity for {seconds:g} seconds.', flush=True)
            start = last_row = time.monotonic()
            while time.monotonic() - start < seconds:
                raw = lines.read()
                if raw is not None:
                    target.write(csv_row(raw))
                    count += 1
                    last_row = time.monotonic()
                if time.monotonic() - last_row > 1:
                    raise ValueError('No complete readings for one second; check the connection.')
            if count < 2:
                raise ValueError('Fewer than two readings received.')
        except BaseException:
            target.close()
            output.unlink()  # Only this newly created, incomplete take.
            print('Take failed or interrupted; incomplete CSV removed. Retry with the same name.',
                  file=sys.stderr)
            raise
    print(f'STOP. Saved {count} rows to {output} (UTF-8, x,y,z; no header).')
    print('Inspect/plot the take before using it. Row count does not verify regular timing.')
    return count


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', nargs='?', type=Path, help='new filename, e.g. wave_01.csv')
    parser.add_argument('--port', help='serial port; auto-selects if exactly one USB port is found')
    parser.add_argument('--list-ports', action='store_true', help='list ports without opening them')
    parser.add_argument('--seconds', type=float, default=10, help='take duration (default: 10)')
    parser.add_argument('--baud', type=int, default=115200, help='baud rate (default: 115200)')
    args = parser.parse_args(argv)
    if not math.isfinite(args.seconds) or args.seconds <= 0 or args.baud <= 0:
        parser.error('seconds and baud must be positive, finite numbers')
    if not args.list_ports and args.output is None:
        parser.error('provide an output filename or use --list-ports')
    try:
        import serial
        from serial.tools import list_ports
    except ImportError:
        parser.exit(1, "pyserial is missing from this Python. Use PlatformIO's bundled Python; "
                    'see the README recording instructions.\n')
    try:
        ports = sorted(list_ports.comports(), key=lambda p: p.device)
        if args.list_ports:
            for p in ports:
                print(f'{p.device}: {p.description}')
            if not ports:
                print('No serial ports found. Check the UART USB cable/driver.')
            return 0
        if args.output.exists():
            raise ValueError(f'{args.output} already exists. Use a new take number; nothing overwritten.')
        name = choose_port(ports, args.port)
        print(f'Opening {name} at {args.baud} baud. Close other Serial Monitors first.', flush=True)
        # Deassert reset/boot control lines before opening the USB-UART bridge.
        # Some drivers can still pulse these lines on open; allow startup above.
        with serial.Serial() as port:
            port.port, port.baudrate, port.timeout = name, args.baud, 0.1
            port.dtr = port.rts = False
            port.open()
            capture(port, args.output, args.seconds)
        return 0
    except (OSError, ValueError, serial.SerialException) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Cancelled.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
