#!/usr/bin/env python3
"""Round coolant_c to 2 sig figs in the _CO_4sig.csv files (in place via .tmp.csv;
swap done separately after verification). Only coolant_c changes."""

import csv
import math
import os

FILES = [
    r"D:\occt_history\For_CO_TUNING\CPU_06132026_CO_4sig.csv",
    r"D:\occt_history\For_CO_TUNING\CPU_06142026_CO_4sig.csv",
]
COOLANT_COL = "coolant_c"
SIG = 2


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


def process(path):
    tmp = path + ".tmp.csv"
    rows = 0
    with open(path, "r", newline="", encoding="utf-8") as f_in:
        reader = csv.DictReader(f_in)
        fields = reader.fieldnames
        if COOLANT_COL not in fields:
            raise KeyError(f"{os.path.basename(path)} missing {COOLANT_COL}")
        with open(tmp, "w", newline="", encoding="utf-8") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fields)
            writer.writeheader()
            for row in reader:
                rows += 1
                row[COOLANT_COL] = round_cell(row.get(COOLANT_COL))
                writer.writerow(row)
    return tmp, rows


def main():
    for path in FILES:
        tmp, rows = process(path)
        print(f"{os.path.basename(path)}: {rows} rows -> {tmp}")


if __name__ == "__main__":
    main()
