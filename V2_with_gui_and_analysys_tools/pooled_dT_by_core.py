#!/usr/bin/env python3
"""
Pool the four per-band Rth CSVs into one per-core summary, ordered core 0..7.
For each core: mean (across the 4 coolant bands) of dT (temp rise above coolant)
evaluated at two common powers inside all band overlaps, plus mean fit slope.
Numbers are recomputed from the band CSVs (value_at_P0 + slope*P) -- not retyped.
"""

import csv
import glob
import os
import statistics

DIR = r"D:\occt_history\For_CO_TUNING"
PL, PH = 4.0, 11.0          # common powers inside all four band overlaps
OUT = "pooled_dT_by_core.csv"


def main():
    bands = sorted(glob.glob(os.path.join(DIR, "rth_coolant_*.csv")))
    per = {i: {"lo": [], "hi": [], "slope": []} for i in range(8)}
    for fn in bands:
        with open(fn, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        for r in rows[2:]:                       # row0 = comment, row1 = header
            core = int(r[0]); a0 = float(r[10]); slope = float(r[8])
            per[core]["lo"].append(a0 + slope * PL)
            per[core]["hi"].append(a0 + slope * PH)
            per[core]["slope"].append(slope)

    out_path = os.path.join(DIR, OUT)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["# pooled over coolant bands",
                    f"n_bands={len(bands)}", f"P_low_W={PL}", f"P_high_W={PH}"])
        w.writerow(["core", "dT_at_4W", "dT_at_11W", "slope_confounded"])
        for i in range(8):                        # ordered 0..7
            lo = statistics.mean(per[i]["lo"])
            hi = statistics.mean(per[i]["hi"])
            sl = statistics.mean(per[i]["slope"])
            w.writerow([i, f"{lo:.2f}", f"{hi:.2f}", f"{sl:.2f}"])

    # echo
    print(f"bands pooled: {[os.path.basename(b) for b in bands]}")
    with open(out_path, "r", encoding="utf-8") as f:
        print(f.read().rstrip())
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
