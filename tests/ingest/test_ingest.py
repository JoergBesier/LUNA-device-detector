from __future__ import annotations

import pathlib
import re

import pytest

from luna_tb.services.ingest import IngestError, ingest_logs
from luna_tb.services.registry_import import import_run_registry
from luna_tb.storage.db import get_connection

pytestmark = pytest.mark.ingest


def _import_registry_for_log(
    db_path: pathlib.Path,
    tmp_path: pathlib.Path,
    *,
    run_id: str,
    log_file_name: str,
) -> None:
    registry_csv = tmp_path / "run_registry.csv"
    registry_csv.write_text(
        "runID,test status,timestamp,test device,sensor cap,diaper type,findings / comments,test protocol,test result,log file\n"
        f"{run_id},Done,2026-02-03 13:37,LD002,SC003,DT-TODI-001,,d=0cm,plot.png,{log_file_name}\n",
        encoding="utf-8",
    )
    import_run_registry(db_path, registry_csv)


def test_ingest_basic(initialized_db: pathlib.Path, repo_root: pathlib.Path, tmp_path: pathlib.Path) -> None:
    log_path = repo_root / "tests" / "data" / "log_basic.csv"
    _import_registry_for_log(initialized_db, tmp_path, run_id="T10000", log_file_name=log_path.name)

    run_ids = ingest_logs(
        initialized_db,
        [log_path],
        device_id="LUNA-001",
        diaper_type="infant",
        sensor_layout="front",
    )

    assert len(run_ids) == 1

    with get_connection(initialized_db) as conn:
        run = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_ids[0],)).fetchone()
        assert run is not None
        assert run["device_id"] == "LUNA-001"
        assert run["file_name"] == "log_basic.csv"
        assert run["sampling_interval_s"] is not None
        assert run["external_run_id"] == "T10000"

        linked = conn.execute(
            "SELECT run_id FROM run_registry WHERE external_run_id = ?",
            ("T10000",),
        ).fetchone()
        assert linked["run_id"] == run_ids[0]

        readings = conn.execute("SELECT COUNT(*) AS n FROM readings WHERE run_id = ?", (run_ids[0],)).fetchone()
        assert readings["n"] == 3


def test_ingest_missing_registry_entry_raises(
    initialized_db: pathlib.Path,
    repo_root: pathlib.Path,
) -> None:
    log_path = repo_root / "tests" / "data" / "log_basic.csv"

    with pytest.raises(IngestError, match="No run_registry entry matches log file"):
        ingest_logs(
            initialized_db,
            [log_path],
            device_id="LUNA-001",
            diaper_type="infant",
            sensor_layout="front",
        )


def test_ingest_missing_columns(initialized_db: pathlib.Path, tmp_path: pathlib.Path) -> None:
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("t_elapsed_s,temp_c\n0,25.0\n", encoding="utf-8")
    _import_registry_for_log(initialized_db, tmp_path, run_id="T10001", log_file_name=bad_csv.name)

    with pytest.raises(IngestError, match="Missing required columns"):
        ingest_logs(
            initialized_db,
            [bad_csv],
            device_id="LUNA-001",
            diaper_type="infant",
            sensor_layout="front",
        )


def test_ingest_device_log(initialized_db: pathlib.Path, repo_root: pathlib.Path, tmp_path: pathlib.Path) -> None:
    log_path = repo_root / "tests" / "data" / "2026-02-03 13-37-48.log"
    _import_registry_for_log(initialized_db, tmp_path, run_id="T10002", log_file_name=log_path.name)

    run_ids = ingest_logs(
        initialized_db,
        [log_path],
        device_id="LUNA-002",
        diaper_type="infant",
        sensor_layout="front",
    )

    assert len(run_ids) == 1

    pattern = re.compile(
        r"temp_humid_sample:\s*\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{1,2}:\d{1,2},\s*temp:\s*[0-9.]+,\s*humid:\s*[0-9.]+%"
    )
    expected = len(pattern.findall(log_path.read_text(encoding="utf-8", errors="ignore")))
    assert expected > 0

    with get_connection(initialized_db) as conn:
        readings = conn.execute(
            "SELECT COUNT(*) AS n FROM readings WHERE run_id = ?",
            (run_ids[0],),
        ).fetchone()
        assert readings["n"] == expected

        sample = conn.execute(
            "SELECT timestamp FROM readings WHERE run_id = ? ORDER BY t_elapsed_s LIMIT 1",
            (run_ids[0],),
        ).fetchone()
        assert sample["timestamp"] is not None
        assert sample["timestamp"].endswith(("+01:00", "+02:00", "+00:00"))
