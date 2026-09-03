"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function DeploymentsPage() {
  const [models, setModels] = useState<Array<Record<string, unknown>>>([]);
  useEffect(() => { api.mlModels().then(setModels).catch(() => setModels([])); }, []);
  return (
    <div>
      <h1 className="page-title">Deployments</h1>
      <p className="page-sub">Champion/challenger status — LOCAL_SIMULATION clearly labeled.</p>
      <div className="panel">
        <table className="table">
          <thead>
            <tr><th>Model</th><th>Version</th><th>Stage</th><th>Mode</th><th>Endpoint</th></tr>
          </thead>
          <tbody>
            {models.map((m) => (
              <tr key={String(m.model_id)}>
                <td>{String(m.name)}</td>
                <td className="mono">{String(m.version)}</td>
                <td>{String(m.stage)}</td>
                <td><span className="badge hypothesis">{String(m.mode)}</span></td>
                <td className="mono">{String(m.endpoint)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
