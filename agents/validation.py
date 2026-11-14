"""Validation helpers shared by the agents and the API schemas."""

import math


def require_finite(value: float, message: str) -> float:
    """Return ``value`` unchanged, or raise ``ValueError(message)`` for NaN and infinity.

    pydantic accepts NaN, inf and -inf for a float field, and every comparison
    with NaN is False, so ``v == 0`` and ``v <= 0`` let it through. NaN then
    fails at the database (SQLite stores it as NULL) and infinity is stored as
    a value that breaks every sum. Call this first in a validator so the
    "must be a finite number" message wins over "must not be zero" and
    "must be positive".
    """
    if not math.isfinite(value):
        raise ValueError(message)
    return value
