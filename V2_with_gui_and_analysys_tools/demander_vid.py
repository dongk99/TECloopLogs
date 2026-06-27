"""
Demander-conditioned per-core VID read.

Co-active cores share one plane, so same-instant VID is tautologically equal --
that test can't see per-core silicon. Instead, select samples where ONE core is
the sole rail-driver (high power, siblings parked); then the plane voltage == that
core's own request, so its reported VID IS its request. Compare core-as-demander
vs core-as-demander at matched clock + temperature -> that is the silicon read.

Demander row for core X (per row):
  X = highest-power core, X.power >= DEMW, AND 2nd-highest core power <= SIBW
  (exactly one core working, rest quiet), and X has valid temp/vid/clk.
per-core eclk = max(thread0 EClk, thread1 EClk).

Primary lens = power/temperature (per user); clock gated at CLKBIN (default 25 MHz),
temperature banded at TEMPBIN (default 5 C).

Read-only; prints coverage first, then the per-core demander-VID picture.
Writes D:\\occt_history\\For_CO_TUNING\\demander_vid_matrix.csv
"""
import csv, math, statistics, sys
from collections import defaultdict

SRC = [
    r"D:\occt_history\CPU_DATA\CPU_06132026.csv",
    r"D:\occt_history\CPU_DATA\CPU_06142026.csv",
]
OUT = r"D:\occt_history\For_CO_TUNING\demander_vid_matrix.csv"
NCORE = 8
DEMW = 6.0     # demander min power (W)
SIBW = 4.0     # max 2nd-highest sibling power (W)
CLKBIN = 25.0
TEMPBIN = 5.0
MIN_N = 5

a = sys.argv[1:]; i = 0
while i < len(a):
    if a[i] == "--demw": DEMW = float(a[i+1]); i += 2
    elif a[i] == "--sibw": SIBW = float(a[i+1]); i += 2
    elif a[i] == "--clkbin": CLKBIN = float(a[i+1]); i += 2
    elif a[i] == "--tempbin": TEMPBIN = float(a[i+1]); i += 2
    elif a[i] == "--min-n": MIN_N = int(a[i+1]); i += 2
    else: i += 1

dem = defaultdict(list)            # core -> [(clkbin,tempband,vid,p,eclk,temp,clk)]
total_rows = 0

for path in SRC:
    with open(path, newline="") as f:
        r = csv.reader(f)
        header = next(r)
        idx = {name: k for k, name in enumerate(header)}
        cc = [(idx[f"C{n}_Clk"], idx[f"C{n}_VID"], idx[f"C{n}_T"], idx[f"C{n}_P"],
               idx[f"C{n}_T0_EClk"], idx[f"C{n}_T1_EClk"]) for n in range(NCORE)]
        for fields in r:
            if not fields:
                continue
            total_rows += 1
            rec = {}
            for n, (ci, vi, ti, pi, e0i, e1i) in enumerate(cc):
                try:
                    p = float(fields[pi])
                except (ValueError, IndexError):
                    p = -1.0
                try:
                    t = float(fields[ti]); v = float(fields[vi]); c = float(fields[ci])
                    e = max(float(fields[e0i]), float(fields[e1i]))
                except (ValueError, IndexError):
                    t = v = c = e = float("nan")
                rec[n] = (p, v, t, c, e)
            order = sorted(range(NCORE), key=lambda n: rec[n][0], reverse=True)
            top = order[0]; second = order[1]
            p_top = rec[top][0]; p_second = rec[second][0]
            if p_top < DEMW or p_second > SIBW:
                continue
            p, v, t, c, e = rec[top]
            if t == 0.0 or not (0.3 <= v <= 1.6) or not (c > 0) or math.isnan(t):
                continue
            cb = int(round(c / CLKBIN) * CLKBIN)
            tb = int(math.floor(t / TEMPBIN) * TEMPBIN)
            dem[top].append((cb, tb, v, p, e, t, c))

# ---------- coverage ----------
print(f"total rows scanned: {total_rows}")
print(f"demander gate: power>={DEMW}W AND 2nd-core<={SIBW}W   clkbin={CLKBIN:.0f}  tempbin={TEMPBIN:.0f}C\n")
print("coverage per core (sole-demander samples):")
for n in range(NCORE):
    s = dem[n]
    if not s:
        print(f"  core {n}: 0 samples  <-- NO demander coverage"); continue
    clks = [x[6] for x in s]; tmps = [x[5] for x in s]
    cells = len({(x[0], x[1]) for x in s})
    print(f"  core {n}: {len(s):6d} samples  clk {min(clks):.0f}-{max(clks):.0f}  "
          f"temp {min(tmps):.1f}-{max(tmps):.1f}C  ({cells} clk/temp cells)")

