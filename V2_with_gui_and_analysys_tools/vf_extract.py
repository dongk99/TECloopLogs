"""
vf_extract.py  -- Stage 1 of the per-core V/F (VID-vs-Core-Clock) build.

Pulls per-core (Core Clock, VID, Temp) from the ORIGINAL CPU_DATA logs
(these still carry C*_VID and C*_Clk; the For_CO_TUNING outputs dropped them).
Effective-clock columns are carried alongside (nothing lost) but are NOT the
binning axis -- VID is requested for the requested P-state = Core Clock.

Dropout handling is PER CORE: a (timestamp, core) sample enters the output iff
that core's temperature != 0.0 (the established 0 C dropout marker) and its VID
and Clk are positive. This is intentionally NOT the row-wise "drop if ANY core
== 0" filter, because each core's curve is built independently and a dropout on
one core must not discard valid samples from the others.

Optional idle/parked filters are provided but OFF by default (flagged, not baked
in): --max-c6res <pct> drops samples whose C6 residency exceeds the threshold;
--min-clk <mhz> drops samples below a clock floor.

Output: D:\\occt_history\\For_CO_TUNING\\vf_samples.csv  (tidy long format)
"""
import csv, sys, os

SRC = [
    r"D:\occt_history\CPU_DATA\CPU_06132026.csv",
    r"D:\occt_history\CPU_DATA\CPU_06142026.csv",
]
OUT = r"D:\occt_history\For_CO_TUNING\vf_samples.csv"
NCORE = 8

# ---- optional idle filters (default disabled) ----
MAX_C6RES = None
MIN_CLK = None
a = sys.argv[1:]
i = 0
while i < len(a):
    if a[i] == "--max-c6res":
        MAX_C6RES = float(a[i + 1]); i += 2
    elif a[i] == "--min-clk":
        MIN_CLK = float(a[i + 1]); i += 2
    else:
        i += 1

rows_out = []
rows_in = 0
kept = 0
drop_t0 = 0
drop_badvid = 0
drop_idle = 0

for path in SRC:
    with open(path, newline="") as f:
        r = csv.reader(f)
        header = next(r)
        idx = {name: k for k, name in enumerate(header)}
        ts_i = idx["wall_time_utc"]
        col = {}
        for n in range(NCORE):
            col[n] = {
                "clk": idx[f"C{n}_Clk"],
                "vid": idx[f"C{n}_VID"],
                "t":   idx[f"C{n}_T"],
                "c6":  idx[f"C{n}_C6res"],
                "e0":  idx[f"C{n}_T0_EClk"],
                "e1":  idx[f"C{n}_T1_EClk"],
            }
        for fields in r:
            if not fields:
                continue
            rows_in += 1
            ts = fields[ts_i]
            for n in range(NCORE):
                c = col[n]
                try:
                    t = float(fields[c["t"]])
                    vid = float(fields[c["vid"]])
                    clk = float(fields[c["clk"]])
                    c6 = float(fields[c["c6"]])
                    e0 = float(fields[c["e0"]])
                    e1 = float(fields[c["e1"]])
                except (ValueError, IndexError):
                    continue
                if t == 0.0:
                    drop_t0 += 1; continue
                if vid <= 0.0 or clk <= 0.0:
                    drop_badvid += 1; continue
                if MAX_C6RES is not None and c6 > MAX_C6RES:
                    drop_idle += 1; continue
                if MIN_CLK is not None and clk < MIN_CLK:
                    drop_idle += 1; continue
                rows_out.append((ts, n, clk, vid, t, c6, e0, e1))
                kept += 1

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["wall_time_utc", "core", "clk_mhz", "vid_v", "temp_c", "c6res", "eclk_t0", "eclk_t1"])
    w.writerows(rows_out)

print(f"sources={len(SRC)}  rows_in={rows_in}  per_core_samples_kept={kept}")
print(f"dropped: T==0 -> {drop_t0}   vid<=0|clk<=0 -> {drop_badvid}   idle_filter -> {drop_idle}")
print(f"idle filters: max_c6res={MAX_C6RES}  min_clk={MIN_CLK}")
print(f"out={OUT}")
