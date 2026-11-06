#!/usr/bin/env python3
"""Record 5-column sensor data from serial to CSV and plot it live."""
import argparse
from collections import deque
import math
from pathlib import Path
import sys
import threading
import time

import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

SENSOR_LABELS = ("VOC", "NH3", "H2S", "EtOH", "Odor")
SAMPLE_RATE_HZ = 50
MAX_PLOT_POINTS = 1000  # Rolling 20-second window for smooth UI performance


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
    """Record data on a background thread while the main thread runs the GUI smoothly."""
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

    # Shared state between serial worker thread and GUI main thread
    lock = threading.Lock()
    # If continuous, cap memory with maxlen; otherwise keep full take for final view
    maxlen = MAX_PLOT_POINTS if math.isinf(seconds) else None
    time_data = deque(maxlen=maxlen)
    columns = [deque(maxlen=maxlen) for _ in SENSOR_LABELS]
    
    state = {
        'count': 0,
        'done': False,
        'error': None,
        'stop_requested': False
    }

    target = output.open('x', encoding='utf-8', newline='\n') if output is not None else None

    def serial_worker():
        """Background thread: reads serial and writes CSV without GUI interruptions."""
        try:
            start = last_row = time.monotonic()
            while not state['stop_requested'] and (time.monotonic() - start < seconds):
                raw = lines.read()
                if raw is not None:
                    csv_str, values = parse_row(raw)
                    if target:
                        target.write(csv_str)
                    
                    with lock:
                        current_time = state['count'] / SAMPLE_RATE_HZ
                        time_data.append(current_time)
                        for col_deque, val in zip(columns, values):
                            col_deque.append(val)
                        state['count'] += 1
                    
                    last_row = time.monotonic()

                if time.monotonic() - last_row > 2.0:
                    raise ValueError('No complete readings for 2 seconds; check the connection.')
            
            if state['count'] < 2 and not state['stop_requested']:
                raise ValueError('Fewer than two readings received.')
        except BaseException as exc:
            state['error'] = exc
        finally:
            state['done'] = True

    # Setup Plot Window
    fig, ax = plt.subplots()
    fig.canvas.manager.set_window_title(output.name if output else "Live Plot (No Recording)")
    ax.set_title("Live Sensor Data")
    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("ADC value")
    ax.grid(True)
    
    plot_lines = [ax.plot([], [], label=label)[0] for label in SENSOR_LABELS]
    ax.legend(loc="upper left")
    plt.tight_layout()

    def update_plot(frame):
        """Called every 50ms by the Qt GUI timer to redraw the graph."""
        with lock:
            if not time_data:
                return plot_lines
            t_list = list(time_data)
            c_lists = [list(c) for c in columns]

        for line, col_data in zip(plot_lines, c_lists):
            line.set_data(t_list, col_data)
        
        ax.relim()
        ax.autoscale_view()

        if state['done']:
            ani.event_source.stop()
            if state['error'] is not None:
                plt.close(fig)  # Close window immediately on error
            else:
                ax.set_title(f"Finished ({state['count']} samples) - Close window to exit")
                fig.canvas.draw_idle()

        return plot_lines

    action_word = "Plotting" if output is None else "Recording"
    if math.isinf(seconds):
        duration_str = "indefinitely (close the plot window or press Ctrl+C to stop)"
    else:
        duration_str = f"for {seconds:g} seconds"
    print(f'GO! {action_word} {duration_str}.', flush=True)

    # Start the background serial reader
    worker = threading.Thread(target=serial_worker, daemon=True)
    worker.start()

    # Run the GUI update timer at 20 FPS (50ms interval)
    ani = FuncAnimation(fig, update_plot, interval=50, blit=False, cache_frame_data=False)

    try:
        # plt.show() runs the native Qt event loop, keeping the window 100% responsive
        plt.show()
    except KeyboardInterrupt:
        print('\nStopped by user.', flush=True)
    finally:
        # Signal thread to stop when the user closes the window or hits Ctrl+C
        state['stop_requested'] = True
        worker.join(timeout=2.0)
        if target:
            target.close()

    # If the background thread crashed, clean up the incomplete file
    if state['error'] is not None:
        if output is not None and output.exists():
            output.unlink()
            print('Take failed or interrupted; incomplete CSV removed.', file=sys.stderr)
        raise state['error']

    if output:
        print(f"STOP. Saved {state['count']} rows to {output}.")
    else:
        print(f"STOP. Plotted {state['count']} rows (no file saved).")

    return state['count']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', nargs='?', type=Path, help='new filename, e.g. handsanitizer1.csv')
    parser.add_argument('-c', '--continuous', action='store_true', help='record/plot indefinitely until window is closed')
    parser.add_argument('--plot-only', action='store_true', help='plot live data without saving to CSV')
    parser.add_argument('--port', help='serial port')
    parser.add_argument('--list-ports', action='store_true', help='list ports without opening them')
    parser.add_argument('--seconds', type=float, default=10, help='take duration (default: 10)')
    parser.add_argument('--baud', type=int, default=115200, help='baud rate (default: 115200)')
    args = parser.parse_args(argv)
    
    if args.continuous:
        args.seconds = math.inf
        
    if (not math.isfinite(args.seconds) and not args.continuous) or args.seconds <= 0 or args.baud <= 0:
        parser.error('seconds and baud must be positive numbers')
    if not args.list_ports and not args.plot_only and args.output is None:
        parser.error('provide an output filename or use --plot-only')
        
    if args.output and not args.plot_only:
        args.output = Path('data') / args.output.name
        args.output.parent.mkdir(parents=True, exist_ok=True)
    elif args.plot_only:
        args.output = None
        
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