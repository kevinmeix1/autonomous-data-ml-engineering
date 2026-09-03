"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import { Panel } from "@/components/Panel";
import { Stat } from "@/components/Stat";

export default function CostPage() {
  const [queries, setQueries] = useState<Array<Record<string, unknown>>>([]);
  useEffect(() => { api.queries().then(setQueries).catch(() => setQueries([])); }, []);

  const total = useMemo(() => queries.reduce((s, q) => s + Number(q.credits_used || 0), 0), [queries]);
  const byWh = useMemo(() => {
    const map = new Map<string, number>();
    for (const q of queries) {
      const wh = String(q.warehouse);
      map.set(wh, (map.get(wh) || 0) + Number(q.credits_used || 0));
    }
    return Array.from(map.entries()).map(([warehouse, credits]) => ({ warehouse, credits: Number(credits.toFixed(3)) }));
  }, [queries]);

  return (
    <div>
      <h1 className="page-title">Cost</h1>
      <p className="page-sub">Warehouse credit proxies, expensive-query explorer, and optimization opportunities.</p>
      <div className="grid">
        <div className="span-4"><Stat label="Credits (sample)" value={total.toFixed(2)} tone="warn" /></div>
        <div className="span-4"><Stat label="Queries sampled" value={queries.length} /></div>
        <div className="span-4"><Stat label="Top opportunity" value="Full scans" hint="fct_claims repeated scans" /></div>

        <Panel span={6} title="Credits by warehouse">
          <div style={{ width: "100%", height: 260 }}>
            <ResponsiveContainer>
              <BarChart data={byWh}>
                <CartesianGrid stroke="rgba(148,163,184,0.12)" vertical={false} />
                <XAxis dataKey="warehouse" stroke="#5d6d8a" fontSize={11} />
                <YAxis stroke="#5d6d8a" fontSize={11} />
                <Tooltip contentStyle={{ background: "#0e1524", border: "1px solid rgba(148,163,184,0.2)", borderRadius: 12 }} />
                <Bar dataKey="credits" fill="#e8b84a" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel span={6} title="Optimization backlog">
          <div className="lane">
            <div className="lane-item hypothesis">
              <strong>Repeated full scans</strong>
              <div className="muted">fct_claims scanned without pruning predicates in multiple models</div>
              <div className="progress" style={{ marginTop: 8 }}><i style={{ width: "82%" }} /></div>
            </div>
            <div className="lane-item hypothesis">
              <strong>Warehouse oversize</strong>
              <div className="muted">TRANSFORM_WH XL during off-peak windows</div>
              <div className="progress" style={{ marginTop: 8 }}><i style={{ width: "64%" }} /></div>
            </div>
            <div className="lane-item hypothesis">
              <strong>Incremental watermark drift</strong>
              <div className="muted">loss_date watermark causes replay waste</div>
              <div className="progress" style={{ marginTop: 8 }}><i style={{ width: "71%" }} /></div>
            </div>
          </div>
        </Panel>

        <Panel span={12} title="Expensive queries">
          <table className="table">
            <thead>
              <tr><th>Query</th><th>Warehouse</th><th>Credits</th><th>GB scanned</th><th>Status</th></tr>
            </thead>
            <tbody>
              {queries.slice(0, 20).map((q) => (
                <tr key={String(q.query_id)}>
                  <td className="mono">{String(q.query_id)}</td>
                  <td>{String(q.warehouse)}</td>
                  <td>{Number(q.credits_used).toFixed(4)}</td>
                  <td>{(Number(q.bytes_scanned) / 1e9).toFixed(2)}</td>
                  <td><span className={`badge ${q.status === "FAILED" ? "danger" : "ok"}`}>{String(q.status)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </div>
    </div>
  );
}
