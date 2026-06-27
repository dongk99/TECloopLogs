#!/usr/bin/env python3
"""
Conditional sig-fig rounding of per-core POWER and TEMP in the _CO_4sig.csv files.

Per cell (classified by its INPUT value):
  |value| <  10  -> 2 significant figures   (e.g. 9.235 -> 9.2 ;  0.0606 -> 0.061)
  |value| >= 10  -> 3 significant figures   (e.g. 10.231 -> 10.2 ; 44.03 -> 44.0)

Applies ONLY to the 16 per-core columns C0_P..C7_P and C0_T..C7_T.
coolant_c and wall_time_utc pass through byte-identical.
New files written (originals kept). round_sig copied verbatim from occt_logger.py.
"""

import csv
import math
import os

FILES = [
    r"D:\occt_history\For_CO_TUNING\CPU_06132026_CO_4sig.csv",
    r"D:\occt_history\For_CO_TUNING\CPU_06142026_CO_4sig.csv",
]
N_CORES = 8
NUM_COLS = [f"C{i}_P" for i in range(N_CORES)] + [f"C{i}_T" for i in range(N_CORES)]


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


def cond_round(s):
    if s is None or s.strip() == "":
        return ""
    try:
        v = float(s)
    except (ValueError, TypeError):
        return ""
    n = 2 if abs(v) < 10 else 3
    return round_sig(v, n)


def process(path, out_path):
    rows = 0
    with open(path, "r", newline="", encoding="utf-8") as f_in:
        reader = csv.DictReader(f_in)
        fields = reader.fieldnames
        missing = [c for c in NUM_COLS if c not in fields]
        if missing:
            raise KeyError(f"{os.path.basename(path)} missing columns: {missing}")
        with open(out_path, "w", newline="", encoding="utf-8") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fields)
            writer.writeheader()
            for row in reader:
                rows += 1
                for c in NUM_COLS:
                    row[c] = cond_round(row.get(c))
                writer.writerow(row)
    return rows


def main():
    for path in FILES:
        base = os.path.splitext(os.path.basename(path))[0]  # CPU_..._CO_4sig
        out_path = os.path.join(os.path.dirname(path), f"{base}_condsig.csv")
        rows = process(path, out_path)
        print(f"{os.path.basename(path)} -> {os.path.basename(out_path)}  ({rows} rows)")


if __name__ == "__main__":
    main()
