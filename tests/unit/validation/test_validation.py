from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quen.core.errors import DataValidationError
from quen.validation import (
    DropIncompleteDates,
    ForwardFill,
    InternalGaps,
    PositivePrices,
    PriceValidator,
    Severity,
    StaleSeries,
)
from quen.validation.alignment import common_window
from quen.validation.normalize import to_wide

DAYS = pd.bdate_range("2026-05-11", periods=6)  # Mon 11 -> Mon 18 May 2026


def raw(series: dict[str, list[float | None]], dates: pd.DatetimeIndex = DAYS) -> pd.DataFrame:
    """Long raw frame as ingestion returns it; None = no row for that day."""
    rows = [
        (ticker, f"{day:%Y-%m-%d}", price)
        for ticker, prices in series.items()
        for day, price in zip(dates, prices, strict=True)
        if price is not None
    ]
    return pd.DataFrame(rows, columns=["ticker", "as_of", "close"])


def wide(series: dict[str, list[float | None]]) -> pd.DataFrame:
    frame, issues = to_wide(raw(series))
    assert not issues
    return frame


# --------------------------------------------------------------------------- normalize
def test_to_wide_parses_dates_and_pivots() -> None:
    frame = wide({"A": [1, 2, 3, 4, 5, 6], "B": [1, 2, None, 4, 5, 6]})

    assert isinstance(frame.index, pd.DatetimeIndex)
    assert list(frame.columns) == ["A", "B"]
    assert np.isnan(frame.loc["2026-05-13", "B"])


def test_unparseable_dates_and_duplicates_are_errors() -> None:
    bad = pd.DataFrame(
        [
            ("A", "2026-05-11", 1.0),
            ("A", "11/05/2026", 2.0),  # wrong date format
            ("B", "2026-05-11", 1.0),
            ("B", "2026-05-11", 1.5),  # duplicate (ticker, date)
        ],
        columns=["ticker", "as_of", "close"],
    )

    _, issues = to_wide(bad)

    messages = " | ".join(i.message for i in issues)
    assert all(i.severity == Severity.ERROR for i in issues)
    assert "unparseable" in messages
    assert "duplicated" in messages


def test_missing_columns_is_an_error() -> None:
    _, issues = to_wide(pd.DataFrame({"ticker": ["A"], "close": [1.0]}))

    assert "missing columns" in issues[0].message


# --------------------------------------------------------------------------- rules
def test_positive_prices_rule() -> None:
    issues = PositivePrices().check(wide({"A": [1, 2, 3, 4, 5, 6], "B": [1, 0, 3, 4, 5, 6]}))

    assert [(i.severity, i.tickers) for i in issues] == [(Severity.ERROR, ("B",))]


def test_stale_series_is_a_warning() -> None:
    prices = wide({"A": [1, 2, 3, 4, 5, 6], "OLD": [1, 2, None, None, None, None]})

    issues = StaleSeries(max_lag_days=3).check(prices)

    assert [(i.severity, i.tickers) for i in issues] == [(Severity.WARNING, ("OLD",))]


def test_internal_gaps_ignore_missing_start_and_end() -> None:
    prices = wide(
        {
            "A": [1, 2, None, 4, 5, 6],
            "LATE": [None, None, 3, 4, 5, 6],
            "EARLY": [1, 2, 3, 4, None, None],
        }
    )

    issues = InternalGaps().check(prices)

    assert [(i.tickers, i.message) for i in issues] == [(("A",), "1 missing day(s)")]


# --------------------------------------------------------------------------- alignment
def test_common_window_trims_to_the_overlap() -> None:
    prices = wide({"LATE": [None, 2, 3, 4, 5, 6], "STALE": [1, 2, 3, 4, None, None]})

    window, issues = common_window(prices)

    assert window.index[0] == pd.Timestamp("2026-05-12")
    assert window.index[-1] == pd.Timestamp("2026-05-14")
    assert issues[0].severity == Severity.WARNING


def test_no_overlap_is_an_error() -> None:
    _, issues = common_window(wide({"A": [1, 2, None, None, None, None], "B": [None] * 4 + [5, 6]}))

    assert issues[0].severity == Severity.ERROR


def test_drop_incomplete_dates() -> None:
    clean, issues = DropIncompleteDates().apply(
        wide({"A": [1, 2, 3, 4, 5, 6], "B": [1, None, 3, 4, 5, 6]})
    )

    assert len(clean) == 5
    assert pd.Timestamp("2026-05-12") not in clean.index
    assert "1 incomplete date(s) dropped" in issues[0].message


def test_forward_fill_respects_its_limit() -> None:
    prices = wide({"A": [1, 2, 3, 4, 5, 6], "B": [1, None, 3, None, None, None]})

    clean, issues = ForwardFill(limit=1).apply(prices)

    assert clean.loc["2026-05-12", "B"] == 1  # one-day gap filled
    assert len(clean) == 4  # 2nd and 3rd day of the long gap dropped
    assert any("carried forward" in i.message for i in issues)


# --------------------------------------------------------------------------- validator
def test_validator_end_to_end_on_realistic_data() -> None:
    """Mirrors the real DB: a gap (like MSFT) and a series that stops early."""
    raw_closes = raw(
        {
            "AAPL": [100, 101, 102, 103, 104, 105],
            "MSFT": [400, 401, None, 403, 404, 405],
            "PG": [150, 151, 152, 153, None, None],
        }
    )

    result = PriceValidator(
        rules=(InternalGaps(), StaleSeries(max_lag_days=3)), min_observations=2
    ).validate(raw_closes)

    panel = result.panel
    assert panel.tickers == ("AAPL", "MSFT", "PG")
    assert list(panel.dates.strftime("%d")) == ["11", "12", "14"]  # 13th dropped, window ends 14th
    rules_fired = {i.rule for i in result.report.warnings}
    assert {
        "internal_gaps",
        "stale_series",
        "common_window",
        "drop_incomplete_dates",
    } <= rules_fired


def test_validator_raises_with_the_report_attached() -> None:
    raw_closes = raw({"A": [1, 2, 3, 4, 5, 6], "B": [1, -2, 3, 4, 5, 6]})

    with pytest.raises(DataValidationError, match="positive") as excinfo:
        PriceValidator(min_observations=2).validate(raw_closes)

    assert excinfo.value.report.has_errors


def test_too_short_history_is_an_error() -> None:
    with pytest.raises(DataValidationError, match="at least 60 required"):
        PriceValidator().validate(raw({"A": [1, 2, 3, 4, 5, 6]}))
