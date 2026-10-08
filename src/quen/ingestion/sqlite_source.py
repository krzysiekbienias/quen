"""Read-only SQLite market-data source.

The only module in quen that knows table and column names of the market-data database.
If that schema changes, this file changes; nothing above the ingestion layer does.

Safety:
    * the database is opened with ``mode=ro``: SQLite itself rejects any write;
    * one short-lived connection per query, closed immediately, so we never hold a lock;
    * ``busy_timeout`` makes a read wait (instead of failing) if a writer holds the lock.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pandas as pd

from quen.core.errors import DataSourceError
from quen.ingestion.source import CLOSE_COLUMNS, INSTRUMENT_COLUMNS, RATE_COLUMNS

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

logger = logging.getLogger(__name__)

_EQUITY_TABLE = "equity_daily_eod"
_INDEX_TABLE = "index_daily_eod"
_DAILY = "1d"
_SPLIT_ADJUSTED = 1


@dataclass(frozen=True, slots=True)
class SqliteMarketDataSource:
    """``MarketDataSource`` backed by a SQLite file, opened read-only."""

    db_path: Path
    busy_timeout_s: float = 5.0

    def __post_init__(self) -> None:
        if not self.db_path.is_file():
            raise DataSourceError(f"Market-data database not found: {self.db_path}")

    # ------------------------------------------------------------------ public API
    def instruments(self, asset_class: str) -> pd.DataFrame:
        sql = f"""
            SELECT {", ".join(INSTRUMENT_COLUMNS)}
            FROM universe_instrument
            WHERE is_active = 1 AND asset_class = ?
            ORDER BY provider_symbol
        """
        return self._query(sql, [asset_class], label=f"instruments[{asset_class}]")

    def equity_closes(
        self, tickers: Sequence[str], start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        return self._closes(_EQUITY_TABLE, tickers, start, end)

    def index_closes(
        self, tickers: Sequence[str], start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        return self._closes(_INDEX_TABLE, tickers, start, end)

    def par_rates(
        self, curve_id: str, tenor: str, start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        date_sql, date_params = _date_range("as_of", start, end)
        sql = f"""
            SELECT {", ".join(RATE_COLUMNS)}
            FROM par_curve_point_eod
            WHERE curve_id = ? AND tenor = ? {date_sql}
            ORDER BY as_of
        """
        return self._query(sql, [curve_id, tenor, *date_params], label=f"par[{curve_id} {tenor}]")

    # ------------------------------------------------------------------ internals
    def _closes(
        self, table: str, tickers: Sequence[str], start: str | None, end: str | None
    ) -> pd.DataFrame:
        if not tickers:
            return pd.DataFrame(columns=list(CLOSE_COLUMNS))
        placeholders = ", ".join("?" * len(tickers))
        date_sql, date_params = _date_range("as_of", start, end)
        sql = f"""
            SELECT {", ".join(CLOSE_COLUMNS)}
            FROM {table}
            WHERE timespan = ? AND adjusted = ? AND ticker IN ({placeholders}) {date_sql}
            ORDER BY ticker, as_of
        """
        params = [_DAILY, _SPLIT_ADJUSTED, *tickers, *date_params]
        return self._query(sql, params, label=f"{table}[{len(tickers)} tickers]")

    def _connect(self) -> sqlite3.Connection:
        uri = f"{self.db_path.resolve().as_uri()}?mode=ro"
        return sqlite3.connect(uri, uri=True, timeout=self.busy_timeout_s)

    def _query(self, sql: str, params: Sequence[Any], label: str) -> pd.DataFrame:
        started = time.perf_counter()
        try:
            with closing(self._connect()) as conn:
                frame = pd.read_sql_query(sql, conn, params=list(params))
        except (sqlite3.Error, pd.errors.DatabaseError) as exc:
            raise DataSourceError(f"Query {label} failed on {self.db_path}: {exc}") from exc
        logger.debug(
            "%s: %d rows in %.1f ms", label, len(frame), (time.perf_counter() - started) * 1e3
        )
        return frame


def _date_range(column: str, start: str | None, end: str | None) -> tuple[str, list[str]]:
    """Inclusive ISO-date bounds as an SQL fragment plus bound parameters."""
    clauses: list[str] = []
    params: list[str] = []
    if start is not None:
        clauses.append(f"AND {column} >= ?")
        params.append(start)
    if end is not None:
        clauses.append(f"AND {column} <= ?")
        params.append(end)
    return " ".join(clauses), params
