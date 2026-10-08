"""Expected returns and covariance: the two inputs of mean-variance analysis.

Estimators work on per-period returns; ``MomentEstimator`` annualises the result.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from quen.core.errors import EstimationError
from quen.domain import ReturnKind, ReturnPanel

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Moments:
    """Annualised expected returns (mu) and covariance matrix (Sigma), same ticker order."""

    mean: pd.Series
    covariance: pd.DataFrame

    def __post_init__(self) -> None:
        tickers = list(self.mean.index)
        if list(self.covariance.index) != tickers or list(self.covariance.columns) != tickers:
            raise EstimationError("Moments: mean and covariance must cover the same tickers")
        values = self.covariance.to_numpy()
        if not (np.isfinite(values).all() and np.isfinite(self.mean.to_numpy()).all()):
            raise EstimationError("Moments: non-finite values")
        if not np.allclose(values, values.T):
            raise EstimationError("Moments: covariance matrix is not symmetric")

    @property
    def tickers(self) -> tuple[str, ...]:
        return tuple(self.mean.index)

    @property
    def volatilities(self) -> pd.Series:
        return pd.Series(np.sqrt(np.diag(self.covariance.to_numpy())), index=self.mean.index)


class ExpectedReturnEstimator(ABC):
    """Per-period expected return of every asset."""

    @abstractmethod
    def estimate(self, returns: ReturnPanel) -> pd.Series: ...


class CovarianceEstimator(ABC):
    """Per-period covariance matrix of asset returns."""

    @abstractmethod
    def estimate(self, returns: ReturnPanel) -> pd.DataFrame: ...


@dataclass(frozen=True, slots=True)
class HistoricalMean(ExpectedReturnEstimator):
    """Arithmetic mean of past returns."""

    def estimate(self, returns: ReturnPanel) -> pd.Series:
        return returns.returns.mean()


@dataclass(frozen=True, slots=True)
class SampleCovariance(CovarianceEstimator):
    """Unbiased sample covariance (``ddof=1``)."""

    ddof: int = 1

    def estimate(self, returns: ReturnPanel) -> pd.DataFrame:
        return returns.returns.cov(ddof=self.ddof)


@dataclass(frozen=True, slots=True)
class MomentEstimator:
    """Annualised moments from per-period returns: mean x k, covariance x k (k periods a year)."""

    mean: ExpectedReturnEstimator = field(default_factory=HistoricalMean)
    covariance: CovarianceEstimator = field(default_factory=SampleCovariance)
    periods_per_year: int = 252

    def estimate(self, returns: ReturnPanel) -> Moments:
        # Portfolio return is exactly w'r only for *simple* returns; log returns do not
        # aggregate across assets, so mean-variance must be fed simple returns.
        if returns.kind != ReturnKind.SIMPLE:
            raise EstimationError("Mean-variance analysis needs simple returns, got log returns")
        n_dates, n_assets = returns.returns.shape
        if n_dates <= n_assets:
            logger.warning(
                "%d dates for %d assets: the sample covariance will be singular", n_dates, n_assets
            )
        k = self.periods_per_year
        return Moments(
            mean=self.mean.estimate(returns) * k,
            covariance=self.covariance.estimate(returns) * k,
        )
