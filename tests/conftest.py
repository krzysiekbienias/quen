from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
INGESTED_AT = "2026-10-08T00:00:00Z"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "integration: reads the real market-data DB (set QUEN_DB_PATH to run)"
    )


def _seed(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT INTO universe_instrument"
        " (instrument_id, provider_symbol, asset_class, sector, is_active) VALUES (?, ?, ?, ?, ?)",
        [
            ("AAPL", "AAPL", "EQUITY", "Technology", 1),
            ("MSFT", "MSFT", "EQUITY", "Technology", 1),
            ("OLD", "OLD", "EQUITY", "Industrials", 0),  # inactive
            ("CL", "CL", "COMMODITY", None, 1),
            ("NDX", "I:NDX", "INDEX", None, 1),
        ],
    )
    bar = (
        "INSERT INTO {table} (ticker, as_of, open, high, low, close, source, timespan,"
        " adjusted, ingested_at) VALUES (?, ?, 1, 1, 1, ?, 'TEST', ?, ?, ?)"
    )
    conn.executemany(
        bar.format(table="equity_daily_eod"),
        [
            ("AAPL", "2026-05-14", 210.0, "1d", 1, INGESTED_AT),
            ("AAPL", "2026-05-15", 212.0, "1d", 1, INGESTED_AT),
            ("AAPL", "2026-05-18", 215.0, "1d", 1, INGESTED_AT),
            ("AAPL", "2026-05-18", 860.0, "1d", 0, INGESTED_AT),  # unadjusted twin
            ("AAPL", "2026-05-18", 999.0, "1w", 1, INGESTED_AT),  # weekly bar
            ("MSFT", "2026-05-15", 410.0, "1d", 1, INGESTED_AT),
            ("MSFT", "2026-05-18", 405.0, "1d", 1, INGESTED_AT),
            ("CL", "2026-09-03", 70.0, "1d", 1, INGESTED_AT),  # futures stored as equity
        ],
    )
    conn.executemany(
        bar.format(table="index_daily_eod"),
        [
            ("I:NDX", "2026-05-15", 21000.0, "1d", 1, INGESTED_AT),
            ("I:NDX", "2026-05-18", 21100.0, "1d", 1, INGESTED_AT),
        ],
    )
    conn.executemany(
        "INSERT INTO par_curve_eod (curve_id, as_of) VALUES (?, ?)",
        [("USD_TREASURY_PAR_FRED", "2026-05-27"), ("USD_TREASURY_PAR_FRED", "2026-05-28")],
    )
    conn.executemany(
        "INSERT INTO par_curve_point_eod (curve_id, as_of, tenor, instrument_type,"
        " fred_series_id, quoted_rate) VALUES (?, ?, ?, 'deposit', ?, ?)",
        [
            ("USD_TREASURY_PAR_FRED", "2026-05-27", "3M", "DGS3MO", 0.0430),
            ("USD_TREASURY_PAR_FRED", "2026-05-28", "3M", "DGS3MO", 0.0432),
            ("USD_TREASURY_PAR_FRED", "2026-05-27", "1M", "DGS1MO", 0.0440),
        ],
    )


@pytest.fixture
def market_db(tmp_path: Path) -> Path:
    """A small SQLite file with the real market-data schema and a handful of rows."""
    path = tmp_path / "market.sqlite"
    with sqlite3.connect(path) as conn:
        conn.executescript((FIXTURES / "market_schema.sql").read_text(encoding="utf-8"))
        _seed(conn)
    return path
