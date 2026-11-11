## Setup & Requirements

Run Python scripts from the PlatformIO Core CLI (found via the Alien head icon -> Quick Access -> Miscellaneous).

Since PlatformIO's built-in Python environment doesn't include everything by default, run this in your terminal once:
```bash
pip install pyserial matplotlib PyQt5
```

---

## 1. Live Recording & Plotting (`record_live.py`)

This script captures 5-column sensor data (VOC, NH3, H2S, EtOH, Odor) from the microcontroller, saves it to a CSV file in the `data/` folder, and plots it live on your screen. Make sure all other Serial Monitors are **closed** so the script can access the port.

### Basic Usage
```bash
python tools/record_live.py handsanitizer1.csv
```
- **Auto-folder:** Automatically creates a `data/` folder and saves your file as `data/handsanitizer1.csv`.
- **Default behavior:** Auto-detects the USB port, waits for valid data, gives a 3-second countdown, and records for 10 seconds.

### Baseline Mode (For Edge Impulse Deltas)
Use the `-b` flag to interactively capture a clean-air baseline, then record only the peak delta values (Value - Baseline).
```bash
python tools/record_live.py handsanitizer1.csv -b
```
1. **Step 1:** The live plot opens showing raw streaming data. When the lines stabilize in clean air, press **SPACE** (or Enter) on the window to lock in a 5-second baseline average.
2. **Step 2:** Place the cup over your sample. Watch the live plot rise. When it hits the peak, press **SPACE** to capture 15 seconds of data. The script automatically subtracts the baseline and saves the delta values to your CSV.

### Continuous Mode
Record and plot indefinitely. The script will safely save your CSV when you close the plot window.
```bash
python tools/record_live.py handsanitizer1.csv -c
```

### Plot Live Without Saving
View the live sensor streams indefinitely without creating a CSV file:
```bash
python tools/record_live.py --plot-only -c
```

### Advanced Options
You can customize the recording duration, manually select a port, or list available ports:
```bash
# List available COM/USB ports
python tools/record_live.py --list-ports

# Record for 30 seconds on a specific port
python tools/record_live.py my_test.csv --seconds 30 --port COM3
```

---

## 2. Plotting an Existing CSV (`plot.py`)

To view a CSV you previously recorded, use the plotting script. It automatically looks in your current directory and the `data/` folder.

```bash
python tools/plot_csv.py handsanitizer1.csv
```
This opens an interactive window where you can zoom, pan, and inspect the 5 sensor columns.

---

## 3. Basic Headless Recording (`record_csv.py`)

If you want to record raw data without the live GUI plot, use the basic recording script:
```bash
python tools/record_csv.py handsanitizer1.csv
```
