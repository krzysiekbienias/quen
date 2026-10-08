"""The contract every market-data source fulfils.

Ingestion returns data *exactly as stored* in the source, in long format
(one row per instrument and day). It does no parsing, cleaning or reshaping:
turning raw records into a clean price panel is the job of the validation layer.
Dates therefore stay ISO strings (``"2026-05-18"``) here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pandas as pd

# Column contracts of the frames returned by a MarketDataSource.
INSTRUMENT_COLUMNS: Final = (
    "instrument_id",
    "provider_symbol",
    "asset_class",
    "sector",
    "industry",
    "quote_currency",
)
CLOSE_COLUMNS: Final = ("ticker", "as_of", "close")
RATE_COLUMNS: Final = ("as_of", "quoted_rate")


class MarketDataSource(Protocol):
    """Read-only access to raw market data.

    ``start`` and ``end`` are inclusive ISO dates (``YYYY-MM-DD``); ``None`` means unbounded.
    """

    def instruments(self, asset_class: str) -> pd.DataFrame:
        """Active instruments of one asset class (``EQUITY``, ``INDEX``, ...)."""
        ...

    def equity_closes(
        self, tickers: Sequence[str], start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        """Split-adjusted daily closes of equities. Columns: ``CLOSE_COLUMNS``."""
        ...

    def index_closes(
        self, tickers: Sequence[str], start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        """Daily closes of indices (e.g. ``I:NDX``). Columns: ``CLOSE_COLUMNS``."""
        ...

    def par_rates(
        self, curve_id: str, tenor: str, start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        """Quoted par rates (annualised decimal) of one curve pillar. Columns: ``RATE_COLUMNS``."""
        ...
