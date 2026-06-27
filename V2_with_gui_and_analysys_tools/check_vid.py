"""
Validity probe: is per-core C*_VID an independent per-core request, or just the
shared VDDCR_VDD rail echoed onto every core?

For each row, take the cores that are NOT in dropout (T!=0, vid>0, clk>0):
  - within-row VID spread (max-min) over those cores
  - fraction of multi-core rows where all those VIDs are byte-identical
  - per-row sign test: does the highest-CLOCK active core request a HIGHER VID
    than the lowest-clock active core? (true V/F per-core -> yes most of the time;
    shared rail -> VID flat regardless of clk -> ~no relationship)
Read-only. Prints to console.
"""
import csv, statistics

SRC = [
    r"D:\occt_history\CPU_DATA\CPU_06132026.csv",
    r"D:\occt_history\CPU_DATA\CPU_06142026.csv",
]
NCORE = 8

spreads = []
ident = 0
multi = 0
hi_gt_lo = 0       # rows where max-clk core VID  >  min-clk core VID
hi_eq_lo = 0       # equal
hi_lt_lo = 0       # less
dvid_when_distinct = []  # vid(hi-clk) - vid(lo-clk)

for path in SRC:
    with open(path, newline="") as f:
        r = csv.reader(f)
        header = next(r)
        idx = {name: k for k, name in enumerate(header)}
        cols = [(idx[f"C{n}_Clk"], idx[f"C{n}_VID"], idx[f"C{n}_T"]) for n in range(NCORE)]
        for fields in r:
            if not fields:
                continue
            active = []
            for ci, vi, ti in cols:
                try:
                    t = float(fields[ti]); v = float(fields[vi]); c = float(fields[ci])
                except (ValueError, IndexError):
                    continue
                if t == 0.0 or v <= 0.0 or c <= 0.0:
                    continue
                active.append((c, v))
            if len(active) < 2:
                continue
            multi += 1
            vids = [v for _, v in active]
            spreads.append(max(vids) - min(vids))
            if max(vids) == min(vids):
                ident += 1
            # sign test on the clock extremes
            hi = max(active, key=lambda cv: cv[0])
            lo = min(active, key=lambda cv: cv[0])
            if hi[0] != lo[0]:
                d = hi[1] - lo[1]
                dvid_when_distinct.append(d)
                if d > 0:
                    hi_gt_lo += 1
                elif d == 0:
                    hi_eq_lo += 1
                else:
                    hi_lt_lo += 1

print(f"multi-active rows: {multi}")
print(f"rows where all active VIDs identical: {ident}  ({100.0*ident/multi:.1f}%)")
print(f"within-row VID spread (V): mean={statistics.mean(spreads):.4f}  "
      f"median={statistics.median(spreads):.4f}  max={max(spreads):.4f}")
nd = len(dvid_when_distinct)
print(f"\nrows with distinct hi/lo clock: {nd}")
print(f"  hi-clk core VID > lo-clk core VID : {hi_gt_lo}  ({100.0*hi_gt_lo/nd:.1f}%)")
print(f"  equal                            : {hi_eq_lo}  ({100.0*hi_eq_lo/nd:.1f}%)")
print(f"  hi-clk core VID < lo-clk core VID : {hi_lt_lo}  ({100.0*hi_lt_lo/nd:.1f}%)")
print(f"  mean VID(hi-clk) - VID(lo-clk): {statistics.mean(dvid_when_distinct):+.4f} V")
print(f"  median: {statistics.median(dvid_when_distinct):+.4f} V")
