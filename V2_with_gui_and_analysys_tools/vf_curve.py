"""
vf_curve.py  -- Stage 2: build per-core V/F curve + ranking from vf_samples.csv.

Method follows SkatterBencher's Ryzen 9000 V/F-curve construction (verified):
bin by Core Clock, AVERAGE VID per clock bin (smooths the curve). The one
deliberate deviation: he POOLS all cores into a single CCD curve; here each core
is kept SEPARATE so they can be ranked (lower VID at matched clock = better core).

Outputs (-> D:\\occt_history\\For_CO_TUNING\\):
  vf_curve_matrix.csv  clock_bin x C0_VID..C7_VID (+ C0_T..C7_T), one series/core
  vf_curve_counts.csv  clock_bin x C0_n..C7_n        (samples behind each cell)
  vf_ranking.csv       per-core ranking, equal weight per shared clock bin

Ranking is computed FROM the binned matrix (one value per shared clock bin per
core, averaged with equal weight) -- NOT a raw sample mean over the clock range,
which would penalise a core merely for spending more time at high clock (the same
weighting confound that hit the thermal slope).

Display rounding only (values computed in full float): VID 4 dp, Temp 2 dp.
"""
import csv, math, sys
from collections import defaultdict

SRC = r"D:\occt_history\For_CO_TUNING\vf_samples.csv"
OUT_MATRIX = r"D:\occt_history\For_CO_TUNING\vf_curve_matrix.csv"
OUT_COUNTS = r"D:\occt_history\For_CO_TUNING\vf_curve_counts.csv"
OUT_RANK = r"D:\occt_history\For_CO_TUNING\vf_ranking.csv"

BIN = 25.0      # MHz bin width
MIN_N = 5       # bins with fewer samples than this are blank (sparse-noise trim)
NCORE = 8

a = sys.argv[1:]
i = 0
while i < len(a):
    if a[i] == "--bin":
        BIN = float(a[i + 1]); i += 2
    elif a[i] == "--min-n":
        MIN_N = int(a[i + 1]); i += 2
    else:
        i += 1

# ---- gather raw values per (core, bin) ----
vid_vals = defaultdict(list)   # (core,bin) -> [vid,...]
tmp_vals = defaultdict(list)   # (core,bin) -> [temp,...]
with open(SRC, newline="") as f:
    r = csv.DictReader(f)
    for row in r:
        core = int(row["core"])
        clk = float(row["clk_mhz"])
        b = int(round(clk / BIN) * BIN)
        vid_vals[(core, b)].append(float(row["vid_v"]))
        tmp_vals[(core, b)].append(float(row["temp_c"]))

def trimmed_mean(xs):
    """Light 3-sigma outlier trim then mean (VID at fixed clock is tight, so
    this rarely removes anything; it is a safety net, not aggressive cleaning)."""
    n = len(xs)
    if n < 3:
        return sum(xs) / n, n
    m = sum(xs) / n
    sd = (sum((x - m) ** 2 for x in xs) / n) ** 0.5
    if sd == 0:
        return m, n
    kept = [x for x in xs if abs(x - m) <= 3 * sd]
    if not kept:
        return m, n
    return sum(kept) / len(kept), len(kept)

# ---- per (core,bin) binned means (only bins with >= MIN_N samples) ----
binmean_vid = {}   # (core,bin) -> mean vid
binmean_tmp = {}   # (core,bin) -> mean temp
bincount = {}      # (core,bin) -> raw sample count
all_bins = set()
for (core, b), xs in vid_vals.items():
    raw_n = len(xs)
    bincount[(core, b)] = raw_n
    if raw_n < MIN_N:
        continue
    mv, _ = trimmed_mean(xs)
    mt, _ = trimmed_mean(tmp_vals[(core, b)])
    binmean_vid[(core, b)] = mv
    binmean_tmp[(core, b)] = mt
    all_bins.add(b)

bins_sorted = sorted(all_bins)

# ---- matrix output ----
with open(OUT_MATRIX, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["clock_bin_mhz"] + [f"C{n}_VID" for n in range(NCORE)]
               + [f"C{n}_T" for n in range(NCORE)])
    for b in bins_sorted:
        vrow = [(f"{binmean_vid[(n, b)]:.4f}" if (n, b) in binmean_vid else "")
                for n in range(NCORE)]
        trow = [(f"{binmean_tmp[(n, b)]:.2f}" if (n, b) in binmean_tmp else "")
                for n in range(NCORE)]
        w.writerow([b] + vrow + trow)

with open(OUT_COUNTS, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["clock_bin_mhz"] + [f"C{n}_n" for n in range(NCORE)])
    for b in bins_sorted:
        w.writerow([b] + [bincount.get((n, b), 0) for n in range(NCORE)])

# ---- ranking: equal weight per SHARED bin (all 8 cores present) ----
shared = [b for b in bins_sorted if all((n, b) in binmean_vid for n in range(NCORE))]

rank_rows = []
if shared:
    # reference clock = shared bin with the most total samples
    ref = max(shared, key=lambda b: sum(bincount.get((n, b), 0) for n in range(NCORE)))
    score = {}
    for n in range(NCORE):
        vals = [binmean_vid[(n, b)] for b in shared]
        score[n] = sum(vals) / len(vals)
    order = sorted(range(NCORE), key=lambda n: score[n])
    for rank, n in enumerate(order, 1):
        rank_rows.append((n, rank, f"{score[n]:.4f}", f"{binmean_vid[(n, ref)]:.4f}"))
    spread_mv = (max(score.values()) - min(score.values())) * 1000.0
else:
    ref = None
    spread_mv = None
    # fallback: rank by overall per-core mean VID across ALL its bins (NOT matched)
    score = {}
    for n in range(NCORE):
        bs = [b for b in bins_sorted if (n, b) in binmean_vid]
        score[n] = (sum(binmean_vid[(n, b)] for b in bs) / len(bs)) if bs else float("inf")
    order = sorted(range(NCORE), key=lambda n: score[n])
    for rank, n in enumerate(order, 1):
        rank_rows.append((n, rank, f"{score[n]:.4f}", ""))

with open(OUT_RANK, "w", newline="") as f:
    w = csv.writer(f)
    note = "mean_vid_over_shared_bins" if shared else "FALLBACK_mean_vid_all_bins_NOT_matched"
    w.writerow(["core", "rank_best_to_worst", note, "vid_at_ref_clock"])
    for row in rank_rows:
        w.writerow(row)

# ---- console summary ----
print(f"bin={BIN:.0f}MHz  min_n={MIN_N}")
print(f"clock bins populated: {len(bins_sorted)}"
      + (f"  range {bins_sorted[0]}..{bins_sorted[-1]} MHz" if bins_sorted else ""))
print(f"shared bins (all 8 cores): {len(shared)}")
if shared:
    print(f"reference clock bin: {ref} MHz")
    print(f"per-core VID spread across shared bins: {spread_mv:.1f} mV")
    print("ranking best->worst (lower VID = better):")
    for n, rank, sc, vref in rank_rows:
        print(f"  #{rank}  core {n}  meanVID={sc} V  @{ref}MHz={vref} V")
else:
    print("WARNING: no shared bins -- ranking used NON-matched fallback (see file)")
print(f"out: {OUT_MATRIX}")
print(f"out: {OUT_COUNTS}")
print(f"out: {OUT_RANK}")
