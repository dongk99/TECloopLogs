# OCCT per-component logger pipeline

A single self-contained script that decodes OCCT's binary sensor stream into clean,
significant-figure-capped, per-component daily CSVs, with the CPU coolant-loop
temperature joined in. Verified live against a running OCCT session.

---

## Key files & directories

| Path | Role |
|---|---|
| `D:\occt_history\occt_logger.py` | **The logger** — self-contained, 1045 lines. Everything below runs from here. |
| `D:\occt_history\occt_logger_startup.bat` | Boot launcher (runs the script via Python 3.11). |
| `…\Start Menu\Programs\Startup\occt_logger.lnk` | Auto-starts the logger at login. |
| `D:\occt_history\<COMP>_DATA\<COMP>_MMDDYYYY.csv` | **Output.** One folder + daily file per component: `CPU_DATA`, `GPU_DATA`, `RAM_DATA`, `STORAGE_DATA`, `MB_DATA`. |
| `D:\occt_history\.occt_logger_selection.json` | Remembers the last component selection (for the 15 s auto-proceed). |
| `C:\Users\dongk\.claude\plans\eager-booping-moth.md` | Implementation plan (constraints + runtime workflow). |

**Data sources (read-only):**
- OCCT State dir `…\AppData\Local\Temp\OCCT\State\` — `sensorpoints.bin` (binary sensor stream), `sensors.json` (id → name / class / device / unit), `schedule_execution.json` (session `Started`, UTC).
- `C:\Users\dongk\Desktop\Peltierlog\peltier.log` — PuTTY capture of the TEC coolant-loop temperature.

---

## What the script does (runtime workflow)

**Phase 0 — launch:** opens a settings window (Tkinter), loads the saved component selection.

**Phase 1 — detect + gate:** polls `sensorpoints.bin` size. Logging does not start until the bin is **growing** AND a component is selected. Shows `OCCT Monitoring only not detected` while the bin is static. Auto-proceeds with the saved selection 15 s after OCCT is detected.

**Phase 2 — metadata:** loads `sensors.json`; builds short column labels; restricts to the sensors of the **selected** component(s) (`DeviceType` → CPU / GPU / RAM / STORAGE / MB).

**Phase 3 — logging loop:** tails the bin (CRC32-validated blocks; `open_shared_rb` handles the file-share lock while OCCT writes it), stamps each point as `started_utc + elapsed`, groups into **0.5 s windows averaged per sensor**, formats each value at its **sig-fig rule**, and appends one wide row per window to the selected components' daily CSVs (new file each UTC day).

**Coolant feed (parallel):** tails `peltier.log`, stamps each new line with the **PC clock-time when it is read**, and writes the nearest reading (±4 s) into a `coolant_c` column on the **CPU** file. Blank when PuTTY is silent — never fabricated.

### Sig-fig rules
voltage 4 · power 5 · current 5 · fan RPM 4 · clock (MHz) 6 · percentages 4 · RAM-usage (MB) 6 · memory timings 2 (3 for tRC/tRFC) · everything else incl. temperature 6 max. (`round_sig` formats to N significant figures, no scientific notation.)

### Run modes
- **No args** → GUI (the normal / boot path).
- `--components CPU GPU …` → headless; logs those components, no window.
- `--replay <session>` → offline self-test: replays a session from a reference DB snapshot and checks the windowed, rounded core temps match the reference (windowing + rounding parity).

---

## Coolant ↔ OCCT time alignment

The OCCT and peltier devices are **two free-running clocks with no shared sync signal.** The peltier device's elapsed counter drifts (~90 s over 6 h vs the PC clock, measured), so the script does **not** align by either device's elapsed time. It aligns by the only shared clock — **real PC wall-clock at capture**: each coolant line is stamped with the PC time it is read; OCCT windows are on the PC clock too (verified: they track the wall clock within the ~2 s window-close lag). This gives alignment to ~**1–2 s** — the precision floor for un-synced clocks, well under how fast the coolant loop moves. Tighter would require a hardware-timestamped coolant sensor.

---

## Verification (live + offline)
- **Decode:** native CRC-validated decode of a real bin — 481,797 points, **0 CRC errors**.
- **Transform parity:** `--replay` of a 1135-window session — **9080/9080** core-temp values matched the reference after rounding.
- **Live:** ran against active OCCT — all 5 component files written, sub-ambient core temps captured, `coolant_c` populated via the PC-clock join.

---

## Caveats
- **Coolant alignment** is bounded to ~1–2 s by the two un-synced clocks (precision floor); a hardware-timestamped sensor would tighten it.
- **Coolant backlog edge:** if the logger stalls and catches up, a burst of coolant lines read in one poll all get stamped "now," so their alignment degrades for that burst. Fine in steady state.
