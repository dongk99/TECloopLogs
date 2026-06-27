#!/usr/bin/env python3
"""
Combine the per-watt empirical bins (B) into one matrix, then run A: a linear
fit of dT vs power through B's bin means, per core.

Outputs (in CO_TUNING_WATTAGE/):
  COMBINED_dT_by_watt.csv  -- power_W x core matrix of measured dT (blank=unsupported)
  A_fit_from_bins.csv      -- per core: slope/intercept/R2 fit through the bin means
"""

import csv
import glob
import os

import numpy as np
from scipy import stats

OUTDIR = r"D:\occt_history\For_CO_TUNING\CO_TUNING_WATTAGE"


def main():
    files = sorted(glob.glob(os.path.join(OUTDIR, "dT_bin_*W.csv")))
    # matrix[w][core] = (dT_mean or None, n)
    mat = {}
    for fn in files:
        with open(fn, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        for r in rows[2:]:                       # skip comment + header
            w = int(r[0]); core = int(r[1]); n = int(r[2])
            dT = float(r[4]) if r[4] != "" else None
            mat.setdefault(w, {})[core] = (dT, n)
    watts = sorted(mat)

    # --- COMBINED matrix (B) ---
    m_path = os.path.join(OUTDIR, "COMBINED_dT_by_watt.csv")
    with open(m_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["# measured dT (C) by power, band [-2,-1) C; blank = <20 samples"])
        w.writerow(["power_W"] + [f"C{i}_dT" for i in range(8)])
        for watt in watts:
            row = [watt]
            for i in range(8):
                dT, n = mat[watt].get(i, (None, 0))
                row.append(f"{dT:.3f}" if dT is not None else "")
            w.writerow(row)

    # --- A: linear fit through the bin means, per core ---
    a_path = os.path.join(OUTDIR, "A_fit_from_bins.csv")
    with open(a_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["# A: OLS of measured dT vs power through B bin means (band [-2,-1) C)"])
        w.writerow(["core", "slope_CperW", "intercept_C", "R2", "n_bins", "watt_lo", "watt_hi"])
        a_rows = []
        for i in range(8):
            xs = [watt for watt in watts if mat[watt].get(i, (None,))[0] is not None]
            ys = [mat[watt][i][0] for watt in xs]
            if len(xs) >= 2:
                lr = stats.linregress(np.array(xs, float), np.array(ys, float))
                a_rows.append([i, f"{lr.slope:.3f}", f"{lr.intercept:.3f}",
                               f"{lr.rvalue**2:.4f}", len(xs), min(xs), max(xs)])
            else:
                a_rows.append([i, "", "", "", len(xs), "", ""])
        w.writerows(a_rows)

    # echo
    print("COMBINED_dT_by_watt.csv:")
    with open(m_path, encoding="utf-8") as f:
        print(f.read().rstrip())
    print("\nA_fit_from_bins.csv:")
    with open(a_path, encoding="utf-8") as f:
        print(f.read().rstrip())


if __name__ == "__main__":
    main()
