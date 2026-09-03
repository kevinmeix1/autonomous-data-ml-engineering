"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Panel } from "@/components/Panel";

export default function MLPage() {
  const [models, setModels] = useState<Array<Record<string, unknown>>>([]);
  useEffect(() => { api.mlModels().then(setModels).catch(() => setModels([])); }, []);

  return (
    <div>
      <h1 className="page-title">ML Models</h1>
      <p className="page-sub">Champion health, drift signals, and deployment mode honesty (LOCAL_SIMULATION vs REAL_AWS).</p>
      <div className="grid">
        {models.map((m) => {
          const metrics = (m.metrics || {}) as Record<string, number>;
          const auc = Number(metrics.auc || 0);
          const auc7 = Number(metrics.auc_7d_ago || auc);
          const drop = auc7 - auc;
          return (
            <Panel
              key={String(m.model_id)}
              span={6}
              title={`${String(m.name)} · v${String(m.version)}`}
              subtitle={String(m.model_id)}
              action={<Link className="btn" href="/agents?agent=ml_doctor">Diagnose</Link>}
            >
              <div className="row" style={{ marginBottom: 10 }}>
                <span className="badge">{String(m.stage)}</span>
                <span className="badge warn">{String(m.mode)}</span>
                <span className={`badge ${drop > 0.02 ? "danger" : "ok"}`}>
                  ΔAUC {drop > 0 ? "-" : "+"}{Math.abs(drop).toFixed(3)}
                </span>
              </div>
              <div className="lane">
                <div className="lane-item fact">
                  <div className="muted">AUC</div>
                  <div className="stat-value" style={{ fontSize: "1.6rem" }}>{auc.toFixed(3)}</div>
                  <div className="progress"><i style={{ width: `${Math.min(100, auc * 100)}%` }} /></div>
                </div>
                <div className="lane-item inference">
                  <div className="muted">Calibration ECE</div>
                  <div>{Number(metrics.calibration_ece || 0).toFixed(3)}</div>
                </div>
                <div className="lane-item">
                  <div className="muted">Features</div>
                  <div className="mono">{(m.features as string[])?.join(", ")}</div>
                </div>
              </div>
            </Panel>
          );
        })}
      </div>
    </div>
  );
}
