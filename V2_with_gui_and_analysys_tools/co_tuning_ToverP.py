#!/usr/bin/env python3
"""
co_tuning_ToverP.py

Compute per-core T/P (core temperature divided by that core's power) from the
filtered _CO.csv files produced by co_tuning_extract.py.

Output column layout (option B): timestamp + the 8 per-core ratios only.
    wall_time_utc, C0_ToverP, C1_ToverP, ... C7_ToverP

Definition / scope:
  - This is the LITERAL ratio C{i}_T / C{i}_P, units degC/W.
  - It is NOT thermal resistance: there is NO reference-temperature subtraction
    (Rth = dT/P would need a reference). Deliberately named ToverP, never Rth.
  - No rounding: full float precision is preserved.
  - No power floor: near-zero power yields large ratios; those are kept as-is.
    Flooring is a downstream analysis decision, not done here.

Zero-power safety (measurement integrity):
  - If a power cell is exactly 0.0 (or empty / unparseable), the ratio cell is
    left BLANK -- never inf, never 0, never a fabricated value. Blank reads back
    as NaN in pandas and is auto-excluded from stats.
  - This is done PER CELL, so one parked core does not void the other 7 in the
    same timestamp. Row count stays 1:1 with the input _CO file.
"""

import csv
import glob
import os

INPUT_DIR = r"D:\occt_history\For_CO_TUNING"
OUTPUT_DIR = r"D:\occt_history\For_CO_TUNING"

N_CORES = 8
TIME_COL = "wall_time_utc"
OUT_COLS = [TIME_COL] + [f"C{i}_ToverP" for i in range(N_CORES)]


def ratio(temp_str, power_str):
    """Return repr of temp/power, or '' (blank) if power is 0.0 / unparseable."""
    try:
        p = float(power_str)
        t = float(temp_str)
    except (ValueError, TypeError):
        return ""
    if p == 0.0:
        return ""
    return repr(t / p)


def process_file(in_path, out_path):
    rows = 0
    blanks = 0

    with open(in_path, "r", newline="", encoding="utf-8") as f_in:
        reader = csv.DictReader(f_in)
        needed = [TIME_COL] + [f"C{i}_T" for i in range(N_CORES)] + \
                 [f"C{i}_P" for i in range(N_CORES)]
        missing = [c for c in needed if c not in reader.fieldnames]
        if missing:
            raise KeyError(
                f"{os.path.basename(in_path)} is missing expected columns: {missing}"
            )

        with open(out_path, "w", newline="", encoding="utf-8") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=OUT_COLS)
            writer.writeheader()
            for row in reader:
                rows += 1
                out = {TIME_COL: row.get(TIME_COL, "")}
                for i in range(N_CORES):
                    val = ratio(row.get(f"C{i}_T"), row.get(f"C{i}_P"))
                    if val == "":
                        blanks += 1
                    out[f"C{i}_ToverP"] = val
                writer.writerow(out)

    return rows, blanks


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Only the _CO.csv inputs; never re-glob our own _ToverP outputs.
    inputs = sorted(glob.glob(os.path.join(INPUT_DIR, "CPU_*_CO.csv")))
    if not inputs:
        print(f"No CPU_*_CO.csv files found in {INPUT_DIR}")
        return

    print(f"Found {len(inputs)} input file(s) in {INPUT_DIR}\n")
    for in_path in inputs:
        base = os.path.splitext(os.path.basename(in_path))[0]  # e.g. CPU_06142026_CO
        out_path = os.path.join(OUTPUT_DIR, f"{base}_ToverP.csv")
        rows, blanks = process_file(in_path, out_path)
        print(f"{os.path.basename(in_path)}")
        print(f"    rows written : {rows}")
        print(f"    blank ratios : {blanks}  (power == 0.0 / unparseable)")
        print(f"    -> {out_path}\n")


if __name__ == "__main__":
    main()
