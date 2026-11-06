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


def capture_and_plot(port, output, seconds, baseline_mode=False, baseline_seconds=5.0, countdown=3, startup_timeout=8):
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

    if not baseline_mode:
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

    lock = threading.Lock()
    # Keep rolling window during continuous or interactive baseline stages
    maxlen = MAX_PLOT_POINTS if (math.isinf(seconds) or baseline_mode) else None
    time_data = deque(maxlen=maxlen)
    columns = [deque(maxlen=maxlen) for _ in SENSOR_LABELS]
    
    state = {
        'plot_count': 0,
        'saved_count': 0,
        'done': False,
        'error': None,
        'stop_requested': False,
        'stage': 'WAIT_BASELINE' if baseline_mode else 'RECORD_NORMAL',
        'stage_start': 0.0,
        'baseline_sums': [0.0] * len(SENSOR_LABELS),
        'baseline_count': 0,
        'baseline_array': None,
        'title': 'Live Sensor Data'
    }

    target = output.open('x', encoding='utf-8', newline='\n') if output is not None else None

    def advance_stage():
        """Trigger transitions between waiting and recording in baseline mode."""
        with lock:
            if state['stage'] == 'WAIT_BASELINE':
                state['stage'] = 'RECORD_BASELINE'
                state['stage_start'] = time.monotonic()
                state['baseline_sums'] = [0.0] * len(SENSOR_LABELS)
                state['baseline_count'] = 0
                print(f"\n--> Recording baseline for {baseline_seconds:g}s... Keep sensors in clean air.", flush=True)
            elif state['stage'] == 'WAIT_PEAK':
                state['stage'] = 'RECORD_PEAK'
                state['stage_start'] = time.monotonic()
                print(f"\n--> Recording peak data for {seconds:g}s...", flush=True)

    def stdin_listener():
        """Allow pressing Enter in the terminal to trigger stages."""
        while not state['done'] and not state['stop_requested']:
            line = sys.stdin.readline()
            if not line:
                break
            advance_stage()

    if baseline_mode:
        threading.Thread(target=stdin_listener, daemon=True).start()
        print("\n[STEP 1] Sensors streaming. Press SPACE/ENTER in the plot window (or ENTER in terminal) to capture baseline...", flush=True)

    def serial_worker():
        """Background thread: reads serial, computes deltas, and writes CSV."""
        try:
            start = last_row = time.monotonic()
            while not state['stop_requested']:
                now = time.monotonic()
                if not baseline_mode and (now - start >= seconds):
                    break

                raw = lines.read()
                if raw is not None:
                    csv_str, values = parse_row(raw)
                    now = time.monotonic()
                    
                    with lock:
                        # Always push raw ADC values to the live plot deques
                        current_time = state['plot_count'] / SAMPLE_RATE_HZ
                        time_data.append(current_time)
                        for col_deque, val in zip(columns, values):
                            col_deque.append(val)
                        state['plot_count'] += 1

                        st = state['stage']
                        
                        if st == 'RECORD_NORMAL':
                            if target:
                                target.write(csv_str)
                            state['saved_count'] += 1

                        elif st == 'WAIT_BASELINE':
                            state['title'] = "STEP 1: Press SPACE or ENTER to record baseline"

                        elif st == 'RECORD_BASELINE':
                            elapsed = now - state['stage_start']
                            for i, val in enumerate(values):
                                state['baseline_sums'][i] += val
                            state['baseline_count'] += 1
                            rem = max(0.0, baseline_seconds - elapsed)
                            state['title'] = f"Recording Baseline... {rem:.1f}s remaining"

                            if elapsed >= baseline_seconds:
                                if state['baseline_count'] == 0:
                                    raise ValueError("No samples received during baseline window.")
                                state['baseline_array'] = [
                                    s / state['baseline_count'] for s in state['baseline_sums']
                                ]
                                b_str = ", ".join(
                                    f"{label}={val:.2f}" for label, val in zip(SENSOR_LABELS, state['baseline_array'])
                                )
                                print(f"Baseline locked ({state['baseline_count']} samples): {b_str}", flush=True)
                                print("\n[STEP 2] Place cup over sample, wait for peak, then press SPACE/ENTER to record...", flush=True)
                                state['stage'] = 'WAIT_PEAK'

                        elif st == 'WAIT_PEAK':
                            state['title'] = "STEP 2: Place cup & wait for peak. Press SPACE/ENTER to capture"

                        elif st == 'RECORD_PEAK':
                            elapsed = now - state['stage_start']
                            if elapsed <= seconds:
                                deltas = [v - b for v, b in zip(values, state['baseline_array'])]
                                if target:
                                    delta_line = ",".join(f"{d:.2f}" for d in deltas) + "\n"
                                    target.write(delta_line)
                                state['saved_count'] += 1
                                rem = max(0.0, seconds - elapsed)
                                state['title'] = f"Recording Peak (saving deltas)... {rem:.1f}s remaining"
                            
                            if elapsed >= seconds:
                                state['title'] = f"Finished ({state['saved_count']} delta rows saved) - Close window to exit"
                                break

                    last_row = now

                if time.monotonic() - last_row > 2.0:
                    raise ValueError('No complete readings for 2 seconds; check the connection.')
            
            if state['saved_count'] < 2 and not state['stop_requested']:
                raise ValueError('Fewer than two readings recorded.')
        except BaseException as exc:
            state['error'] = exc
        finally:
            state['done'] = True

    # Setup Plot Window
    fig, ax = plt.subplots()
    fig.canvas.manager.set_window_title(output.name if output else "Live Plot (No Recording)")
    ax.set_title(state['title'])
    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("Raw ADC value")
    ax.grid(True)
    
    plot_lines = [ax.plot([], [], label=label)[0] for label in SENSOR_LABELS]
    ax.legend(loc="upper left")
    plt.tight_layout()

    def on_key(event):
        if event.key in (' ', 'enter', 'return'):
            advance_stage()

    if baseline_mode:
        fig.canvas.mpl_connect('key_press_event', on_key)

    def update_plot(frame):
        """Called every 50ms by the Qt GUI timer to redraw the graph."""
        with lock:
            if not time_data:
                return plot_lines
            t_list = list(time_data)
            c_lists = [list(c) for c in columns]
            current_title = state['title']
            is_done = state['done']
            err = state['error']
            saved = state['saved_count']

        for line, col_data in zip(plot_lines, c_lists):
            line.set_data(t_list, col_data)
        
        ax.set_title(current_title)
        ax.relim()
        ax.autoscale_view()

        if is_done:
            ani.event_source.stop()
            if err is not None:
                plt.close(fig)
            else:
                ax.set_title(f"Finished ({saved} samples saved) - Close window to exit")
                fig.canvas.draw_idle()

        return plot_lines

    if not baseline_mode:
        action_word = "Plotting" if output is None else "Recording"
        if math.isinf(seconds):
            duration_str = "indefinitely (close the plot window or press Ctrl+C to stop)"
        else:
            duration_str = f"for {seconds:g} seconds"
        print(f'GO! {action_word} {duration_str}.', flush=True)

    worker = threading.Thread(target=serial_worker, daemon=True)
    worker.start()

    ani = FuncAnimation(fig, update_plot, interval=50, blit=False, cache_frame_data=False)

    try:
        plt.show()
    except KeyboardInterrupt:
        print('\nStopped by user.', flush=True)
    finally:
        state['stop_requested'] = True
        worker.join(timeout=2.0)
        if target:
            target.close()

    # Clean up file if interrupted before finishing or if an error occurred
    incomplete_baseline = baseline_mode and state['stage'] != 'RECORD_PEAK' and state['saved_count'] == 0
    if state['error'] is not None or incomplete_baseline:
        if output is not None and output.exists():
            output.unlink()
            print('Take failed or cancelled before completion; incomplete CSV removed.', file=sys.stderr)
        if state['error'] is not None:
            raise state['error']
        return 0

    if output:
        mode_note = "baseline-subtracted delta " if baseline_mode else ""
        print(f"STOP. Saved {state['saved_count']} {mode_note}rows to {output}.")
    else:
        print(f"STOP. Plotted {state['saved_count']} rows (no file saved).")

    return state['saved_count']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', nargs='?', type=Path, help='new filename, e.g. handsanitizer1.csv')
    parser.add_argument('-b', '--baseline', action='store_true', help='interactive baseline subtraction mode (5s baseline -> peak delta capture)')
    parser.add_argument('--baseline-seconds', type=float, default=5.0, help='baseline averaging duration in seconds (default: 5)')
    parser.add_argument('-c', '--continuous', action='store_true', help='record/plot indefinitely until window is closed')
    parser.add_argument('--plot-only', action='store_true', help='plot live data without saving to CSV')
    parser.add_argument('--port', help='serial port')
    parser.add_argument('--list-ports', action='store_true', help='list ports without opening them')
    parser.add_argument('--seconds', type=float, default=None, help='take duration (default: 15 in baseline mode, 10 otherwise)')
    parser.add_argument('--baud', type=int, default=115200, help='baud rate (default: 115200)')
    args = parser.parse_args(argv)
    
    if args.seconds is None:
        args.seconds = 15.0 if args.baseline else 10.0

    if args.continuous:
        if args.baseline:
            parser.error('--continuous and --baseline cannot be used together')
        args.seconds = math.inf
        
    if (not math.isfinite(args.seconds) and not args.continuous) or args.seconds <= 0 or args.baud <= 0 or args.baseline_seconds <= 0:
        parser.error('durations and baud must be positive numbers')
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
            capture_and_plot(
                port,
                args.output,
                args.seconds,
                baseline_mode=args.baseline,
                baseline_seconds=args.baseline_seconds
            )
        return 0
    except (OSError, ValueError, serial.SerialException) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Cancelled.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())