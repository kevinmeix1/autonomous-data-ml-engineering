from __future__ import annotations

from typing import Any

import numpy as np
from domain.enums import ActionRisk, QualityDimension
from pydantic import BaseModel, Field
from tool_sdk.base import BaseTool, ToolContext, ToolError

from data_quality_agent.stats import compute_ks, compute_psi, detect_outliers_iqr, profile_dimension


class ProfileTableInput(BaseModel):
    table_id: str


class ProfileTableOutput(BaseModel):
    table_id: str
    profile: dict[str, Any]
    dimensions: dict[str, dict[str, Any]]


class HistoricalDistributionInput(BaseModel):
    table_id: str
    column: str


class HistoricalDistributionOutput(BaseModel):
    table_id: str
    column: str
    current_null_rate: float
    historical_null_rates: list[float]
    historical_mean: float
    historical_std: float


class GetLineageInput(BaseModel):
    node_id: str


class GetLineageOutput(BaseModel):
    upstream: list[dict[str, Any]]
    downstream: list[dict[str, Any]]


class UpstreamChangesInput(BaseModel):
    table_id: str


class UpstreamChangesOutput(BaseModel):
    table_id: str
    schema_versions: list[dict[str, Any]]
    recent_changes: list[str]


class ComputePsiInput(BaseModel):
    table_id: str
    column: str


class ComputePsiOutput(BaseModel):
    table_id: str
    column: str
    psi: float
    threshold: float = 0.2
    is_drift: bool


class ComputeKsInput(BaseModel):
    table_id: str
    column: str


class ComputeKsOutput(BaseModel):
    table_id: str
    column: str
    ks_statistic: float
    p_value: float
    is_significant: bool


class DetectOutliersInput(BaseModel):
    table_id: str
    column: str


class DetectOutliersOutput(BaseModel):
    table_id: str
    column: str
    outlier_count: int
    outlier_rate: float
    lower: float
    upper: float


class HypothesisTestInput(BaseModel):
    hypothesis: str
    table_id: str
    column: str


class HypothesisTestOutput(BaseModel):
    hypothesis: str
    supported: bool
    confidence: float
    evidence: dict[str, Any]


def _column_series(profile: dict[str, Any], column: str) -> tuple[np.ndarray, np.ndarray]:
    """Build synthetic current/historical arrays from profile metadata."""
    rng = np.random.default_rng(abs(hash(column)) % (2**32))
    hist_rates = profile.get("historical_null_rates", {}).get(column, [0.02] * 14)
    historical = rng.normal(loc=np.mean(hist_rates), scale=0.01, size=500)
    current_rate = float(profile.get("null_rates", {}).get(column, 0.02))
    current = rng.normal(loc=current_rate, scale=0.01, size=500)
    return historical, current


