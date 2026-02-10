from __future__ import annotations

import pathlib

import pytest

from luna_tb.domain.models import RunMetadata
from luna_tb.services.label_import import LabelImportError, import_labels_csv
from luna_tb.storage.repositories import RunRepository
from luna_tb.storage.db import get_connection

pytestmark = pytest.mark.labels


def test_label_import_basic(initialized_db: pathlib.Path, repo_root: pathlib.Path) -> None:
    labels_path = repo_root / "tests" / "data" / "labels_basic.csv"

    with get_connection(initialized_db) as conn:
        run_id = RunRepository(conn).create_run(
            RunMetadata(
                device_id="LUNA-001",
                diaper_type="infant",
                sensor_layout="front",
            )
        )
        conn.commit()

    count = import_labels_csv(initialized_db, labels_path, run_id=run_id)
    assert count == 2

    with get_connection(initialized_db) as conn:
        labels = conn.execute(
            "SELECT COUNT(*) AS n FROM labels WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        assert labels["n"] == 2


def test_label_import_requires_run_id(initialized_db: pathlib.Path, tmp_path: pathlib.Path) -> None:
    bad_labels = tmp_path / "labels.csv"
    bad_labels.write_text("event_type,event_time_s\nADDITION,1.0\n", encoding="utf-8")

    with pytest.raises(LabelImportError, match="run_id missing"):
        import_labels_csv(initialized_db, bad_labels)
