#!/usr/bin/env python3
"""Plot the five sensor columns from a CSV file in the project folder."""
import csv
from pathlib import Path

import matplotlib.pyplot as plt


CSV_FILE = Path(__file__).resolve().parent.parent / "handsanitizer1.csv"
SENSOR_LABELS = ("VOC", "NH3", "H2S", "EtOH", "Odor")
SAMPLE_RATE_HZ = 50


def load_columns() -> list[list[float]]:
    columns = [[] for _ in SENSOR_LABELS]
    with CSV_FILE.open(newline="", encoding="utf-8") as csv_file:
        for line_number, row in enumerate(csv.reader(csv_file), start=1):
            if not row:
                continue
            if len(row) != len(SENSOR_LABELS):
                raise ValueError(
                    f"{CSV_FILE} line {line_number}: expected "
                    f"{len(SENSOR_LABELS)} values, found {len(row)}"
                )
            try:
                values = [float(value) for value in row]
            except ValueError as error:
                raise ValueError(
                    f"{CSV_FILE} line {line_number}: values must be numeric"
                ) from error
            for column, value in zip(columns, values):
                column.append(value)

    if not columns[0]:
        raise ValueError(f"{CSV_FILE} contains no data")
    return columns


def main() -> None:
    columns = load_columns()
    sample_times = [sample / SAMPLE_RATE_HZ for sample in range(len(columns[0]))]

    for label, values in zip(SENSOR_LABELS, columns):
        plt.plot(sample_times, values, label=label)

    plt.title(CSV_FILE.name)
    plt.xlabel("Time (seconds)")
    plt.ylabel("ADC value")
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
