#!/usr/bin/env python3
"""Drop rows where coolant_c is blank, in the _CO_4sig.csv files.
Writes <name>.tmp.csv (atomic replace done separately after verification)."""

import csv
import os

FILES = [
    r"D:\occt_history\For_CO_TUNING\CPU_06132026_CO_4sig.csv",
    r"D:\occt_history\For_CO_TUNING\CPU_06142026_CO_4sig.csv",
]
COOLANT_COL = "coolant_c"


def process(path):
    tmp = path + ".tmp.csv"
    read = kept = dropped = 0
    with open(path, "r", newline="", encoding="utf-8") as f_in:
        reader = csv.DictReader(f_in)
        fields = reader.fieldnames
        if COOLANT_COL not in fields:
            raise KeyError(f"{os.path.basename(path)} missing {COOLANT_COL}")
        with open(tmp, "w", newline="", encoding="utf-8") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=fields)
            writer.writeheader()
            for row in reader:
                read += 1
                v = row.get(COOLANT_COL)
                if v is None or v.strip() == "":
                    dropped += 1
                    continue
                writer.writerow(row)
                kept += 1
    return tmp, read, kept, dropped


def main():
    for path in FILES:
        tmp, read, kept, dropped = process(path)
        print(f"{os.path.basename(path)}: read={read} kept={kept} dropped_blank={dropped}")
        print(f"    -> {tmp}")


if __name__ == "__main__":
    main()
