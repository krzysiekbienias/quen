"""Peek at the market data through the ingestion layer.

make explore            (reads QUEN_DB_PATH from .env)
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from quen.core.errors import DataValidationError
from quen.domain import ReturnKind
from quen.ingestion import SqliteMarketDataSource
from quen.validation import PriceValidator


def main() -> int:
    db_path = os.environ.get("QUEN_DB_PATH")
    if not db_path:
        print("QUEN_DB_PATH is not set (add it to .env)", file=sys.stderr)
        return 1

    # Show the adapter's debug logs: query, row count, time.
    logging.basicConfig(level=logging.DEBUG, format="%(name)s | %(message)s")
    source = SqliteMarketDataSource(Path(db_path))

    equities = source.instruments("EQUITY")
    print(f"\n== Equity universe: {len(equities)} instruments")
    print(equities.head(10).to_string(index=False))

    closes = source.equity_closes(["AAPL", "MSFT", "NVDA"], start="2026-05-01")
    print(f"\n== Closes since 2026-05-01: {closes.shape}")
    print(closes.head(8).to_string(index=False))
    print("\nRows per ticker:")
    print(closes.groupby("ticker").size().to_string())

    ndx = source.index_closes(["I:NDX"], start="2026-09-01")
    print(f"\n== I:NDX since 2026-09-01: {ndx.shape}")
    print(ndx.tail(5).to_string(index=False))

    rates = source.par_rates("USD_TREASURY_PAR_FRED", "3M")
    print(f"\n== 3M Treasury par rate: {rates.shape}")
    print(rates.tail(5).to_string(index=False))

    # ---- validation: raw closes of the whole equity universe -> clean PricePanel
    tickers = equities["provider_symbol"].tolist()
    print(f"\n== Validating {len(tickers)} equities")
    try:
        result = PriceValidator().validate(source.equity_closes(tickers))
    except DataValidationError as exc:
        print(exc)
        return 1
    panel = result.panel
    print(
        f"\nPanel: {len(panel)} dates x {len(panel.tickers)} tickers, "
        f"{panel.dates[0]:%Y-%m-%d} -> {panel.dates[-1]:%Y-%m-%d}"
    )
    print("\nReport:")
    print(result.report)
    returns = panel.returns(ReturnKind.LOG)
    print(f"\nLog returns: {returns.returns.shape}; last row:")
    print(returns.returns.tail(1).T.round(4).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
