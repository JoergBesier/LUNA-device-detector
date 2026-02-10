# LUNA Algorithm Testbench — Software Design (Option B)

**Status:** Draft  
**Last updated:** 2026-02-09  
**Scope:** Defines the software architecture and must-have elements for the LUNA algorithm testbench, following the Domain + Services structure.

---

## 1. Goals

- Provide a reproducible, offline-first experiment harness for wetness/leakage detection algorithms.
- Support multiple log sources (lab logs today; narrowband IoT cloud logs in the future).
- Support lab run metadata ingestion from spreadsheet-based run tracking (`test runs` tab).
- Enable consistent comparisons across algorithms, simulation configs, and datasets.
- Experiments should determine the best algorithm that detects most of the wetting events correctly

## 2. Non-goals

- No clinical claims or medical outcome predictions.
- No production cloud service required for core operation.

---

## 3. Architecture Summary (Option B)

**Option A (Monolithic pipeline):** Single Python package with a linear, script-driven pipeline where ingestion, derivation, simulation, evaluation, and reporting live in one module tree. Data is passed as in-memory dataframes and persisted ad-hoc (CSV/Parquet/SQLite) by each stage. Fast to prototype, but coupling grows quickly, interfaces drift, and reproducibility/traceability require manual discipline.

**Option B (Domain + Services):** Explicit domain model with dedicated services and repositories, backed by a canonical store and plugin APIs.

**Motivation for Option B:** The testbench needs repeatability, auditable lineage, and easy extension across new sensors/algorithms. Separating domain rules from orchestration makes pipelines deterministic and testable, while a shared store enforces provenance and simplifies regression checks as the log volume and algorithm count scale.


**Pattern:** Domain + Services + Storage + Algorithms + Reporting.

```
luna_tb/
  domain/          # core types and invariants
  services/        # ingest, derive, simulate, experiment orchestration
  storage/         # SQLite/DuckDB repositories + migrations
  algorithms/      # plugin API + implementations
  reporting/       # metrics, plots, exports
  cli/             # command-line orchestration
```

---

## 4. Canonical Data Store

**Primary store:** SQLite (single file, portable).  
**Future option:** DuckDB for analytics at scale.

**Baseline schema (from SRD):**
- `runs`
- `run_registry`
- `readings`
- `labels`
- `simulations`
- `experiments`
- `results`

**Design notes:**
- Storage layer owns schema and migrations (explicit versioning).
- Repositories provide typed read/write methods (no SQL in services).
- All derived data is stored with provenance (config hash + seed).
- Runs must capture `device_id`, `diaper_type`, and `sensor_layout`.
- Lab addition labels must capture `volume_ml`, `location_label`, `distance_cm`, and `water_temp_c`.
- `run_registry` stores planning/execution metadata imported from lab sheets and links to `runs` when log files are available.

---

## 5. Domain Model (core types)

Minimal set to start:
- `Run`, `Reading`, `Label`, `Simulation`, `Experiment`, `Result`
- `RunRegistryEntry`
- `AlgorithmSpec`, `AlgorithmConfig`, `SimulationConfig`
- `MetricSet`, `Artifact`

Domain rules:
- Runs are immutable once ingested (edits create new run or revision).
- Registry entries are upserted by external run identifier (`runID`) and preserve source-row provenance.
- Derived metrics are recomputed deterministically from raw readings + config.
- Simulations are pure transforms with seed control.
- `Run` requires `device_id`, `diaper_type`, and `sensor_layout`.
- `Label` for lab additions includes `volume_ml`, `location_label`, `distance_cm`, `water_temp_c`.

---

## 6. Services (must-have)

### 6.1 Ingest Service
- Supports lab log format now; extendable for IoT/cloud logs later.
- Normalizes timestamps and sensor metadata.
- Writes to `runs` + `readings`.
- Requires run metadata: device id, diaper type, sensor layout.
- Optionally links ingested log to `run_registry` by matching `log_file_ref` and/or external run id.

