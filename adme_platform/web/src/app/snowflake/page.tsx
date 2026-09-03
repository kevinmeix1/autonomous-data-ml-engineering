"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function SnowflakePage() {
  const [queries, setQueries] = useState<Array<Record<string, unknown>>>([]);
  useEffect(() => { api.queries().then(setQueries).catch(() => setQueries([])); }, []);
  return (
    <div>
      <h1 className="page-title">Snowflake</h1>
      <p className="page-sub">Expensive-query explorer (credits & bytes scanned proxies).</p>
      <div className="panel">
        <table className="table">
          <thead>
            <tr><th>Query</th><th>Warehouse</th><th>Credits</th><th>Bytes</th><th>Status</th><th>Model</th></tr>
          </thead>
          <tbody>
            {queries.slice(0, 40).map((q) => (
              <tr key={String(q.query_id)}>
                <td className="mono">{String(q.query_id)}</td>
                <td>{String(q.warehouse)}</td>
                <td>{Number(q.credits_used).toFixed(4)}</td>
                <td className="mono">{Number(q.bytes_scanned).toLocaleString()}</td>
                <td><span className={`badge ${q.status === "FAILED" ? "danger" : "ok"}`}>{String(q.status)}</span></td>
                <td className="mono">{String(q.dbt_model || "—")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
