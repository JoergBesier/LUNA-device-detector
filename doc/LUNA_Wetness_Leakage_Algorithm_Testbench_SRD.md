# LUNA Wetness / Leakage Algorithm Testbench — SRD

**Project name:** LUNA Algorithm Testbench  
**Owner:** Curaluna / LUNA team  
**Status:** Draft  
**Last updated:** 2026-02-09  
**Primary goal:** Compare wetness/leakage detection algorithms using replayed + simulated Temp/RH time series derived from real device logs.

---

## 1. Purpose and scope

### 1.1 Purpose
Build a program that:
- Extracts temperature and relative-humidity time series from real LUNA logs (1–N sensors).
- Derives physical moisture features (e.g., vapor pressure, absolute humidity, load).
- Generates simulated variants (noise/drift/delay/saturation/missing samples) for robustness testing.
- Runs multiple detection algorithms in a consistent experiment harness.
- Produces comparable metrics, plots, and reports.

### 1.2 Scope boundaries (non-goals)
- No clinical claims or medical outcome prediction (e.g., skin damage).
- No requirement to estimate absolute urine volume in milliliters (can be a future research track).
- No online service dependency required for core operation (offline-first).

---

## 2. Definitions

- **RH:** Relative Humidity (%)  
- **T:** Temperature (°C)  
- **e (vapor pressure):** Partial pressure of water vapor (hPa)  
- **AH (absolute humidity):** Water vapor mass per volume (g/m³)  
- **Load:** Baseline-corrected moisture proxy (e.g., AH − baseline_AH)  
- **Run:** One continuous test recording session (a time series).  
- **Label/Event:** Ground-truth timestamp(s) for known wetting actions (e.g., lab additions).  
- **Algorithm:** A detection method producing event timestamps + continuous estimates (e.g., load/headroom).

---

## 3. Stakeholders and users

- **Algorithm developer:** Implement/iterate detection strategies.
- **Firmware/devops:** Provide log formats, ensure reproducibility, run regression.
- **QA/product:** Validate behavior on standard datasets, compare versions.

---

## 4. System overview

### 4.1 High-level workflow
1. **Ingest** raw LUNA log files into a canonical dataset (SQLite/DuckDB).
2. **Derive** physical features (VP, AH, Load, etc.).
3. **Label** events (protocol markers or manual annotation).
4. **Simulate** variants (noise/drift/delay/saturation/missing data; multi-sensor scenarios).
5. **Run** algorithms across the dataset grid (algorithm params × simulation params).
6. **Evaluate** and generate reports (metrics + plots + artifacts).

### 4.2 Key outputs
- Ranked algorithm comparison summary.
- Per-run plots with overlays (signals, thresholds, states, detections).
- Exportable result tables (CSV/SQLite) and reproducible configs.

---

## 5. Functional requirements

### FR1 — Data ingestion
- Parse LUNA log formats to extract:
  - timestamp (device/RTC), elapsed time, sensor id (if available)
  - temperature, RH
- Support datasets with 1–4 sensors (future-proof).
- Store raw and cleaned readings.

**Acceptance criteria:**
- Given a set of log files, the tool builds a canonical DB with ≥ 99% correct sample parsing (excluding corrupted lines).

### FR2 — Derived measurements
Compute and store derived signals for each sample:
- vapor pressure (hPa)
- absolute humidity (g/m³)
- baseline(s) per run (e.g., first sample or pre-event window)
- load signals (AH-load and optionally VP-load)

**Acceptance criteria:**
- Derived values recompute deterministically given the same raw inputs and config.

### FR3 — Label/event management
- Import labels from:
  - protocol definitions (e.g., Add1/Add2/Add3)
  - manual edits (timestamp + metadata)
- Permit label corrections and versioning.

**Acceptance criteria:**
- Labels can be updated without rebuilding the entire dataset; changes are tracked.

### FR4 — Simulation engine
Generate simulated variants per run with configurable transforms:
- additive noise (RH domain and/or AH domain)
- temperature drift injection
- time delay (plume delay)
- saturation/clipping and sensor lag
- missing samples / jitter
- multi-sensor synthesis (second stream with different gain/delay/saturation)

**Acceptance criteria:**
- A simulation config produces the same output when the same random seed is used.

### FR5 — Algorithm plugin interface
Algorithms must implement a common interface:

**Input:**
- run dataframe (time series) including derived columns
- algorithm config (parameters)
- optional simulation metadata

**Output:**
- `events`: list of detected events: time, type, confidence, debug tags
- `signals`: continuous series (e.g., load, headroom, state)
- `diagnostics`: thresholds, internal stats, state transitions

**Acceptance criteria:**
- New algorithms can be added without modifying the core runner.

### FR6 — Experiment runner
- Run experiments over:
  - multiple runs
  - multiple simulation configs
  - multiple algorithm configs
- Track all parameters + git commit hash + seed.
- Save result artifacts per run (plots, JSON summaries).

