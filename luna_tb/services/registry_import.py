"""Run registry import service for lab tracking sheets."""
from __future__ import annotations

import csv
import datetime as dt
import pathlib
import re
import xml.etree.ElementTree as ET
import zipfile
from typing import Any

from luna_tb.domain.models import RunRegistryEntry
from luna_tb.storage.db import get_connection
from luna_tb.storage.repositories import RunRegistryRepository


class RegistryImportError(RuntimeError):
    """Raised when run registry import fails."""


_COLUMN_MAP = {
    "runid": "external_run_id",
    "test status": "status",
    "timestamp": "planned_or_recorded_ts",
    "test device": "test_device",
    "sensor cap": "sensor_cap",
    "diaper type": "diaper_type",
    "findings / comments": "findings_comments",
    "test protocol": "test_protocol",
    "test result": "test_result_ref",
    "log file": "log_file_ref",
}


def import_run_registry(
    db_path: str | pathlib.Path,
    file_path: str | pathlib.Path,
    *,
    sheet_name: str = "test runs",
    default_tz: str = "Europe/Berlin",
) -> int:
    """Import registry rows from a spreadsheet export and upsert by external run id."""
    path_obj = pathlib.Path(file_path)
    suffix = path_obj.suffix.lower()
    if suffix == ".csv":
        entries = _parse_registry_csv(path_obj, default_tz=default_tz)
    elif suffix == ".xlsx":
        entries = _parse_registry_xlsx(path_obj, sheet_name=sheet_name, default_tz=default_tz)
    else:
        raise RegistryImportError(f"Unsupported registry format: {path_obj.suffix}")

    if not entries:
        raise RegistryImportError(f"No registry rows found in {path_obj}")

    with get_connection(db_path) as conn:
        repo = RunRegistryRepository(conn)
        count = repo.upsert_entries(entries)
        conn.commit()
        return count


def _parse_registry_csv(path: pathlib.Path, *, default_tz: str) -> list[RunRegistryEntry]:
    if not path.exists():
        raise RegistryImportError(f"Registry file does not exist: {path}")

    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise RegistryImportError(f"Missing header row in {path}")

        normalized = {_normalize_header(h): h for h in reader.fieldnames if h is not None}
        _validate_required_headers(normalized)

        entries: list[RunRegistryEntry] = []
        for idx, row in enumerate(reader, start=2):
            mapped = _map_row(row, normalized, path, idx, default_tz=default_tz)
            if mapped is not None:
                entries.append(mapped)

    return entries


def _parse_registry_xlsx(
    path: pathlib.Path,
    *,
    sheet_name: str,
    default_tz: str,
) -> list[RunRegistryEntry]:
    if not path.exists():
        raise RegistryImportError(f"Registry file does not exist: {path}")

    ns = {
        "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    }

    with zipfile.ZipFile(path) as zf:
        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rel_by_id = {node.attrib["Id"]: node.attrib["Target"] for node in rels.findall("rel:Relationship", ns)}

        shared_strings = _load_shared_strings(zf, ns)

        target_sheet = None
        normalized_target = _normalize_sheet_name(sheet_name)
        for sheet in workbook.findall("main:sheets/main:sheet", ns):
            name = sheet.attrib["name"]
            if _normalize_sheet_name(name) != normalized_target:
                continue

            rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = rel_by_id[rel_id]
            target_sheet = target if target.startswith("xl/") else f"xl/{target}"
            break

        if target_sheet is None:
            raise RegistryImportError(f"Sheet '{sheet_name}' not found in {path}")

        ws = ET.fromstring(zf.read(target_sheet))

        row_values: list[list[str]] = []
        for row in ws.findall("main:sheetData/main:row", ns):
            row_cells: dict[int, str] = {}
            max_col = 0
            for cell in row.findall("main:c", ns):
                ref = cell.attrib.get("r")
                if not ref:
                    continue
                col = _column_index(ref)
                max_col = max(max_col, col)
                row_cells[col] = _xlsx_cell_value(cell, ns, shared_strings)

            values = [row_cells.get(i, "") for i in range(1, max_col + 1)]
            row_values.append(values)

    if not row_values:
        return []

    headers = row_values[0]
    normalized = {_normalize_header(h): h for h in headers if h}
    _validate_required_headers(normalized)

    header_to_pos = {h: i for i, h in enumerate(headers)}

    entries: list[RunRegistryEntry] = []
    for row_num, values in enumerate(row_values[1:], start=2):
        row_dict = {
            header: values[pos] if pos < len(values) else ""
            for header, pos in header_to_pos.items()
        }
        mapped = _map_row(row_dict, normalized, path, row_num, default_tz=default_tz)
        if mapped is not None:
            entries.append(mapped)

    return entries


def _load_shared_strings(zf: zipfile.ZipFile, ns: dict[str, str]) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []

    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for si in root.findall("main:si", ns):
        text = "".join(node.text or "" for node in si.findall(".//main:t", ns))
        values.append(text)
    return values


def _xlsx_cell_value(cell: ET.Element, ns: dict[str, str], shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    value_node = cell.find("main:v", ns)
    if value_node is None:
        inline = cell.find("main:is/main:t", ns)
        return (inline.text or "") if inline is not None else ""

    raw = value_node.text or ""
    if cell_type == "s":
        try:
            return shared_strings[int(raw)]
        except Exception:
            return raw
    return raw


def _column_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch.upper()) - ord("A") + 1)
    return idx


