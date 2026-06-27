#!/usr/bin/env python3
"""
round_power_4sig.py

Round the per-core power columns (C0_P..C7_P) in the _CO.csv files down to
4 significant figures, writing new _CO_P4sig.csv files.

Scope (ONLY this):
  - Rounds ONLY the 8 per-core power columns to 4 sig figs.
  - Temperature (C*_T) and timestamp pass through UNCHANGED, character for
    character. Column set/order is identical to the input _CO file.
  - This is a display-precision reduction (5 sig fig -> 4 sig fig) of an
    already-stored value. It does not add accuracy.

Cell rules:
  - 0.0 power -> "0" (a legitimate value to round; round_sig returns "0").
  - empty / unparseable power cell -> left blank (no fabrication).

round_sig() is copied VERBATIM from occt_logger.py (pure, only depends on math)
so the rounding/trailing-zero-strip behavior matches how this data was
originally formatted. Not imported, to avoid running that module's top-level code.
"""

import csv
import glob
import math
import os

INPUT_DIR = r"D:\occt_history\For_CO_TUNING"
OUTPUT_DIR = r"D:\occt_history\For_CO_TUNING"

N_CORES = 8
POWER_COLS = [f"C{i}_P" for i in range(N_CORES)]
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


def round_power_cell(s):
    """Round a power cell to SIG sig figs; blank stays blank / unparseable->blank."""
    if s is None or s.strip() == "":
        return ""
    try:
        return round_sig(float(s), SIG)
    except (ValueError, TypeError):
        return ""


def process_file(in_path, out_path):
    rows = 0
    rounded = 0
    blanks = 0

    with open(in_path, "r", newline="", encoding="utf-8") as f_in:
        reader = csv.DictReader(f_in)
        fields = reader.fieldnames
        missing = [c for c in POWER_COLS if c not in fields]
        if missing:
            raise KeyError(
                f"{os.path.basename(in_path)} is missing power columns: {missing}"
            )

        with open(out_path, "w", newline="", encoding="utf-8") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fields)  # same order as source
            writer.writeheader()
            for row in reader:
                rows += 1
                for c in POWER_COLS:
                    new = round_power_cell(row.get(c))
                    if new == "":
                        blanks += 1
                    row[c] = new        # only power cells touched; all else untouched
                    rounded += 1
                writer.writerow(row)

    return rows, rounded, blanks


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    inputs = sorted(glob.glob(os.path.join(INPUT_DIR, "CPU_*_CO.csv")))
    if not inputs:
        print(f"No CPU_*_CO.csv files found in {INPUT_DIR}")
        return

    print(f"Found {len(inputs)} input file(s) in {INPUT_DIR}\n")
    for in_path in inputs:
        base = os.path.splitext(os.path.basename(in_path))[0]  # CPU_..._CO
        out_path = os.path.join(OUTPUT_DIR, f"{base}_P4sig.csv")
        rows, rounded, blanks = process_file(in_path, out_path)
        print(f"{os.path.basename(in_path)}")
        print(f"    rows           : {rows}")
        print(f"    power cells set : {rounded}  (rounded to {SIG} sig figs)")
        print(f"    blank power     : {blanks}")
        print(f"    -> {out_path}\n")


if __name__ == "__main__":
    main()
