#!/usr/bin/env python3
"""
round_all_4sig.py

Round all numeric per-core columns (C0_P..C7_P and C0_T..C7_T) to 4 significant
figures in the two _CO.csv files, writing NEW copies (*_4sig.csv).
wall_time_utc is left unchanged. round_sig copied verbatim from occt_logger.py.
"""

import csv
import math
import os

FILES = [
    r"D:\occt_history\For_CO_TUNING\CPU_06132026_CO.csv",
    r"D:\occt_history\For_CO_TUNING\CPU_06142026_CO.csv",
]

N_CORES = 8
TIME_COL = "wall_time_utc"
NUM_COLS = [f"C{i}_P" for i in range(N_CORES)] + [f"C{i}_T" for i in range(N_CORES)]
SIG = 4


# --- copied verbatim from occt_logger.py:50 ---
def round_sig(x: float, n: int) -> str:
    """n significant figures, no scientific notation, no trailing-zero pad."""
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
# --- end copy ---


def round_cell(s):
    if s is None or s.strip() == "":
        return ""
    try:
        return round_sig(float(s), SIG)
    except (ValueError, TypeError):
        return ""


def process_file(in_path):
    base = os.path.splitext(os.path.basename(in_path))[0]  # CPU_..._CO
    out_path = os.path.join(os.path.dirname(in_path), f"{base}_4sig.csv")
    rows = 0
    with open(in_path, "r", newline="", encoding="utf-8") as f_in:
        reader = csv.DictReader(f_in)
        fields = reader.fieldnames
        missing = [c for c in NUM_COLS if c not in fields]
        if missing:
            raise KeyError(f"{os.path.basename(in_path)} missing columns: {missing}")
        with open(out_path, "w", newline="", encoding="utf-8") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fields)
            writer.writeheader()
            for row in reader:
                rows += 1
                for c in NUM_COLS:
                    row[c] = round_cell(row.get(c))
                writer.writerow(row)
    return out_path, rows


def main():
    for in_path in FILES:
        out_path, rows = process_file(in_path)
        print(f"{os.path.basename(in_path)} -> {out_path}  ({rows} rows)")


if __name__ == "__main__":
    main()
