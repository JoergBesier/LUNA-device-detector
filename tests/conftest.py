from __future__ import annotations

import datetime as dt
import os
import pathlib

import pytest

from luna_tb.storage.db import init_db


@pytest.fixture()
def repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture()
def migrations_dir(repo_root: pathlib.Path) -> pathlib.Path:
    return repo_root / "luna_tb" / "storage" / "migrations"


@pytest.fixture()
def test_db_path(tmp_path: pathlib.Path) -> pathlib.Path:
    return tmp_path / "test.sqlite"


@pytest.fixture()
def initialized_db(test_db_path: pathlib.Path, migrations_dir: pathlib.Path) -> pathlib.Path:
    init_db(test_db_path, migrations_dir)
    return test_db_path


def pytest_configure(config: pytest.Config) -> None:
    repo = pathlib.Path(__file__).resolve().parents[1]
    results_dir = repo / "test-results"
    results_dir.mkdir(parents=True, exist_ok=True)

    tag = os.environ.get("PYTEST_REPORT_TAG")
    if tag:
        safe_tag = "".join(ch for ch in tag if ch.isalnum() or ch in ("-", "_"))
        timestamp = safe_tag or dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    else:
        timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")

    config.option.xmlpath = str(results_dir / f"pytest-{timestamp}.xml")
    config.option.htmlpath = str(results_dir / f"pytest-{timestamp}.html")
    config.option.self_contained_html = True
