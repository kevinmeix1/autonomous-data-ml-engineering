"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function FeaturesPage() {
  const [rows, setRows] = useState<Array<Record<string, unknown>>>([]);
  useEffect(() => { api.features().then(setRows).catch(() => setRows([])); }, []);
  return (
    <div>
      <h1 className="page-title">Features</h1>
      <p className="page-sub">Feature registry with leakage risk and availability timestamps.</p>
      <div className="panel">
        <table className="table">
          <thead>
            <tr><th>Feature</th><th>Leakage</th><th>Availability</th><th>Contribution</th><th>Owner</th></tr>
          </thead>
          <tbody>
            {rows.map((f) => (
              <tr key={String(f.feature_id)}>
                <td className="mono">{String(f.name)}</td>
                <td><span className={`badge ${f.leakage_risk === "high" ? "danger" : "ok"}`}>{String(f.leakage_risk)}</span></td>
                <td className="mono">{String(f.availability_timestamp_column)}</td>
                <td>{String(f.performance_contribution ?? "—")}</td>
                <td>{String(f.owner)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
