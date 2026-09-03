const BASE = process.env.NEXT_PUBLIC_API_BASE || "";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
  return res.json();
}

export const api = {
  health: () => get<{ status: string }>("/api/health"),
  overview: () => get<Record<string, unknown>>("/api/overview"),
  agents: () => get<Array<{ name: string }>>("/api/agents"),
  incidents: () => get<Array<Record<string, unknown>>>("/api/incidents"),
  pipelines: () => get<Array<Record<string, unknown>>>("/api/pipelines"),
  dbtModels: () => get<Array<Record<string, unknown>>>("/api/dbt/models"),
  dbtTests: () => get<Array<Record<string, unknown>>>("/api/dbt/tests"),
  queries: () => get<Array<Record<string, unknown>>>("/api/snowflake/queries"),
  warehouses: () => get<Array<Record<string, unknown>>>("/api/snowflake/warehouses"),
  mlModels: () => get<Array<Record<string, unknown>>>("/api/ml/models"),
  features: () => get<Array<Record<string, unknown>>>("/api/features"),
  lineage: (nodeId?: string) =>
    get<Record<string, unknown>>(nodeId ? `/api/lineage?node_id=${encodeURIComponent(nodeId)}` : "/api/lineage"),
  audit: () => get<Array<Record<string, unknown>>>("/api/audit"),
  executions: () => get<Array<Record<string, unknown>>>("/api/executions"),
  execution: (id: string) => get<Record<string, unknown>>(`/api/executions/${id}`),
  runAgent: (agent: string, objective: string, context: Record<string, unknown> = {}) =>
    post<Record<string, unknown>>("/api/agents/run", { agent, objective, context }),
  approve: (execution_id: string, action_id: string, decision: "approve" | "reject", reason = "") =>
    post<Record<string, unknown>>("/api/approvals", {
      execution_id,
      action_id,
      decision,
      approver: "ui-operator",
      reason,
    }),
};
