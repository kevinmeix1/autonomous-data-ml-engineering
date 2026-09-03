from __future__ import annotations

import random
import statistics
from typing import Any

from domain.enums import ActionRisk
from ml_doctor.diagnostics import (
    classify_problem_domain,
    kolmogorov_smirnov_statistic,
    population_stability_index,
)
from pydantic import BaseModel, Field
from tool_sdk.base import BaseTool, ToolContext, ToolError


class ModelMetricsInput(BaseModel):
    model_id: str


class ModelMetricsOutput(BaseModel):
    model_id: str
    name: str
    version: str
    stage: str
    metrics: dict[str, float]
    mode: str
    endpoint: str | None = None
    degradation_detected: bool = False


class FeatureDistributionsInput(BaseModel):
    model_id: str
    feature_names: list[str] | None = None


class FeatureDistribution(BaseModel):
    feature: str
    mean: float
    std: float
    min_val: float
    max_val: float
    null_rate: float
    histogram: list[float]


class FeatureDistributionsOutput(BaseModel):
    model_id: str
    distributions: list[FeatureDistribution]


class DetectDriftInput(BaseModel):
    model_id: str
    feature: str
    method: str = "both"  # psi | ks | both


class DriftResult(BaseModel):
    feature: str
    psi: float | None = None
    ks_statistic: float | None = None
    drift_detected: bool
    threshold_psi: float = 0.2
    threshold_ks: float = 0.1
    method: str


class DetectDriftOutput(BaseModel):
    model_id: str
    results: list[DriftResult]
    any_drift: bool


class InferenceStatsInput(BaseModel):
    model_id: str
    hours: int = 24


class InferenceStatsOutput(BaseModel):
    model_id: str
    mode: str
    request_count: int
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    error_rate: float
    avg_score: float
    latency_anomaly: bool


class FeaturePipelineInput(BaseModel):
    model_id: str


class FeaturePipelineOutput(BaseModel):
    model_id: str
    features: list[str]
    pipeline_healthy: bool
    failed_tasks: list[str]
    stale_features: list[str]
    last_success_at: str | None = None


class DiagnoseIncidentInput(BaseModel):
    model_id: str
    objective: str = ""


class DiagnoseIncidentOutput(BaseModel):
    model_id: str
    problem_domain: str
    confidence: float
    signals: dict[str, Any]
    statistical_tests: list[dict[str, Any]]
    summary: str


class RecommendActionInput(BaseModel):
    model_id: str
    problem_domain: str


class RecommendActionOutput(BaseModel):
    model_id: str
    problem_domain: str
    recommended_actions: list[dict[str, str]]
    urgency: str


def _get_model(store: Any, model_id: str) -> Any:
    platform = store.require()
    model = next((m for m in platform.models if m.model_id == model_id), None)
    if not model:
        raise ToolError(f"Model not found: {model_id}", code="NOT_FOUND")
    return model


def _feature_bins(feature: str, seed: int) -> tuple[list[float], list[float]]:
    rng = random.Random(hash((feature, seed)) & 0xFFFFFFFF)
    baseline = [rng.uniform(0.05, 0.25) for _ in range(10)]
    total = sum(baseline)
    baseline = [b / total for b in baseline]
    current = list(baseline)
    # inject drift for avg_incurred_12m
    if "incurred" in feature:
        current[8] += 0.08
        current[2] -= 0.04
    total = sum(current)
    current = [c / total for c in current]
    return baseline, current


