"""Exception hierarchy.

Every error raised on purpose by quen derives from ``QuenError``, so an application
boundary (CLI, web view) can catch the whole family with a single ``except``.
"""

from __future__ import annotations


class QuenError(Exception):
    """Base class for all errors raised by quen."""


class DataError(QuenError):
    """Base class for problems with input data."""


class DataSourceError(DataError):
    """A data source could not be read: missing file, missing table, I/O failure."""