def _map_row(
    row: dict[str, Any],
    normalized_headers: dict[str, str],
    source_file: pathlib.Path,
    source_row_number: int,
    *,
    default_tz: str,
) -> RunRegistryEntry | None:
    external_header = normalized_headers["runid"]
    external_run_id = _clean_str(row.get(external_header))
    if not external_run_id:
        return None

    mapped: dict[str, str | None] = {}
    for source_name, target_name in _COLUMN_MAP.items():
        header = normalized_headers.get(source_name)
        raw = row.get(header) if header is not None else None
        cleaned = _clean_str(raw)
        mapped[target_name] = cleaned

    mapped["planned_or_recorded_ts"] = _normalize_timestamp(
        mapped.get("planned_or_recorded_ts"),
        default_tz=default_tz,
    )

    return RunRegistryEntry(
        external_run_id=external_run_id,
        status=mapped.get("status"),
        planned_or_recorded_ts=mapped.get("planned_or_recorded_ts"),
        test_device=mapped.get("test_device"),
        sensor_cap=mapped.get("sensor_cap"),
        diaper_type=mapped.get("diaper_type"),
        findings_comments=mapped.get("findings_comments"),
        test_protocol=mapped.get("test_protocol"),
        test_result_ref=mapped.get("test_result_ref"),
        log_file_ref=mapped.get("log_file_ref"),
        source_file=source_file.name,
        source_row_number=source_row_number,
    )


def _validate_required_headers(normalized_headers: dict[str, str]) -> None:
    missing = [h for h in ["runid", "test status", "log file"] if h not in normalized_headers]
    if missing:
        raise RegistryImportError(f"Missing required headers: {missing}")


def _normalize_header(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _normalize_sheet_name(value: str) -> str:
    return _normalize_header(value.replace("_", " "))


def _clean_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_timestamp(value: str | None, *, default_tz: str) -> str | None:
    if value is None:
        return None

    tzinfo = _tz_from_name(default_tz)

    # Excel serial timestamp.
    try:
        numeric = float(value)
        if numeric > 1000:
            base = dt.datetime(1899, 12, 30)
            dt_value = base + dt.timedelta(days=numeric)
            dt_value = dt_value.replace(tzinfo=tzinfo)
            return dt_value.isoformat()
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt_value = dt.datetime.strptime(value, fmt)
            dt_value = dt_value.replace(tzinfo=tzinfo)
            return dt_value.isoformat()
        except ValueError:
            continue

    try:
        dt_value = dt.datetime.fromisoformat(value)
        if dt_value.tzinfo is None:
            dt_value = dt_value.replace(tzinfo=tzinfo)
        return dt_value.isoformat()
    except ValueError:
        return value


def _tz_from_name(name: str) -> dt.tzinfo:
    try:
        from zoneinfo import ZoneInfo
    except ImportError as exc:
        raise RegistryImportError("ZoneInfo not available; use Python 3.11+") from exc

    try:
        return ZoneInfo(name)
    except Exception as exc:  # noqa: BLE001
        raise RegistryImportError(f"Unknown timezone: {name}") from exc
