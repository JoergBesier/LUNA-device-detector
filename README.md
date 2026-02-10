# LUNA Algorithm Testbench

Offline-first, reproducible testbench for wetness/leakage detection algorithms.

This repo is in early bootstrap phase.

## Quick Start (Bootstrap)

Initialize a database:

```bash
luna-testbench db-init --db data/luna.sqlite
```

Import run registry metadata first:

```bash
luna-testbench registry import --db data/luna.sqlite --file data/reference/LUNAdevice_testResults.xlsx --sheet "test runs"
```

Ingest lab log CSVs (required columns: `t_elapsed_s`, `temp_c`, `rh_pct`):

```bash
luna-testbench ingest --db data/luna.sqlite --device-id LUNA-001 --diaper-type infant --sensor-layout front logs/run1.csv
```

Import labels (required columns: `event_type`, `event_time_s`; include `run_id` or pass `--run-id`):

```bash
luna-testbench label import --db data/luna.sqlite --file labels.csv --run-id 1
```
