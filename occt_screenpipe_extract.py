#!/usr/bin/env python3
"""Extract OCCT sensor values from screenpipe OCR data into daily CSV.

Polls D:\\screenpipe_recording_data\\db.sqlite every POLL_INTERVAL_SEC, reads
frames newer than last processed frame_id (cursor persisted to disk),
parses bounding boxes from ocr_text.text_json, identifies the OCCT table
region by header tokens, extracts sensor rows, writes to
D:\\occt_history\\YYYY-MM-DD_screenpipe.csv.

Output CSV schema:
  wall_time, frame_id, sensor_name, value, min, avg, max, unit

Notes on the screenpipe DB (Mitsukeru fork, schema discovered empirically):
  frames.device_name = 'monitor_65539' (the bottom monitor identifier)
  ocr_text.ocr_engine = 'WindowsNative' (not Tesseract)
  ocr_text.text_json = JSON array of tokens with normalized 0-1 coords as STRINGS:
    [{"text":"...","left":"0.08","top":"0.17","width":"0.04","height":"0.01","conf":"1.0"}, ...]
"""
import os
import sys
import csv
import json
import sqlite3
import datetime
import time
import re
import argparse

DB_PATH = r"D:\screenpipe_recording_data\db.sqlite"
CURSOR_PATH = r"D:\occt_history\.screenpipe_cursor"
LOG_DIR = r"D:\occt_history"
POLL_INTERVAL_SEC = 10
BOTTOM_DEVICE_NAME = "monitor_65539"  # the bottom monitor's device_name in frames table

# OCR character substitution. Common WindowsNative misreads of digits.
OCR_NUM_SUB = str.maketrans({"O": "0", "o": "0", "B": "8", "l": "1", "I": "1",
                              "S": "5", "s": "5", "Z": "2", "z": "2", "g": "9",
                              "D": "0"})

NUM_RE = re.compile(r"^(-?\d+(?:\.\d+)?)$")
# Unit patterns ordered by specificity. WindowsNative often reads "°C" as "oc"
# and uses lowercase v/w. Each entry maps regex match -> normalized unit.
UNIT_PATTERNS = [
    (re.compile(r"(?:°[Cc]|oc|OC|0c|0C)\b"), "C"),
    (re.compile(r"(?:°[Ff]|of|OF|0f|0F)\b"), "F"),
    (re.compile(r"MHz\b", re.IGNORECASE), "MHz"),
    (re.compile(r"kHz\b", re.IGNORECASE), "kHz"),
    (re.compile(r"RPM\b", re.IGNORECASE), "RPM"),
    (re.compile(r"mV\b"), "mV"),
    (re.compile(r"[vV]\b"), "V"),
    (re.compile(r"[wW]\b"), "W"),
    (re.compile(r"[aA]\b"), "A"),
    (re.compile(r"%"), "%"),
]

HEADER_TOKENS = {"Name", "Value", "Min", "Avg", "Max"}
# Tolerance for "same row" in normalized coords. Bottom monitor is 1440px tall;
# a row is ~17px = 17/1440 = 0.012. Use 0.008 (~11 px).
ROW_BAND_NORM = 0.008
# Max horizontal gap to consider tokens part of the same word (normalized).
# Monitor 2560px wide; 30 px = 0.012.
TOKEN_GAP_NORM = 0.012
# OCCT region: left half of screen. Right edge at 0.5 by default.
OCCT_RIGHT_EDGE_NORM = 0.5


def log(msg):
    print(f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)


def load_cursor():
    try:
        with open(CURSOR_PATH) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return 0


def save_cursor(frame_id):
    os.makedirs(os.path.dirname(CURSOR_PATH), exist_ok=True)
    with open(CURSOR_PATH, "w") as f:
        f.write(str(frame_id))


def parse_text_json(blob):
    """Parse ocr_text.text_json into list of normalized-coord token dicts."""
    if not blob:
        return []
    try:
        raw = json.loads(blob)
    except (ValueError, TypeError):
        return []
    tokens = []
    for item in raw:
        text = (item.get("text") or "").strip()
        if not text:
            continue
        try:
            tokens.append({
                "text": text,
                "left": float(item.get("left", 0)),
                "top": float(item.get("top", 0)),
                "width": float(item.get("width", 0)),
                "height": float(item.get("height", 0)),
                "conf": float(item.get("conf", 0)),
            })
        except (ValueError, TypeError):
            continue
    return tokens


