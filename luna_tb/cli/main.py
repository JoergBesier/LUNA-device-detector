"""CLI entrypoint for the LUNA Algorithm Testbench."""
from __future__ import annotations

import argparse
import pathlib
from luna_tb.config import ConfigError, load_config
from luna_tb.logging_setup import configure_logging
from luna_tb.services.ingest import ingest_logs
from luna_tb.services.label_import import import_labels_csv
from luna_tb.services.registry_import import import_run_registry
from luna_tb.storage.db import init_db


def _default_migrations_dir() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[1] / "storage" / "migrations"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="luna-testbench")
    parser.add_argument("--config", help="Path to TOML/JSON config.")
    parser.add_argument("--log-level", default="INFO", help="Logging level.")
    parser.add_argument(
        "--json-logs", action="store_true", help="Emit logs in JSON format."
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    db_init = subparsers.add_parser("db-init", help="Initialize/upgrade SQLite DB")
    db_init.add_argument("--db", required=True, help="Path to SQLite file.")
    db_init.add_argument(
        "--migrations-dir",
        default=str(_default_migrations_dir()),
        help="Path to migrations directory.",
    )

    registry = subparsers.add_parser("registry", help="Run registry import utilities")
    registry_sub = registry.add_subparsers(dest="registry_command", required=True)
    registry_import = registry_sub.add_parser("import", help="Import run registry sheet")
    registry_import.add_argument("--db", required=True, help="Path to SQLite file.")
    registry_import.add_argument("--file", required=True, help="Path to registry .xlsx/.csv file.")
    registry_import.add_argument(
        "--sheet",
        default="test runs",
        help="Sheet name for .xlsx import.",
    )
    registry_import.add_argument(
        "--default-tz",
        default="Europe/Berlin",
        help="Timezone to apply to naive/serial timestamps.",
    )

    ingest = subparsers.add_parser("ingest", help="Ingest lab log CSV files")
    ingest.add_argument("--db", required=True, help="Path to SQLite file.")
    ingest.add_argument("--device-id", required=True, help="Device identifier.")
    ingest.add_argument("--diaper-type", required=True, help="Diaper type.")
    ingest.add_argument("--sensor-layout", required=True, help="Sensor layout.")
    ingest.add_argument("--run-notes", help="Optional run notes.")
    ingest.add_argument(
        "--default-tz",
        default="Europe/Berlin",
        help="Timezone name to assume when logs lack timezone.",
    )
    ingest.add_argument("logs", nargs="+", help="CSV log file(s) to ingest.")

    label = subparsers.add_parser("label", help="Label import utilities")
    label_sub = label.add_subparsers(dest="label_command", required=True)
    label_import = label_sub.add_parser("import", help="Import labels from CSV")
    label_import.add_argument("--db", required=True, help="Path to SQLite file.")
    label_import.add_argument("--file", required=True, help="Path to label CSV.")
    label_import.add_argument("--run-id", type=int, help="Run id for all labels.")

    for name in ["derive", "simulate", "run", "report", "ui"]:
        subparsers.add_parser(name, help=f"(stub) {name} command")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    configure_logging(level=args.log_level, json_format=args.json_logs)

    if args.config:
        try:
            load_config(args.config)
        except ConfigError as exc:
            parser.error(str(exc))

    if args.command == "db-init":
        init_db(args.db, args.migrations_dir)
        return 0

    if args.command == "registry" and args.registry_command == "import":
        import_run_registry(
            args.db,
            args.file,
            sheet_name=args.sheet,
            default_tz=args.default_tz,
        )
        return 0

    if args.command == "ingest":
        ingest_logs(
            args.db,
            args.logs,
            device_id=args.device_id,
            diaper_type=args.diaper_type,
            sensor_layout=args.sensor_layout,
            run_notes=args.run_notes,
            default_tz=args.default_tz,
        )
        return 0

    if args.command == "label" and args.label_command == "import":
        import_labels_csv(args.db, args.file, run_id=args.run_id)
        return 0

    parser.error(f"Command not implemented yet: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
