"""The optimiser interface and the portfolio it returns.

Every optimiser (closed-form today, long-only QP later) answers the same two questions,
so code that draws a frontier does not care which one it is talking to.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pandas as pd

    from quen.models.estimation import Moments


@dataclass(frozen=True, slots=True)
class Portfolio:
    """Weights plus their annualised expected return and volatility."""

    weights: pd.Series
    expected_return: float
    volatility: float

    @classmethod
    def from_weights(cls, weights: pd.Series, moments: Moments) -> Portfolio:
        w = weights.to_numpy()
        variance = float(w @ moments.covariance.to_numpy() @ w)
        return cls(
            weights=weights,
            expected_return=float(w @ moments.mean.to_numpy()),
            volatility=float(np.sqrt(max(variance, 0.0))),
        )

    @property
    def variance(self) -> float:
        return self.volatility**2

    @property
    def gross_exposure(self) -> float:
        """sum |w_i|: 1.0 means no short positions; 3.0 means 200% long / 100% short, etc."""
        return float(self.weights.abs().sum())


class PortfolioOptimizer(ABC):
    """Minimum-variance portfolios: the global one, and one for a given target return."""

    @abstractmethod
    def global_minimum_variance(self) -> Portfolio: ...

    @abstractmethod
    def minimum_variance(self, target_return: float) -> Portfolio: ...

    def efficient_frontier(self, max_return: float, n_points: int = 50) -> list[Portfolio]:
        """Efficient branch: from the GMV portfolio's return up to ``max_return``."""
        start = self.global_minimum_variance().expected_return
        targets = np.linspace(start, max(start, max_return), n_points)
        return [self.minimum_variance(float(m)) for m in targets]
