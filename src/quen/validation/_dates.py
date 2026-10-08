"""Per-ticker first / last observed dates of a wide frame (NaN = no price)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


def first_valid_dates(prices: pd.DataFrame) -> pd.Series:
    """Date of the first non-missing price of every ticker."""
    return prices.notna().idxmax()


def last_valid_dates(prices: pd.DataFrame) -> pd.Series:
    """Date of the last non-missing price of every ticker."""
    return prices.notna().iloc[::-1].idxmax()