### 6.1b Run Registry Import Service
- Imports spreadsheet metadata from `test runs` tab (`.xlsx` and `.csv` export).
- Upserts `run_registry` by `external_run_id` (`runID`).
- Normalizes timestamps and trims string fields.
- Captures source provenance (`source_file`, `source_row_number`).
- Leaves rows without log references in registry-only state (no `run_id` link yet).
- Applies field mapping:
  - `runID` -> `external_run_id`
  - `test status` -> `status`
  - `timestamp` -> `planned_or_recorded_ts`
  - `test device` -> `test_device`
  - `sensor cap` -> `sensor_cap`
  - `diaper type` -> `diaper_type`
  - `findings / comments` -> `findings_comments`
  - `test protocol` -> `test_protocol`
  - `test result` -> `test_result_ref`
  - `log file` -> `log_file_ref`

### 6.2 Derive Service
- Computes VP, AH, load, baselines.
- Stores derived columns on `readings`.
- Deterministic for a given config.

### 6.3 Label Service
- Imports protocol events or manual labels.
- Supports edits with versioning.
- Captures lab addition metadata (volume, location, distance to sensor, water temperature).

### 6.4 Simulation Service
- Applies transforms: noise, drift, delay, saturation, missing data.
- Deterministic with seed.
- Stores outputs and metadata as a simulation run.

### 6.5 Experiment Service
- Expands grid: runs × simulations × algorithm configs.
- Tracks git hash, seed, config, and outputs.
- Writes `experiments` + `results` + artifacts.

---

## 7. Algorithm Plugin Interface

**Input:**
- dataframe for a run (raw + derived columns)
- algorithm config
- simulation metadata

**Output:**
- `events`: time, type, confidence, tags
- `signals`: time series (load, headroom, state)
- `diagnostics`: thresholds, state transitions, stats

**Design notes:**
- New algorithms can be added without modifying core runner.
- All outputs must be JSON-serializable.

---

## 8. Evaluation and Comparison

### 8.1 Metrics (minimum set)
- precision / recall / F1 (time tolerance)
- detection latency
- false positives per hour
- robustness vs noise/drift/delay sweeps

### 8.2 Comparison
- Per-experiment summary tables.
- Cross-experiment comparison (same dataset + different algorithms).
- Ranking and regression diffs vs baseline.

---

## 9. Ingestion Sources

**Current:** Lab log files.  
**Current (metadata):** Lab run registry spreadsheet (`test runs` tab, maintained by lab staff).  
**Reference snapshot in repo:** `data/reference/LUNAdevice_testResults.xlsx`  
**Planned:** Narrowband IoT cloud logs (additional parser + normalizer).

Design expectation:
- Add parsers under `services/ingest` / `services/registry_import` without changing core service contracts.
- Keep a consistent canonical record format.
- Keep spreadsheet import offline-first by ingesting local `.xlsx`/`.csv` exports.

---

## 10. CLI and UX

Single entrypoint with subcommands:
- `registry import`, `ingest`, `derive`, `label`, `simulate`, `run`, `report`, `ui`

CLI orchestrates services; services do not call CLI.

---

## 11. Artifacts and Reporting

Artifacts stored as files with stable paths; DB holds references.
- Plots per run
- JSON summaries
- CSV exports

---

## 12. Testing and Validation

- Unit tests: parsing, derived metrics, simulation transforms.
- Regression tests: golden dataset + pinned outputs.
- Performance checks: runtime per 10k samples per algorithm.

---

## 13. Open Decisions

- Leakage ground truth definition for evaluation.
- Storage of artifacts: filesystem only vs optional DB BLOBs.
- Whether to add dataset versioning beyond run-level immutability.
- Spreadsheet import cadence and ownership (manual export/import vs scheduled sync in a future hosted deployment).
