from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from quen.core.errors import DataSourceError
from quen.ingestion import (
    CLOSE_COLUMNS,
    INSTRUMENT_COLUMNS,
    RATE_COLUMNS,
    MarketDataSource,
    SqliteMarketDataSource,
)


@pytest.fixture
def source(market_db: Path) -> MarketDataSource:
    return SqliteMarketDataSource(market_db)


# --------------------------------------------------------------------------- instruments
def test_instruments_returns_only_active_rows_of_the_asset_class(source: MarketDataSource) -> None:
    frame = source.instruments("EQUITY")

    assert tuple(frame.columns) == INSTRUMENT_COLUMNS
    assert frame["provider_symbol"].tolist() == ["AAPL", "MSFT"]  # no OLD, no CL


# --------------------------------------------------------------------------- closes
def test_equity_closes_keep_only_daily_split_adjusted_bars(source: MarketDataSource) -> None:
    frame = source.equity_closes(["AAPL"])

    assert tuple(frame.columns) == CLOSE_COLUMNS
    assert frame["close"].tolist() == [210.0, 212.0, 215.0]  # no unadjusted / weekly twin


def test_equity_closes_are_sorted_by_ticker_then_date(source: MarketDataSource) -> None:
    frame = source.equity_closes(["MSFT", "AAPL"])

    assert frame["ticker"].tolist() == ["AAPL"] * 3 + ["MSFT"] * 2
    assert frame.groupby("ticker")["as_of"].apply(lambda s: s.is_monotonic_increasing).all()


def test_dates_stay_raw_iso_strings(source: MarketDataSource) -> None:
    frame = source.equity_closes(["AAPL"])

    assert frame["as_of"].iloc[0] == "2026-05-14"  # parsing is validation's job


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("2026-05-15", None, ["2026-05-15", "2026-05-18"]),
        (None, "2026-05-15", ["2026-05-14", "2026-05-15"]),
        ("2026-05-15", "2026-05-15", ["2026-05-15"]),  # bounds are inclusive
    ],
)
def test_date_range_is_inclusive(
    source: MarketDataSource, start: str | None, end: str | None, expected: list[str]
) -> None:
    assert source.equity_closes(["AAPL"], start, end)["as_of"].tolist() == expected


def test_unknown_ticker_gives_empty_frame(source: MarketDataSource) -> None:
    frame = source.equity_closes(["NOPE"])

    assert frame.empty
    assert tuple(frame.columns) == CLOSE_COLUMNS


def test_no_tickers_gives_empty_frame_without_touching_the_db(market_db: Path) -> None:
    source = SqliteMarketDataSource(market_db)
    market_db.unlink()  # any query would now fail

    frame = source.equity_closes([])

    assert frame.empty
    assert tuple(frame.columns) == CLOSE_COLUMNS


def test_index_closes(source: MarketDataSource) -> None:
    frame = source.index_closes(["I:NDX"])

    assert frame["close"].tolist() == [21000.0, 21100.0]


# --------------------------------------------------------------------------- rates
def test_par_rates_for_one_pillar(source: MarketDataSource) -> None:
    frame = source.par_rates("USD_TREASURY_PAR_FRED", "3M")

    assert tuple(frame.columns) == RATE_COLUMNS
    assert frame["quoted_rate"].tolist() == pytest.approx([0.0430, 0.0432])


def test_par_rates_respect_date_range(source: MarketDataSource) -> None:
    frame = source.par_rates("USD_TREASURY_PAR_FRED", "3M", start="2026-05-28")

    assert frame["as_of"].tolist() == ["2026-05-28"]


# --------------------------------------------------------------------------- safety & errors
def test_connection_is_read_only(market_db: Path) -> None:
    source = SqliteMarketDataSource(market_db)

    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        source._connect().execute("DELETE FROM equity_daily_eod")


def test_missing_file_fails_at_construction(tmp_path: Path) -> None:
    with pytest.raises(DataSourceError, match="not found"):
        SqliteMarketDataSource(tmp_path / "missing.sqlite")


def test_missing_table_is_reported_as_data_source_error(tmp_path: Path) -> None:
    empty_db = tmp_path / "empty.sqlite"
    sqlite3.connect(empty_db).close()

    with pytest.raises(DataSourceError, match="no such table"):
        SqliteMarketDataSource(empty_db).equity_closes(["AAPL"])
