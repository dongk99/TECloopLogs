#!/usr/bin/env python3
"""
extract_coolant.py

From the ORIGINAL CPU_DATA logs (where coolant_c exists), write a new file with
ONLY wall_time_utc + coolant_c, keeping only rows that actually have a coolant
temperature. Rows with empty/missing coolant_c are dropped.
"""

import csv
import glob
import os

INPUT_DIR = r"D:\occt_history\CPU_DATA"
OUTPUT_DIR = r"D:\occt_history\For_CO_TUNING"

TIME_COL = "wall_time_utc"
COOLANT_COL = "coolant_c"
OUT_COLS = [TIME_COL, COOLANT_COL]


def process_file(in_path, out_path):
    read = kept = dropped = 0
    with open(in_path, "r", newline="", encoding="utf-8") as f_in:
        reader = csv.DictReader(f_in)
        for c in OUT_COLS:
            if c not in reader.fieldnames:
                raise KeyError(f"{os.path.basename(in_path)} missing column: {c}")
        with open(out_path, "w", newline="", encoding="utf-8") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=OUT_COLS, extrasaction="ignore")
            writer.writeheader()
            for row in reader:
                read += 1
                val = row.get(COOLANT_COL)
                if val is None or val.strip() == "":
                    dropped += 1
                    continue
                writer.writerow({TIME_COL: row.get(TIME_COL, ""), COOLANT_COL: val})
                kept += 1
    return read, kept, dropped


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    inputs = sorted(glob.glob(os.path.join(INPUT_DIR, "CPU_*.csv")))
    if not inputs:
        print(f"No CPU_*.csv files in {INPUT_DIR}")
        return
    for in_path in inputs:
        base = os.path.splitext(os.path.basename(in_path))[0]
        out_path = os.path.join(OUTPUT_DIR, f"{base}_coolant.csv")
        read, kept, dropped = process_file(in_path, out_path)
        print(f"{os.path.basename(in_path)}: read={read} kept={kept} dropped(no coolant)={dropped}")
        print(f"    -> {out_path}")


if __name__ == "__main__":
    main()
