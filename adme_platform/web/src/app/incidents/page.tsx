"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Panel } from "@/components/Panel";
import { Stat } from "@/components/Stat";

export default function IncidentsPage() {
  const [rows, setRows] = useState<Array<Record<string, unknown>>>([]);
  const [q, setQ] = useState("");

  useEffect(() => {
    api.incidents().then(setRows).catch(() => setRows([]));
  }, []);

  const filtered = useMemo(() => {
    const needle = q.toLowerCase();
    return rows.filter((r) =>
      !needle ||
      String(r.title).toLowerCase().includes(needle) ||
      String(r.ground_truth_root_cause).toLowerCase().includes(needle) ||
      String(r.incident_id).toLowerCase().includes(needle)
    );
  }, [rows, q]);

  const critical = rows.filter((r) => String(r.severity) === "CRITICAL" || String(r.severity) === "HIGH").length;

  return (
    <div>
      <h1 className="page-title">Incidents</h1>
      <p className="page-sub">Synthetic failures with ground-truth labels used for agent evaluation.</p>
      <div className="grid">
        <div className="span-4"><Stat label="Total incidents" value={rows.length} /></div>
        <div className="span-4"><Stat label="High / critical" value={critical} tone="danger" /></div>
        <div className="span-4"><Stat label="Visible" value={filtered.length} /></div>
        <Panel span={12} title="Incident queue" action={<input placeholder="Filter…" value={q} onChange={(e) => setQ(e.target.value)} />}>
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Title</th>
                <th>Severity</th>
                <th>Source</th>
                <th>Ground truth</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, 60).map((r) => (
                <tr key={String(r.incident_id)}>
                  <td className="mono">{String(r.incident_id)}</td>
                  <td>{String(r.title)}</td>
                  <td><span className="badge danger">{String(r.severity)}</span></td>
                  <td>{String(r.source_system)}</td>
                  <td className="mono">{String(r.ground_truth_root_cause)}</td>
                  <td>
                    <Link className="btn primary" href={`/agents?incident=${r.incident_id}&agent=pipeline_sre`}>
                      Investigate
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </div>
    </div>
  );
}
