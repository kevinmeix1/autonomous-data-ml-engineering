"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { EvidenceBadge } from "@/components/EvidenceBadge";
import { Panel } from "@/components/Panel";

type Exec = Record<string, unknown>;

export default function AgentsPage() {
  const params = useSearchParams();
  const [agents, setAgents] = useState<Array<{ name: string }>>([]);
  const [agent, setAgent] = useState("pipeline_sre");
  const [objective, setObjective] = useState("Investigate the latest insurance_daily_pipeline failure");
  const [running, setRunning] = useState(false);
  const [exec, setExec] = useState<Exec | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"timeline" | "evidence" | "tools" | "result">("timeline");

  useEffect(() => {
    api.agents().then(setAgents).catch(() => setAgents([{ name: "pipeline_sre" }]));
    const incident = params.get("incident");
    const a = params.get("agent");
    if (a) setAgent(a);
    if (incident) setObjective(`Investigate incident ${incident} on insurance_daily_pipeline`);
  }, [params]);

  const pendingActions = useMemo(() => {
    const actions = (exec?.actions as Array<Record<string, unknown>>) || [];
    return actions.filter((a) => a.status === "proposed" && a.approval_required);
  }, [exec]);

  const evidenceByKind = useMemo(() => {
    const evidence = (exec?.evidence as Array<Record<string, string>>) || [];
    const groups: Record<string, number> = {};
    for (const e of evidence) groups[e.kind] = (groups[e.kind] || 0) + 1;
    return groups;
  }, [exec]);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      const result = await api.runAgent(agent, objective, {
        dag_id: "insurance_daily_pipeline",
        incident_id: params.get("incident") || "UI-RUN",
        model_id: "ml.claims_severity_v3",
        model_unique_id: "model.analytics.fct_claims",
        table_id: "RAW.CLAIM.claims",
        node_id: "RAW.CLAIM.claims",
      });
      setExec(result);
      setTab("timeline");
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  }

  async function decide(actionId: string, decision: "approve" | "reject") {
    if (!exec) return;
    if (decision === "approve") {
      const ok = window.confirm(
        "Approve production-style change?\n\nThis is an explicit confirmation gate for HIGH-RISK remediation."
      );
      if (!ok) return;
    }
    const updated = await api.approve(String(exec.execution_id), actionId, decision);
    setExec(updated);
  }

  return (
    <div>
      <h1 className="page-title">Agent Control Center</h1>
      <p className="page-sub">
        Launch investigations, inspect evidence classes, and gate remediations. Observed facts, hypotheses,
        and recommended actions are kept visually distinct.
      </p>

      <div className="grid">
        <Panel span={12} title="Dispatch" subtitle="Choose a specialist agent and objective">
          <div className="row" style={{ marginBottom: "0.35rem" }}>
            <select value={agent} onChange={(e) => setAgent(e.target.value)} style={{ minWidth: 220 }}>
              {(agents.length ? agents : [{ name: "pipeline_sre" }]).map((a) => (
                <option key={a.name} value={a.name}>{a.name}</option>
              ))}
            </select>
            <input
              style={{ flex: 1, minWidth: 280 }}
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
            />
            <button className="btn primary" onClick={run} disabled={running}>
              {running ? "Investigating…" : "Run investigation"}
            </button>
          </div>
          {error && <p className="badge danger">{error}</p>}
        </Panel>

        {exec && (
          <>
            <Panel span={4} title="Execution" subtitle={String(exec.execution_id)}>
              <div className="lane">
                <div className="lane-item">
                  <div className="muted">State</div>
                  <div><span className={`badge ${String(exec.state).includes("await") ? "warn" : "ok"}`}>{String(exec.state)}</span></div>
                </div>
                <div className="lane-item">
                  <div className="muted">Tool calls</div>
                  <div className="stat-value" style={{ fontSize: "1.5rem" }}>{((exec.tool_calls as unknown[]) || []).length}</div>
                </div>
                <div className="lane-item">
                  <div className="muted">Evidence mix</div>
                  <div className="row" style={{ marginTop: 6 }}>
                    {Object.entries(evidenceByKind).map(([k, v]) => (
                      <span key={k} className="chip">{k.split("_").pop()} · {v}</span>
                    ))}
                  </div>
                </div>
              </div>
            </Panel>

            <Panel span={8} title="Investigation workspace">
              <div className="row" style={{ marginBottom: "0.85rem" }}>
                {(["timeline", "evidence", "tools", "result"] as const).map((t) => (
                  <button key={t} className={`btn ${tab === t ? "primary" : ""}`} onClick={() => setTab(t)}>
                    {t}
                  </button>
                ))}
              </div>

              {tab === "timeline" && (
                <ul className="timeline">
                  {((exec.investigation_steps as Array<Record<string, string>>) || []).map((s, i) => (
                    <li key={i}><strong>{s.step}</strong> — {s.detail}</li>
                  ))}
                </ul>
              )}

              {tab === "evidence" && (
                <div className="lane">
                  {((exec.evidence as Array<Record<string, string>>) || []).slice(0, 40).map((e, i) => (
                    <div key={i} className={`lane-item ${e.kind.includes("hypothesis") ? "hypothesis" : e.kind.includes("action") ? "action" : e.kind.includes("inference") ? "inference" : "fact"}`}>
                      <div className="row" style={{ justifyContent: "space-between" }}>
                        <EvidenceBadge kind={e.kind} />
                        <span className="mono dim">{e.source}</span>
                      </div>
                      <div style={{ marginTop: 6 }}>{e.summary}</div>
                    </div>
                  ))}
                </div>
              )}

              {tab === "tools" && (
                <table className="table">
                  <thead>
                    <tr><th>Tool</th><th>Risk</th><th>OK</th><th>Latency</th><th>Summary</th></tr>
                  </thead>
                  <tbody>
                    {((exec.tool_calls as Array<Record<string, unknown>>) || []).map((t) => (
                      <tr key={String(t.call_id)}>
                        <td className="mono">{String(t.tool_name)}</td>
                        <td><span className="badge">{String(t.risk)}</span></td>
                        <td>{t.success ? "✓" : "✗"}</td>
                        <td>{Math.round(Number(t.latency_ms))}ms</td>
                        <td className="muted">{String(t.output_summary || t.error || "—").slice(0, 120)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}

              {tab === "result" && (
                <>
                  <h3 style={{ marginTop: 0 }}>Hypotheses</h3>
                  <div className="lane" style={{ marginBottom: "1rem" }}>
                    {((exec.hypotheses as Array<Record<string, unknown>>) || []).map((h) => (
                      <div key={String(h.hypothesis_id)} className="lane-item hypothesis">
                        <EvidenceBadge kind="agent_hypothesis" /> {String(h.statement)}
                        <span className="muted"> · confidence {String(h.confidence)}</span>
                      </div>
                    ))}
                  </div>
                  <h3>Final result</h3>
                  <pre className="mono" style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(exec.final_result, null, 2)}</pre>
                </>
              )}
            </Panel>

            {pendingActions.length > 0 && (
              <Panel span={12} title="Human approval required" subtitle="High-risk remediations cannot execute without explicit confirmation">
                {pendingActions.map((a) => (
                  <div key={String(a.action_id)} className="lane-item action" style={{ marginBottom: "0.75rem" }}>
                    <div className="row" style={{ justifyContent: "space-between" }}>
                      <EvidenceBadge kind="recommended_action" />
                      <span className="badge warn">{String(a.risk)}</span>
                    </div>
                    <p>{String(a.rationale)}</p>
                    <p className="mono">tool={String(a.tool_name)}</p>
                    <pre className="mono">{JSON.stringify(a.args, null, 2)}</pre>
                    <div className="row">
                      <button className="btn primary" onClick={() => decide(String(a.action_id), "approve")}>
                        Approve Production Change
                      </button>
                      <button className="btn danger" onClick={() => decide(String(a.action_id), "reject")}>
                        Reject
                      </button>
                    </div>
                  </div>
                ))}
              </Panel>
            )}
          </>
        )}
      </div>
    </div>
  );
}
