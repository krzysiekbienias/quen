from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from hypothesis import given
from hypothesis import strategies as st

from quen.core.errors import DomainInvariantError
from quen.domain import PricePanel, ReturnKind, ReturnPanel

DATES = pd.DatetimeIndex(["2026-05-14", "2026-05-15", "2026-05-18"], name="date")


def frame(data: dict[str, list[float]], index: pd.Index = DATES) -> pd.DataFrame:
    return pd.DataFrame(data, index=index)


# --------------------------------------------------------------------------- invariants
def test_valid_panel_exposes_tickers_and_dates() -> None:
    panel = PricePanel(frame({"AAPL": [100.0, 110.0, 99.0], "MSFT": [400.0, 404.0, 400.0]}))

    assert panel.tickers == ("AAPL", "MSFT")
    assert len(panel) == 3
    assert panel.dates[0] == pd.Timestamp("2026-05-14")


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        (frame({"A": [1.0, 2.0, 3.0]}, index=pd.Index(["a", "b", "c"])), "DatetimeIndex"),
        (frame({"A": [1.0, 2.0, 3.0]}, index=DATES[::-1]), "sorted and unique"),
        (frame({"A": [1.0, 2.0, 3.0]}, index=DATES[[0, 0, 1]]), "sorted and unique"),
        (frame({"A": [1.0, np.nan, 3.0]}), "missing"),
        (frame({"A": [1.0, 0.0, 3.0]}), "strictly positive"),
        (frame({"A": []}, index=pd.DatetimeIndex([])), "empty"),
    ],
)
def test_panel_rejects_broken_data(bad: pd.DataFrame, message: str) -> None:
    with pytest.raises(DomainInvariantError, match=message):
        PricePanel(bad)


def test_panel_keeps_a_defensive_copy() -> None:
    source = frame({"A": [1.0, 2.0, 3.0]})
    panel = PricePanel(source)

    source.iloc[0, 0] = 999.0

    assert panel.prices.iloc[0, 0] == 1.0


def test_simple_returns_below_minus_100_percent_are_impossible() -> None:
    with pytest.raises(DomainInvariantError, match="-100%"):
        ReturnPanel(frame({"A": [0.1, -1.0, 0.0]}), ReturnKind.SIMPLE)


# --------------------------------------------------------------------------- returns
def test_simple_returns_by_hand() -> None:
    returns = PricePanel(frame({"A": [100.0, 110.0, 99.0]})).returns()

    assert returns.kind == ReturnKind.SIMPLE
    assert returns.returns["A"].tolist() == pytest.approx([0.10, -0.10])
    assert len(returns) == 2  # the first date has no previous price


def test_log_returns_by_hand() -> None:
    returns = PricePanel(frame({"A": [100.0, 110.0, 99.0]})).returns(ReturnKind.LOG)

    assert returns.returns["A"].tolist() == pytest.approx([np.log(1.1), np.log(0.9)])


prices_strategy = st.lists(
    st.floats(min_value=1.0, max_value=1e4, allow_nan=False), min_size=2, max_size=60
)


@given(prices_strategy)
def test_simple_returns_compound_to_total_growth(prices: list[float]) -> None:
    """prod(1 + r_t) = P_T / P_0"""
    index = pd.bdate_range("2024-01-01", periods=len(prices))
    r = PricePanel(pd.DataFrame({"A": prices}, index=index)).returns().returns["A"]

    assert np.prod(1 + r.to_numpy()) == pytest.approx(prices[-1] / prices[0], rel=1e-9)


@given(prices_strategy)
def test_log_returns_telescope_and_match_simple_returns(prices: list[float]) -> None:
    """sum(ln P_t/P_{t-1}) = ln(P_T / P_0)  and  r_log = ln(1 + r_simple)"""
    index = pd.bdate_range("2024-01-01", periods=len(prices))
    panel = PricePanel(pd.DataFrame({"A": prices}, index=index))
    log_r = panel.returns(ReturnKind.LOG).returns["A"].to_numpy()
    simple_r = panel.returns(ReturnKind.SIMPLE).returns["A"].to_numpy()

    assert log_r.sum() == pytest.approx(np.log(prices[-1] / prices[0]), abs=1e-9)
    assert log_r == pytest.approx(np.log1p(simple_r), abs=1e-12)
