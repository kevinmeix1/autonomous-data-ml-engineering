from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from domain.enums import ActionRisk
from pydantic import BaseModel, Field
from tool_sdk.base import BaseTool, ToolContext, ToolError


FEATURE_FAMILIES = {
    "aggregation": "Window or group aggregations (sum, avg, count)",
    "ratio": "Ratios between numeric columns",
    "rolling": "Rolling window statistics",
    "temporal": "Time-based features (datediff, seasonality)",
    "categorical": "Encodings and bucketization",
    "interaction": "Cross-feature products or combinations",
}


class ListFeaturesInput(BaseModel):
    owner: str | None = None


class ListFeaturesOutput(BaseModel):
    features: list[dict[str, Any]]


class ProposeFeatureInput(BaseModel):
    name: str
    family: str
    definition: str
    source_tables: list[str]
    transformation: str
    availability_timestamp_column: str


class ProposeFeatureOutput(BaseModel):
    feature_id: str
    name: str
    family: str
    status: str


class ValidateFeatureInput(BaseModel):
    feature_id: str
    sql: str | None = None


class ValidateFeatureOutput(BaseModel):
    feature_id: str
    valid: bool
    issues: list[str]


class DetectLeakageInput(BaseModel):
    feature_id: str
    outcome_timestamp_column: str = "loss_date"
    prediction_timestamp_column: str = "as_of_ts"


class DetectLeakageOutput(BaseModel):
    feature_id: str
    leakage_risk: str
    issues: list[str]
    timestamp_aware: bool


class EvaluateFeatureInput(BaseModel):
    feature_id: str
    target_column: str = "severity_bucket"


class EvaluateFeatureOutput(BaseModel):
    feature_id: str
    auc_lift: float
    correlation: float
    recommended: bool


class RegisterFeatureInput(BaseModel):
    feature_id: str
    version: int = 1


class RegisterFeatureOutput(BaseModel):
    feature_id: str
    version: int
    registry_path: str
    status: str


def _registry_path() -> Path:
    path = Path("data/synthetic/feature_registry")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_registry() -> dict[str, Any]:
    reg_file = _registry_path() / "registry.json"
    if reg_file.exists():
        return json.loads(reg_file.read_text())
    return {"features": {}}


def _save_registry(data: dict[str, Any]) -> None:
    (_registry_path() / "registry.json").write_text(json.dumps(data, indent=2, default=str))


