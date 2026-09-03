from __future__ import annotations

import math
from typing import Any


def population_stability_index(
    expected: list[float],
    actual: list[float],
    *,
    epsilon: float = 1e-6,
) -> float:
    """Compute PSI between two binned distributions."""
    if len(expected) != len(actual):
        raise ValueError("expected and actual must have same length")
    psi = 0.0
    for e, a in zip(expected, actual, strict=True):
        e_pct = max(e, epsilon)
        a_pct = max(a, epsilon)
        psi += (a_pct - e_pct) * math.log(a_pct / e_pct)
    return round(psi, 4)


def kolmogorov_smirnov_statistic(
    baseline: list[float],
    current: list[float],
) -> float:
    """Two-sample KS statistic (deterministic approximation via sorted merge)."""
    if not baseline or not current:
        return 0.0
    b_sorted = sorted(baseline)
    c_sorted = sorted(current)
    n, m = len(b_sorted), len(c_sorted)
    i = j = 0
    d_max = 0.0
    while i < n or j < m:
        if j >= m or (i < n and b_sorted[i] <= c_sorted[j]):
            val = b_sorted[i]
            i += 1
        else:
            val = c_sorted[j]
            j += 1
        fb = sum(1 for x in b_sorted if x <= val) / n
        fc = sum(1 for x in c_sorted if x <= val) / m
        d_max = max(d_max, abs(fb - fc))
    return round(d_max, 4)


def classify_problem_domain(signals: dict[str, Any]) -> str:
    """Classify root cause domain using statistical test outcomes."""
    if signals.get("infra_failure"):
        return "INFRASTRUCTURE"
    if signals.get("latency_spike") or signals.get("endpoint_errors"):
        return "INFRASTRUCTURE"
    if signals.get("feature_pipeline_failed"):
        return "DATA"
    if signals.get("drift_detected") or signals.get("null_spike"):
        return "DATA"
    if signals.get("calibration_issue") or signals.get("metric_degradation"):
        return "MODEL"
    if signals.get("business_distribution_shift"):
        return "BUSINESS-DISTRIBUTION"
    return "UNKNOWN"
