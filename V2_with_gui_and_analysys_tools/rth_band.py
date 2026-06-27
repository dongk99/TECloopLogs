#!/usr/bin/env python3
"""
Per-core temperature comparison within ONE ~1 C coolant band, for CO tuning.

PRIMARY metric: dT_at_Pstar = each core's temperature rise above coolant
(dT = T_core - coolant) evaluated at a COMMON operating power P*, by a linear
fit centered at P* (so the reported value and its standard error are an
interpolation INSIDE the data, not an extrapolation to P=0). This answers
"which core runs hottest at the same power" -- the CO-relevant question.

Also reported, but NOT as a clean per-core thermal resistance: the raw slope
(dT vs P). On an all-core load every core's power is correlated with total die
heat, so the single-variable slope is CONFOUNDED by cross-core heating. It is
kept as a diagnostic column only; a clean per-core resistance would need a
multiple regression dT ~ P_core + P_total (not done here).

All numbers come from scipy/numpy. Deterministic.

Usage:  python rth_band.py --band-low -2     # band [-2, -1)
"""

import argparse
import csv
import math
import os

import numpy as np
from scipy import stats

DIR = r"D:\occt_history\For_CO_TUNING"
IN = "CPU_06132026_06142026_CO_SANITIZED_coolant1dp_MERGED.csv"
NCORES = 8
EXPECTED = {-1: 1011, -2: 6166, -3: 3650, -4: 2469, -5: 439, -6: 132}  # tie-back


def bin_low(v):
    """1 C bin assignment, matching the histogram: floor, with 0.0 folded to -1."""
    n = math.floor(v)
    if v == 0.0:
        n = -1
    return n


