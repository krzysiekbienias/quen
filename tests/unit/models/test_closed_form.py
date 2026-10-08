from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from quen.core.errors import EstimationError
from quen.domain import PricePanel, ReturnKind
from quen.models.estimation import MomentEstimator, Moments


@pytest.fixture
def panel() -> PricePanel:
    rng = np.random.default_rng(0)
    dates = pd.bdate_range("2025-01-01", periods=300)
    log_r = rng.normal(0.0004, 0.01, size=(300, 3))
    prices = 100 * np.exp(np.cumsum(log_r, axis=0))
    return PricePanel(pd.DataFrame(prices, index=dates, columns=["A", "B", "C"]))


def test_moments_are_annualised(panel: PricePanel) -> None:
    returns = panel.returns()

    moments = MomentEstimator(periods_per_year=252).estimate(returns)

    r = returns.returns
    np.testing.assert_allclose(moments.mean, r.mean() * 252)
    np.testing.assert_allclose(moments.covariance, np.cov(r.to_numpy(), rowvar=False) * 252)


def test_volatilities_are_square_roots_of_the_diagonal(panel: PricePanel) -> None:
    moments = MomentEstimator().estimate(panel.returns())

    np.testing.assert_allclose(moments.volatilities**2, np.diag(moments.covariance))


def test_log_returns_are_rejected(panel: PricePanel) -> None:
    with pytest.raises(EstimationError, match="simple returns"):
        MomentEstimator().estimate(panel.returns(ReturnKind.LOG))


def test_misaligned_tickers_are_rejected() -> None:
    with pytest.raises(EstimationError, match="same tickers"):
        Moments(
            mean=pd.Series([0.1, 0.2], index=["A", "B"]),
            covariance=pd.DataFrame(np.eye(2), index=["B", "A"], columns=["B", "A"]),
        )


def test_asymmetric_covariance_is_rejected() -> None:
    with pytest.raises(EstimationError, match="symmetric"):
        Moments(
            mean=pd.Series([0.1, 0.2], index=["A", "B"]),
            covariance=pd.DataFrame([[1.0, 0.5], [0.2, 1.0]], index=["A", "B"], columns=["A", "B"]),
        )
