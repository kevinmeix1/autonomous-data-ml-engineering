"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Panel } from "@/components/Panel";
import { Stat } from "@/components/Stat";

export default function DataQualityPage() {
  const [tests, setTests] = useState<Array<Record<string, unknown>>>([]);
  useEffect(() => { api.dbtTests().then(setTests).catch(() => setTests([])); }, []);
  const failed = useMemo(() => tests.filter((t) => t.status === "fail"), [tests]);

  return (
    <div>
      <h1 className="page-title">Data Quality</h1>
      <p className="page-sub">Failed tests are investigation triggers — not the end of the story.</p>
      <div className="grid">
        <div className="span-4"><Stat label="Tests" value={tests.length} /></div>
        <div className="span-4"><Stat label="Failed" value={failed.length} tone={failed.length ? "danger" : "ok"} /></div>
        <div className="span-4"><Stat label="Dimensions" value="8" hint="completeness → volume" /></div>
        <Panel span={12} title="Test inventory" action={<Link className="btn primary" href="/agents?agent=data_quality">Investigate with DQ agent</Link>}>
          <table className="table">
            <thead>
              <tr><th>Test</th><th>Model</th><th>Status</th><th>Failures</th><th>Dimension</th></tr>
            </thead>
            <tbody>
              {tests.map((t) => (
                <tr key={String(t.test_id)}>
                  <td className="mono">{String(t.test_name)}</td>
                  <td className="mono">{String(t.model_unique_id)}</td>
                  <td><span className={`badge ${t.status === "fail" ? "danger" : "ok"}`}>{String(t.status)}</span></td>
                  <td>{String(t.failures)}</td>
                  <td>{String(t.dimension || "—")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </div>
    </div>
  );
}
