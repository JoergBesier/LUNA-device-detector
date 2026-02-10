"""Repository layer for storage access."""
from __future__ import annotations

import sqlite3
from typing import Iterable

from luna_tb.domain.models import LabelEvent, ReadingSample, RunMetadata, RunRegistryEntry


class RunRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create_run(self, metadata: RunMetadata) -> int:
        cursor = self._conn.execute(
            """
            INSERT INTO runs (
                external_run_id,
                file_name,
                start_ts,
                end_ts,
                sampling_interval_s,
                baseline_temp_c,
                baseline_rh_pct,
                baseline_vp_hpa,
                baseline_ah_g_m3,
                baseline_n,
                device_id,
                diaper_type,
                sensor_layout,
                notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metadata.external_run_id,
                metadata.file_name,
                metadata.start_ts,
                metadata.end_ts,
                metadata.sampling_interval_s,
                None,
                None,
                None,
                None,
                None,
                metadata.device_id,
                metadata.diaper_type,
                metadata.sensor_layout,
                metadata.notes,
            ),
        )
        return int(cursor.lastrowid)


class ReadingRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def insert_readings(self, run_id: int, readings: Iterable[ReadingSample]) -> None:
        rows = [
            (
                run_id,
                reading.timestamp,
                reading.t_elapsed_s,
                reading.sensor_id,
                reading.temp_c,
                reading.rh_pct,
            )
            for reading in readings
        ]
        self._conn.executemany(
            """
            INSERT INTO readings (
                run_id,
                timestamp,
                t_elapsed_s,
                sensor_id,
                temp_c,
                rh_pct
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


class LabelRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def insert_labels(self, labels: Iterable[LabelEvent]) -> None:
        rows = [
            (
                label.run_id,
                label.event_type,
                label.event_time_s,
                label.event_ts,
                label.volume_ml,
                label.location_label,
                label.distance_cm,
                label.water_temp_c,
                label.confidence,
                label.source,
                label.notes,
            )
            for label in labels
        ]
        self._conn.executemany(
            """
            INSERT INTO labels (
                run_id,
                event_type,
                event_time_s,
                event_ts,
                volume_ml,
                location_label,
                distance_cm,
                water_temp_c,
                confidence,
                source,
                notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )


class RunRegistryRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def upsert_entries(self, entries: Iterable[RunRegistryEntry]) -> int:
        rows = [
            (
                entry.external_run_id,
                entry.status,
                entry.planned_or_recorded_ts,
                entry.test_device,
                entry.sensor_cap,
                entry.diaper_type,
                entry.test_protocol,
                entry.findings_comments,
                entry.test_result_ref,
                entry.log_file_ref,
                entry.source_file,
                entry.source_row_number,
            )
            for entry in entries
        ]
        self._conn.executemany(
            """
            INSERT INTO run_registry (
                external_run_id,
                status,
                planned_or_recorded_ts,
                test_device,
                sensor_cap,
                diaper_type,
                test_protocol,
                findings_comments,
                test_result_ref,
                log_file_ref,
                source_file,
                source_row_number
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(external_run_id) DO UPDATE SET
                status = excluded.status,
                planned_or_recorded_ts = excluded.planned_or_recorded_ts,
                test_device = excluded.test_device,
                sensor_cap = excluded.sensor_cap,
                diaper_type = excluded.diaper_type,
                test_protocol = excluded.test_protocol,
                findings_comments = excluded.findings_comments,
                test_result_ref = excluded.test_result_ref,
                log_file_ref = excluded.log_file_ref,
                source_file = excluded.source_file,
                source_row_number = excluded.source_row_number
            """,
            rows,
        )
        return len(rows)

    def find_by_log_file_ref(self, log_file_name: str) -> sqlite3.Row | None:
        return self._conn.execute(
            """
            SELECT *
            FROM run_registry
            WHERE TRIM(log_file_ref) = ?
            """,
            (log_file_name,),
        ).fetchone()

    def attach_run(self, registry_id: int, run_id: int) -> None:
        self._conn.execute(
            "UPDATE run_registry SET run_id = ? WHERE registry_id = ?;",
            (run_id, registry_id),
        )
