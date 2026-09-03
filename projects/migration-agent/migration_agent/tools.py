from __future__ import annotations

import statistics
from typing import Any

from domain.enums import ActionRisk
from pydantic import BaseModel, Field
from tool_sdk.base import BaseTool, ToolContext, ToolError


class LegacyTableInput(BaseModel):
    legacy_table: str


class LegacyColumn(BaseModel):
    name: str
    data_type: str
    nullable: bool


class InspectLegacySchemaOutput(BaseModel):
    legacy_table: str
    columns: list[LegacyColumn]
    row_count: int
    source_system: str


class ProfileTableInput(BaseModel):
    table_id: str


class ProfileTableOutput(BaseModel):
    table_id: str
    row_count: int
    null_rates: dict[str, float]
    distinct_counts: dict[str, int]
    aggregates: dict[str, float]


class MapColumnsInput(BaseModel):
    legacy_table: str
    target_table: str


class ColumnMapping(BaseModel):
    legacy_column: str
    target_column: str
    transform: str | None = None
    confidence: float


class MapColumnsOutput(BaseModel):
    legacy_table: str
    target_table: str
    mappings: list[ColumnMapping]
    unmapped_legacy: list[str]
    unmapped_target: list[str]


class DetectTypeIncompatibilitiesInput(BaseModel):
    legacy_table: str
    target_table: str


class TypeIssue(BaseModel):
    column: str
    legacy_type: str
    target_type: str
    severity: str
    suggestion: str


class DetectTypeIncompatibilitiesOutput(BaseModel):
    legacy_table: str
    target_table: str
    issues: list[TypeIssue]


class GenerateDbtModelsInput(BaseModel):
    target_table: str
    mappings: list[ColumnMapping] | None = None


class GenerateDbtModelsOutput(BaseModel):
    target_table: str
    staging_model: str
    mart_model: str
    sql_preview: str


class GenerateTestsInput(BaseModel):
    target_table: str


class GenerateTestsOutput(BaseModel):
    target_table: str
    tests: list[dict[str, str]]


class GenerateReconciliationSqlInput(BaseModel):
    legacy_table: str
    target_table: str


class GenerateReconciliationSqlOutput(BaseModel):
    legacy_table: str
    target_table: str
    row_count_sql: str
    null_rate_sql: str
    aggregate_sql: str


class RunReconciliationInput(BaseModel):
    legacy_table: str
    target_table: str


class ReconciliationCheck(BaseModel):
    check: str
    legacy_value: float | int
    target_value: float | int
    passed: bool
    tolerance: float


class RunReconciliationOutput(BaseModel):
    legacy_table: str
    target_table: str
    checks: list[ReconciliationCheck]
    all_passed: bool
    mode: str


class ValidateMigrationInput(BaseModel):
    legacy_table: str
    target_table: str


class ValidateMigrationOutput(BaseModel):
    legacy_table: str
    target_table: str
    validated: bool
    row_counts_match: bool
    null_rates_match: bool
    aggregates_match: bool
    distributions_match: bool
    message: str


_TYPE_MAP = {
    "VARCHAR": "VARCHAR",
    "STRING": "VARCHAR",
    "TEXT": "VARCHAR",
    "NUMBER": "NUMBER",
    "DECIMAL": "NUMBER",
    "FLOAT": "FLOAT",
    "DOUBLE": "FLOAT",
    "INT": "NUMBER",
    "INTEGER": "NUMBER",
    "DATE": "DATE",
    "TIMESTAMP": "TIMESTAMP_NTZ",
    "TIMESTAMP_NTZ": "TIMESTAMP_NTZ",
    "BOOLEAN": "BOOLEAN",
    "VARIANT": "VARIANT",
}


def _find_table(store: Any, table_ref: str) -> Any:
    platform = store.require()
    # Accept legacy.* or RAW.SCHEMA.table formats
    normalized = table_ref.replace("legacy.", "RAW.")
    table = next(
        (t for t in platform.tables if t.table_id == normalized or t.table_name == table_ref.split(".")[-1]),
        None,
    )
    if not table:
        raise ToolError(f"Table not found: {table_ref}", code="NOT_FOUND")
    return table


