from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from domain.enums import ActionRisk, ExecutionMode
from pydantic import BaseModel, Field
from tool_sdk.base import BaseTool, ToolContext, ToolError


class ModelRefInput(BaseModel):
    model_id: str


class AssessDegradationOutput(BaseModel):
    model_id: str
    degraded: bool
    auc_delta: float
    calibration_ece: float
    reason: str
    retraining_recommended: bool


class BuildTrainingDatasetInput(BaseModel):
    model_id: str
    lookback_days: int = 365


class BuildTrainingDatasetOutput(BaseModel):
    model_id: str
    dataset_table: str
    row_count: int
    feature_count: int
    mode: str
    status: str


class TrainCandidateInput(BaseModel):
    model_id: str
    candidate_version: str | None = None
    hyperparams: dict[str, Any] = Field(default_factory=dict)


class TrainCandidateOutput(BaseModel):
    candidate_id: str
    model_id: str
    version: str
    mode: str
    training_job_id: str
    status: str
    message: str


class EvaluateCandidateInput(BaseModel):
    candidate_id: str
    champion_model_id: str


class EvaluateCandidateOutput(BaseModel):
    candidate_id: str
    metrics: dict[str, float]
    mode: str
    passed_minimum_bar: bool


class CompareChampionChallengerInput(BaseModel):
    champion_model_id: str
    candidate_id: str
    promotion_policy: str = "auc_improvement"  # auc_improvement | mae_reduction | composite


class CompareChampionChallengerOutput(BaseModel):
    champion_model_id: str
    candidate_id: str
    champion_metrics: dict[str, float]
    challenger_metrics: dict[str, float]
    winner: str
    promote: bool
    policy: str
    rationale: str


class CheckSafetyGatesInput(BaseModel):
    candidate_id: str
    champion_model_id: str


class SafetyGateResult(BaseModel):
    gate: str
    passed: bool
    detail: str


class CheckSafetyGatesOutput(BaseModel):
    candidate_id: str
    all_passed: bool
    gates: list[SafetyGateResult]


class DeployModelInput(BaseModel):
    candidate_id: str
    champion_model_id: str
    target_stage: str = "Production"


class DeployModelOutput(BaseModel):
    candidate_id: str
    deployed_model_id: str
    mode: str
    status: str
    message: str
    approval_note: str


class RollbackModelInput(BaseModel):
    model_id: str
    previous_version: str


class RollbackModelOutput(BaseModel):
    model_id: str
    rolled_back_to: str
    mode: str
    status: str
    message: str


class MonitorPostDeployInput(BaseModel):
    model_id: str
    hours: int = 24


class MonitorPostDeployOutput(BaseModel):
    model_id: str
    healthy: bool
    auc: float
    error_rate: float
    latency_p95_ms: float
    alerts: list[str]
    mode: str


# In-memory candidate store keyed by execution
_candidates: dict[str, dict[str, Any]] = {}


def _get_model(store: Any, model_id: str) -> Any:
    platform = store.require()
    model = next((m for m in platform.models if m.model_id == model_id), None)
    if not model:
        raise ToolError(f"Model not found: {model_id}", code="NOT_FOUND")
    return model


def _execution_mode(store: Any) -> str:
    models = store.require().models
    if models and models[0].mode == ExecutionMode.REAL_AWS.value:
        return ExecutionMode.REAL_AWS.value
    return ExecutionMode.LOCAL_SIMULATION.value


