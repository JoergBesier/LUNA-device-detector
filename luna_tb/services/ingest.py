"""Ingest service for lab log files."""
from __future__ import annotations

import csv
import datetime as dt
import logging
import pathlib
import re
from typing import Iterable, Optional

from luna_tb.domain.models import ReadingSample, RunMetadata
from luna_tb.storage.db import get_connection
from luna_tb.storage.repositories import ReadingRepository, RunRegistryRepository, RunRepository

LOGGER = logging.getLogger(__name__)
_TEMP_HUMID_PATTERN = re.compile(
    r"temp_humid_sample:\s*"
    r"(\d{4})-(\d{1,2})-(\d{1,2})\s+"
    r"(\d{1,2}):(\d{1,2}):(\d{1,2}),\s*"
    r"temp:\s*([0-9.]+),\s*humid:\s*([0-9.]+)%",
)
_TZ_PAREN_PATTERN = re.compile(r"tz\(([+-]?\d+)\)")
_TZ_CCLK_PATTERN = re.compile(r'\+CCLK:\s*"\d{2}/\d{2}/\d{2},\d{2}:\d{2}:\d{2}([+-]\d{2})"')


class IngestError(RuntimeError):
    """Raised when ingestion fails."""


def ingest_logs(
    db_path: str | pathlib.Path,
    log_paths: Iterable[str | pathlib.Path],
    *,
    device_id: str,
    diaper_type: str,
    sensor_layout: str,
    run_notes: Optional[str] = None,
    default_tz: str = "Europe/Berlin",
) -> list[int]:
    """Ingest one or more log files and return created run IDs."""
    run_ids: list[int] = []
    with get_connection(db_path) as conn:
        run_repo = RunRepository(conn)
        reading_repo = ReadingRepository(conn)

        for log_path in log_paths:
            path_obj = pathlib.Path(log_path)
            registry_repo = RunRegistryRepository(conn)
            registry_entry = registry_repo.find_by_log_file_ref(path_obj.name)
            if registry_entry is None:
                raise IngestError(
                    "No run_registry entry matches log file "
                    f"'{path_obj.name}'. Import/update the registry source first."
                )
            if registry_entry["run_id"] is not None:
                raise IngestError(
                    f"run_registry entry for '{path_obj.name}' is already linked to run_id="
                    f"{registry_entry['run_id']}"
                )

            readings = _parse_log_file(path_obj, default_tz=default_tz)
            if not readings:
                raise IngestError(f"No readings parsed from {path_obj}")

            start_ts = readings[0].timestamp
            end_ts = readings[-1].timestamp
            sampling_interval_s = _estimate_sampling_interval(readings)

            metadata = RunMetadata(
                device_id=device_id,
                diaper_type=diaper_type,
                sensor_layout=sensor_layout,
                external_run_id=registry_entry["external_run_id"],
                file_name=path_obj.name,
                notes=run_notes,
                start_ts=start_ts,
                end_ts=end_ts,
                sampling_interval_s=sampling_interval_s,
            )
            run_id = run_repo.create_run(metadata)
            reading_repo.insert_readings(run_id, readings)
            registry_repo.attach_run(registry_entry["registry_id"], run_id)
            conn.commit()
            run_ids.append(run_id)
            LOGGER.info("Ingested %s as run_id=%s (%s readings)", path_obj, run_id, len(readings))

    return run_ids


def _parse_log_file(path: pathlib.Path, *, default_tz: str) -> list[ReadingSample]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _parse_csv_log(path, default_tz=default_tz)
    if suffix == ".log":
        return _parse_device_log(path, default_tz=default_tz)
    raise IngestError(f"Unsupported log format: {path.suffix}")