def find_occt_region(tokens):
    """Locate the OCCT table by finding header tokens Name/Value/Min/Avg/Max
    co-located on the same horizontal row, within the left half of screen."""
    headers = {}
    for t in tokens:
        if t["text"] in HEADER_TOKENS and t["left"] < OCCT_RIGHT_EDGE_NORM:
            if t["text"] not in headers or t["conf"] > headers[t["text"]]["conf"]:
                headers[t["text"]] = t
    if len(headers) < 4:
        return None
    tops = [headers[k]["top"] for k in headers]
    if max(tops) - min(tops) > ROW_BAND_NORM * 2:
        return None
    if "Max" not in headers or "Value" not in headers:
        return None
    max_tok = headers["Max"]
    region = {
        "name_x": headers.get("Name", {}).get("left", 0),
        "value_x": headers["Value"]["left"],
        "min_x": headers.get("Min", headers["Value"])["left"],
        "avg_x": headers.get("Avg", headers["Value"])["left"],
        "max_x": max_tok["left"],
        "right_edge": min(max_tok["left"] + max_tok["width"] + 0.03, OCCT_RIGHT_EDGE_NORM),
        "header_top": max_tok["top"],
        "header_height": max_tok["height"],
    }
    return region


def group_into_rows(tokens, region):
    """Group tokens into rows by top band, restricted to OCCT region and
    below the header row."""
    threshold_top = region["header_top"] + region["header_height"] * 0.5
    filtered = [t for t in tokens
                if t["left"] < region["right_edge"]
                and t["top"] > threshold_top]
    filtered.sort(key=lambda t: (t["top"], t["left"]))
    rows = []
    current = []
    current_top = None
    for tok in filtered:
        if current_top is None or abs(tok["top"] - current_top) <= ROW_BAND_NORM:
            current.append(tok)
            current_top = tok["top"] if current_top is None else (current_top + tok["top"]) / 2
        else:
            rows.append(current)
            current = [tok]
            current_top = tok["top"]
    if current:
        rows.append(current)
    return rows


def combine_adjacent(tokens):
    """Combine adjacent tokens whose horizontal gap is small."""
    if not tokens:
        return []
    tokens = sorted(tokens, key=lambda t: t["left"])
    combined = []
    i = 0
    while i < len(tokens):
        cur = tokens[i]
        text = cur["text"]
        left = cur["left"]
        right = cur["left"] + cur["width"]
        j = i + 1
        while j < len(tokens) and tokens[j]["left"] - right < TOKEN_GAP_NORM:
            text = text + " " + tokens[j]["text"]
            right = tokens[j]["left"] + tokens[j]["width"]
            j += 1
        combined.append({"left": left, "right": right, "text": text})
        i = j
    return combined


def split_value_unit(text):
    """Split a combined token like '19.63 °C' or '19.63oc' into (number, unit).
    Returns (number_string, unit_string) where unit may be empty."""
    text = text.strip()
    best_match = None  # (start_pos, unit_normalized)
    for pat, unit_norm in UNIT_PATTERNS:
        m = pat.search(text)
        if m and (best_match is None or m.start() < best_match[0]):
            best_match = (m.start(), unit_norm)
    if best_match is None:
        return text, ""
    pos, unit_norm = best_match
    num_part = text[:pos].strip()
    return num_part, unit_norm


def parse_number(num_str):
    """Parse a numeric string, applying OCR substitution if direct parse fails."""
    if not num_str:
        return None
    s = num_str.strip()
    m = NUM_RE.match(s)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    # Try with OCR substitution
    substituted = s.translate(OCR_NUM_SUB)
    m = NUM_RE.match(substituted)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


def extract_row(row_tokens, region):
    """Extract (sensor_name, value, min, avg, max, unit) from a row.
    Returns None if not a valid sensor row."""
    if not row_tokens:
        return None
    # Sort by left within row so name tokens come out in correct reading order
    # (group_into_rows uses top-then-left, which can produce wrong order when
    # tokens in the same row have slightly different top coordinates).
    row_tokens = sorted(row_tokens, key=lambda t: t["left"])
    # Sidebar buttons (STABILITY TEST, CERTIFICATE, MONITORING, etc.) sit at
    # the far left edge well before the Name column. Reject tokens left of
    # name_x - 0.05 to exclude them.
    name_left_floor = region["name_x"] - 0.05
    name_tokens = [t for t in row_tokens
                   if name_left_floor <= t["left"] < region["value_x"] - 0.005]
    value_tokens = [t for t in row_tokens if t["left"] >= region["value_x"] - 0.005]
    if not name_tokens or not value_tokens:
        return None
    sensor_name = " ".join(t["text"] for t in name_tokens).strip()
    if not sensor_name or sensor_name in HEADER_TOKENS:
        return None
    if sensor_name.startswith("Filter"):
        return None
    combined = combine_adjacent(value_tokens)
    if not combined:
        return None
    anchors = [("value", region["value_x"]), ("min", region["min_x"]),
               ("avg", region["avg_x"]), ("max", region["max_x"])]
    parsed = {"value": None, "min": None, "avg": None, "max": None}
    units = []
    used = set()
    for c in combined:
        best_col, best_dist = None, 0.1
        for name, anchor in anchors:
            if name in used:
                continue
            d = abs(c["left"] - anchor)
            if d < best_dist:
                best_dist = d
                best_col = name
        if best_col is None:
            continue
        num_str, unit = split_value_unit(c["text"])
        val = parse_number(num_str)
        if val is None:
            continue
        parsed[best_col] = val
        if unit:
            units.append(unit)
        used.add(best_col)
    if parsed["value"] is None:
        return None
    unit = units[0] if units else ""
    return sensor_name, parsed["value"], parsed["min"], parsed["avg"], parsed["max"], unit