def build_dq_tools(store: Any) -> list[BaseTool[Any, Any]]:
    class ProfileTable(BaseTool[ProfileTableInput, ProfileTableOutput]):
        name = "profile_table"
        description = "Profile a table across DQ dimensions"
        risk = ActionRisk.READ_ONLY
        input_model = ProfileTableInput
        output_model = ProfileTableOutput

        def _execute(self, args: ProfileTableInput, context: ToolContext) -> ProfileTableOutput:
            profile = store.require().data_profiles.get(args.table_id)
            if profile is None:
                raise ToolError(f"Profile not found: {args.table_id}", code="NOT_FOUND")
            dims = {}
            for dim in QualityDimension:
                col = "incurred_amount" if "claim" in args.table_id.lower() else "id"
                dims[dim.value] = profile_dimension(dim, profile, col)
            return ProfileTableOutput(table_id=args.table_id, profile=profile, dimensions=dims)

    class GetHistoricalDistribution(BaseTool[HistoricalDistributionInput, HistoricalDistributionOutput]):
        name = "get_historical_distribution"
        description = "Compare current vs historical column distribution"
        risk = ActionRisk.READ_ONLY
        input_model = HistoricalDistributionInput
        output_model = HistoricalDistributionOutput

        def _execute(
            self, args: HistoricalDistributionInput, context: ToolContext
        ) -> HistoricalDistributionOutput:
            profile = store.require().data_profiles.get(args.table_id)
            if profile is None:
                raise ToolError("Profile not found", code="NOT_FOUND")
            hist = [float(x) for x in profile.get("historical_null_rates", {}).get(args.column, [])]
            current = float(profile.get("null_rates", {}).get(args.column, 0.0))
            mean = float(np.mean(hist)) if hist else 0.0
            std = float(np.std(hist)) if len(hist) > 1 else 0.01
            return HistoricalDistributionOutput(
                table_id=args.table_id,
                column=args.column,
                current_null_rate=current,
                historical_null_rates=hist,
                historical_mean=mean,
                historical_std=std,
            )

    class GetLineage(BaseTool[GetLineageInput, GetLineageOutput]):
        name = "get_lineage"
        description = "Get upstream/downstream lineage for a table or model"
        risk = ActionRisk.READ_ONLY
        input_model = GetLineageInput
        output_model = GetLineageOutput

        def _execute(self, args: GetLineageInput, context: ToolContext) -> GetLineageOutput:
            return GetLineageOutput(
                upstream=store.lineage.upstream(args.node_id),
                downstream=store.lineage.downstream(args.node_id),
            )

    class GetUpstreamChanges(BaseTool[UpstreamChangesInput, UpstreamChangesOutput]):
        name = "get_upstream_changes"
        description = "Detect recent upstream schema changes"
        risk = ActionRisk.READ_ONLY
        input_model = UpstreamChangesInput
        output_model = UpstreamChangesOutput

        def _execute(self, args: UpstreamChangesInput, context: ToolContext) -> UpstreamChangesOutput:
            versions = [
                v.model_dump(mode="json")
                for v in store.require().schema_versions
                if v.table_id == args.table_id
            ]
            versions.sort(key=lambda v: v["version"], reverse=True)
            changes = [v["change_summary"] for v in versions[:3]]
            return UpstreamChangesOutput(
                table_id=args.table_id,
                schema_versions=versions,
                recent_changes=changes,
            )

    class ComputePsiTool(BaseTool[ComputePsiInput, ComputePsiOutput]):
        name = "compute_psi"
        description = "Compute Population Stability Index for column drift"
        risk = ActionRisk.READ_ONLY
        input_model = ComputePsiInput
        output_model = ComputePsiOutput

        def _execute(self, args: ComputePsiInput, context: ToolContext) -> ComputePsiOutput:
            profile = store.require().data_profiles.get(args.table_id)
            if profile is None:
                raise ToolError("Profile not found", code="NOT_FOUND")
            expected, actual = _column_series(profile, args.column)
            psi = compute_psi(expected, actual)
            return ComputePsiOutput(
                table_id=args.table_id,
                column=args.column,
                psi=round(psi, 4),
                is_drift=psi > 0.2,
            )

    class ComputeKsTool(BaseTool[ComputeKsInput, ComputeKsOutput]):
        name = "compute_ks_test"
        description = "Run two-sample Kolmogorov-Smirnov test"
        risk = ActionRisk.READ_ONLY
        input_model = ComputeKsInput
        output_model = ComputeKsOutput

        def _execute(self, args: ComputeKsInput, context: ToolContext) -> ComputeKsOutput:
            profile = store.require().data_profiles.get(args.table_id)
            if profile is None:
                raise ToolError("Profile not found", code="NOT_FOUND")
            expected, actual = _column_series(profile, args.column)
            ks_stat, p_value = compute_ks(expected, actual)
            return ComputeKsOutput(
                table_id=args.table_id,
                column=args.column,
                ks_statistic=round(ks_stat, 4),
                p_value=round(p_value, 6),
                is_significant=p_value < 0.05,
            )

    class DetectOutliers(BaseTool[DetectOutliersInput, DetectOutliersOutput]):
        name = "detect_outliers"
        description = "IQR-based outlier detection on column distribution"
        risk = ActionRisk.READ_ONLY
        input_model = DetectOutliersInput
        output_model = DetectOutliersOutput

        def _execute(self, args: DetectOutliersInput, context: ToolContext) -> DetectOutliersOutput:
            profile = store.require().data_profiles.get(args.table_id)
            if profile is None:
                raise ToolError("Profile not found", code="NOT_FOUND")
            _, actual = _column_series(profile, args.column)
            result = detect_outliers_iqr(actual)
            return DetectOutliersOutput(
                table_id=args.table_id,
                column=args.column,
                outlier_count=result["outlier_count"],
                outlier_rate=result["outlier_rate"],
                lower=result["lower"],
                upper=result["upper"],
            )

    class HypothesisTest(BaseTool[HypothesisTestInput, HypothesisTestOutput]):
        name = "hypothesis_test"
        description = "Test a DQ hypothesis using statistical tools"
        risk = ActionRisk.READ_ONLY
        input_model = HypothesisTestInput
        output_model = HypothesisTestOutput

        def _execute(self, args: HypothesisTestInput, context: ToolContext) -> HypothesisTestOutput:
            profile = store.require().data_profiles.get(args.table_id)
            if profile is None:
                raise ToolError("Profile not found", code="NOT_FOUND")
            expected, actual = _column_series(profile, args.column)
            psi = compute_psi(expected, actual)
            ks_stat, p_value = compute_ks(expected, actual)
            outliers = detect_outliers_iqr(actual)
            supported = False
            confidence = 0.5
            if "drift" in args.hypothesis.lower():
                supported = psi > 0.2 or p_value < 0.05
                confidence = min(0.95, 0.5 + psi)
            elif "null" in args.hypothesis.lower():
                current = float(profile.get("null_rates", {}).get(args.column, 0))
                hist = profile.get("historical_null_rates", {}).get(args.column, [0.02])
                z = abs(current - np.mean(hist)) / (np.std(hist) or 0.01)
                supported = z > 3
                confidence = min(0.99, 0.5 + z / 10)
            elif "outlier" in args.hypothesis.lower():
                supported = outliers["outlier_rate"] > 0.05
                confidence = 0.6 + outliers["outlier_rate"]
            evidence = {
                "psi": round(psi, 4),
                "ks_statistic": round(ks_stat, 4),
                "p_value": round(p_value, 6),
                "outlier_rate": outliers["outlier_rate"],
            }
            return HypothesisTestOutput(
                hypothesis=args.hypothesis,
                supported=supported,
                confidence=round(confidence, 3),
                evidence=evidence,
            )

    return [
        ProfileTable(),
        GetHistoricalDistribution(),
        GetLineage(),
        GetUpstreamChanges(),
        ComputePsiTool(),
        ComputeKsTool(),
        DetectOutliers(),
        HypothesisTest(),
    ]
