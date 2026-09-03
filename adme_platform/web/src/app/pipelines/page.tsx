"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Panel } from "@/components/Panel";
import { Stat } from "@/components/Stat";

export default function PipelinesPage() {
  const [dags, setDags] = useState<Array<Record<string, unknown>>>([]);
  useEffect(() => { api.pipelines().then(setDags).catch(() => setDags([])); }, []);
  const dag = dags[0];
  const tasks = ((dag?.tasks as Array<Record<string, unknown>>) || []);
  const failed = useMemo(() => tasks.filter((t) => t.status === "failed").length, [tasks]);
  const avgDur = useMemo(() => {
    if (!tasks.length) return 0;
    return Math.round(tasks.reduce((s, t) => s + Number(t.duration_seconds || 0), 0) / tasks.length);
  }, [tasks]);

  return (
    <div>
      <h1 className="page-title">Pipelines</h1>
      <p className="page-sub">Airflow DAG topology, task health, and critical-path oriented duration view.</p>
      {dag && (
        <div className="grid">
          <div className="span-3"><Stat label="DAG status" value={String(dag.last_run_status)} tone={String(dag.last_run_status) === "failed" ? "danger" : "ok"} /></div>
          <div className="span-3"><Stat label="Failed tasks" value={failed} tone={failed ? "danger" : "ok"} /></div>
          <div className="span-3"><Stat label="Avg duration" value={`${avgDur}s`} /></div>
          <div className="span-3"><Stat label="Schedule" value={String(dag.schedule)} hint="cron" /></div>

          <Panel span={12} title={String(dag.dag_id)} subtitle={String(dag.description)}>
            <div className="dag">
              {tasks.map((t) => (
                <div key={String(t.task_id)} className={`dag-node ${t.status === "failed" ? "failed" : "success"}`}>
                  <div className="mono">{String(t.task_id)}</div>
                  <div className={`badge ${t.status === "failed" ? "danger" : "ok"}`}>{String(t.status)}</div>
                  <div className="muted" style={{ marginTop: 6 }}>{Math.round(Number(t.duration_seconds || 0))}s</div>
                  <div className="dim" style={{ fontSize: "0.75rem", marginTop: 4 }}>
                    ↑ {(t.upstream as string[])?.join(", ") || "root"}
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      )}
    </div>
  );
}