# ---------- per (core, clkbin) : VID vs clock, temp as covariate ----------
cell_vid = defaultdict(list)   # (core, clkbin) -> [vid]
cell_tmp = defaultdict(list)
ct_vid = defaultdict(list)     # (core, clkbin, tempband) -> [vid]
for n in range(NCORE):
    for cb, tb, v, p, e, t, c in dem[n]:
        cell_vid[(n, cb)].append(v)
        cell_tmp[(n, cb)].append(t)
        ct_vid[(n, cb, tb)].append(v)

clkbins = sorted({cb for (n, cb) in cell_vid})

# View A: per-core mean demander VID by clock bin (>=MIN_N)
meanvid = {}
for (n, cb), vs in cell_vid.items():
    if len(vs) >= MIN_N:
        meanvid[(n, cb)] = statistics.mean(vs)

print("\nVIEW A -- per-core demander VID by clock bin (temp = mean covariate):")
bin_present = {cb: [n for n in range(NCORE) if (n, cb) in meanvid] for cb in clkbins}
multi_clk = [cb for cb in clkbins if len(bin_present[cb]) >= 2]
if multi_clk:
    ref = max(multi_clk, key=lambda cb: sum(len(cell_vid[(n, cb)]) for n in bin_present[cb]))
    present = sorted(bin_present[ref], key=lambda n: meanvid[(n, ref)])
    print(f"  bins with >=2 demander cores: {len(multi_clk)}   reference bin = {ref} MHz "
          f"({len(bin_present[ref])} cores present)")
    print(f"  core VID @ {ref} MHz (sole-demander, matched clock):")
    for n in present:
        mt = statistics.mean(cell_tmp[(n, ref)])
        print(f"    core {n}: VID={meanvid[(n,ref)]:.4f}  (mean temp {mt:.1f}C, n={len(cell_vid[(n,ref)])})")
    vs = [meanvid[(n, ref)] for n in present]
    print(f"  spread @ {ref} MHz across {len(present)} cores: {(max(vs)-min(vs))*1000:.1f} mV")
else:
    print("  no clock bin has >=2 cores as demander -- per-core overlap gap (see coverage)")
print("  per-core overall demander VID (each over its OWN samples; NOT matched across cores):")
for n in range(NCORE):
    if dem[n]:
        vs = [x[2] for x in dem[n]]
        print(f"    core {n}: meanVID={statistics.mean(vs):.4f}  n={len(vs)}")

# View B: matched (clock,temp) cell with best multi-core coverage
print("\nVIEW B -- per-core VID at matched (clock, temp) cells (>=4 cores, n>=MIN_N each):")
ct_mean = {}
for (n, cb, tb), vs in ct_vid.items():
    if len(vs) >= MIN_N:
        ct_mean[(n, cb, tb)] = statistics.mean(vs)
cells = sorted({(cb, tb) for (n, cb, tb) in ct_mean})
multi = []
for (cb, tb) in cells:
    present = [n for n in range(NCORE) if (n, cb, tb) in ct_mean]
    if len(present) >= 2:
        vs = [ct_mean[(n, cb, tb)] for n in present]
        multi.append((cb, tb, present, (max(vs) - min(vs)) * 1000))
if multi:
    multi.sort(key=lambda x: -len(x[2]))
    for cb, tb, present, sp in multi[:6]:
        line = "  ".join(f"c{n}={ct_mean[(n,cb,tb)]:.4f}" for n in present)
        print(f"  {cb}MHz {tb}-{tb+int(TEMPBIN)}C ({len(present)} cores, spread {sp:.1f}mV): {line}")
else:
    print("  no (clock,temp) cell has >=4 cores with enough demander samples")

# ---------- matrix CSV (View A) ----------
with open(OUT, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["clock_bin_mhz"] + [f"C{n}_demVID" for n in range(NCORE)]
               + [f"C{n}_n" for n in range(NCORE)])
    for cb in clkbins:
        vrow = [(f"{meanvid[(n,cb)]:.4f}" if (n, cb) in meanvid else "") for n in range(NCORE)]
        nrow = [len(cell_vid.get((n, cb), [])) for n in range(NCORE)]
        w.writerow([cb] + vrow + nrow)
print(f"\nout: {OUT}")
