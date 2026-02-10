"""Label import service for CSV label files."""
from __future__ import annotations

import csv
import logging
import pathlib
from typing import Iterable, Optional

from luna_tb.domain.models import LabelEvent
from luna_tb.storage.db import get_connection
from luna_tb.storage.repositories import LabelRepository

LOGGER = logging.getLogger(__name__)


class LabelImportError(RuntimeError):
    """Raised when label import fails."""


def import_labels_csv(
    db_path: str | pathlib.Path,
    label_path: str | pathlib.Path,
    *,
    run_id: Optional[int] = None,
) -> int:
    """Import labels from a CSV file into the database.

    If the CSV includes a run_id column, it is used per row.
    Otherwise, a run_id argument is required.
    """
    path_obj = pathlib.Path(label_path)
    labels = _parse_labels_csv(path_obj, run_id=run_id)
    if not labels:
        raise LabelImportError(f"No labels parsed from {path_obj}")

    with get_connection(db_path) as conn:
        repo = LabelRepository(conn)
        repo.insert_labels(labels)
        conn.commit()

    LOGGER.info("Imported %s labels from %s", len(labels), path_obj)
    return len(labels)


def _parse_labels_csv(path: pathlib.Path, *, run_id: Optional[int]) -> list[LabelEvent]:
    if not path.exists():
        raise LabelImportError(f"Label path does not exist: {path}")

    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise LabelImportError(f"Missing header row in {path}")

        fieldnames = {name.strip() for name in reader.fieldnames}
        if "event_type" not in fieldnames or "event_time_s" not in fieldnames:
            raise LabelImportError(
                "CSV requires event_type and event_time_s columns"
            )

        labels: list[LabelEvent] = []
        for row in reader:
            row_run_id = _to_int(row.get("run_id")) if "run_id" in fieldnames else None
            effective_run_id = row_run_id if row_run_id is not None else run_id
            if effective_run_id is None:
                raise LabelImportError(
                    "run_id missing: supply --run-id or include run_id column"
                )

            labels.append(
                LabelEvent(
                    run_id=effective_run_id,
                    event_type=_required_str(row.get("event_type"), "event_type", path),
                    event_time_s=_to_float(row.get("event_time_s"), "event_time_s", path),
                    event_ts=_empty_to_none(row.get("event_ts")),
                    volume_ml=_to_float(row.get("volume_ml"), "volume_ml", path, allow_empty=True),
                    location_label=_empty_to_none(row.get("location_label")),
                    distance_cm=_to_float(row.get("distance_cm"), "distance_cm", path, allow_empty=True),
                    water_temp_c=_to_float(row.get("water_temp_c"), "water_temp_c", path, allow_empty=True),
                    confidence=_to_float(row.get("confidence"), "confidence", path, allow_empty=True),
                    source=_empty_to_none(row.get("source")),
                    notes=_empty_to_none(row.get("notes")),
                )
            )

    return labels


def _required_str(value: Optional[str], field: str, path: pathlib.Path) -> str:
    if value is None:
        raise LabelImportError(f"Missing {field} value in {path}")
    stripped = value.strip()
    if not stripped:
        raise LabelImportError(f"Empty {field} value in {path}")
    return stripped


def _empty_to_none(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _to_float(
    value: Optional[str],
    field: str,
    path: pathlib.Path,
    *,
    allow_empty: bool = False,
) -> Optional[float]:
    if value is None:
        if allow_empty:
            return None
        raise LabelImportError(f"Missing {field} value in {path}")
    stripped = value.strip()
    if not stripped:
        if allow_empty:
            return None
        raise LabelImportError(f"Empty {field} value in {path}")
    try:
        return float(stripped)
    except ValueError as exc:
        raise LabelImportError(f"Invalid {field} value '{value}' in {path}") from exc


def _to_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError as exc:
        raise LabelImportError(f"Invalid run_id value '{value}'") from exc
