"""Markowitz with equality constraints only (short selling allowed): the Lagrangian closed form.

    min  1/2 w' S w     s.t.   w' mu = m,   w' 1 = 1

First-order condition:  S w = g mu + d 1   =>   w = g S^-1 mu + d S^-1 1.
With  A = 1'S^-1 1,  B = 1'S^-1 mu,  C = mu'S^-1 mu,  D = AC - B^2:

    w*(m)       = [ (C - B m) S^-1 1 + (A m - B) S^-1 mu ] / D
    sigma^2(m)  = (A m^2 - 2 B m + C) / D          (a hyperbola in the (sigma, m) plane)
    GMV         : w = S^-1 1 / A,  m = B / A,  sigma^2 = 1 / A

S^-1 is never formed: S is Cholesky-factorised once (which also proves it is positive
definite) and the two vectors S^-1 1 and S^-1 mu are obtained by triangular solves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from scipy.linalg import LinAlgError, cho_factor, cho_solve

from quen.core.errors import DegenerateFrontierError, NotPositiveDefiniteError
from quen.models.optimization.base import Portfolio, PortfolioOptimizer

if TYPE_CHECKING:
    from quen.models.estimation import Moments


@dataclass(frozen=True, slots=True)
class FrontierCoefficients:
    """The four scalars that define the whole unconstrained frontier."""

    a: float  # 1' S^-1 1
    b: float  # 1' S^-1 mu
    c: float  # mu' S^-1 mu
    d: float  # AC - B^2  (> 0 by Cauchy-Schwarz unless mu is constant)

    def variance(self, target_return: float) -> float:
        m = target_return
        return (self.a * m * m - 2.0 * self.b * m + self.c) / self.d


@dataclass(frozen=True, slots=True)
class ClosedFormMeanVariance(PortfolioOptimizer):
    """Exact mean-variance frontier when weights may be negative (shorting allowed)."""

    moments: Moments
    coefficients: FrontierCoefficients = field(init=False)
    _inv_ones: np.ndarray = field(init=False, repr=False)  # S^-1 1
    _inv_mu: np.ndarray = field(init=False, repr=False)  # S^-1 mu

    def __post_init__(self) -> None:
        sigma = self.moments.covariance.to_numpy()
        mu = self.moments.mean.to_numpy()
        ones = np.ones_like(mu)
        try:
            factor = cho_factor(sigma)
        except LinAlgError as exc:
            raise NotPositiveDefiniteError(
                "Covariance matrix is not positive definite: Cholesky failed"
            ) from exc
        inv_ones = cho_solve(factor, ones)
        inv_mu = cho_solve(factor, mu)

        a, b, c = float(ones @ inv_ones), float(ones @ inv_mu), float(mu @ inv_mu)
        d = a * c - b * b
        if d <= 1e-12 * a * c:
            raise DegenerateFrontierError(
                "All expected returns are (almost) equal: D = AC - B^2 = 0"
            )

        object.__setattr__(self, "coefficients", FrontierCoefficients(a, b, c, d))
        object.__setattr__(self, "_inv_ones", inv_ones)
        object.__setattr__(self, "_inv_mu", inv_mu)

    def global_minimum_variance(self) -> Portfolio:
        return self._portfolio(self._inv_ones / self.coefficients.a)

    def minimum_variance(self, target_return: float) -> Portfolio:
        k, m = self.coefficients, target_return
        weights = ((k.c - k.b * m) * self._inv_ones + (k.a * m - k.b) * self._inv_mu) / k.d
        return self._portfolio(weights)

    def _portfolio(self, weights: np.ndarray) -> Portfolio:
        return Portfolio.from_weights(
            pd.Series(weights, index=self.moments.mean.index), self.moments
        )
