#!/usr/bin/env python3
"""Record 5-column sensor data from serial to CSV and plot it live."""
import argparse
import math
from pathlib import Path
import sys
import time

import matplotlib
matplotlib.use('Qt5Agg') # Force an interactive window backend (PyQt5)
import matplotlib.pyplot as plt

SENSOR_LABELS = ("VOC", "NH3", "H2S", "EtOH", "Odor")
SAMPLE_RATE_HZ = 50

def parse_row(raw):
    """Require one complete, finite five-number row and return as floats."""
    try:
        values_str = raw.decode('ascii').strip().split(',')
        if len(values_str) != 5:
            raise ValueError
        values = [float(v) for v in values_str]
        if not all(math.isfinite(v) for v in values):
            raise ValueError
    except (UnicodeError, ValueError):
        raise ValueError('expected five finite numbers') from None
    
    # Return both the raw CSV string and the parsed floats for plotting
    csv_string = ','.join(v.strip() for v in values_str) + '\n'
    return csv_string, values

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

def capture_and_plot(port, output, seconds, countdown=3, startup_timeout=8):
    """Record data to CSV (if output provided) while updating a live Matplotlib plot."""
    if output is not None and output.exists():
        raise ValueError(f'{output} already exists. Use a new take number; nothing overwritten.')
    
    lines = Lines(port)
    print('Waiting for sensor readings...', flush=True)
    deadline = time.monotonic() + startup_timeout
    last_text = ''
    
    while time.monotonic() < deadline:
        raw = None
        try:
            raw = lines.read()
            if raw is not None:
                parse_row(raw)
                break
        except ValueError as exc:
            last_text = repr(raw[:100]) if raw is not None else str(exc)
    else:
        raise ValueError('No valid readings. Check connection and baud rate.')

    for remaining in range(countdown, 0, -1):
        print(f'Get ready: {remaining}...', flush=True)
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            lines.read()
            
    if lines.pending:
        deadline = time.monotonic() + 1
        while lines.read() is None:
            if time.monotonic() >= deadline:
                raise ValueError('Serial stream stopped before recording.')

    plt.ion() 
    fig, ax = plt.subplots()
    fig.canvas.manager.set_window_title(output.name if output else "Live Plot (No Recording)")
    ax.set_title("Live Sensor Data")
    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("ADC value")
    ax.grid(True)
    
    plot_lines = []
    for label in SENSOR_LABELS:
        line, = ax.plot([], [], label=label)
        plot_lines.append(line)
    ax.legend()
    plt.tight_layout()
    plt.show(block=False)

    columns = [[] for _ in SENSOR_LABELS]
    time_data = []
    count = 0
    plot_active = True

    target = None
    if output is not None:
        target = output.open('x', encoding='utf-8', newline='\n')

    try:
        action_word = "Plotting" if output is None else "Recording"
        duration_str = "indefinitely (press Ctrl+C to stop)" if math.isinf(seconds) else f"for {seconds:g} seconds"
        print(f'GO! {action_word} {duration_str}.', flush=True)
        
        start = last_row = time.monotonic()
        
        while time.monotonic() - start < seconds:
            raw = lines.read()
            if raw is not None:
                csv_str, values = parse_row(raw)
                
                if target:
                    target.write(csv_str)
                
                current_time = count / SAMPLE_RATE_HZ
                time_data.append(current_time)
                for col_list, val in zip(columns, values):
                    col_list.append(val)
                
                count += 1
                last_row = time.monotonic()
                
                # Update plot periodically (every 10 samples)
                if count % 10 == 0 and plot_active:
                    # Check if user closed the window manually
                    if not plt.fignum_exists(fig.number):
                        plot_active = False
                        print("\nPlot window closed. Continuing to record in background... (Press Ctrl+C to stop)", flush=True)
                    else:
                        # Memory management: actively trim lists if running indefinitely
                        if math.isinf(seconds) and len(time_data) > 2000:
                            time_data = time_data[-1000:]
                            for i in range(len(columns)):
                                columns[i] = columns[i][-1000:]

                        for line, col_data in zip(plot_lines, columns):
                            line.set_data(time_data, col_data)
                        
                        ax.relim()
                        ax.autoscale_view()
                        
                        try:
                            plt.pause(0.001)
                        except Exception:
                            pass # Ignore thread errors if killed mid-draw
                        
                        # Reset timeout so moving the window doesn't trigger a false serial dropout
                        last_row = time.monotonic()

            # Increased timeout to 3 seconds to be highly tolerant of OS GUI freezes
            if time.monotonic() - last_row > 3.0:
                raise ValueError('No complete readings for 3 seconds; check the connection.')
        
        if count < 2:
            raise ValueError('Fewer than two readings received.')
            
    except KeyboardInterrupt:
        print('\nStopped by user. Finishing up...', flush=True)
    except BaseException:
        if target:
            target.close()
            output.unlink()
            print('Take failed or interrupted; incomplete CSV removed.', file=sys.stderr)
        raise
    finally:
        if target:
            target.close()
        
    if output:
        print(f'STOP. Saved {count} rows to {output}.')
    else:
        print(f'STOP. Plotted {count} rows (no file saved).')
    
    # Finalize plot if it's still open
    if plot_active and plt.fignum_exists(fig.number):
        plt.ioff() 
        for line, col_data in zip(plot_lines, columns):
            line.set_data(time_data, col_data)
        ax.relim()
        ax.autoscale_view()
        plt.show() 
        
    return count

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', nargs='?', type=Path, help='new filename, e.g. handsanitizer1.csv')
    parser.add_argument('-c', '--continuous', action='store_true', help='record/plot indefinitely until Ctrl+C is pressed')
    parser.add_argument('--plot-only', action='store_true', help='plot live data without saving to CSV')
    parser.add_argument('--port', help='serial port')
    parser.add_argument('--list-ports', action='store_true', help='list ports without opening them')
    parser.add_argument('--seconds', type=float, default=10, help='take duration (default: 10)')
    parser.add_argument('--baud', type=int, default=115200, help='baud rate (default: 115200)')
    args = parser.parse_args(argv)
    
    if args.continuous:
        args.seconds = math.inf
        
    if not math.isfinite(args.seconds) and not args.continuous or args.seconds <= 0 or args.baud <= 0:
        parser.error('seconds and baud must be positive numbers')
    if not args.list_ports and not args.plot_only and args.output is None:
        parser.error('provide an output filename or use --plot-only')
        
    if args.output and not args.plot_only:
        # Force the file into a 'data' folder and create it if missing
        args.output = Path('data') / args.output.name
        args.output.parent.mkdir(parents=True, exist_ok=True)
    elif args.plot_only:
        args.output = None # Ensure output is explicitly None if plotting only
        
    try:
        import serial
        from serial.tools import list_ports
    except ImportError:
        parser.exit(1, "pyserial is missing. Install with 'pip install pyserial'\n")
        
    try:
        ports = sorted(list_ports.comports(), key=lambda p: p.device)
        if args.list_ports:
            for p in ports:
                print(f'{p.device}: {p.description}')
            return 0
            
        name = choose_port(ports, args.port)
        print(f'Opening {name} at {args.baud} baud.', flush=True)
        
        with serial.Serial() as port:
            port.port, port.baudrate, port.timeout = name, args.baud, 0.1
            port.dtr = port.rts = False
            port.open()
            capture_and_plot(port, args.output, args.seconds)
        return 0
    except (OSError, ValueError, serial.SerialException) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Cancelled.', file=sys.stderr)
        return 130

if __name__ == '__main__':
    sys.exit(main())