def open_csv_for_today():
    path = os.path.join(LOG_DIR, f"{datetime.date.today().isoformat()}_screenpipe.csv")
    new = not os.path.exists(path)
    f = open(path, "a", newline="", encoding="utf-8")
    w = csv.writer(f)
    if new:
        w.writerow(["wall_time", "frame_id", "sensor_name", "value", "min", "avg", "max", "unit"])
        f.flush()
    return path, f, w


def normalize_timestamp(ts):
    """Screenpipe stores timestamp as ISO string or epoch. Return ISO 8601."""
    if ts is None:
        return ""
    if isinstance(ts, str):
        return ts
    if isinstance(ts, (int, float)):
        if ts > 1e12:
            ts = ts / 1000.0
        try:
            return datetime.datetime.fromtimestamp(ts).isoformat(timespec="seconds")
        except (OSError, ValueError, OverflowError):
            return str(ts)
    return str(ts)


def run_once(dry_run=False, max_frames=200):
    if not os.path.exists(DB_PATH):
        return 0, 0, 0
    cursor = load_cursor()
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        q = """SELECT f.id, f.timestamp, o.text_json
               FROM frames f LEFT JOIN ocr_text o ON o.frame_id = f.id
               WHERE f.id > ? AND f.device_name = ?
               ORDER BY f.id LIMIT ?"""
        rows = conn.execute(q, (cursor, BOTTOM_DEVICE_NAME, max_frames)).fetchall()
    finally:
        conn.close()
    if not rows:
        return 0, 0, 0

    csv_path, csv_file, csv_writer = (None, None, None) if dry_run else open_csv_for_today()
    seen = set()
    n_rows_written = 0
    n_frames_with_occt = 0
    last_id = cursor
    try:
        for r in rows:
            frame_id = r["id"]
            ts = normalize_timestamp(r["timestamp"])
            tj = r["text_json"]
            last_id = frame_id
            if not tj:
                continue
            tokens = parse_text_json(tj)
            region = find_occt_region(tokens)
            if region is None:
                continue
            n_frames_with_occt += 1
            for row_tokens in group_into_rows(tokens, region):
                parsed = extract_row(row_tokens, region)
                if parsed is None:
                    continue
                name, val, mn, av, mx, unit = parsed
                key = (name, val, mn, av, mx)
                if key in seen:
                    continue
                seen.add(key)
                if dry_run:
                    print(f"  fid={frame_id:>4} ts={ts}  {name:<32}  val={val:>10}  min={mn}  avg={av}  max={mx}  unit={unit}")
                else:
                    csv_writer.writerow([ts, frame_id, name, val, mn, av, mx, unit])
                n_rows_written += 1
    finally:
        if csv_file:
            csv_file.flush()
            csv_file.close()
    if not dry_run:
        save_cursor(last_id)
    return len(rows), n_frames_with_occt, n_rows_written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Print rows to stdout, don't write CSV or advance cursor")
    ap.add_argument("--once", action="store_true", help="One polling cycle then exit")
    args = ap.parse_args()

    os.makedirs(LOG_DIR, exist_ok=True)
    log(f"OCCT screenpipe extractor (dry_run={args.dry_run}, once={args.once})")
    log(f"DB: {DB_PATH}")
    log(f"Filtering frames by device_name='{BOTTOM_DEVICE_NAME}'")

    while True:
        try:
            n_frames, n_with_occt, n_rows = run_once(dry_run=args.dry_run)
            if n_frames:
                log(f"Processed {n_frames} frames ({n_with_occt} with OCCT visible), wrote {n_rows} rows")
        except sqlite3.OperationalError as e:
            log(f"SQLite error (retry next cycle): {e}")
        except Exception as e:
            log(f"Unexpected error: {e}")
        if args.once:
            break
        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
