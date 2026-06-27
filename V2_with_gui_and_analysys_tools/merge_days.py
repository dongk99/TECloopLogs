#!/usr/bin/env python3
"""Vertically concatenate the two daily _coolant1dp files into one (06-13 then
06-14). Single header; all rows preserved; no dedup; no extra columns.
Aborts if the two headers are not identical."""

import csv
import os

DIR = r"D:\occt_history\For_CO_TUNING"
INPUTS = [
    "CPU_06132026_CO_SANITIZED_coolant1dp.csv",
    "CPU_06142026_CO_SANITIZED_coolant1dp.csv",
]
OUT = "CPU_06132026_06142026_CO_SANITIZED_coolant1dp_MERGED.csv"


def main():
    paths = [os.path.join(DIR, f) for f in INPUTS]

    # integrity: headers must match exactly
    headers = []
    for p in paths:
        with open(p, "r", newline="", encoding="utf-8") as f:
            headers.append(next(csv.reader(f)))
    if headers[0] != headers[1]:
        raise SystemExit(f"Header mismatch, aborting:\n  {headers[0]}\n  {headers[1]}")
    fields = headers[0]

    out_path = os.path.join(DIR, OUT)
    total = 0
    per = []
    with open(out_path, "w", newline="", encoding="utf-8") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fields)
        writer.writeheader()
        for p in paths:
            n = 0
            with open(p, "r", newline="", encoding="utf-8") as f_in:
                for row in csv.DictReader(f_in):
                    writer.writerow(row)
                    n += 1
            per.append((os.path.basename(p), n))
            total += n

    for name, n in per:
        print(f"  {name}: {n} rows")
    print(f"-> {OUT}  ({total} data rows + 1 header)")


if __name__ == "__main__":
    main()
