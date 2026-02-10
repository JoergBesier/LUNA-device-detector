"""Domain models for the testbench."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RunMetadata:
    device_id: str
    diaper_type: str
    sensor_layout: str
    external_run_id: Optional[str] = None
    file_name: Optional[str] = None
    notes: Optional[str] = None
    start_ts: Optional[str] = None
    end_ts: Optional[str] = None
    sampling_interval_s: Optional[float] = None


@dataclass(frozen=True)
class ReadingSample:
    t_elapsed_s: float
    temp_c: Optional[float]
    rh_pct: Optional[float]
    timestamp: Optional[str] = None
    sensor_id: Optional[str] = None


@dataclass(frozen=True)
class LabelEvent:
    event_type: str
    event_time_s: float
    run_id: int
    event_ts: Optional[str] = None
    volume_ml: Optional[float] = None
    location_label: Optional[str] = None
    distance_cm: Optional[float] = None
    water_temp_c: Optional[float] = None
    confidence: Optional[float] = None
    source: Optional[str] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class RunRegistryEntry:
    external_run_id: str
    source_file: str
    source_row_number: int
    status: Optional[str] = None
    planned_or_recorded_ts: Optional[str] = None
    test_device: Optional[str] = None
    sensor_cap: Optional[str] = None
    diaper_type: Optional[str] = None
    test_protocol: Optional[str] = None
    findings_comments: Optional[str] = None
    test_result_ref: Optional[str] = None
    log_file_ref: Optional[str] = None
