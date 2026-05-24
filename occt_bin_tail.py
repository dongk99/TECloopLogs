#!/usr/bin/env python3
"""Tail OCCT v17 sensorpoints.bin and write per-sample CSV to D:\\occt_history\\.

Adapted from sirmalloc's monitor_occt.py:
https://gist.github.com/sirmalloc/e0717460c7870548f5c24b0d63aa593c

Differences from upstream:
- Daily-rotating CSV at D:\\occt_history\\YYYY-MM-DD_occt_bin.csv
- Cursor persisted across script restarts: resume same OCCT session if
  Started timestamp unchanged, else start-from-end on new session
- Schema drops min/avg/max (raw samples; aggregate downstream in pandas)
- Logs progress to stdout (captured by launcher .bat to log file)

Binary format (extracted by sirmalloc):
  block = int32 count, count*(int32 sensor_id, f64 elapsed_s, f64 value), uint32 crc32(prev)

CSV schema:
  wall_time, elapsed_seconds, sensor_id, sensor_name, value, unit
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import struct
import sys
import time
import zlib
from pathlib import Path
from typing import BinaryIO

STATE_DIR = Path(os.environ.get("TEMP", r"C:\Users\dongk\AppData\Local\Temp")) / "OCCT" / "State"
CURSOR_PATH = Path(r"D:\occt_history\.occt_bin_cursor")
LOG_DIR = Path(r"D:\occt_history")
POLL_INTERVAL_SEC = 0.25

COUNT_STRUCT = struct.Struct("<i")
CRC_STRUCT = struct.Struct("<I")
POINT_STRUCT = struct.Struct("<idd")

UNIT_LABELS_INT = {
    0: "", 100: "C", 200: "V", 300: "W", 400: "A",
    500: "RPM", 600: "MHz", 700: "%", 701: "MB", 702: "MB/s", 800: "",
}
UNIT_LABELS_STR = {
    "Celsius": "C", "Volt": "V", "Watt": "W", "Ampere": "A",
    "Rpm": "RPM", "MHz": "MHz", "Percent": "%",
    "MB": "MB", "MBs": "MB/s", "Default": "", "Other": "",
}


def log(msg: str) -> None:
    print(f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)


def load_cursor() -> dict:
    try:
        with open(CURSOR_PATH) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_cursor(state_dir: str, started: str | None, position: int) -> None:
    CURSOR_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CURSOR_PATH, "w") as f:
        json.dump({"state_dir": state_dir, "started": started, "position": position}, f)


def load_json(path: Path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def load_sensors(path: Path) -> dict[int, dict]:
    data = load_json(path)
    if not isinstance(data, list):
        return {}
    out: dict[int, dict] = {}
    for item in data:
        if isinstance(item, dict) and "SensorId" in item:
            out[int(item["SensorId"])] = item
    return out


def parse_started(path: Path) -> tuple[str | None, datetime.datetime | None]:
    if not path.exists():
        return None, None
    try:
        data = load_json(path)
    except Exception:
        return None, None
    if not isinstance(data, dict) or not data.get("Started"):
        return None, None
    started = str(data["Started"])
    try:
        dt = datetime.datetime.fromisoformat(started)
    except ValueError:
        return None, None
    if dt.year <= 1:
        return None, None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    dt = dt.astimezone(datetime.timezone.utc)
    return dt.isoformat(), dt


def unit_label(sensor: dict) -> str:
    raw = sensor.get("ReadingUnit", "")
    if isinstance(raw, int):
        return UNIT_LABELS_INT.get(raw, str(raw))
    if isinstance(raw, str):
        return UNIT_LABELS_STR.get(raw, raw)
    return ""


def read_exact(handle: BinaryIO, size: int) -> bytes | None:
    data = handle.read(size)
    return data if len(data) == size else None


def read_block(handle: BinaryIO, validate_crc: bool) -> list[tuple[int, float, float]] | None:
    block_start = handle.tell()
    count_bytes = read_exact(handle, COUNT_STRUCT.size)
    if count_bytes is None:
        handle.seek(block_start)
        return None
    (count,) = COUNT_STRUCT.unpack(count_bytes)
    if count < 0 or count > 1_000_000:
        raise ValueError(f"invalid point count {count} at offset {block_start}")
    records_bytes = read_exact(handle, count * POINT_STRUCT.size)
    crc_bytes = read_exact(handle, CRC_STRUCT.size) if records_bytes is not None else None
    if records_bytes is None or crc_bytes is None:
        handle.seek(block_start)
        return None
    expected_crc = CRC_STRUCT.unpack(crc_bytes)[0]
    actual_crc = zlib.crc32(count_bytes + records_bytes) & 0xFFFFFFFF
    if validate_crc and expected_crc != actual_crc:
        raise ValueError(f"CRC mismatch at offset {block_start}")
    points: list[tuple[int, float, float]] = []
    offset = 0
    for _ in range(count):
        points.append(POINT_STRUCT.unpack_from(records_bytes, offset))
        offset += POINT_STRUCT.size
    return points


def csv_path_for_today() -> Path:
    return LOG_DIR / f"{datetime.date.today().isoformat()}_occt_bin.csv"


def open_csv(path: Path):
    new_file = not path.exists()
    f = open(path, "a", newline="", encoding="utf-8")
    w = csv.writer(f, lineterminator="\n")
    if new_file:
        w.writerow(["wall_time", "elapsed_seconds", "sensor_id", "sensor_name", "value", "unit"])
        f.flush()
    return f, w


def wait_for(path: Path, label: str) -> None:
    announced = False
    while not path.exists():
        if not announced:
            log(f"waiting for {label}: {path}")
            announced = True
        time.sleep(POLL_INTERVAL_SEC * 4)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-crc", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="print to stdout, no CSV/cursor write")
    args = ap.parse_args()

    validate_crc = not args.no_crc
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log(f"OCCT bin tail starting (state_dir={STATE_DIR}, dry_run={args.dry_run}, once={args.once})")

    wait_for(STATE_DIR, "OCCT State directory")
    sensors_path = STATE_DIR / "sensors.json"
    points_path = STATE_DIR / "sensorpoints.bin"
    schedule_path = STATE_DIR / "schedule_execution.json"
    wait_for(sensors_path, "sensors.json")
    wait_for(points_path, "sensorpoints.bin")

    cursor = load_cursor()
    started_iso, started_dt = parse_started(schedule_path)
    if (cursor.get("state_dir") == str(STATE_DIR)
            and cursor.get("started") == started_iso
            and started_iso is not None
            and cursor.get("position", 0) <= points_path.stat().st_size):
        position = cursor["position"]
        log(f"resuming from cursor: position={position}, started={started_iso}")
    else:
        position = points_path.stat().st_size
        log(f"new session (started={started_iso}); starting from end at position={position}")

    sensors_mtime: float | None = None
    sensors: dict[int, dict] = {}
    current_csv_date: str | None = None
    csv_file = None
    csv_writer = None

    try:
        while True:
            try:
                s_mtime = sensors_path.stat().st_mtime
                if s_mtime != sensors_mtime:
                    sensors = load_sensors(sensors_path)
                    sensors_mtime = s_mtime
                    log(f"loaded {len(sensors)} sensors from sensors.json")

                new_iso, new_dt = parse_started(schedule_path)
                if new_iso != started_iso:
                    log(f"session changed: {started_iso} -> {new_iso}")
                    started_iso, started_dt = new_iso, new_dt
                    position = 0

                size = points_path.stat().st_size
                if size < position:
                    log(f"file shrunk ({position} -> {size}); resetting cursor")
                    position = 0

                today = datetime.date.today().isoformat()
                if today != current_csv_date and not args.dry_run:
                    if csv_file:
                        csv_file.close()
                    target = csv_path_for_today()
                    csv_file, csv_writer = open_csv(target)
                    current_csv_date = today
                    log(f"writing to {target}")

                points_read = 0
                with points_path.open("rb") as handle:
                    handle.seek(position)
                    while True:
                        block_position = handle.tell()
                        try:
                            block = read_block(handle, validate_crc=validate_crc)
                        except ValueError as e:
                            log(f"parse error at {block_position}: {e}; skipping past")
                            position = handle.tell()
                            break
                        if block is None:
                            position = block_position
                            break
                        for sensor_id, elapsed_s, value in block:
                            sensor = sensors.get(sensor_id, {})
                            if started_dt is not None:
                                wall = (started_dt + datetime.timedelta(seconds=elapsed_s)).isoformat()
                            else:
                                wall = datetime.datetime.now(datetime.timezone.utc).isoformat()
                            row = [
                                wall,
                                f"{elapsed_s:.6f}",
                                sensor_id,
                                sensor.get("Name", f"Sensor {sensor_id}"),
                                f"{value:.12g}",
                                unit_label(sensor),
                            ]
                            if args.dry_run:
                                print(",".join(str(x) for x in row))
                            else:
                                csv_writer.writerow(row)
                            points_read += 1
                        position = handle.tell()
                if csv_file:
                    csv_file.flush()
                if points_read and not args.dry_run:
                    save_cursor(str(STATE_DIR), started_iso, position)

            except FileNotFoundError:
                log("file disappeared; waiting")
                time.sleep(POLL_INTERVAL_SEC * 4)
            except json.JSONDecodeError:
                time.sleep(POLL_INTERVAL_SEC)
            except Exception as e:
                log(f"unexpected error: {e}")
                time.sleep(POLL_INTERVAL_SEC * 4)

            if args.once:
                break
            time.sleep(POLL_INTERVAL_SEC)
    finally:
        if csv_file:
            csv_file.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
