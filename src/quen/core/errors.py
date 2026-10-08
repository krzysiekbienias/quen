"""Exception hierarchy.

Every error raised on purpose by quen derives from ``QuenError``, so an application
boundary (CLI, web view) can catch the whole family with a single ``except``.
"""

from __future__ import annotations


class QuenError(Exception):
    """Base class for all errors raised by quen."""


class DomainInvariantError(QuenError):
    """A domain object was built from data that breaks its invariants (a programming error:
    the validation layer should have caught it)."""


class DataError(QuenError):
    """Base class for problems with input data."""


class DataSourceError(DataError):
    """A data source could not be read: missing file, missing table, I/O failure."""


class DataValidationError(DataError):
    """Data was read but breaks a business rule. Carries the full validation report."""

    def __init__(self, message: str, report: object) -> None:
        super().__init__(message)
        self.report = report


class EstimationError(QuenError):
    """A statistical estimate could not be produced or is inconsistent."""


class NotPositiveDefiniteError(EstimationError):
    """Covariance matrix is not positive definite (collinear assets, or fewer dates than assets)."""


class OptimizationError(QuenError):
    """A portfolio optimisation failed."""


class DegenerateFrontierError(OptimizationError):
    """All assets have the same expected return (D = AC - B^2 = 0): no frontier to trace."""
