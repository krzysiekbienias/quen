"""Canonical data model (frozen dataclasses): the only language the layers speak.

Validation produces these objects; models, risk and analytics consume them.
"""

from quen.domain.prices import PricePanel, ReturnKind, ReturnPanel

__all__ = ["PricePanel", "ReturnKind", "ReturnPanel"]
