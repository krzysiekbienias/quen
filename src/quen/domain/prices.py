"""Canonical price and return panels.

A panel is a wide frame: one row per date, one column per ticker. Once constructed, a
panel is guaranteed clean (sorted unique dates, no missing values, valid numbers), so
models can use it without defensive checks. Build panels through the validation layer;
the checks here are a last line of defence, not the place where data gets cleaned.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import pandas as pd

from quen.core.errors import DomainInvariantError


class ReturnKind(StrEnum):
    SIMPLE = "simple"  # r_t = P_t / P_{t-1} - 1
    LOG = "log"  # r_t = ln(P_t / P_{t-1})


@dataclass(frozen=True, slots=True)
class PricePanel:
    """Clean prices, dates x tickers. Strictly positive, no gaps."""

    prices: pd.DataFrame

    def __post_init__(self) -> None:
        frame = _checked_panel(self.prices, "PricePanel")
        if (frame <= 0).to_numpy().any():
            raise DomainInvariantError("PricePanel: prices must be strictly positive")
        object.__setattr__(self, "prices", frame)

    @property
    def tickers(self) -> tuple[str, ...]:
        return tuple(self.prices.columns)

    @property
    def dates(self) -> pd.DatetimeIndex:
        return pd.DatetimeIndex(self.prices.index)

    def __len__(self) -> int:
        return len(self.prices)

    def returns(self, kind: ReturnKind = ReturnKind.SIMPLE) -> ReturnPanel:
        """Period returns; the first date is lost (no previous price)."""
        growth = self.prices / self.prices.shift(1)  # P_t / P_{t-1}
        values = (
            growth - 1.0
            if kind == ReturnKind.SIMPLE
            else pd.DataFrame(np.log(growth.to_numpy()), index=growth.index, columns=growth.columns)
        )
        return ReturnPanel(values.iloc[1:], kind)


@dataclass(frozen=True, slots=True)
class ReturnPanel:
    """Period returns, dates x tickers. No gaps."""

    returns: pd.DataFrame
    kind: ReturnKind

    def __post_init__(self) -> None:
        frame = _checked_panel(self.returns, "ReturnPanel")
        if self.kind == ReturnKind.SIMPLE and (frame <= -1).to_numpy().any():
            raise DomainInvariantError("ReturnPanel: simple returns must be > -100%")
        object.__setattr__(self, "returns", frame)

    @property
    def tickers(self) -> tuple[str, ...]:
        return tuple(self.returns.columns)

    def __len__(self) -> int:
        return len(self.returns)


def _checked_panel(frame: pd.DataFrame, owner: str) -> pd.DataFrame:
    """Shared invariants of every panel. Returns a defensive float64 copy."""
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise DomainInvariantError(f"{owner}: index must be a DatetimeIndex")
    if frame.empty:
        raise DomainInvariantError(f"{owner}: panel is empty")
    if not frame.index.is_monotonic_increasing or frame.index.has_duplicates:
        raise DomainInvariantError(f"{owner}: dates must be sorted and unique")
    if frame.columns.has_duplicates:
        raise DomainInvariantError(f"{owner}: tickers must be unique")
    try:
        values = frame.astype("float64")
    except (TypeError, ValueError) as exc:
        raise DomainInvariantError(f"{owner}: values must be numeric") from exc
    if not np.isfinite(values.to_numpy()).all():
        raise DomainInvariantError(f"{owner}: missing or non-finite values")
    return values.copy()
