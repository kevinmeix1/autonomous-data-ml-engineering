"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function AuditPage() {
  const [rows, setRows] = useState<Array<Record<string, unknown>>>([]);
  useEffect(() => { api.audit().then(setRows).catch(() => setRows([])); }, []);
  return (
    <div>
      <h1 className="page-title">Audit Log</h1>
      <p className="page-sub">Immutable record of agent actions, approvals, and outcomes.</p>
      <div className="panel">
        <table className="table">
          <thead>
            <tr><th>When</th><th>Who</th><th>What</th><th>Why</th><th>Agent</th></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={String(r.audit_id)}>
                <td className="mono">{String(r.when)}</td>
                <td>{String(r.who)}</td>
                <td>{String(r.what)}</td>
                <td>{String(r.why)}</td>
                <td>{String(r.agent || "—")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
