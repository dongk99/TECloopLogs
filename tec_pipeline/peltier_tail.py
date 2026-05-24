#!/usr/bin/env python3
"""Tail the active PuTTY log in C:\\Users\\dongk\\Desktop\\Peltierlog\\ and
extract TEC coolant temperatures into a daily CSV.

Active log = file in the folder whose mtime is within the last 60 seconds.
Tracks byte offset per file in a cursor JSON. On file rotation, picks up
the new active file from its current end (no replay).

Output CSV schema:
  wall_time, device_time, source_file, tec_temp_c

Line formats handled:
  With PuTTY "Log line timestamps" enabled:
    2026-05-24T01:23:45 00:23:45,-4.0625
  Plain (fallback - uses current PC wall clock):
    00:23:45,-4.0625
"""
import os
import sys
import json
import csv
import time
import datetime
import re
import glob
import argparse

PELTIER_DIR = r"C:\Users\dongk\Desktop\Peltierlog"
CURSOR_PATH = r"D:\occt_history\.peltier_cursor"
LOG_DIR = r"D:\occt_history"
POLL_INTERVAL_SEC = 5
ACTIVE_MTIME_WINDOW_SEC = 60

LINE_WITH_PC_TS = re.compile(r"^(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})\s+(\d{2}:\d{2}:\d{2}),(-?\d+(?:\.\d+)?)")
LINE_PLAIN = re.compile(r"^(\d{2}:\d{2}:\d{2}),(-?\d+(?:\.\d+)?)")


def log(msg):
    print(f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)


def load_cursor():
    try:
        with open(CURSOR_PATH) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_cursor(state):
    os.makedirs(os.path.dirname(CURSOR_PATH), exist_ok=True)
    with open(CURSOR_PATH, "w") as f:
        json.dump(state, f)


def find_active_log():
    """Find the file in PELTIER_DIR with most recent mtime within window."""
    files = []
    for pat in ("*.log", "*.txt"):
        files.extend(glob.glob(os.path.join(PELTIER_DIR, pat)))
    if not files:
        return None
    candidates = [(f, os.path.getmtime(f)) for f in files]
    candidates.sort(key=lambda x: x[1], reverse=True)
    newest_file, newest_mtime = candidates[0]
    if time.time() - newest_mtime > ACTIVE_MTIME_WINDOW_SEC:
        return None
    return newest_file


def parse_line(line):
    """Parse one log line. Returns (wall_iso, device_time, temp_c) or None."""
    line = line.strip()
    if not line:
        return None
    m = LINE_WITH_PC_TS.match(line)
    if m:
        wall, dev, temp = m.groups()
        try:
            return wall, dev, float(temp)
        except ValueError:
            return None
    m = LINE_PLAIN.match(line)
    if m:
        dev, temp = m.groups()
        try:
            return datetime.datetime.now().isoformat(timespec="seconds"), dev, float(temp)
        except ValueError:
            return None
    return None


def open_csv_for_today():
    today_path = os.path.join(LOG_DIR, f"{datetime.date.today().isoformat()}_tec.csv")
    new_file = not os.path.exists(today_path)
    f = open(today_path, "a", newline="", encoding="utf-8")
    w = csv.writer(f)
    if new_file:
        w.writerow(["wall_time", "device_time", "source_file", "tec_temp_c"])
        f.flush()
    return today_path, f, w


def run_once(dry_run=False):
    """One polling cycle. Returns (active_file, lines_parsed)."""
    active = find_active_log()
    if active is None:
        return None, 0
    cursor = load_cursor()
    offset = cursor.get(active)
    if offset is None:
        # New active file - start from end (don't replay history)
        offset = os.path.getsize(active)
        cursor[active] = offset
        save_cursor(cursor)
    try:
        with open(active, "rb") as f:
            f.seek(offset)
            new_data = f.read()
            new_offset = f.tell()
    except OSError as e:
        log(f"Error reading {active}: {e}")
        return active, 0

    if not new_data:
        return active, 0

    try:
        text = new_data.decode("utf-8")
    except UnicodeDecodeError:
        text = new_data.decode("latin-1", errors="replace")

    csv_path, csv_file, csv_writer = (None, None, None) if dry_run else open_csv_for_today()
    parsed_count = 0
    try:
        for line in text.splitlines():
            parsed = parse_line(line)
            if parsed is None:
                continue
            wall, dev, temp = parsed
            if dry_run:
                print(f"  {wall}  dev={dev}  temp={temp}  src={os.path.basename(active)}")
            else:
                csv_writer.writerow([wall, dev, os.path.basename(active), temp])
            parsed_count += 1
    finally:
        if csv_file:
            csv_file.flush()
            csv_file.close()
    if not dry_run:
        cursor[active] = new_offset
        save_cursor(cursor)
    return active, parsed_count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Print to stdout, don't write CSV or advance cursor")
    ap.add_argument("--once", action="store_true", help="One polling cycle then exit")
    args = ap.parse_args()

    os.makedirs(LOG_DIR, exist_ok=True)
    log(f"Peltier tailer starting (dry_run={args.dry_run}, once={args.once})")
    log(f"Watching: {PELTIER_DIR}")

    last_active = None
    while True:
        try:
            active, n = run_once(dry_run=args.dry_run)
            if active and active != last_active:
                log(f"Active log: {active}")
                last_active = active
            elif active is None and last_active is not None:
                log("No active PuTTY log (no file modified in last 60s)")
                last_active = None
            if n:
                log(f"{n} new lines from {os.path.basename(active)}")
        except Exception as e:
            log(f"Unexpected error: {e}")
        if args.once:
            break
        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
