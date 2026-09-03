from __future__ import annotations

from enum import Enum


class ActionRisk(str, Enum):
    READ_ONLY = "READ_ONLY"
    SAFE_AUTOMATION = "SAFE_AUTOMATION"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    PROHIBITED = "PROHIBITED"


class EvidenceKind(str, Enum):
    OBSERVED_FACT = "observed_fact"
    MODEL_INFERENCE = "model_inference"
    AGENT_HYPOTHESIS = "agent_hypothesis"
    RECOMMENDED_ACTION = "recommended_action"
    TOOL_RESULT = "tool_result"
    STATISTICAL_TEST = "statistical_test"
    RETRIEVED_KNOWLEDGE = "retrieved_knowledge"


class IncidentSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class PipelineStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    RUNNING = "running"
    UP_FOR_RETRY = "up_for_retry"
    SKIPPED = "skipped"
    QUEUED = "queued"


class QualityDimension(str, Enum):
    COMPLETENESS = "completeness"
    UNIQUENESS = "uniqueness"
    VALIDITY = "validity"
    CONSISTENCY = "consistency"
    FRESHNESS = "freshness"
    REFERENTIAL_INTEGRITY = "referential_integrity"
    DISTRIBUTION_STABILITY = "distribution_stability"
    VOLUME = "volume"


class FindingSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    SUGGESTION = "SUGGESTION"


class ExecutionMode(str, Enum):
    LOCAL_SIMULATION = "LOCAL_SIMULATION"
    REAL_AWS = "REAL_AWS"
    REAL_SNOWFLAKE = "REAL_SNOWFLAKE"


class AgentState(str, Enum):
    PENDING = "pending"
    OBSERVING = "observing"
    DETECTING = "detecting"
    INVESTIGATING = "investigating"
    HYPOTHESIZING = "hypothesizing"
    TESTING = "testing"
    REMEDIATING = "remediating"
    AWAITING_APPROVAL = "awaiting_approval"
    VERIFYING = "verifying"
    DOCUMENTING = "documenting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
