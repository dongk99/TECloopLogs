#!/usr/bin/env python3
"""
Attach coolant_c onto the _CO_4sig.csv files via a KEYED left join on
wall_time_utc (never positional). Writes <name>.tmp.csv (atomic replace done
separately after verification). Existing columns untouched; coolant_c appended.
Blank where no timestamp match. coolant_c taken as-is from the 3-sig file.
"""

import csv
import os

PAIRS = [
    (r"D:\occt_history\For_CO_TUNING\CPU_06132026_CO_4sig.csv",
     r"D:\occt_history\For_CO_TUNING\CPU_06132026_coolant_3sig.csv"),
    (r"D:\occt_history\For_CO_TUNING\CPU_06142026_CO_4sig.csv",
     r"D:\occt_history\For_CO_TUNING\CPU_06142026_coolant_3sig.csv"),
]
TIME_COL = "wall_time_utc"
COOLANT_COL = "coolant_c"


def load_coolant(path):
    m = {}
    dups = 0
    with open(path, "r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            k = row[TIME_COL]
            if k in m:
                dups += 1
            m[k] = row[COOLANT_COL]
    return m, dups


def join(co_path, cool_path):
    cool, dups = load_coolant(cool_path)
    tmp_path = co_path + ".tmp.csv"
    rows = matched = blank = 0
    with open(co_path, "r", newline="", encoding="utf-8") as f_in:
        reader = csv.DictReader(f_in)
        fields = list(reader.fieldnames)
        if COOLANT_COL in fields:
            raise KeyError(f"{os.path.basename(co_path)} already has {COOLANT_COL}")
        out_fields = fields + [COOLANT_COL]
        with open(tmp_path, "w", newline="", encoding="utf-8") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=out_fields)
            writer.writeheader()
            for row in reader:
                rows += 1
                val = cool.get(row[TIME_COL], "")
                if val == "":
                    blank += 1
                else:
                    matched += 1
                row[COOLANT_COL] = val
                writer.writerow(row)
    return tmp_path, rows, matched, blank, dups


def main():
    for co_path, cool_path in PAIRS:
        tmp, rows, matched, blank, dups = join(co_path, cool_path)
        print(f"{os.path.basename(co_path)}: rows={rows} matched={matched} "
              f"blank={blank} coolant_dup_keys={dups}")
        print(f"    -> {tmp}")


if __name__ == "__main__":
    main()
