"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import { Stat } from "@/components/Stat";
import { Panel } from "@/components/Panel";

export default function OverviewPage() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [incidents, setIncidents] = useState<Array<Record<string, unknown>>>([]);
  const [queries, setQueries] = useState<Array<Record<string, unknown>>>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.overview(), api.incidents(), api.queries()])
      .then(([o, i, q]) => {
        setData(o);
        setIncidents(i.slice(0, 8));
        setQueries(q.slice(0, 24));
      })
      .catch((e) => setError(String(e)));
  }, []);

  const costSeries = useMemo(() => {
    return queries
      .slice()
      .reverse()
      .map((q, idx) => ({
        i: idx + 1,
        credits: Number(q.credits_used || 0),
        bytes: Number(q.bytes_scanned || 0) / 1e9,
      }));
  }, [queries]);

  return (
    <div>
      <h1 className="page-title">Mission Control</h1>
      <p className="page-sub">
        Live operations view across Airflow, dbt, Snowflake, features, and ML — with autonomous agents
        that investigate using real tools, not chat wrappers.
      </p>

      {error && (
        <Panel span={12} title="Backend offline">
          <p className="muted">Start the API with <code className="mono">make run</code>. {error}</p>
        </Panel>
      )}

      {data && (
        <div className="grid">
          <div className="span-3"><Stat label="Open incidents" value={Number(data.incidents_open)} tone="danger" hint="Requires investigation" /></div>
          <div className="span-3"><Stat label="Failed tests" value={Number(data.failed_tests)} tone="warn" /></div>
          <div className="span-3"><Stat label="Agent executions" value={Number(data.executions)} tone="ok" hint="Persisted locally" /></div>
          <div className="span-3"><Stat label="Tracked queries" value={Number(data.queries)} /></div>

          <Panel span={8} title="Credit burn (sample window)" subtitle="Synthetic Snowflake query credits as a cost proxy">
            <div style={{ width: "100%", height: 240 }}>
              <ResponsiveContainer>
                <AreaChart data={costSeries}>
                  <defs>
                    <linearGradient id="gCredits" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#2fd4c2" stopOpacity={0.45} />
                      <stop offset="100%" stopColor="#2fd4c2" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="rgba(148,163,184,0.12)" vertical={false} />
                  <XAxis dataKey="i" stroke="#5d6d8a" fontSize={11} />
                  <YAxis stroke="#5d6d8a" fontSize={11} />
                  <Tooltip
                    contentStyle={{ background: "#0e1524", border: "1px solid rgba(148,163,184,0.2)", borderRadius: 12 }}
                  />
                  <Area type="monotone" dataKey="credits" stroke="#2fd4c2" fill="url(#gCredits)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          <Panel span={4} title="Agent fleet" subtitle="Specialized autonomous workers">
            <div className="lane">
              {[
                ["pipeline_sre", "Pipeline failures"],
                ["data_quality", "DQ root cause"],
                ["ml_doctor", "Model health"],
                ["engineering_os", "Multi-agent routing"],
              ].map(([id, label]) => (
                <Link key={id} href={`/agents?agent=${id}`} className="lane-item action">
                  <div className="mono">{id}</div>
                  <div className="muted">{label}</div>
                </Link>
              ))}
            </div>
          </Panel>

          <Panel
            span={12}
            title="Hot incidents"
            subtitle="Ground-truth labeled synthetic failures for evaluation"
            action={<Link className="btn" href="/incidents">View all</Link>}
          >
            <table className="table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Title</th>
                  <th>Severity</th>
                  <th>Ground truth</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {incidents.map((r) => (
                  <tr key={String(r.incident_id)}>
                    <td className="mono">{String(r.incident_id)}</td>
                    <td>{String(r.title)}</td>
                    <td><span className="badge danger">{String(r.severity)}</span></td>
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
      )}
    </div>
  );
}
