#!/usr/bin/env python3
"""
B: empirical per-watt bin of dT (= T_core - coolant) for ONE integer power N,
within the -2..-1 C coolant band (44% of data; single band avoids smearing
coolant dependence into the per-watt spread).

For each core: take samples whose power is in [N-0.5, N+0.5) W and report the
MEASURED mean dT, its spread, and n. If support is thin (n < MIN_N) the dT cell
is left BLANK -- never extrapolated/projected. (So 15 W, beyond the data, comes
out blank.)

Output: CO_TUNING_WATTAGE/dT_bin_{N:02d}W.csv

Usage: python wattage_bin.py --power 5
"""

import argparse
import csv
import math
import os

import numpy as np

DIR = r"D:\occt_history\For_CO_TUNING"
OUTDIR = os.path.join(DIR, "CO_TUNING_WATTAGE")
IN = "CPU_06132026_06142026_CO_SANITIZED_coolant1dp_MERGED.csv"
BAND_LOW = -2                 # the -2..-1 C band
HALF = 0.5                    # bin half-width (W)
MIN_N = 20                    # minimum samples to report a measured mean


def bin_low(v):
    return -1 if v == 0.0 else math.floor(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--power", type=int, required=True)
    N = ap.parse_args().power
    lo, hi = N - HALF, N + HALF

    os.makedirs(OUTDIR, exist_ok=True)

    per = {i: [] for i in range(8)}    # core -> list of (P, dT) in the bin
    with open(os.path.join(DIR, IN), "r", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            s = r.get("coolant_c", "").strip()
            if s == "":
                continue
            c = float(s)
            if bin_low(c) != BAND_LOW:
                continue
            for i in range(8):
                ps = r.get(f"C{i}_P", "").strip()
                ts = r.get(f"C{i}_T", "").strip()
                if not ps or not ts:
                    continue
                P = float(ps)
                if lo <= P < hi:
                    per[i].append((P, float(ts) - c))

    out = os.path.join(OUTDIR, f"dT_bin_{N:02d}W.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["# band [-2,-1) C", f"power_W={N}", f"bin=[{lo},{hi})", f"min_n={MIN_N}"])
        w.writerow(["power_W", "core", "n", "P_mean", "dT_mean", "dT_sem", "dT_std", "supported"])
        for i in range(8):
            pts = per[i]
            n = len(pts)
            if n >= MIN_N:
                P = np.array([p for p, _ in pts]); d = np.array([x for _, x in pts])
                pm = float(P.mean()); dm = float(d.mean())
                sd = float(d.std(ddof=1)); sem = sd / math.sqrt(n)
                w.writerow([N, i, n, f"{pm:.3f}", f"{dm:.3f}", f"{sem:.4f}", f"{sd:.3f}", "yes"])
            else:
                w.writerow([N, i, n, "", "", "", "", "no"])

    # echo
    print(f"power {N} W  band [-2,-1)  bin [{lo},{hi})")
    with open(out, "r", encoding="utf-8") as f:
        print(f.read().rstrip())
    print(f"-> CO_TUNING_WATTAGE/dT_bin_{N:02d}W.csv")


if __name__ == "__main__":
    main()
