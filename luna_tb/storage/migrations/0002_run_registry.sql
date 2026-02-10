-- Add run registry metadata import and linkage to ingested runs.

PRAGMA foreign_keys = ON;

ALTER TABLE runs ADD COLUMN external_run_id TEXT;

CREATE TABLE IF NOT EXISTS run_registry (
    registry_id INTEGER PRIMARY KEY,
    external_run_id TEXT NOT NULL UNIQUE,
    status TEXT,
    planned_or_recorded_ts TEXT,
    test_device TEXT,
    sensor_cap TEXT,
    diaper_type TEXT,
    test_protocol TEXT,
    findings_comments TEXT,
    test_result_ref TEXT,
    log_file_ref TEXT,
    source_file TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    run_id INTEGER,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_run_registry_log_file_ref_unique
ON run_registry(log_file_ref)
WHERE log_file_ref IS NOT NULL AND log_file_ref <> '';

CREATE INDEX IF NOT EXISTS idx_run_registry_status ON run_registry(status);
CREATE INDEX IF NOT EXISTS idx_run_registry_run_id ON run_registry(run_id);
CREATE INDEX IF NOT EXISTS idx_runs_external_run_id ON runs(external_run_id);