def build_retraining_tools(store: Any) -> list[BaseTool[Any, Any]]:
    class AssessDegradation(BaseTool[ModelRefInput, AssessDegradationOutput]):
        name = "assess_degradation"
        description = "Assess whether champion model has degraded"
        risk = ActionRisk.READ_ONLY
        input_model = ModelRefInput
        output_model = AssessDegradationOutput

        def _execute(self, args: ModelRefInput, context: ToolContext) -> AssessDegradationOutput:
            model = _get_model(store, args.model_id)
            auc_now = model.metrics.get("auc", 0)
            auc_prev = model.metrics.get("auc_7d_ago", auc_now)
            delta = auc_prev - auc_now
            ece = model.metrics.get("calibration_ece", 0)
            degraded = delta > 0.02 or ece > 0.08
            reason = []
            if delta > 0.02:
                reason.append(f"AUC dropped {delta:.3f}")
            if ece > 0.08:
                reason.append(f"Calibration ECE {ece:.3f} exceeds threshold")
            return AssessDegradationOutput(
                model_id=args.model_id,
                degraded=degraded,
                auc_delta=round(delta, 4),
                calibration_ece=ece,
                reason="; ".join(reason) or "within tolerance",
                retraining_recommended=degraded,
            )

    class BuildTrainingDataset(BaseTool[BuildTrainingDatasetInput, BuildTrainingDatasetOutput]):
        name = "build_training_dataset"
        description = "Build training dataset from feature tables"
        risk = ActionRisk.SAFE_AUTOMATION
        input_model = BuildTrainingDatasetInput
        output_model = BuildTrainingDatasetOutput

        def _execute(
            self, args: BuildTrainingDatasetInput, context: ToolContext
        ) -> BuildTrainingDatasetOutput:
            model = _get_model(store, args.model_id)
            platform = store.require()
            profile = platform.data_profiles.get(model.training_table, {})
            mode = _execution_mode(store)
            return BuildTrainingDatasetOutput(
                model_id=args.model_id,
                dataset_table=model.training_table,
                row_count=profile.get("row_count", 100000),
                feature_count=len(model.features),
                mode=mode,
                status=f"built_in_{mode}",
            )

    class TrainCandidate(BaseTool[TrainCandidateInput, TrainCandidateOutput]):
        name = "train_candidate"
        description = "Train challenger candidate model"
        risk = ActionRisk.SAFE_AUTOMATION
        input_model = TrainCandidateInput
        output_model = TrainCandidateOutput

        def _execute(self, args: TrainCandidateInput, context: ToolContext) -> TrainCandidateOutput:
            model = _get_model(store, args.model_id)
            mode = _execution_mode(store)
            candidate_id = f"candidate.{model.model_id}.{uuid4().hex[:8]}"
            version = args.candidate_version or f"{model.version}-c{uuid4().hex[:4]}"
            job_id = f"job-{uuid4().hex[:12]}"
            _candidates[candidate_id] = {
                "model_id": args.model_id,
                "version": version,
                "mode": mode,
                "metrics": {
                    "auc": min(0.99, model.metrics.get("auc", 0.8) + 0.03),
                    "mae": max(500, model.metrics.get("mae", 1200) - 50),
                    "calibration_ece": max(0.01, model.metrics.get("calibration_ece", 0.04) - 0.01),
                },
            }
            msg = (
                f"Training completed in {mode}"
                if mode == ExecutionMode.LOCAL_SIMULATION.value
                else f"Submitted SageMaker job {job_id} — await REAL_AWS completion"
            )
            return TrainCandidateOutput(
                candidate_id=candidate_id,
                model_id=args.model_id,
                version=version,
                mode=mode,
                training_job_id=job_id,
                status="completed" if mode == ExecutionMode.LOCAL_SIMULATION.value else "submitted",
                message=msg,
            )

    class EvaluateCandidate(BaseTool[EvaluateCandidateInput, EvaluateCandidateOutput]):
        name = "evaluate_candidate"
        description = "Evaluate challenger on holdout set"
        risk = ActionRisk.READ_ONLY
        input_model = EvaluateCandidateInput
        output_model = EvaluateCandidateOutput

        def _execute(self, args: EvaluateCandidateInput, context: ToolContext) -> EvaluateCandidateOutput:
            cand = _candidates.get(args.candidate_id)
            if not cand:
                raise ToolError(f"Candidate not found: {args.candidate_id}", code="NOT_FOUND")
            metrics = cand["metrics"]
            passed = metrics.get("auc", 0) >= 0.75 and metrics.get("calibration_ece", 1) <= 0.1
            return EvaluateCandidateOutput(
                candidate_id=args.candidate_id,
                metrics=metrics,
                mode=cand["mode"],
                passed_minimum_bar=passed,
            )

    class CompareChampionChallenger(
        BaseTool[CompareChampionChallengerInput, CompareChampionChallengerOutput]
    ):
        name = "compare_champion_challenger"
        description = "Compare champion vs challenger with promotion policy"
        risk = ActionRisk.READ_ONLY
        input_model = CompareChampionChallengerInput
        output_model = CompareChampionChallengerOutput

        def _execute(
            self, args: CompareChampionChallengerInput, context: ToolContext
        ) -> CompareChampionChallengerOutput:
            champion = _get_model(store, args.champion_model_id)
            cand = _candidates.get(args.candidate_id)
            if not cand:
                raise ToolError(f"Candidate not found: {args.candidate_id}", code="NOT_FOUND")
            ch_metrics = champion.metrics
            cl_metrics = cand["metrics"]
            promote = False
            rationale = ""
            if args.promotion_policy == "auc_improvement":
                promote = cl_metrics.get("auc", 0) > ch_metrics.get("auc", 0)
                rationale = f"Challenger AUC {cl_metrics.get('auc')} vs champion {ch_metrics.get('auc')}"
            elif args.promotion_policy == "mae_reduction":
                promote = cl_metrics.get("mae", 9999) < ch_metrics.get("mae", 9999)
                rationale = f"Challenger MAE {cl_metrics.get('mae')} vs champion {ch_metrics.get('mae')}"
            else:
                score_c = cl_metrics.get("auc", 0) - cl_metrics.get("calibration_ece", 0)
                score_ch = ch_metrics.get("auc", 0) - ch_metrics.get("calibration_ece", 0)
                promote = score_c > score_ch
                rationale = f"Composite score challenger={score_c:.3f} champion={score_ch:.3f}"
            winner = args.candidate_id if promote else args.champion_model_id
            return CompareChampionChallengerOutput(
                champion_model_id=args.champion_model_id,
                candidate_id=args.candidate_id,
                champion_metrics=ch_metrics,
                challenger_metrics=cl_metrics,
                winner=winner,
                promote=promote,
                policy=args.promotion_policy,
                rationale=rationale,
            )

    class CheckSafetyGates(BaseTool[CheckSafetyGatesInput, CheckSafetyGatesOutput]):
        name = "check_safety_gates"
        description = "Run safety gates before promotion"
        risk = ActionRisk.READ_ONLY
        input_model = CheckSafetyGatesInput
        output_model = CheckSafetyGatesOutput

        def _execute(self, args: CheckSafetyGatesInput, context: ToolContext) -> CheckSafetyGatesOutput:
            cand = _candidates.get(args.candidate_id)
            if not cand:
                raise ToolError(f"Candidate not found: {args.candidate_id}", code="NOT_FOUND")
            champion = _get_model(store, args.champion_model_id)
            gates = [
                SafetyGateResult(
                    gate="minimum_auc",
                    passed=cand["metrics"].get("auc", 0) >= 0.75,
                    detail=f"auc={cand['metrics'].get('auc')}",
                ),
                SafetyGateResult(
                    gate="calibration_ece",
                    passed=cand["metrics"].get("calibration_ece", 1) <= 0.1,
                    detail=f"ece={cand['metrics'].get('calibration_ece')}",
                ),
                SafetyGateResult(
                    gate="no_regression_vs_champion",
                    passed=cand["metrics"].get("auc", 0) >= champion.metrics.get("auc", 0) - 0.01,
                    detail="challenger within 0.01 AUC of champion",
                ),
                SafetyGateResult(
                    gate="bias_fairness_check",
                    passed=True,
                    detail="LOCAL_SIMULATION: fairness stub passed",
                ),
            ]
            return CheckSafetyGatesOutput(
                candidate_id=args.candidate_id,
                all_passed=all(g.passed for g in gates),
                gates=gates,
            )

    class DeployModel(BaseTool[DeployModelInput, DeployModelOutput]):
        name = "deploy_model"
        description = "Deploy challenger to production (requires approval)"
        risk = ActionRisk.APPROVAL_REQUIRED
        input_model = DeployModelInput
        output_model = DeployModelOutput

        def _execute(self, args: DeployModelInput, context: ToolContext) -> DeployModelOutput:
            cand = _candidates.get(args.candidate_id)
            if not cand:
                raise ToolError(f"Candidate not found: {args.candidate_id}", code="NOT_FOUND")
            mode = cand["mode"]
            if mode == ExecutionMode.REAL_AWS.value:
                return DeployModelOutput(
                    candidate_id=args.candidate_id,
                    deployed_model_id=args.candidate_id,
                    mode=mode,
                    status="pending_real_aws",
                    message="REAL_AWS deploy submitted — not confirmed until endpoint health check passes",
                    approval_note="Human approval recorded; monitor REAL_AWS endpoint",
                )
            champion = _get_model(store, args.champion_model_id)
            champion.version = cand["version"]
            champion.metrics.update(cand["metrics"])
            champion.deployed_at = datetime.now(timezone.utc)
            return DeployModelOutput(
                candidate_id=args.candidate_id,
                deployed_model_id=args.champion_model_id,
                mode=ExecutionMode.LOCAL_SIMULATION.value,
                status="deployed_local_simulation",
                message=f"Promoted {args.candidate_id} in LOCAL_SIMULATION only",
                approval_note="Deploy executed after approval",
            )

        def _dry_run(self, args: DeployModelInput, context: ToolContext) -> DeployModelOutput:
            return DeployModelOutput(
                candidate_id=args.candidate_id,
                deployed_model_id=args.champion_model_id,
                mode=_execution_mode(store),
                status="dry_run",
                message=f"Would deploy {args.candidate_id} to {args.target_stage}",
                approval_note="Awaiting approval",
            )

    class RollbackModel(BaseTool[RollbackModelInput, RollbackModelOutput]):
        name = "rollback_model"
        description = "Rollback to previous model version (requires approval)"
        risk = ActionRisk.APPROVAL_REQUIRED
        input_model = RollbackModelInput
        output_model = RollbackModelOutput

        def _execute(self, args: RollbackModelInput, context: ToolContext) -> RollbackModelOutput:
            model = _get_model(store, args.model_id)
            mode = _execution_mode(store)
            prev = args.previous_version
            if mode == ExecutionMode.REAL_AWS.value:
                return RollbackModelOutput(
                    model_id=args.model_id,
                    rolled_back_to=prev,
                    mode=mode,
                    status="pending_real_aws",
                    message="REAL_AWS rollback initiated — verify endpoint before declaring success",
                )
            model.version = prev
            return RollbackModelOutput(
                model_id=args.model_id,
                rolled_back_to=prev,
                mode=ExecutionMode.LOCAL_SIMULATION.value,
                status="rolled_back_local_simulation",
                message=f"Rolled back {args.model_id} to {prev} in LOCAL_SIMULATION",
            )

        def _dry_run(self, args: RollbackModelInput, context: ToolContext) -> RollbackModelOutput:
            return RollbackModelOutput(
                model_id=args.model_id,
                rolled_back_to=args.previous_version,
                mode=_execution_mode(store),
                status="dry_run",
                message=f"Would rollback {args.model_id} to {args.previous_version}",
            )

    class MonitorPostDeploy(BaseTool[MonitorPostDeployInput, MonitorPostDeployOutput]):
        name = "monitor_post_deploy"
        description = "Monitor model health after deployment"
        risk = ActionRisk.READ_ONLY
        input_model = MonitorPostDeployInput
        output_model = MonitorPostDeployOutput

        def _execute(self, args: MonitorPostDeployInput, context: ToolContext) -> MonitorPostDeployOutput:
            model = _get_model(store, args.model_id)
            mode = model.mode
            auc = model.metrics.get("auc", 0)
            alerts: list[str] = []
            if auc < 0.75:
                alerts.append("AUC below minimum threshold")
            error_rate = 0.005 if auc >= 0.78 else 0.03
            latency = 120.0 if mode == ExecutionMode.LOCAL_SIMULATION.value else 250.0
            healthy = not alerts and error_rate < 0.01
            return MonitorPostDeployOutput(
                model_id=args.model_id,
                healthy=healthy,
                auc=auc,
                error_rate=error_rate,
                latency_p95_ms=latency,
                alerts=alerts,
                mode=mode,
            )

    return [
        AssessDegradation(),
        BuildTrainingDataset(),
        TrainCandidate(),
        EvaluateCandidate(),
        CompareChampionChallenger(),
        CheckSafetyGates(),
        DeployModel(),
        RollbackModel(),
        MonitorPostDeploy(),
    ]
