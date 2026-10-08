"""Turning a ragged wide frame into a gap-free panel.

Two steps, both reported:
    1. common window — keep only dates where every series has started and not yet ended;
    2. missing-data policy — what to do with gaps that remain inside that window.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from quen.validation._dates import first_valid_dates, last_valid_dates
from quen.validation.report import Issue, Severity

if TYPE_CHECKING:
    import pandas as pd


def common_window(prices: pd.DataFrame) -> tuple[pd.DataFrame, list[Issue]]:
    """Restrict to [latest first date, earliest last date] across all tickers."""
    start = first_valid_dates(prices).max()
    end = last_valid_dates(prices).min()
    if start > end:
        return prices.iloc[0:0], [
            Issue("common_window", Severity.ERROR, "series do not overlap in time")
        ]
    window = prices.loc[start:end]
    dropped = len(prices) - len(window)
    issues = []
    if dropped:
        message = f"window {start:%Y-%m-%d} -> {end:%Y-%m-%d}; {dropped} date(s) outside dropped"
        issues.append(Issue("common_window", Severity.WARNING, message))
    return window, issues


class MissingDataPolicy(ABC):
    """Strategy for gaps inside the common window. Must return a frame with no NaN."""

    name: ClassVar[str]

    @abstractmethod
    def apply(self, prices: pd.DataFrame) -> tuple[pd.DataFrame, list[Issue]]: ...


@dataclass(frozen=True, slots=True)
class DropIncompleteDates(MissingDataPolicy):
    """Drop every date on which any ticker has no price.

    Honest: no invented prices. Cost: the next return spans two periods.
    """

    name: ClassVar[str] = "drop_incomplete_dates"

    def apply(self, prices: pd.DataFrame) -> tuple[pd.DataFrame, list[Issue]]:
        complete = prices.dropna(how="any")
        return complete, _dropped_issue(self.name, prices, complete)


@dataclass(frozen=True, slots=True)
class ForwardFill(MissingDataPolicy):
    """Carry the last price forward for at most ``limit`` days; drop dates still incomplete.

    Cost: each filled day produces a zero return, which biases volatility down.
    """

    limit: int = 2
    name: ClassVar[str] = "forward_fill"

    def apply(self, prices: pd.DataFrame) -> tuple[pd.DataFrame, list[Issue]]:
        filled = prices.ffill(limit=self.limit)
        n_filled = int(prices.isna().sum().sum() - filled.isna().sum().sum())
        issues = []
        if n_filled:
            message = f"{n_filled} price(s) carried forward (limit {self.limit} day(s))"
            issues.append(Issue(self.name, Severity.WARNING, message))
        complete = filled.dropna(how="any")
        return complete, issues + _dropped_issue(self.name, filled, complete)


def _dropped_issue(rule: str, before: pd.DataFrame, after: pd.DataFrame) -> list[Issue]:
    dropped = len(before) - len(after)
    if not dropped:
        return []
    return [Issue(rule, Severity.WARNING, f"{dropped} incomplete date(s) dropped")]
