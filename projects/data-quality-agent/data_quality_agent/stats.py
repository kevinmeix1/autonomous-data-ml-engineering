from __future__ import annotations

from typing import Any

import numpy as np
from scipy import stats

from domain.enums import QualityDimension


def compute_psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index between two distributions."""
    expected = expected[~np.isnan(expected)]
    actual = actual[~np.isnan(actual)]
    if len(expected) == 0 or len(actual) == 0:
        return 0.0
    breakpoints = np.linspace(
        min(expected.min(), actual.min()),
        max(expected.max(), actual.max()),
        bins + 1,
    )
    if breakpoints[0] == breakpoints[-1]:
        return 0.0
    exp_pct = np.histogram(expected, bins=breakpoints)[0] / len(expected)
    act_pct = np.histogram(actual, bins=breakpoints)[0] / len(actual)
    exp_pct = np.clip(exp_pct, 1e-6, 1.0)
    act_pct = np.clip(act_pct, 1e-6, 1.0)
    return float(np.sum((act_pct - exp_pct) * np.log(act_pct / exp_pct)))


def compute_ks(expected: np.ndarray, actual: np.ndarray) -> tuple[float, float]:
    """Two-sample Kolmogorov-Smirnov test."""
    expected = expected[~np.isnan(expected)]
    actual = actual[~np.isnan(actual)]
    if len(expected) < 2 or len(actual) < 2:
        return 0.0, 1.0
    stat, pvalue = stats.ks_2samp(expected, actual)
    return float(stat), float(pvalue)


def detect_outliers_iqr(values: np.ndarray, k: float = 1.5) -> dict[str, Any]:
    """IQR-based outlier detection."""
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return {"outlier_count": 0, "outlier_rate": 0.0, "lower": 0.0, "upper": 0.0}
    q1, q3 = np.percentile(values, [25, 75])
    iqr = q3 - q1
    lower = q1 - k * iqr
    upper = q3 + k * iqr
    mask = (values < lower) | (values > upper)
    count = int(mask.sum())
    return {
        "outlier_count": count,
        "outlier_rate": round(count / len(values), 4),
        "lower": float(lower),
        "upper": float(upper),
    }


def profile_dimension(
    dimension: QualityDimension,
    profile: dict[str, Any],
    column: str,
) -> dict[str, Any]:
    """Map profile data to a quality dimension signal."""
    null_rates = profile.get("null_rates", {})
    distinct = profile.get("distinct_counts", {})
    row_count = profile.get("row_count", 0)
    freshness = profile.get("freshness_hours", 0)

    if dimension == QualityDimension.COMPLETENESS:
        rate = float(null_rates.get(column, 0.0))
        return {"null_rate": rate, "passed": rate < 0.1}
    if dimension == QualityDimension.UNIQUENESS:
        d = int(distinct.get(column, 0))
        dup_rate = 1 - (d / row_count) if row_count else 0
        return {"distinct_count": d, "duplicate_rate": round(dup_rate, 4), "passed": dup_rate < 0.01}
    if dimension == QualityDimension.FRESHNESS:
        return {"freshness_hours": freshness, "passed": freshness <= 24}
    if dimension == QualityDimension.VOLUME:
        return {"row_count": row_count, "passed": row_count > 0}
    return {"passed": True}
