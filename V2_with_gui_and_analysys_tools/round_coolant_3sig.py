#!/usr/bin/env python3
"""Round coolant_c to 3 sig figs in the *_coolant.csv files -> new *_3sig.csv files."""

import csv
import glob
import math
import os

INPUT_DIR = r"D:\occt_history\For_CO_TUNING"
COOLANT_COL = "coolant_c"
SIG = 3


# copied verbatim from occt_logger.py:50
def round_sig(x: float, n: int) -> str:
    if x == 0:
        return "0"
    if not math.isfinite(x):
        return repr(x)
    exp = math.floor(math.log10(abs(x)))
    decimals = max(0, n - 1 - exp)
    s = f"{x:.{decimals}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def round_cell(s):
    if s is None or s.strip() == "":
        return ""
    try:
        return round_sig(float(s), SIG)
    except (ValueError, TypeError):
        return ""


def process_file(in_path, out_path):
    rows = 0
    with open(in_path, "r", newline="", encoding="utf-8") as f_in:
        reader = csv.DictReader(f_in)
        fields = reader.fieldnames
        if COOLANT_COL not in fields:
            raise KeyError(f"{os.path.basename(in_path)} missing {COOLANT_COL}")
        with open(out_path, "w", newline="", encoding="utf-8") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fields)
            writer.writeheader()
            for row in reader:
                rows += 1
                row[COOLANT_COL] = round_cell(row.get(COOLANT_COL))
                writer.writerow(row)
    return rows


def main():
    inputs = sorted(glob.glob(os.path.join(INPUT_DIR, "CPU_*_coolant.csv")))
    if not inputs:
        print(f"No CPU_*_coolant.csv in {INPUT_DIR}")
        return
    for in_path in inputs:
        base = os.path.splitext(os.path.basename(in_path))[0]  # CPU_..._coolant
        out_path = os.path.join(INPUT_DIR, f"{base}_3sig.csv")
        rows = process_file(in_path, out_path)
        print(f"{os.path.basename(in_path)} -> {out_path}  ({rows} rows)")


if __name__ == "__main__":
    main()
