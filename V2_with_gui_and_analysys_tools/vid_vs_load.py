"""
Does per-core VID track ACTUAL per-core activity (power, effective clock),
or is it the shared rail echoed onto every core?

Per row, among active cores (T!=0, 0.3<=VID<=1.6, Clk>0) pick the extreme pair
under four different classifiers and compare the pair's VID, plus report the
power / effective-clock / core-clock of each side:
  - by VID         (hi-VID core vs lo-VID core: are hi-VID cores actually busier?)
  - by POWER       (hi-power vs lo-power core: does VID rise with real power draw?)
  - by EFF. CLOCK  (hi-eclk vs lo-eclk core: does VID rise with real running speed?)
  - by CORE CLOCK  (the requested P-state -- shown WITH its power/eclk to expose
                    whether "hi core clock" is a bad proxy for actual activity)

per-core effective clock = max(thread0 EClk, thread1 EClk).
Read-only.
"""
import csv, statistics

SRC = [
    r"D:\occt_history\CPU_DATA\CPU_06132026.csv",
    r"D:\occt_history\CPU_DATA\CPU_06142026.csv",
]
NCORE = 8

def acc():
    return {"gt": 0, "eq": 0, "lt": 0, "n": 0,
            "dvid": [], "hi_p": [], "lo_p": [], "hi_e": [], "lo_e": [],
            "hi_c": [], "lo_c": [], "hi_v": [], "lo_v": []}

by_vid, by_pow, by_eclk, by_clk = acc(), acc(), acc(), acc()

def tally(A, hi, lo):
    # hi/lo are core dicts; compare VID of hi-side vs lo-side
    A["n"] += 1
    d = hi["vid"] - lo["vid"]
    A["dvid"].append(d)
    if d > 0: A["gt"] += 1
    elif d == 0: A["eq"] += 1
    else: A["lt"] += 1
    A["hi_p"].append(hi["p"]); A["lo_p"].append(lo["p"])
    A["hi_e"].append(hi["e"]); A["lo_e"].append(lo["e"])
    A["hi_c"].append(hi["clk"]); A["lo_c"].append(lo["clk"])
    A["hi_v"].append(hi["vid"]); A["lo_v"].append(lo["vid"])

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
            act = []
            for ci, vi, ti, pi, e0i, e1i in cc:
                try:
                    t = float(fields[ti]); v = float(fields[vi]); c = float(fields[ci])
                    p = float(fields[pi]); e0 = float(fields[e0i]); e1 = float(fields[e1i])
                except (ValueError, IndexError):
                    continue
                if t == 0.0 or not (0.3 <= v <= 1.6) or c <= 0:
                    continue
                act.append({"clk": c, "vid": v, "p": p, "e": max(e0, e1)})
            if len(act) < 2:
                continue
            # by VID
            hv = max(act, key=lambda d: d["vid"]); lv = min(act, key=lambda d: d["vid"])
            if hv["vid"] != lv["vid"]: tally(by_vid, hv, lv)
            # by power
            hp = max(act, key=lambda d: d["p"]); lp = min(act, key=lambda d: d["p"])
            if hp["p"] != lp["p"]: tally(by_pow, hp, lp)
            # by eclk
            he = max(act, key=lambda d: d["e"]); le = min(act, key=lambda d: d["e"])
            if he["e"] != le["e"]: tally(by_eclk, he, le)
            # by core clock
            hc = max(act, key=lambda d: d["clk"]); lc = min(act, key=lambda d: d["clk"])
            if hc["clk"] != lc["clk"]: tally(by_clk, hc, lc)

def report(name, A):
    n = A["n"]
    if n == 0:
        print(f"\n[{name}] no qualifying rows"); return
    m = statistics.mean
    print(f"\n[{name}]  pairs={n}")
    print(f"  VID(hi-side) > VID(lo-side): {100.0*A['gt']/n:.1f}%   "
          f"==:{100.0*A['eq']/n:.1f}%   <:{100.0*A['lt']/n:.1f}%   "
          f"meanDVID={m(A['dvid'])*1000:+.1f} mV")
    print(f"  hi-side: P={m(A['hi_p']):6.2f}W  eclk={m(A['hi_e']):7.1f}  "
          f"coreclk={m(A['hi_c']):7.1f}  VID={m(A['hi_v']):.4f}")
    print(f"  lo-side: P={m(A['lo_p']):6.2f}W  eclk={m(A['lo_e']):7.1f}  "
          f"coreclk={m(A['lo_c']):7.1f}  VID={m(A['lo_v']):.4f}")

report("classify by VID", by_vid)
report("classify by POWER", by_pow)
report("classify by EFFECTIVE CLOCK", by_eclk)
report("classify by CORE CLOCK (requested P-state)", by_clk)
