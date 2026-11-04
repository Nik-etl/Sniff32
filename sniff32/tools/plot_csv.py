#!/usr/bin/env python3
"""Plot the five sensor columns from a CSV file."""
import argparse
import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Qt5Agg') # Force an interactive window backend (PyQt5)
import matplotlib.pyplot as plt

SENSOR_LABELS = ("VOC", "NH3", "H2S", "EtOH", "Odor")
SAMPLE_RATE_HZ = 50


def load_columns(csv_file: Path) -> list[list[float]]:
    columns = [[] for _ in SENSOR_LABELS]
    with csv_file.open(newline="", encoding="utf-8") as f:
        for line_number, row in enumerate(csv.reader(f), start=1):
            if not row:
                continue
            if len(row) != len(SENSOR_LABELS):
                raise ValueError(
                    f"{csv_file} line {line_number}: expected "
                    f"{len(SENSOR_LABELS)} values, found {len(row)}"
                )
            try:
                values = [float(value) for value in row]
            except ValueError as error:
                raise ValueError(
                    f"{csv_file} line {line_number}: values must be numeric"
                ) from error
            for column, value in zip(columns, values):
                column.append(value)

    if not columns[0]:
        raise ValueError(f"{csv_file} contains no data")
    return columns


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='CSV filename to plot, e.g. handsanitizer1.csv')
    args = parser.parse_args()

    # Automatically check the 'data' folder if the file isn't found in the current directory
    if not args.input.exists():
        data_path = Path('data') / args.input.name
        if data_path.exists():
            args.input = data_path
        else:
            print(f"Error: Could not find '{args.input}' or '{data_path}'", file=sys.stderr)
            return 1

    try:
        columns = load_columns(args.input)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    sample_times = [sample / SAMPLE_RATE_HZ for sample in range(len(columns[0]))]

    # Name the window after the file
    plt.figure(args.input.name)
    
    for label, values in zip(SENSOR_LABELS, columns):
        plt.plot(sample_times, values, label=label)

    plt.title(args.input.name)
    plt.xlabel("Time (seconds)")
    plt.ylabel("ADC value")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())