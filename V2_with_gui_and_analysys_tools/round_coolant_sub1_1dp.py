#!/usr/bin/env python3
"""
On coolant_c ONLY: values with 0 < |v| < 1 (the -0.xx / +0.xx values) -> round to
ONE decimal place (0.x). Exact zero ("0") and |v| >= 1 are left byte-identical.
All other columns untouched. New files written; originals kept.
"""

import csv
import os

FILES = [
    r"D:\occt_history\For_CO_TUNING\CPU_06132026_CO_SANITIZED.csv",
    r"D:\occt_history\For_CO_TUNING\CPU_06142026_CO_SANITIZED.csv",
]
COOLANT_COL = "coolant_c"


def transform(s):
    """Round sub-1 (0<|v|<1) coolant to 1 decimal place; leave everything else as-is."""
    if s is None or s.strip() == "":
        return s
    try:
        v = float(s)
    except (ValueError, TypeError):
        return s
    if 0 < abs(v) < 1:
        out = f"{v:.1f}"
        if out == "-0.0":          # clamp negative zero artifact
            out = "0.0"
        return out
    return s                        # exact 0 and |v|>=1 unchanged (original bytes)


def process(path, out_path):
    rows = changed = 0
    with open(path, "r", newline="", encoding="utf-8") as f_in:
        reader = csv.DictReader(f_in)
        fields = reader.fieldnames
        if COOLANT_COL not in fields:
            raise KeyError(f"{os.path.basename(path)} missing {COOLANT_COL}")
        with open(out_path, "w", newline="", encoding="utf-8") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fields)
            writer.writeheader()
            for row in reader:
                rows += 1
                orig = row.get(COOLANT_COL)
                new = transform(orig)
                if new != orig:
                    changed += 1
                row[COOLANT_COL] = new
                writer.writerow(row)
    return rows, changed


def main():
    for path in FILES:
        base = os.path.splitext(os.path.basename(path))[0]
        out_path = os.path.join(os.path.dirname(path), f"{base}_coolant1dp.csv")
        rows, changed = process(path, out_path)
        print(f"{os.path.basename(path)} -> {os.path.basename(out_path)}  "
              f"({rows} rows, {changed} coolant cells changed)")


if __name__ == "__main__":
    main()
