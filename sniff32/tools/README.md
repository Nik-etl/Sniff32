## Recording instructions

> Run python script from PlatformIO Core CLI, found from Alien head -> Quick Access -> Miscellaneous
```
python tools/record_csv.py filenamehere.csv
```

## Plotting a CSV

Install Matplotlib if needed, then run the plotter:
```
python -m pip install matplotlib
python tools/plot_csv.py
```

By default, the plotter reads `handsanitizer1.csv` from the project folder.
To plot another CSV in that folder, change `CSV_FILE` in `tools/plot_csv.py`.
The five columns are labeled VOC, NH3, H2S, EtOH, and Odor, matching `src/main.cpp`.

## Live Recording & Plotting (`record_live.py`)

This script captures 5-column sensor data from the microcontroller, saves it to a CSV file in the `data/` folder, and plots it live on your screen.

### 1. Install Requirements
Since PlatformIO's built-in Python environment doesn't include everything by default, run this in your terminal once:
```bash
pip install pyserial matplotlib PyQt5
```

### 2. Basic Usage
Make sure all other Serial Monitors are **closed** so the script can access the port. Run the script and give it a filename:

```bash
python tools/record_live.py my_test.csv
```
* **Auto-folder:** The script will automatically create a `data` folder and save your file as `data/my_test.csv`.
* **Default behavior:** It auto-detects the USB port, waits for valid data, gives a 3-second countdown, and records for 10 seconds.

### 3. Advanced Options
You can customize the recording duration, manually select a port, or list available ports:

**List available ports:**
```bash
python tools/record_live.py --list-ports
```

**Record for 30 seconds on a specific port:**
```bash
python tools/record_live.py my_test.csv --seconds 30 --port COM3
```

**Plot only:**
```bash
python tools/record_live.py --plot-only
```
It still plots for a specified time default is 10 seconds


*Note: The script plots every 10th sample to keep the live graph smooth, but every single reading (50Hz) is safely logged to your CSV file without data loss.*