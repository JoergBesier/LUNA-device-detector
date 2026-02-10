-- Initial schema for LUNA Algorithm Testbench

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id INTEGER PRIMARY KEY,
    file_name TEXT,
    start_ts TEXT,
    end_ts TEXT,
    sampling_interval_s REAL,
    baseline_temp_c REAL,
    baseline_rh_pct REAL,
    baseline_vp_hpa REAL,
    baseline_ah_g_m3 REAL,
    baseline_n INTEGER,
    device_id TEXT NOT NULL,
    diaper_type TEXT NOT NULL,
    sensor_layout TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS readings (
    reading_id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL,
    timestamp TEXT,
    t_elapsed_s REAL NOT NULL,
    sensor_id TEXT,
    temp_c REAL,
    rh_pct REAL,
    vp_hpa REAL,
    ah_g_m3 REAL,
    load_vp_hpa REAL,
    load_ah_g_m3 REAL,
    is_addition INTEGER DEFAULT 0,
    addition_index INTEGER,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS labels (
    label_id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    event_time_s REAL NOT NULL,
    event_ts TEXT,
    volume_ml REAL,
    location_label TEXT,
    distance_cm REAL,
    water_temp_c REAL,
    confidence REAL,
    source TEXT,
    notes TEXT,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS simulations (
    sim_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    seed INTEGER,
    params_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS experiments (
    exp_id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL,
    description TEXT,
    git_commit TEXT,
    runner_version TEXT,
    seed INTEGER,
    algorithm_id TEXT NOT NULL,
    sim_id INTEGER,
    FOREIGN KEY (sim_id) REFERENCES simulations(sim_id)
);

CREATE TABLE IF NOT EXISTS results (
    result_id INTEGER PRIMARY KEY,
    exp_id INTEGER NOT NULL,
    run_id INTEGER NOT NULL,
    metrics_json TEXT,
    events_json TEXT,
    artifacts_path TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (exp_id) REFERENCES experiments(exp_id),
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_readings_run_id ON readings(run_id);
CREATE INDEX IF NOT EXISTS idx_readings_run_time ON readings(run_id, t_elapsed_s);
CREATE INDEX IF NOT EXISTS idx_labels_run_id ON labels(run_id);
CREATE INDEX IF NOT EXISTS idx_labels_run_time ON labels(run_id, event_time_s);
CREATE INDEX IF NOT EXISTS idx_results_exp_id ON results(exp_id);
CREATE INDEX IF NOT EXISTS idx_results_run_id ON results(run_id);
