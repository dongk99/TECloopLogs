#!/usr/bin/env python3
"""
co_tuning_extract.py

Extract per-core power (C*_P) and temperature (C*_T) from OCCT CPU logs for
per-core Curve Optimizer (CO) tuning.

What it does (and ONLY this):
  1. Reads every CPU_*.csv in INPUT_DIR.
  2. Keeps the timestamp + the 8 per-core power/temp pairs (C0..C7).
  3. DROPS any row where ANY of the 8 core-temp columns (C0_T..C7_T) reads
     exactly 0.0 -- that is a sensor dropout, not a real reading.
  4. Writes one filtered CSV per input file into OUTPUT_DIR.

IMPORTANT measurement-integrity notes:
  - The zero check is EXACTLY == 0.0 on the parsed float. Negative / sub-ambient
    core temperatures are VALID on this sub-zero TEC rig and are PRESERVED.
  - The zero check looks ONLY at the 8 per-core temps C0_T..C7_T. It deliberately
    ignores L3_T, CPU_Tctl, CCD1_Tdie, CPU_DieAvg, IOD_* etc. so a stray non-core
    zero cannot delete a good row.
  - No thermal resistance is computed here. This script only parses/filters/writes;
    Rth is derived downstream.
"""

import csv
import glob
import os

INPUT_DIR = r"D:\occt_history\CPU_DATA"
OUTPUT_DIR = r"D:\occt_history\For_CO_TUNING"

N_CORES = 8
TIME_COL = "wall_time_utc"
# Output column order: timestamp, then per-core (power, temp) grouped by core.
TEMP_COLS = [f"C{i}_T" for i in range(N_CORES)]
POWER_COLS = [f"C{i}_P" for i in range(N_CORES)]
OUT_COLS = [TIME_COL]
for i in range(N_CORES):
    OUT_COLS.append(f"C{i}_P")
    OUT_COLS.append(f"C{i}_T")


def is_zero_or_bad(value):
    """True if a core-temp cell is a sensor dropout (exactly 0.0) or unparseable.

    Such a row must be dropped. Negative values parse fine and return False
    (kept) -- sub-ambient is valid on this rig.
    """
    try:
        return float(value) == 0.0
    except (ValueError, TypeError):
        # empty string or non-numeric -> treat as dropout, drop the row
        return True


def process_file(in_path, out_path):
    rows_read = 0
    rows_kept = 0
    rows_dropped = 0

    with open(in_path, "r", newline="", encoding="utf-8") as f_in:
        reader = csv.DictReader(f_in)

        missing = [c for c in OUT_COLS if c not in reader.fieldnames]
        if missing:
            raise KeyError(
                f"{os.path.basename(in_path)} is missing expected columns: {missing}"
            )

        with open(out_path, "w", newline="", encoding="utf-8") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=OUT_COLS, extrasaction="ignore")
            writer.writeheader()

            for row in reader:
                rows_read += 1
                # Drop the row if ANY of the 8 core temps is exactly 0.0 (or bad).
                if any(is_zero_or_bad(row.get(c)) for c in TEMP_COLS):
                    rows_dropped += 1
                    continue
                writer.writerow({c: row.get(c, "") for c in OUT_COLS})
                rows_kept += 1

    return rows_read, rows_kept, rows_dropped


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    inputs = sorted(glob.glob(os.path.join(INPUT_DIR, "CPU_*.csv")))
    if not inputs:
        print(f"No CPU_*.csv files found in {INPUT_DIR}")
        return

    print(f"Found {len(inputs)} input file(s) in {INPUT_DIR}\n")
    grand_read = grand_kept = grand_dropped = 0

    for in_path in inputs:
        base = os.path.splitext(os.path.basename(in_path))[0]
        out_path = os.path.join(OUTPUT_DIR, f"{base}_CO.csv")
        read, kept, dropped = process_file(in_path, out_path)
        grand_read += read
        grand_kept += kept
        grand_dropped += dropped
        print(f"{os.path.basename(in_path)}")
        print(f"    rows read   : {read}")
        print(f"    rows kept   : {kept}")
        print(f"    rows dropped: {dropped}  (any core temp == 0.0 / unparseable)")
        print(f"    -> {out_path}\n")

    print("-" * 50)
    print(f"TOTAL  read: {grand_read}  kept: {grand_kept}  dropped: {grand_dropped}")


if __name__ == "__main__":
    main()
