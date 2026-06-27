"""Quantify data-quality: ragged rows (field count != header) and out-of-range VID."""
import csv

SRC = [
    r"D:\occt_history\CPU_DATA\CPU_06132026.csv",
    r"D:\occt_history\CPU_DATA\CPU_06142026.csv",
]
NCORE = 8

for path in SRC:
    with open(path, newline="") as f:
        r = csv.reader(f)
        header = next(r)
        H = len(header)
        idx = {name: k for k, name in enumerate(header)}
        vids = [idx[f"C{n}_VID"] for n in range(NCORE)]
        rows = ragged = 0
        vid_total = vid_bad = 0
        worst = 0.0
        for fields in r:
            if not fields:
                continue
            rows += 1
            if len(fields) != H:
                ragged += 1
            for vi in vids:
                if vi < len(fields):
                    try:
                        v = float(fields[vi])
                    except ValueError:
                        continue
                    vid_total += 1
                    if not (0.3 <= v <= 1.6):   # plausible Ryzen core VID window
                        vid_bad += 1
                        worst = max(worst, v)
        print(f"{path.split(chr(92))[-1]}: header_cols={H} rows={rows} "
              f"ragged_rows={ragged} ({100.0*ragged/rows:.2f}%)")
        print(f"   VID values checked={vid_total} out-of-range(0.3..1.6V)={vid_bad} "
              f"({100.0*vid_bad/vid_total:.3f}%) worst={worst:g}")