**Acceptance criteria:**
- Re-running an experiment reproduces the same results (within floating point tolerance).

### FR7 — Evaluation and reporting
Metrics (minimum set):
- Event detection:
  - precision / recall / F1 (within time tolerance)
  - detection latency (distribution)
  - false positives per hour
- Load/headroom proxy stability:
  - monotonicity across step tests
  - “post-saturation usefulness” (does a second sensor preserve range?)
- Robustness:
  - metric degradation vs noise/drift/delay sweeps

Outputs:
- Summary tables + per-run drilldown views
- Export as CSV + store in DB

**Acceptance criteria:**
- Reports generated for a dataset in a single command.

### FR8 — Interactive inspection (optional but recommended)
- UI to:
  - select run, algorithm, simulation config
  - view overlays and state transitions
  - edit labels and re-run quickly

**Acceptance criteria:**
- A user can validate why an event was detected (or missed) within 2 minutes.

---

## 6. Non-functional requirements

- **Reproducibility:** deterministic runs with config + seed + code version.
- **Performance:** target ≥ 1,000 run-minutes processed per minute on a laptop for baseline algorithms.
- **Extensibility:** multi-sensor ready; easy to add columns, transforms, algorithms.
- **Offline-first:** core functionality works without network.
- **Transparency:** algorithm outputs include human-readable reasons/state changes.

---

## 7. Data model (SQLite, single file)

### 7.1 Tables
**runs**
- `run_id` (PK)
- metadata: file name, start/end timestamps, sampling interval
- baseline fields: `baseline_temp_c`, `baseline_rh_pct`, `baseline_vp_hpa`, `baseline_ah_g_m3`, `baseline_n`
- optional: diaper_type, sensor_layout, notes

**readings**
- `run_id` (FK)
- `timestamp`, `t_elapsed_s`, `sensor_id` (nullable)
- `temp_c`, `rh_pct`
- derived: `vp_hpa`, `ah_g_m3`, `load_vp_hpa`, `load_ah_g_m3`
- markers: `is_addition`, `addition_index`

**labels**
- `label_id` (PK)
- `run_id` (FK)
- `event_type` (e.g., WETTING, ADDITION, LEAK_OBSERVED)
- `event_time_s` (elapsed) + optional absolute timestamp
- `confidence`, `source`, `notes`

**simulations**
- `sim_id` (PK)
- `name`, `seed`, `params_json`

**experiments**
- `exp_id` (PK)
- `created_at`, `description`, `git_commit`, `runner_version`, `seed`
- links: `algorithm_id`, `sim_id`

**results**
- `exp_id` (FK), `run_id` (FK)
- `metrics_json`, `events_json`, `artifacts_path`

---

## 8. Proposed tech stack

### 8.1 Core stack (recommended)
- **Python 3.11+**
- **Polars** (fast dataframe) *or* Pandas (start simple)
- **NumPy**, optional **SciPy**
- **SQLite** for canonical DB (single file, easy sharing)  
  - optional later: **DuckDB** for faster analytics at scale
- **Matplotlib** for quick plots, **Plotly** for interactive plots

### 8.2 UI
- **Streamlit** for an interactive run/plot/label tool (fast to ship)
- Optional future: **FastAPI** + web frontend

### 8.3 Engineering hygiene
- **pytest** (tests), **ruff** (lint), **black** (format), optional **mypy**
- Packaging: **uv** or Poetry

**Rationale:** This is the shortest path to a useful, reproducible experiment harness that your team can iterate quickly.

---

## 9. CLI requirements

Provide a single entrypoint, e.g. `luna-testbench`:

- `ingest <logs...> --out dataset.sqlite`
- `derive --db dataset.sqlite`
- `label import --db dataset.sqlite --file labels.csv`
- `simulate --db dataset.sqlite --sim-config sim.yaml`
- `run --db dataset.sqlite --algo algo.yaml --sim sim.yaml --out results/`
- `report --db dataset.sqlite --exp <exp_id> --out report/`
- `ui --db dataset.sqlite`

---

## 10. Repository structure (suggested)

```text
luna-algo-testbench/
  docs/
    SRD.md
    datasets.md
    algorithms.md
  luna_tb/
    __init__.py
    ingest/
    derive/
    simulate/
    algorithms/
    eval/
    report/
    ui/
  scripts/
  tests/
  pyproject.toml
  README.md
```

---

## 11. Validation plan

- Unit tests for:
  - parsing + derived metrics
  - simulation transforms
  - algorithm interface contracts
- Regression suite:
  - a small “golden” dataset with pinned expected outputs
- Performance benchmark:
  - measure runtime per 10k samples per algorithm

---

## 12. Open questions / decisions

- Define leakage “ground truth” for calibration (visual leak, weight, cuff leak, etc.).
- Standardize sensor placement taxonomy (front/back/cuff) for multi-sensor experiments.
- Decide whether to store artifacts in DB (BLOB) or filesystem (paths in DB).
