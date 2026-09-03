"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function DbtPage() {
  const [models, setModels] = useState<Array<Record<string, unknown>>>([]);
  useEffect(() => { api.dbtModels().then(setModels).catch(() => setModels([])); }, []);
  return (
    <div>
      <h1 className="page-title">dbt</h1>
      <p className="page-sub">Model inventory, materializations, tests, and docs coverage.</p>
      <div className="panel">
        <table className="table">
          <thead>
            <tr><th>Model</th><th>Materialization</th><th>Tests</th><th>Docs</th><th>Incremental</th><th>Est. bytes</th></tr>
          </thead>
          <tbody>
            {models.map((m) => (
              <tr key={String(m.unique_id)}>
                <td className="mono">{String(m.name)}</td>
                <td>{String(m.materialization)}</td>
                <td>{m.has_tests ? "yes" : "no"}</td>
                <td>{m.has_docs ? "yes" : "no"}</td>
                <td>{m.is_incremental ? "yes" : "no"}</td>
                <td className="mono">{Number(m.estimated_bytes_scanned || 0).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
