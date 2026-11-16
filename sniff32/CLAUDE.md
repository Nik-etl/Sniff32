# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

SNIFF32: a TinyML odor classifier (Embedded Programming 2 course). An ESP32-S3-DevKitC-1 reads five DFRobot MEMS gas sensors (VOC, NH3, H2S, EtOH, Odor) on ADC pins and runs an Edge Impulse model on the device.

The git root is the parent directory (`../`). It holds the course documents (`README.md`, `data-plan.md`, `threat-model.md`, `report-template.md`), the sensor datasheets in `datasheets/`, and `Test/Test.ino`, the original Arduino IDE sensor test. This directory (`sniff32/`) is the PlatformIO project.

## Commands

Run these from this directory (`pio` is on PATH):

```bash
pio run                          # build
pio run -t upload                # flash over the "UART" USB-C port
pio device monitor               # serial monitor at 115200
pio run -t upload -t monitor     # flash, then open the monitor
```

There are no unit tests (`test/` only holds the PlatformIO template README).

Python data tools need `pip install pyserial matplotlib PyQt5`. Close any serial monitor first, because the tools need the port to themselves. Recordings go to `data/`, which is gitignored.

```bash
python tools/record_live.py <name>.csv -b     # baseline mode: SPACE locks a 5 s clean-air baseline, SPACE again captures 15 s of (value - baseline) deltas
python tools/record_live.py --plot-only -c    # live plot, nothing saved
python tools/record_live.py --list-ports      # add --port COMx when the port isn't auto-detected
python tools/plot_csv.py <name>.csv           # looks in the current directory and in data/
python tools/record_csv.py <name>.csv         # headless recording
```

## Architecture

**Swapping firmware.** PlatformIO compiles only `src/main.cpp`. `example_codes/` is not compiled. To switch firmware, copy the file you want over `src/main.cpp`.
- `src/main.cpp` is the on-device classifier. It runs a one-button state machine: Ready → Baseline (5 s clean air) → WaitForPeak → Measuring (10 s) → Classify → ShowingResult. Sampling runs at 50 Hz in every state, through the same 10-sample moving average as `record.cpp`. The classifier slides the model window over the capture (2 s window, 500 ms step) and averages the class scores. The result appears on an SSD1306 OLED (I2C, SDA=10, SCL=9, address 0x3C). The button is on GPIO2.
- `example_codes/record.cpp` is the data-collection firmware. It applies a 10-sample moving average and prints a headerless CSV line `VOC,NH3,H2S,EtOH,Odor` every 20 ms.
- `example_codes/application.cpp` is the older classifier prototype. Its `classifyMeasurement()` is still a placeholder, so it does not run the model.

**These must stay identical across firmware, the Python tools and the model:**
- Sensor column order `VOC, NH3, H2S, EtOH, Odor` and pins GPIO 4/5/6/7/8. The Python tools reject any line that does not have exactly 5 integer fields, so firmware must not print other text in the middle of the CSV stream.
- Sample rate: 50 Hz (20 ms).
- The Edge Impulse model in `lib/sniff32_inferencing/` (exported Arduino library; include `sniff32_inferencing.h`). Its window is `EI_CLASSIFIER_RAW_SAMPLE_COUNT`=100 samples × 5 axes (2 s at 50 Hz). It has 3 labels: `banana`, `baseline`, `coffee`. See `src/model-parameters/model_metadata.h`.
- Preprocessing: inference must reproduce the training preprocessing. `USE_BASELINE_DELTA` in `src/main.cpp` controls whether the model receives values with the clean-air baseline subtracted (`record_live.py -b`) or absolute smoothed values.
- `run_classifier()` takes frames interleaved as `[VOC0,NH3_0,H2S0,EtOH0,Odor0,VOC1,...]`.

**Libraries.** Everything is vendored in `lib/` (`lib_deps` is empty): Adafruit BusIO, GFX and SSD1306, plus the Edge Impulse export. Do not edit `lib/sniff32_inferencing/`. It is regenerated whenever the model is re-exported from Edge Impulse.

## platformio.ini gotchas

- `platform = espressif32@7.0.1` (Arduino-ESP32 core 2.0.17) is pinned deliberately. Do not upgrade it.
- `ARDUINO_USB_CDC_ON_BOOT=0` sends `Serial` to the UART bridge port, not native USB.
- `EI_CLASSIFIER_TFLITE_ENABLE_ESP_NN=0` disables ESP-NN acceleration for the Edge Impulse library.
- The comments say octal flash (`opi`) is required, but the active values are `qio` / `qio_opi`. If the board boot-loops with `assert failed: do_core_init ... flash_ret == ESP_OK`, switch to the `opi` / `opi_opi` values shown in the comments.
- If Edge Impulse headers don't resolve, add `lib_ldf_mode = deep+`.
