# Implementation Plan (Draft)

This document tracks the initial build plan for the LUNA Algorithm Testbench.

## To-do

Latest automated test run:
- Status: PASS
- Summary: `9 passed, 0 failed`
- Executed: `2026-02-09 21:06` (local)
- HTML report: [pytest-20260209-210611.html](../test-results/pytest-20260209-210611.html)
- JUnit XML: [pytest-20260209-210611.xml](../test-results/pytest-20260209-210611.xml)
- Report history: [test-results](../test-results/)

Current data integration status:
- Persistent DB migrated to include `run_registry`: `data/luna.sqlite`.
- Lab registry imported from `data/reference/LUNAdevice_testResults.xlsx` (`test runs` tab).
- Existing ingested runs linked where `runs.file_name == TRIM(run_registry.log_file_ref)`.
- Notebook updated for registry inspection: `notebooks/run_data_overview.ipynb`.

1. Bootstrap project skeleton: package layout, CLI entrypoint, config loading, logging, and initial storage layer with schema + migrations.
   - Result: `luna_tb/` package tree created with CLI entrypoint (`luna-testbench`), config loader, logging setup, and SQLite storage layer with initial schema migration.
   - Testing: smoke CLI `db-init`; verify migrations apply and schema exists.
2. Implement canonical data store and ingest pipeline for lab logs, including run metadata and label import with lab addition fields.
   - Result: Added repositories + services for CSV/log ingest and label import, plus run registry import from `.xlsx/.csv` with CLI command `registry import`.
   - Result: Added strict linking during ingest (`log file` in `run_registry` must match incoming log filename; mismatch raises error).
   - Testing: unit tests for ingest + label import + registry import; validate required columns, DB inserts, upsert behavior, `.xlsx` parsing, and strict match error handling.
   - Reports: timestamped HTML/XML files in [test-results](../test-results/).
3. Add derivation + simulation services with deterministic seeds and provenance tracking.
   - Testing: unit tests for derived metrics and simulation determinism; verify provenance stored.
4. Define algorithm plugin interface and build the experiment runner (grid expansion, artifact output, result persistence).
   - Testing: contract tests for algorithm interface, grid expansion count checks, provenance fields.
5. Implement evaluation + reporting (metrics, comparisons, exports) and add regression tests with a small golden dataset.
   - Testing: regression tests against golden dataset; metric stability and output format checks.
