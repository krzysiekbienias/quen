"""Raw closes -> validated ``PricePanel`` plus a report of everything that was found or changed."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, NoReturn

from quen.core.errors import DataValidationError
from quen.domain import PricePanel
from quen.validation.alignment import DropIncompleteDates, MissingDataPolicy, common_window
from quen.validation.normalize import to_wide
from quen.validation.report import Issue, Severity, ValidationReport
from quen.validation.rules import ValidationRule, default_rules

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ValidatedPrices:
    panel: PricePanel
    report: ValidationReport


@dataclass(frozen=True, slots=True)
class PriceValidator:
    """Configurable pipeline: structure -> rules -> common window -> missing-data policy."""

    rules: tuple[ValidationRule, ...] = field(default_factory=default_rules)
    missing_data: MissingDataPolicy = field(default_factory=DropIncompleteDates)
    min_observations: int = 60

    def validate(self, raw: pd.DataFrame) -> ValidatedPrices:
        """Raises ``DataValidationError`` (carrying the report) if any rule finds an error."""
        wide, issues = to_wide(raw)
        if _has_errors(issues):
            self._fail(issues)

        for rule in self.rules:
            issues += rule.check(wide)

        window, window_issues = common_window(wide)
        issues += window_issues
        if _has_errors(issues):
            self._fail(issues)

        clean, policy_issues = self.missing_data.apply(window)
        issues += policy_issues
        if len(clean) < self.min_observations:
            issues.append(
                Issue(
                    "min_observations",
                    Severity.ERROR,
                    f"{len(clean)} clean date(s), at least {self.min_observations} required",
                )
            )
            self._fail(issues)

        report = ValidationReport(tuple(issues))
        for issue in report.warnings:
            logger.warning("%s", issue)
        logger.info(
            "Validated %d tickers x %d dates (%s -> %s)",
            clean.shape[1],
            len(clean),
            f"{clean.index.min():%Y-%m-%d}",
            f"{clean.index.max():%Y-%m-%d}",
        )
        return ValidatedPrices(PricePanel(clean), report)

    @staticmethod
    def _fail(issues: list[Issue]) -> NoReturn:
        report = ValidationReport(tuple(issues))
        raise DataValidationError(
            f"Price validation failed with {len(report.errors)} error(s):\n{report}", report
        )


def _has_errors(issues: list[Issue]) -> bool:
    return any(i.severity == Severity.ERROR for i in issues)
