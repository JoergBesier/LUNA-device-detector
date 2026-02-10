from __future__ import annotations

import pathlib

import pytest

from luna_tb.services.registry_import import RegistryImportError, import_run_registry
from luna_tb.storage.db import get_connection

pytestmark = pytest.mark.registry


def test_registry_import_csv(initialized_db: pathlib.Path, repo_root: pathlib.Path) -> None:
    csv_path = repo_root / "tests" / "data" / "run_registry_basic.csv"

    imported = import_run_registry(initialized_db, csv_path)
    assert imported == 2

    with get_connection(initialized_db) as conn:
        rows = conn.execute(
            "SELECT external_run_id, status, sensor_cap, log_file_ref FROM run_registry ORDER BY external_run_id"
        ).fetchall()

    assert len(rows) == 2
    assert rows[0]["external_run_id"] == "T20001"
    assert rows[0]["status"] == "Done"
    assert rows[0]["sensor_cap"] == "SC003"
    assert rows[0]["log_file_ref"] == "2026-02-03 13-37-48.log"


def test_registry_import_xlsx(initialized_db: pathlib.Path, repo_root: pathlib.Path) -> None:
    xlsx_path = repo_root / "data" / "reference" / "LUNAdevice_testResults.xlsx"

    imported = import_run_registry(initialized_db, xlsx_path, sheet_name="test runs")
    assert imported > 0

    with get_connection(initialized_db) as conn:
        row = conn.execute(
            "SELECT external_run_id, status, log_file_ref FROM run_registry WHERE external_run_id = ?",
            ("T00007",),
        ).fetchone()

    assert row is not None
    assert row["status"] == "Done"
    assert row["log_file_ref"] == "2026-02-03 13-37-48.log"


def test_registry_import_requires_runid(initialized_db: pathlib.Path, tmp_path: pathlib.Path) -> None:
    bad_csv = tmp_path / "bad_registry.csv"
    bad_csv.write_text("test status,log file\nDone,sample.log\n", encoding="utf-8")

    with pytest.raises(RegistryImportError, match="Missing required headers"):
        import_run_registry(initialized_db, bad_csv)
