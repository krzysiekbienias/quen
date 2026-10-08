"""Raw long records -> wide frame (dates x tickers), with structural checks.

This is where raw strings become real dates and numbers. Anything that cannot be parsed
is reported, never silently dropped.
"""

from __future__ import annotations

import pandas as pd

from quen.ingestion import CLOSE_COLUMNS
from quen.validation.report import Issue, Severity

_RULE = "structure"
_DATE_FORMAT = "%Y-%m-%d"


def to_wide(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[Issue]]:
    """Parse and pivot raw closes. Returns the wide frame (NaN where a ticker has no price)."""
    missing = [c for c in CLOSE_COLUMNS if c not in raw.columns]
    if missing:
        return pd.DataFrame(), [_error(f"missing columns {missing}")]
    if raw.empty:
        return pd.DataFrame(), [_error("no price records")]

    issues: list[Issue] = []
    frame = raw.loc[:, list(CLOSE_COLUMNS)].copy()
    frame["as_of"] = pd.to_datetime(frame["as_of"], format=_DATE_FORMAT, errors="coerce")
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")

    unparseable = frame["as_of"].isna() | frame["close"].isna()
    if unparseable.any():
        bad = tuple(sorted(frame.loc[unparseable, "ticker"].astype(str).unique()))
        issues.append(_error(f"{int(unparseable.sum())} rows with unparseable date or price", bad))
        frame = frame.loc[~unparseable]

    duplicated = frame.duplicated(subset=["ticker", "as_of"], keep=False)
    if duplicated.any():
        dup = tuple(sorted(frame.loc[duplicated, "ticker"].astype(str).unique()))
        issues.append(_error(f"{int(duplicated.sum())} duplicated (ticker, date) rows", dup))
        frame = frame.drop_duplicates(subset=["ticker", "as_of"], keep="last")

    # Strict pivot on purpose: unlike pivot_table it cannot silently average duplicates.
    wide = frame.pivot(index="as_of", columns="ticker", values="close").sort_index()  # noqa: PD010
    wide.index.name = "date"
    wide.columns.name = None
    return wide, issues


def _error(message: str, tickers: tuple[str, ...] = ()) -> Issue:
    return Issue(_RULE, Severity.ERROR, message, tickers)
