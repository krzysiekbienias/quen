"""Validation findings: what was wrong with the data and how bad it is."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    ERROR = "error"  # data cannot be used; the pipeline stops
    WARNING = "warning"  # data was usable but something was changed or looks suspicious


@dataclass(frozen=True, slots=True)
class Issue:
    rule: str
    severity: Severity
    message: str
    tickers: tuple[str, ...] = ()

    def __str__(self) -> str:
        where = f" [{', '.join(self.tickers)}]" if self.tickers else ""
        return f"{self.severity.upper()} {self.rule}: {self.message}{where}"


@dataclass(frozen=True, slots=True)
class ValidationReport:
    issues: tuple[Issue, ...] = ()

    @property
    def errors(self) -> tuple[Issue, ...]:
        return tuple(i for i in self.issues if i.severity == Severity.ERROR)

    @property
    def warnings(self) -> tuple[Issue, ...]:
        return tuple(i for i in self.issues if i.severity == Severity.WARNING)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    def __str__(self) -> str:
        return "\n".join(str(i) for i in self.issues) if self.issues else "no issues"