def load_band(path, band_low):
    pts = {i: ([], []) for i in range(NCORES)}   # core -> (power[], dT[])
    total = 0
    with open(path, "r", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            s = r.get("coolant_c", "").strip()
            if s == "":
                continue
            c = float(s)
            if bin_low(c) != band_low:
                continue
            total += 1
            for i in range(NCORES):
                ps = r.get(f"C{i}_P", "").strip()
                ts = r.get(f"C{i}_T", "").strip()
                if ps == "" or ts == "":
                    continue
                try:
                    P = float(ps); T = float(ts)
                except ValueError:
                    continue
                pts[i][0].append(P)
                pts[i][1].append(T - c)
    return pts, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--band-low", type=int, required=True,
                    help="integer low edge of the 1 C band, e.g. -2 means [-2,-1)")
    args = ap.parse_args()
    bl = args.band_low
    label = f"{bl}_to_{bl + 1}"

    pts, total = load_band(os.path.join(DIR, IN), bl)

    # per-core arrays + degeneracy + power range
    arr = {}
    for i in range(NCORES):
        P = np.asarray(pts[i][0], float); dT = np.asarray(pts[i][1], float)
        degen = P.size < 2 or np.unique(P).size < 2
        arr[i] = dict(P=P, dT=dT, n=int(P.size), degen=degen,
                      Pmin=float(P.min()) if P.size else float("nan"),
                      Pmax=float(P.max()) if P.size else float("nan"))

    good = [i for i in range(NCORES) if not arr[i]["degen"]]
    overlap_lo = max(arr[i]["Pmin"] for i in good) if good else float("nan")
    overlap_hi = min(arr[i]["Pmax"] for i in good) if good else float("nan")
    # P* = median operating power (pooled), clamped into the common overlap window
    if good:
        pooled = np.concatenate([arr[i]["P"] for i in good])
        pstar = float(np.median(pooled))
        pstar = min(max(pstar, overlap_lo), overlap_hi)
    else:
        pstar = float("nan")

    # centered refit at P*: intercept == dT@P*, intercept_stderr == its prediction SE
    for i in range(NCORES):
        a = arr[i]
        if a["degen"] or math.isnan(pstar):
            a.update(dT_star=float("nan"), dT_star_se=float("nan"),
                     slope=float("nan"), slope_se=float("nan"),
                     R2=float("nan"), intercept_raw=float("nan"))
            continue
        lr = stats.linregress(a["P"] - pstar, a["dT"])
        a.update(dT_star=float(lr.intercept), dT_star_se=float(lr.intercept_stderr),
                 slope=float(lr.slope), slope_se=float(lr.stderr),
                 R2=float(lr.rvalue ** 2),
                 intercept_raw=float(lr.intercept - lr.slope * pstar))  # value at P=0
        a["P_spread"] = a["Pmax"] - a["Pmin"]

    # order by dT@P* descending (hottest at operating power first), NaN last
    order = sorted(range(NCORES),
                   key=lambda i: (math.isnan(arr[i].get("dT_star", float("nan"))),
                                  -arr[i].get("dT_star", 0.0)
                                  if not math.isnan(arr[i].get("dT_star", float("nan"))) else 0.0))

    # write CSV (primary metric first)
    out = f"rth_coolant_{label}.csv"
    cols = ["core", "n", "P_min", "P_max", "P_spread",
            "dT_at_Pstar", "dT_at_Pstar_se", "R2",
            "slope_confounded", "slope_se", "value_at_P0"]
    with open(os.path.join(DIR, out), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["# P_star_W", f"{pstar:.4g}", "metric=dT_at_Pstar (temp rise above coolant at P*)"])
        w.writerow(cols)
        for i in order:
            a = arr[i]
            w.writerow([i, a["n"], f'{a["Pmin"]:.4g}', f'{a["Pmax"]:.4g}',
                        f'{a.get("P_spread", float("nan")):.4g}',
                        f'{a["dT_star"]:.4g}', f'{a["dT_star_se"]:.3g}', f'{a["R2"]:.4f}',
                        f'{a["slope"]:.6g}', f'{a["slope_se"]:.3g}', f'{a["intercept_raw"]:.4g}'])

    # ---- printed summary ----
    tie = EXPECTED.get(bl)
    tietag = "OK" if tie == total else (f"!! expected {tie}" if tie is not None else "n/a")
    print(f"=== Coolant band [{bl}, {bl + 1}) C ===")
    print(f"rows: {total}  (tie-back {tietag})")
    print(f"power overlap: [{overlap_lo:.4g}, {overlap_hi:.4g}] W   P* (median op. power) = {pstar:.4g} W")
    print("PRIMARY = dT at P* (temp rise above coolant at common power). "
          "slope is CONFOUNDED by cross-core heating -- diagnostic only.")
    print(f"{'core':>4} {'n':>5} {'dT@P*':>7} {'+/-se':>6} {'R2':>6} {'slope*':>7} {'Pspread':>8}")
    for i in order:
        a = arr[i]
        print(f"{i:>4} {a['n']:>5} {a['dT_star']:>7.4g} {a['dT_star_se']:>6.3g} "
              f"{a['R2']:>6.3f} {a['slope']:>7.4g} {a.get('P_spread', float('nan')):>8.4g}")

    rank = [i for i in order if not arr[i]["degen"]]
    print(f"rank by dT@P* (hottest first): {rank}")
    # cluster adjacent cores that are NOT distinguishable at ~2 sigma
    clusters, cur = [], [rank[0]] if rank else []
    for a, b in zip(rank, rank[1:]):
        gap = arr[a]["dT_star"] - arr[b]["dT_star"]
        comb = 2 * math.sqrt(arr[a]["dT_star_se"] ** 2 + arr[b]["dT_star_se"] ** 2)
        if gap > comb:
            clusters.append(cur); cur = [b]
        else:
            cur.append(b)
    if cur:
        clusters.append(cur)
    print("clusters (hottest->coolest, cores within a group indistinguishable at 2sd):")
    print("  " + "  >  ".join("{" + ",".join(map(str, g)) + "}" for g in clusters))
    print(f"-> {out}")


if __name__ == "__main__":
    main()