def build_feature_tools(store: Any) -> list[BaseTool[Any, Any]]:
    proposals: dict[str, dict[str, Any]] = {}

    class ListFeatures(BaseTool[ListFeaturesInput, ListFeaturesOutput]):
        name = "list_features"
        description = "List features from platform and local registry"
        risk = ActionRisk.READ_ONLY
        input_model = ListFeaturesInput
        output_model = ListFeaturesOutput

        def _execute(self, args: ListFeaturesInput, context: ToolContext) -> ListFeaturesOutput:
            features = [f.model_dump(mode="json") for f in store.require().features]
            if args.owner:
                features = [f for f in features if f.get("owner") == args.owner]
            reg = _load_registry().get("features", {})
            for fid, meta in reg.items():
                if not any(f["feature_id"] == fid for f in features):
                    features.append(meta)
            return ListFeaturesOutput(features=features)

    class ProposeFeature(BaseTool[ProposeFeatureInput, ProposeFeatureOutput]):
        name = "propose_feature"
        description = "Propose a new feature definition"
        risk = ActionRisk.SAFE_AUTOMATION
        input_model = ProposeFeatureInput
        output_model = ProposeFeatureOutput

        def _execute(self, args: ProposeFeatureInput, context: ToolContext) -> ProposeFeatureOutput:
            if args.family not in FEATURE_FAMILIES:
                raise ToolError(f"Unknown family: {args.family}", code="INVALID_FAMILY")
            fid = f"feat_{args.name}"
            proposals[fid] = {
                "feature_id": fid,
                "name": args.name,
                "family": args.family,
                "definition": args.definition,
                "source_tables": args.source_tables,
                "transformation": args.transformation,
                "availability_timestamp_column": args.availability_timestamp_column,
                "owner": "feature-engineering-agent",
                "version": 1,
                "status": "proposed",
            }
            return ProposeFeatureOutput(
                feature_id=fid,
                name=args.name,
                family=args.family,
                status="proposed",
            )

    class ValidateFeature(BaseTool[ValidateFeatureInput, ValidateFeatureOutput]):
        name = "validate_feature"
        description = "Validate feature definition and SQL"
        risk = ActionRisk.READ_ONLY
        input_model = ValidateFeatureInput
        output_model = ValidateFeatureOutput

        def _execute(self, args: ValidateFeatureInput, context: ToolContext) -> ValidateFeatureOutput:
            platform = store.require()
            feat = next((f for f in platform.features if f.feature_id == args.feature_id), None)
            meta = proposals.get(args.feature_id) or (feat.model_dump() if feat else None)
            if not meta:
                raise ToolError("Feature not found", code="NOT_FOUND")
            issues: list[str] = []
            for tbl in meta.get("source_tables", []):
                if not any(t.table_id.endswith(tbl.split(".")[-1]) or t.table_id == tbl for t in platform.tables):
                    if tbl not in {t.table_id for t in platform.tables}:
                        issues.append(f"Source table not found: {tbl}")
            sql = args.sql or meta.get("transformation", "")
            if "select *" in sql.lower():
                issues.append("Avoid SELECT * in feature SQL")
            if not meta.get("availability_timestamp_column"):
                issues.append("Missing availability_timestamp_column")
            return ValidateFeatureOutput(feature_id=args.feature_id, valid=not issues, issues=issues)

    class DetectLeakage(BaseTool[DetectLeakageInput, DetectLeakageOutput]):
        name = "detect_leakage"
        description = "Detect target leakage using timestamp-aware rules"
        risk = ActionRisk.READ_ONLY
        input_model = DetectLeakageInput
        output_model = DetectLeakageOutput

        def _execute(self, args: DetectLeakageInput, context: ToolContext) -> DetectLeakageOutput:
            platform = store.require()
            feat = next((f for f in platform.features if f.feature_id == args.feature_id), None)
            meta = proposals.get(args.feature_id) or (feat.model_dump(mode="json") if feat else None)
            if not meta:
                raise ToolError("Feature not found", code="NOT_FOUND")
            issues: list[str] = []
            tx = (meta.get("transformation") or "").lower()
            avail = meta.get("availability_timestamp_column", "")
            if "close_date" in tx or "ultimate" in tx:
                issues.append("Uses post-outcome fields (close_date/ultimate)")
            if "paid_amount" in tx and "loss_date" in tx:
                issues.append("paid_amount may not be known at loss_date")
            if avail in {"close_date", "report_date"} and avail != args.prediction_timestamp_column:
                issues.append(f"Availability column {avail} may be after prediction time")
            if feat and feat.leakage_risk == "high":
                issues.append("Existing leakage_risk=high in catalog")
            risk = "high" if issues else meta.get("leakage_risk", "low")
            if len(issues) == 1:
                risk = "medium"
            return DetectLeakageOutput(
                feature_id=args.feature_id,
                leakage_risk=risk,
                issues=issues,
                timestamp_aware=bool(avail),
            )

    class EvaluateFeature(BaseTool[EvaluateFeatureInput, EvaluateFeatureOutput]):
        name = "evaluate_feature"
        description = "Evaluate feature predictive utility (simulated)"
        risk = ActionRisk.READ_ONLY
        input_model = EvaluateFeatureInput
        output_model = EvaluateFeatureOutput

        def _execute(self, args: EvaluateFeatureInput, context: ToolContext) -> EvaluateFeatureOutput:
            feat = next(
                (f for f in store.require().features if f.feature_id == args.feature_id),
                None,
            )
            meta = proposals.get(args.feature_id)
            contrib = 0.05
            if feat and feat.performance_contribution:
                contrib = feat.performance_contribution
            elif meta:
                contrib = 0.07 if meta.get("family") == "aggregation" else 0.04
            return EvaluateFeatureOutput(
                feature_id=args.feature_id,
                auc_lift=round(contrib, 3),
                correlation=round(contrib * 0.8, 3),
                recommended=contrib >= 0.05,
            )

    class RegisterFeature(BaseTool[RegisterFeatureInput, RegisterFeatureOutput]):
        name = "register_feature"
        description = "Register an approved feature in the local registry"
        risk = ActionRisk.SAFE_AUTOMATION
        input_model = RegisterFeatureInput
        output_model = RegisterFeatureOutput

        def _execute(self, args: RegisterFeatureInput, context: ToolContext) -> RegisterFeatureOutput:
            platform = store.require()
            feat = next((f for f in platform.features if f.feature_id == args.feature_id), None)
            meta = proposals.get(args.feature_id)
            if feat:
                payload = feat.model_dump(mode="json")
            elif meta:
                payload = meta
            else:
                raise ToolError("Feature not found", code="NOT_FOUND")
            payload["version"] = args.version
            payload["registered_at"] = datetime.now(timezone.utc).isoformat()
            payload["status"] = "registered"
            reg = _load_registry()
            reg.setdefault("features", {})[args.feature_id] = payload
            _save_registry(reg)
            path = str(_registry_path() / "registry.json")
            return RegisterFeatureOutput(
                feature_id=args.feature_id,
                version=args.version,
                registry_path=path,
                status="registered",
            )

    return [
        ListFeatures(),
        ProposeFeature(),
        ValidateFeature(),
        DetectLeakage(),
        EvaluateFeature(),
        RegisterFeature(),
    ]
