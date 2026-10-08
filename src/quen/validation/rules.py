"""Business rules checked on the wide price frame (dates x tickers, NaN = no price).

Each rule only *reports*. Deciding what to do about the findings (trim the window,
drop or fill dates) belongs to the alignment step, so rules stay small and testable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

import pandas as pd

from quen.validation._dates import last_valid_dates
from quen.validation.report import Issue, Severity


class ValidationRule(ABC):
    """One business rule. Subclasses set ``name`` and implement ``check``."""

    name: ClassVar[str]

    @abstractmethod
    def check(self, prices: pd.DataFrame) -> list[Issue]:
        """Return the issues found; an empty list means the rule passed."""


@dataclass(frozen=True, slots=True)
class PositivePrices(ValidationRule):
    """Prices must be strictly positive: a zero or negative close is a data error."""

    name: ClassVar[str] = "positive_prices"

    def check(self, prices: pd.DataFrame) -> list[Issue]:
        bad = prices.columns[(prices <= 0).any()]
        if bad.empty:
            return []
        return [Issue(self.name, Severity.ERROR, "zero or negative prices", _names(bad))]


@dataclass(frozen=True, slots=True)
class StaleSeries(ValidationRule):
    """A series whose last price is much older than the panel's last date.

    It does not break anything by itself, but it silently shortens the common window
    for every other asset, so it must be visible.
    """

    max_lag_days: int = 7
    name: ClassVar[str] = "stale_series"

    def check(self, prices: pd.DataFrame) -> list[Issue]:
        last = last_valid_dates(prices)
        cutoff = prices.index.max() - pd.Timedelta(days=self.max_lag_days)
        stale = last[last < cutoff]
        if stale.empty:
            return []
        message = (
            f"last price on or before {stale.max():%Y-%m-%d} "
            f"while the panel runs to {prices.index.max():%Y-%m-%d}"
        )
        return [Issue(self.name, Severity.WARNING, message, _names(stale.index))]


@dataclass(frozen=True, slots=True)
class InternalGaps(ValidationRule):
    """Missing prices *inside* a series' own date range (not at its start or end)."""

    name: ClassVar[str] = "internal_gaps"

    def check(self, prices: pd.DataFrame) -> list[Issue]:
        issues: list[Issue] = []
        for ticker, series in prices.items():
            inside = series.loc[series.first_valid_index() : series.last_valid_index()]
            gaps = int(inside.isna().sum())
            if gaps:
                issues.append(
                    Issue(self.name, Severity.WARNING, f"{gaps} missing day(s)", (str(ticker),))
                )
        return issues


def default_rules() -> tuple[ValidationRule, ...]:
    return (PositivePrices(), StaleSeries(), InternalGaps())


def _names(index: pd.Index) -> tuple[str, ...]:
    return tuple(sorted(str(t) for t in index))