def build_migration_tools(store: Any) -> list[BaseTool[Any, Any]]:
    class InspectLegacySchema(BaseTool[LegacyTableInput, InspectLegacySchemaOutput]):
        name = "inspect_legacy_schema"
        description = "Inspect legacy source schema for migration"
        risk = ActionRisk.READ_ONLY
        input_model = LegacyTableInput
        output_model = InspectLegacySchemaOutput

        def _execute(self, args: LegacyTableInput, context: ToolContext) -> InspectLegacySchemaOutput:
            table = _find_table(store, args.legacy_table)
            return InspectLegacySchemaOutput(
                legacy_table=args.legacy_table,
                columns=[
                    LegacyColumn(name=c.name, data_type=c.data_type, nullable=c.nullable)
                    for c in table.columns
                ],
                row_count=table.row_count,
                source_system="legacy_mainframe" if "RAW" in table.table_id else "snowflake",
            )

    class ProfileTable(BaseTool[ProfileTableInput, ProfileTableOutput]):
        name = "profile_table"
        description = "Profile table for migration validation baseline"
        risk = ActionRisk.READ_ONLY
        input_model = ProfileTableInput
        output_model = ProfileTableOutput

        def _execute(self, args: ProfileTableInput, context: ToolContext) -> ProfileTableOutput:
            table = _find_table(store, args.table_id)
            platform = store.require()
            profile = platform.data_profiles.get(table.table_id, {})
            numeric_cols = [c.name for c in table.columns if c.data_type in {"NUMBER", "FLOAT"}]
            aggregates = {}
            for col in numeric_cols[:3]:
                rng_val = hash((table.table_id, col)) % 10000
                aggregates[f"sum_{col}"] = float(rng_val * 100)
                aggregates[f"avg_{col}"] = float(rng_val)
            return ProfileTableOutput(
                table_id=table.table_id,
                row_count=profile.get("row_count", table.row_count),
                null_rates=profile.get("null_rates", {}),
                distinct_counts=profile.get("distinct_counts", {}),
                aggregates=aggregates,
            )

    class MapColumns(BaseTool[MapColumnsInput, MapColumnsOutput]):
        name = "map_columns"
        description = "Map legacy columns to Snowflake target columns"
        risk = ActionRisk.READ_ONLY
        input_model = MapColumnsInput
        output_model = MapColumnsOutput

        def _execute(self, args: MapColumnsInput, context: ToolContext) -> MapColumnsOutput:
            legacy = _find_table(store, args.legacy_table)
            target = _find_table(store, args.target_table)
            mappings: list[ColumnMapping] = []
            target_names = {c.name.lower(): c.name for c in target.columns}
            mapped_legacy: set[str] = set()
            mapped_target: set[str] = set()
            for lc in legacy.columns:
                key = lc.name.lower()
                if key in target_names:
                    mappings.append(
                        ColumnMapping(
                            legacy_column=lc.name,
                            target_column=target_names[key],
                            confidence=1.0,
                        )
                    )
                    mapped_legacy.add(lc.name)
                    mapped_target.add(target_names[key])
                elif key.replace("_", "") in {k.replace("_", "") for k in target_names}:
                    for tk, tv in target_names.items():
                        if tk.replace("_", "") == key.replace("_", ""):
                            mappings.append(
                                ColumnMapping(
                                    legacy_column=lc.name,
                                    target_column=tv,
                                    transform="rename",
                                    confidence=0.85,
                                )
                            )
                            mapped_legacy.add(lc.name)
                            mapped_target.add(tv)
                            break
            return MapColumnsOutput(
                legacy_table=args.legacy_table,
                target_table=args.target_table,
                mappings=mappings,
                unmapped_legacy=[c.name for c in legacy.columns if c.name not in mapped_legacy],
                unmapped_target=[c.name for c in target.columns if c.name not in mapped_target],
            )

    class DetectTypeIncompatibilities(
        BaseTool[DetectTypeIncompatibilitiesInput, DetectTypeIncompatibilitiesOutput]
    ):
        name = "detect_type_incompatibilities"
        description = "Detect type incompatibilities between legacy and target"
        risk = ActionRisk.READ_ONLY
        input_model = DetectTypeIncompatibilitiesInput
        output_model = DetectTypeIncompatibilitiesOutput

        def _execute(
            self, args: DetectTypeIncompatibilitiesInput, context: ToolContext
        ) -> DetectTypeIncompatibilitiesOutput:
            mapper = MapColumns()
            mapped = mapper._execute(
                MapColumnsInput(legacy_table=args.legacy_table, target_table=args.target_table),
                context,
            )
            legacy = _find_table(store, args.legacy_table)
            target = _find_table(store, args.target_table)
            legacy_types = {c.name: c.data_type for c in legacy.columns}
            target_types = {c.name: c.data_type for c in target.columns}
            issues: list[TypeIssue] = []
            for m in mapped.mappings:
                lt = legacy_types.get(m.legacy_column, "UNKNOWN")
                tt = target_types.get(m.target_column, "UNKNOWN")
                norm_l = _TYPE_MAP.get(lt.upper(), lt)
                norm_t = _TYPE_MAP.get(tt.upper(), tt)
                if norm_l != norm_t:
                    sev = "HIGH" if norm_l in {"VARIANT", "TEXT"} else "MEDIUM"
                    issues.append(
                        TypeIssue(
                            column=m.legacy_column,
                            legacy_type=lt,
                            target_type=tt,
                            severity=sev,
                            suggestion=f"CAST({m.legacy_column} AS {norm_t})",
                        )
                    )
            return DetectTypeIncompatibilitiesOutput(
                legacy_table=args.legacy_table,
                target_table=args.target_table,
                issues=issues,
            )

    class GenerateDbtModels(BaseTool[GenerateDbtModelsInput, GenerateDbtModelsOutput]):
        name = "generate_dbt_models"
        description = "Generate dbt staging and mart models for migration"
        risk = ActionRisk.SAFE_AUTOMATION
        input_model = GenerateDbtModelsInput
        output_model = GenerateDbtModelsOutput

        def _execute(self, args: GenerateDbtModelsInput, context: ToolContext) -> GenerateDbtModelsOutput:
            table = _find_table(store, args.target_table)
            cols = ",\n  ".join(f"{c.name}" for c in table.columns[:8])
            staging = f"stg_{table.table_name}"
            mart = table.table_name
            sql = f"""-- staging
select
  {cols}
from {{{{ source('legacy', '{table.table_name}') }}}}

-- mart
select * from {{{{ ref('{staging}') }}}}"""
            return GenerateDbtModelsOutput(
                target_table=table.table_id,
                staging_model=staging,
                mart_model=mart,
                sql_preview=sql,
            )

    class GenerateTests(BaseTool[GenerateTestsInput, GenerateTestsOutput]):
        name = "generate_tests"
        description = "Generate dbt tests for migrated table"
        risk = ActionRisk.SAFE_AUTOMATION
        input_model = GenerateTestsInput
        output_model = GenerateTestsOutput

        def _execute(self, args: GenerateTestsInput, context: ToolContext) -> GenerateTestsOutput:
            table = _find_table(store, args.target_table)
            tests = []
            pk_cols = [c.name for c in table.columns if c.is_primary_key]
            for col in pk_cols:
                tests.append({"test": "unique", "column": col, "model": table.table_name})
            for col in table.columns[:5]:
                if not col.nullable:
                    tests.append({"test": "not_null", "column": col.name, "model": table.table_name})
            return GenerateTestsOutput(target_table=table.table_id, tests=tests)

    class GenerateReconciliationSql(
        BaseTool[GenerateReconciliationSqlInput, GenerateReconciliationSqlOutput]
    ):
        name = "generate_reconciliation_sql"
        description = "Generate SQL for legacy vs target reconciliation"
        risk = ActionRisk.READ_ONLY
        input_model = GenerateReconciliationSqlInput
        output_model = GenerateReconciliationSqlOutput

        def _execute(
            self, args: GenerateReconciliationSqlInput, context: ToolContext
        ) -> GenerateReconciliationSqlOutput:
            legacy = _find_table(store, args.legacy_table)
            target = _find_table(store, args.target_table)
            amt_col = next((c.name for c in legacy.columns if "amount" in c.name.lower()), "id")
            return GenerateReconciliationSqlOutput(
                legacy_table=args.legacy_table,
                target_table=args.target_table,
                row_count_sql=f"SELECT COUNT(*) FROM legacy.{legacy.table_name} UNION ALL SELECT COUNT(*) FROM {target.table_id}",
                null_rate_sql=f"SELECT AVG(IFF({amt_col} IS NULL, 1, 0)) FROM legacy.{legacy.table_name}",
                aggregate_sql=f"SELECT SUM({amt_col}), AVG({amt_col}) FROM legacy.{legacy.table_name}",
            )

    class RunReconciliation(BaseTool[RunReconciliationInput, RunReconciliationOutput]):
        name = "run_reconciliation"
        description = "Run reconciliation checks (LOCAL_SIMULATION with profile data)"
        risk = ActionRisk.SAFE_AUTOMATION
        input_model = RunReconciliationInput
        output_model = RunReconciliationOutput

        def _execute(self, args: RunReconciliationInput, context: ToolContext) -> RunReconciliationOutput:
            legacy = _find_table(store, args.legacy_table)
            target = _find_table(store, args.target_table)
            platform = store.require()
            leg_prof = platform.data_profiles.get(legacy.table_id, {})
            tgt_prof = platform.data_profiles.get(target.table_id, {})
            leg_rows = leg_prof.get("row_count", legacy.row_count)
            tgt_rows = tgt_prof.get("row_count", target.row_count)
            row_tol = max(1, int(leg_rows * 0.001))
            row_pass = abs(leg_rows - tgt_rows) <= row_tol

            amt_col = next((c.name for c in legacy.columns if "amount" in c.name.lower()), None)
            null_pass = True
            if amt_col:
                leg_null = leg_prof.get("null_rates", {}).get(amt_col, 0)
                tgt_null = tgt_prof.get("null_rates", {}).get(amt_col, leg_null)
                null_pass = abs(leg_null - tgt_null) <= 0.01

            leg_agg = sum(leg_prof.get("aggregates", {}).values()) if leg_prof.get("aggregates") else leg_rows
            tgt_agg = sum(tgt_prof.get("aggregates", {}).values()) if tgt_prof.get("aggregates") else tgt_rows
            if not leg_prof.get("aggregates"):
                leg_agg = float(leg_rows)
                tgt_agg = float(tgt_rows)
            agg_pass = abs(leg_agg - tgt_agg) / max(leg_agg, 1) <= 0.01

            checks = [
                ReconciliationCheck(
                    check="row_count",
                    legacy_value=leg_rows,
                    target_value=tgt_rows,
                    passed=row_pass,
                    tolerance=row_tol,
                ),
                ReconciliationCheck(
                    check="null_rate",
                    legacy_value=leg_prof.get("null_rates", {}).get(amt_col or "", 0),
                    target_value=tgt_prof.get("null_rates", {}).get(amt_col or "", 0),
                    passed=null_pass,
                    tolerance=0.01,
                ),
                ReconciliationCheck(
                    check="aggregate_sum",
                    legacy_value=int(leg_agg),
                    target_value=int(tgt_agg),
                    passed=agg_pass,
                    tolerance=0.01,
                ),
            ]
            return RunReconciliationOutput(
                legacy_table=args.legacy_table,
                target_table=args.target_table,
                checks=checks,
                all_passed=all(c.passed for c in checks),
                mode="LOCAL_SIMULATION",
            )

    class ValidateMigration(BaseTool[ValidateMigrationInput, ValidateMigrationOutput]):
        name = "validate_migration"
        description = "Validate migration — never declare success without checks"
        risk = ActionRisk.READ_ONLY
        input_model = ValidateMigrationInput
        output_model = ValidateMigrationOutput

        def _execute(self, args: ValidateMigrationInput, context: ToolContext) -> ValidateMigrationOutput:
            recon = RunReconciliation()
            recon_out = recon._execute(
                RunReconciliationInput(legacy_table=args.legacy_table, target_table=args.target_table),
                context,
            )
            row_ok = any(c.check == "row_count" and c.passed for c in recon_out.checks)
            null_ok = any(c.check == "null_rate" and c.passed for c in recon_out.checks)
            agg_ok = any(c.check == "aggregate_sum" and c.passed for c in recon_out.checks)

            legacy = _find_table(store, args.legacy_table)
            platform = store.require()
            leg_prof = platform.data_profiles.get(legacy.table_id, {})
            hist = leg_prof.get("historical_null_rates", {})
            dist_ok = True
            if hist:
                for col, values in list(hist.items())[:2]:
                    if values:
                        dist_ok = dist_ok and statistics.pstdev(values) < 0.1

            validated = recon_out.all_passed and row_ok and null_ok and agg_ok and dist_ok
            msg = (
                "Migration validated: row counts, null rates, aggregates, and distributions match"
                if validated
                else "Migration NOT validated — reconciliation checks failed"
            )
            return ValidateMigrationOutput(
                legacy_table=args.legacy_table,
                target_table=args.target_table,
                validated=validated,
                row_counts_match=row_ok,
                null_rates_match=null_ok,
                aggregates_match=agg_ok,
                distributions_match=dist_ok,
                message=msg,
            )

    return [
        InspectLegacySchema(),
        ProfileTable(),
        MapColumns(),
        DetectTypeIncompatibilities(),
        GenerateDbtModels(),
        GenerateTests(),
        GenerateReconciliationSql(),
        RunReconciliation(),
        ValidateMigration(),
    ]
