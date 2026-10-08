"""Smoke test against the real market-data database. Skipped unless QUEN_DB_PATH is set.

QUEN_DB_PATH=/path/to/db.sqlite uv run pytest -m integration
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from quen.ingestion import SqliteMarketDataSource

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif("QUEN_DB_PATH" not in os.environ, reason="QUEN_DB_PATH not set"),
]


@pytest.fixture
def source() -> SqliteMarketDataSource:
    return SqliteMarketDataSource(Path(os.environ["QUEN_DB_PATH"]))


def test_equity_universe_is_not_empty(source: SqliteMarketDataSource) -> None:
    assert not source.instruments("EQUITY").empty


def test_closes_exist_for_every_active_equity(source: SqliteMarketDataSource) -> None:
    tickers = source.instruments("EQUITY")["provider_symbol"].tolist()

    closes = source.equity_closes(tickers)

    assert set(closes["ticker"]) == set(tickers)