def _parse_csv_log(path: pathlib.Path, *, default_tz: str) -> list[ReadingSample]:
    if not path.exists():
        raise IngestError(f"Log path does not exist: {path}")

    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise IngestError(f"Missing header row in {path}")

        required = {"t_elapsed_s", "temp_c", "rh_pct"}
        missing = required.difference({name.strip() for name in reader.fieldnames})
        if missing:
            raise IngestError(f"Missing required columns {sorted(missing)} in {path}")

        readings: list[ReadingSample] = []
        for row in reader:
            timestamp = _normalize_timestamp(
                _empty_to_none(row.get("timestamp")),
                default_tz=default_tz,
                path=path,
            )
            readings.append(
                ReadingSample(
                    t_elapsed_s=_to_float(row.get("t_elapsed_s"), "t_elapsed_s", path),
                    temp_c=_to_float(row.get("temp_c"), "temp_c", path, allow_empty=True),
                    rh_pct=_to_float(row.get("rh_pct"), "rh_pct", path, allow_empty=True),
                    timestamp=timestamp,
                    sensor_id=_empty_to_none(row.get("sensor_id")),
                )
            )

    readings.sort(key=lambda sample: sample.t_elapsed_s)
    return readings


def _parse_device_log(path: pathlib.Path, *, default_tz: str) -> list[ReadingSample]:
    if not path.exists():
        raise IngestError(f"Log path does not exist: {path}")

    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    tzinfo = _detect_tzinfo(lines, default_tz=default_tz)

    readings: list[ReadingSample] = []
    base_dt: Optional[dt.datetime] = None

    for line in lines:
        match = _TEMP_HUMID_PATTERN.search(line)
        if not match:
            continue

        year, month, day, hour, minute, second, temp, humid = match.groups()
        sample_dt = dt.datetime(
            int(year),
            int(month),
            int(day),
            int(hour),
            int(minute),
            int(second),
            tzinfo=tzinfo,
        )
        if base_dt is None:
            base_dt = sample_dt

        readings.append(
            ReadingSample(
                t_elapsed_s=(sample_dt - base_dt).total_seconds(),
                temp_c=float(temp),
                rh_pct=float(humid),
                timestamp=sample_dt.isoformat(),
                sensor_id=None,
            )
        )

    readings.sort(key=lambda sample: sample.t_elapsed_s)
    return readings


def _estimate_sampling_interval(readings: list[ReadingSample]) -> Optional[float]:
    if len(readings) < 2:
        return None

    deltas = [
        readings[i + 1].t_elapsed_s - readings[i].t_elapsed_s
        for i in range(len(readings) - 1)
        if readings[i + 1].t_elapsed_s >= readings[i].t_elapsed_s
    ]
    if not deltas:
        return None
    return sum(deltas) / len(deltas)


def _empty_to_none(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_timestamp(
    value: Optional[str],
    *,
    default_tz: str,
    path: pathlib.Path,
) -> Optional[str]:
    if value is None:
        return None
    try:
        if value.endswith("Z"):
            dt_value = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            dt_value = dt.datetime.fromisoformat(value)
    except ValueError as exc:
        raise IngestError(f"Invalid timestamp '{value}' in {path}") from exc

    if dt_value.tzinfo is None:
        dt_value = dt_value.replace(tzinfo=_tz_from_name(default_tz))
    return dt_value.isoformat()


def _detect_tzinfo(lines: list[str], *, default_tz: str) -> dt.tzinfo:
    for line in lines:
        match = _TZ_PAREN_PATTERN.search(line)
        if match:
            return _tz_from_quarters(int(match.group(1)))
        match = _TZ_CCLK_PATTERN.search(line)
        if match:
            return _tz_from_quarters(int(match.group(1)))

    return _tz_from_name(default_tz)


def _tz_from_quarters(value: int) -> dt.tzinfo:
    return dt.timezone(dt.timedelta(minutes=value * 15))


def _tz_from_name(name: str) -> dt.tzinfo:
    try:
        from zoneinfo import ZoneInfo
    except ImportError as exc:
        raise IngestError("ZoneInfo not available; use Python 3.11+") from exc

    try:
        return ZoneInfo(name)
    except Exception as exc:  # noqa: BLE001
        raise IngestError(f"Unknown timezone: {name}") from exc


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
        raise IngestError(f"Missing {field} value in {path}")
    stripped = value.strip()
    if not stripped:
        if allow_empty:
            return None
        raise IngestError(f"Empty {field} value in {path}")
    try:
        return float(stripped)
    except ValueError as exc:
        raise IngestError(f"Invalid {field} value '{value}' in {path}") from exc