def build_ml_doctor_tools(store: Any) -> list[BaseTool[Any, Any]]:
    class GetModelMetrics(BaseTool[ModelMetricsInput, ModelMetricsOutput]):
        name = "get_model_metrics"
        description = "Get ML model training and validation metrics"
        risk = ActionRisk.READ_ONLY
        input_model = ModelMetricsInput
        output_model = ModelMetricsOutput

        def _execute(self, args: ModelMetricsInput, context: ToolContext) -> ModelMetricsOutput:
            model = _get_model(store, args.model_id)
            metrics = dict(model.metrics)
            auc_now = metrics.get("auc", 0.0)
            auc_prev = metrics.get("auc_7d_ago", auc_now)
            degradation = (auc_prev - auc_now) > 0.02 or metrics.get("calibration_ece", 0) > 0.08
            return ModelMetricsOutput(
                model_id=model.model_id,
                name=model.name,
                version=model.version,
                stage=model.stage,
                metrics=metrics,
                mode=model.mode,
                endpoint=model.endpoint,
                degradation_detected=degradation,
            )

    class GetFeatureDistributions(BaseTool[FeatureDistributionsInput, FeatureDistributionsOutput]):
        name = "get_feature_distributions"
        description = "Get feature distribution statistics for a model"
        risk = ActionRisk.READ_ONLY
        input_model = FeatureDistributionsInput
        output_model = FeatureDistributionsOutput

        def _execute(
            self, args: FeatureDistributionsInput, context: ToolContext
        ) -> FeatureDistributionsOutput:
            model = _get_model(store, args.model_id)
            platform = store.require()
            features = args.feature_names or model.features
            dists: list[FeatureDistribution] = []
            seed = platform.seed
            for feat in features:
                rng = random.Random(hash((feat, seed)) & 0xFFFFFFFF)
                samples = [rng.gauss(100, 30) for _ in range(500)]
                null_rate = 0.02 if "days" in feat else 0.01
                hist, _ = _histogram(samples, bins=10)
                dists.append(
                    FeatureDistribution(
                        feature=feat,
                        mean=round(statistics.fmean(samples), 2),
                        std=round(statistics.pstdev(samples), 2),
                        min_val=round(min(samples), 2),
                        max_val=round(max(samples), 2),
                        null_rate=null_rate,
                        histogram=hist,
                    )
                )
            return FeatureDistributionsOutput(model_id=args.model_id, distributions=dists)

    class DetectDrift(BaseTool[DetectDriftInput, DetectDriftOutput]):
        name = "detect_drift"
        description = "Detect feature drift using PSI and/or KS tests"
        risk = ActionRisk.READ_ONLY
        input_model = DetectDriftInput
        output_model = DetectDriftOutput

        def _execute(self, args: DetectDriftInput, context: ToolContext) -> DetectDriftOutput:
            platform = store.require()
            baseline, current = _feature_bins(args.feature, platform.seed)
            psi_val = ks_val = None
            drift = False
            if args.method in {"psi", "both"}:
                psi_val = population_stability_index(baseline, current)
                drift = drift or psi_val > 0.2
            if args.method in {"ks", "both"}:
                rng = random.Random(hash(args.feature) & 0xFFFFFFFF)
                b_samples = [rng.gauss(100, 25) for _ in range(200)]
                c_samples = [rng.gauss(115, 30) for _ in range(200)] if "incurred" in args.feature else b_samples
                ks_val = kolmogorov_smirnov_statistic(b_samples, c_samples)
                drift = drift or ks_val > 0.1
            result = DriftResult(
                feature=args.feature,
                psi=psi_val,
                ks_statistic=ks_val,
                drift_detected=drift,
                method=args.method,
            )
            return DetectDriftOutput(
                model_id=args.model_id,
                results=[result],
                any_drift=drift,
            )

    class GetInferenceStats(BaseTool[InferenceStatsInput, InferenceStatsOutput]):
        name = "get_inference_stats"
        description = "Get SageMaker/inference endpoint latency and error stats"
        risk = ActionRisk.READ_ONLY
        input_model = InferenceStatsInput
        output_model = InferenceStatsOutput

        def _execute(self, args: InferenceStatsInput, context: ToolContext) -> InferenceStatsOutput:
            model = _get_model(store, args.model_id)
            platform = store.require()
            rng = random.Random(hash((args.model_id, platform.seed)) & 0xFFFFFFFF)
            latencies = [
                float(m["value"])
                for m in platform.cloudwatch_metrics
                if m.get("metric") == "TaskDuration"
            ][: args.hours]
            if not latencies:
                latencies = [rng.uniform(50, 200) for _ in range(args.hours)]
            latencies_sorted = sorted(latencies)
            n = len(latencies_sorted)
            p50 = latencies_sorted[n // 2]
            p95 = latencies_sorted[int(n * 0.95)] if n > 1 else latencies_sorted[0]
            p99 = latencies_sorted[int(n * 0.99)] if n > 1 else latencies_sorted[0]
            error_rate = 0.02 if model.metrics.get("auc", 1) < model.metrics.get("auc_7d_ago", 1) else 0.001
            avg = statistics.fmean(latencies_sorted)
            latency_anomaly = p95 > avg * 2.5
            return InferenceStatsOutput(
                model_id=args.model_id,
                mode=model.mode,
                request_count=rng.randint(5000, 50000),
                p50_latency_ms=round(p50, 1),
                p95_latency_ms=round(p95, 1),
                p99_latency_ms=round(p99, 1),
                error_rate=round(error_rate, 4),
                avg_score=round(model.metrics.get("auc", 0.8), 3),
                latency_anomaly=latency_anomaly,
            )

    class GetFeaturePipelineStatus(BaseTool[FeaturePipelineInput, FeaturePipelineOutput]):
        name = "get_feature_pipeline_status"
        description = "Monitor feature pipeline health for a model"
        risk = ActionRisk.READ_ONLY
        input_model = FeaturePipelineInput
        output_model = FeaturePipelineOutput

        def _execute(self, args: FeaturePipelineInput, context: ToolContext) -> FeaturePipelineOutput:
            model = _get_model(store, args.model_id)
            platform = store.require()
            dag = next((d for d in platform.dags if d.dag_id == "insurance_daily_pipeline"), None)
            failed: list[str] = []
            stale: list[str] = []
            if dag:
                failed = [t.task_id for t in dag.tasks if t.status.value == "failed" and "feature" in t.task_id]
                if any(t.task_id == "feature_build" and t.status.value == "failed" for t in dag.tasks):
                    stale = list(model.features)
            profile = platform.data_profiles.get(model.training_table, {})
            freshness = profile.get("freshness_hours", 0)
            if freshness > 24:
                stale.extend(model.features)
            healthy = not failed and not stale
            last_run = dag.last_run_at.isoformat() if dag and dag.last_run_at else None
            return FeaturePipelineOutput(
                model_id=args.model_id,
                features=model.features,
                pipeline_healthy=healthy,
                failed_tasks=failed,
                stale_features=list(set(stale)),
                last_success_at=last_run,
            )

    class DiagnoseIncident(BaseTool[DiagnoseIncidentInput, DiagnoseIncidentOutput]):
        name = "diagnose_incident"
        description = "Diagnose ML incident using statistical tests and platform signals"
        risk = ActionRisk.READ_ONLY
        input_model = DiagnoseIncidentInput
        output_model = DiagnoseIncidentOutput

        def _execute(self, args: DiagnoseIncidentInput, context: ToolContext) -> DiagnoseIncidentOutput:
            model = _get_model(store, args.model_id)
            platform = store.require()
            signals: dict[str, Any] = {}
            tests: list[dict[str, Any]] = []

            auc_now = model.metrics.get("auc", 0)
            auc_prev = model.metrics.get("auc_7d_ago", auc_now)
            signals["metric_degradation"] = (auc_prev - auc_now) > 0.02
            tests.append({"test": "auc_delta", "value": auc_prev - auc_now, "threshold": 0.02})

            ece = model.metrics.get("calibration_ece", 0)
            signals["calibration_issue"] = ece > 0.06
            tests.append({"test": "calibration_ece", "value": ece, "threshold": 0.06})

            for feat in model.features[:2]:
                baseline, current = _feature_bins(feat, platform.seed)
                psi = population_stability_index(baseline, current)
                drift = psi > 0.2
                signals["drift_detected"] = signals.get("drift_detected", False) or drift
                tests.append({"test": f"psi_{feat}", "value": psi, "threshold": 0.2, "drift": drift})

            dag = platform.dags[0] if platform.dags else None
            signals["feature_pipeline_failed"] = bool(
                dag and any(t.task_id == "feature_build" and t.status.value == "failed" for t in dag.tasks)
            )
            signals["infra_failure"] = bool(
                dag and any(t.task_id == "score_claims_model" and t.status.value == "failed" for t in dag.tasks)
            )

            profile = platform.data_profiles.get("RAW.CLAIM.claims", {})
            null_rate = profile.get("null_rates", {}).get("incurred_amount", 0)
            signals["null_spike"] = null_rate > 0.15
            tests.append({"test": "null_rate_incurred_amount", "value": null_rate, "threshold": 0.15})

            if "business" in args.objective.lower() or "distribution" in args.objective.lower():
                signals["business_distribution_shift"] = True

            domain = classify_problem_domain(signals)
            confidence = 0.85 if sum(1 for v in signals.values() if v) >= 2 else 0.6
            summary = (
                f"Model {model.name} ({domain}): "
                + ", ".join(k for k, v in signals.items() if v)
                or "no strong signals"
            )
            return DiagnoseIncidentOutput(
                model_id=args.model_id,
                problem_domain=domain,
                confidence=confidence,
                signals=signals,
                statistical_tests=tests,
                summary=summary,
            )

    class RecommendAction(BaseTool[RecommendActionInput, RecommendActionOutput]):
        name = "recommend_action"
        description = "Recommend remediation actions based on problem domain"
        risk = ActionRisk.READ_ONLY
        input_model = RecommendActionInput
        output_model = RecommendActionOutput

        def _execute(self, args: RecommendActionInput, context: ToolContext) -> RecommendActionOutput:
            actions_map = {
                "DATA": [
                    {"action": "investigate_feature_pipeline", "agent": "pipeline_sre"},
                    {"action": "run_data_quality_checks", "agent": "data_quality"},
                    {"action": "refresh_feature_store", "agent": "feature_engineering"},
                ],
                "MODEL": [
                    {"action": "trigger_retraining", "agent": "retraining"},
                    {"action": "recalibrate_model", "agent": "ml_doctor"},
                ],
                "INFRASTRUCTURE": [
                    {"action": "check_endpoint_health", "agent": "pipeline_sre"},
                    {"action": "scale_inference", "agent": "pipeline_sre"},
                ],
                "BUSINESS-DISTRIBUTION": [
                    {"action": "analyze_portfolio_shift", "agent": "lineage_copilot"},
                    {"action": "evaluate_champion_challenger", "agent": "retraining"},
                ],
            }
            actions = actions_map.get(
                args.problem_domain,
                [{"action": "full_diagnostic", "agent": "ml_doctor"}],
            )
            urgency = "HIGH" if args.problem_domain in {"DATA", "INFRASTRUCTURE"} else "MEDIUM"
            return RecommendActionOutput(
                model_id=args.model_id,
                problem_domain=args.problem_domain,
                recommended_actions=actions,
                urgency=urgency,
            )

    return [
        GetModelMetrics(),
        GetFeatureDistributions(),
        DetectDrift(),
        GetInferenceStats(),
        GetFeaturePipelineStatus(),
        DiagnoseIncident(),
        RecommendAction(),
    ]


def _histogram(values: list[float], bins: int = 10) -> tuple[list[float], list[float]]:
    if not values:
        return [0.0] * bins, list(range(bins))
    mn, mx = min(values), max(values)
    if mx == mn:
        return [1.0] + [0.0] * (bins - 1), [mn] * bins
    step = (mx - mn) / bins
    counts = [0] * bins
    for v in values:
        idx = min(int((v - mn) / step), bins - 1)
        counts[idx] += 1
    total = sum(counts)
    return [round(c / total, 4) for c in counts], [mn + i * step for i in range(bins)]
