#!/usr/bin/env python3
"""
Bin coolant_c into ~1 C bins over the merged file, count rows per bin, report
percentage of total. Output a CSV ranked by percentage (descending).

Bin convention: [n, n+1)  (n <= c < n+1), labelled "n to n+1".
Edge: c == 0.0 is folded into the "-1 to 0" bin so the top edge is not a
1-row degenerate sliver.
"""

import csv
import math
import os
from collections import Counter

DIR = r"D:\occt_history\For_CO_TUNING"
IN = "CPU_06132026_06142026_CO_SANITIZED_coolant1dp_MERGED.csv"
OUT = "coolant_1C_bin_distribution.csv"
COOLANT_COL = "coolant_c"


def bin_low(v):
    n = math.floor(v)
    if v == 0.0:          # fold exact top edge into the -1..0 bin
        n = -1
    return n


def main():
    in_path = os.path.join(DIR, IN)
    counts = Counter()
    total = 0
    with open(in_path, "r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            s = row.get(COOLANT_COL, "").strip()
            if s == "":
                continue
            counts[bin_low(float(s))] += 1
            total += 1

    rows = []
    for n in sorted(counts):
        rows.append({
            "coolant_range_C": f"{n} to {n+1}",
            "bin_low": n,
            "bin_high": n + 1,
            "count": counts[n],
            "percentage": round(100.0 * counts[n] / total, 2),
        })
    rows.sort(key=lambda r: r["count"], reverse=True)

    out_path = os.path.join(DIR, OUT)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["coolant_range_C", "bin_low", "bin_high",
                                          "count", "percentage"])
        w.writeheader()
        w.writerows(rows)

    print(f"total rows binned: {total}")
    for r in rows:
        print(f"  {r['coolant_range_C']:>10} : {r['count']:6d}  {r['percentage']:5.2f}%")
    top = rows[0]
    print(f"-> {OUT}")
    print(f"MODE: {top['coolant_range_C']} C  ({top['percentage']}%, {top['count']} rows)")


if __name__ == "__main__":
    main()
