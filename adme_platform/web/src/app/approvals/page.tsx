"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Panel } from "@/components/Panel";
import { EvidenceBadge } from "@/components/EvidenceBadge";

export default function ApprovalsPage() {
  const [rows, setRows] = useState<Array<Record<string, unknown>>>([]);

  async function refresh() {
    const execs = await api.executions();
    const pending = execs.filter((e) =>
      ((e.actions as Array<Record<string, unknown>>) || []).some(
        (a) => a.status === "proposed" && a.approval_required
      )
    );
    setRows(pending);
  }

  useEffect(() => {
    refresh().catch(() => setRows([]));
  }, []);

  async function decide(executionId: string, actionId: string, decision: "approve" | "reject") {
    if (decision === "approve") {
      const ok = window.confirm("Approve production-style change?");
      if (!ok) return;
    }
    await api.approve(executionId, actionId, decision);
    await refresh();
  }

  return (
    <div>
      <h1 className="page-title">Approvals</h1>
      <p className="page-sub">Queued high-risk remediations awaiting explicit human confirmation.</p>
      <div className="grid">
        {!rows.length && (
          <Panel span={12}>
            <div className="empty">No pending approvals. Run an agent that proposes a high-risk action.</div>
            <div className="row" style={{ justifyContent: "center" }}>
              <Link className="btn primary" href="/agents">Open Agent Control Center</Link>
            </div>
          </Panel>
        )}
        {rows.map((exec) => {
          const actions = ((exec.actions as Array<Record<string, unknown>>) || []).filter(
            (a) => a.status === "proposed" && a.approval_required
          );
          return (
            <Panel key={String(exec.execution_id)} span={12} title={String(exec.agent)} subtitle={String(exec.execution_id)}>
              <p className="muted">{String(exec.objective)}</p>
              {actions.map((a) => (
                <div key={String(a.action_id)} className="lane-item action" style={{ marginTop: 10 }}>
                  <EvidenceBadge kind="recommended_action" /> {String(a.rationale)}
                  <pre className="mono">{JSON.stringify(a.args, null, 2)}</pre>
                  <div className="row">
                    <button className="btn primary" onClick={() => decide(String(exec.execution_id), String(a.action_id), "approve")}>
                      Approve Production Change
                    </button>
                    <button className="btn danger" onClick={() => decide(String(exec.execution_id), String(a.action_id), "reject")}>
                      Reject
                    </button>
                  </div>
                </div>
              ))}
            </Panel>
          );
        })}
      </div>
    </div>
  );
}
