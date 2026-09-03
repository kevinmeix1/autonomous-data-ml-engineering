"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Panel } from "@/components/Panel";

export default function LineagePage() {
  const [graph, setGraph] = useState<Record<string, unknown> | null>(null);
  const [nodeId, setNodeId] = useState("RAW.CLAIM.claims");
  const [impact, setImpact] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    api.lineage().then(setGraph).catch(() => setGraph(null));
  }, []);

  const nodes = useMemo(() => {
    const elements = ((graph?.elements as Array<Record<string, unknown>>) || []);
    return elements
      .map((e) => e.data as Record<string, string>)
      .filter((d) => d && !d.source);
  }, [graph]);

  async function inspect(id = nodeId) {
    setNodeId(id);
    const data = await api.lineage(id);
    setImpact(data);
  }

  return (
    <div>
      <h1 className="page-title">Lineage</h1>
      <p className="page-sub">
        Source → ingestion → dbt → features → ML model → business application. Impact analysis cites graph edges.
      </p>
      <div className="grid">
        <Panel span={12} title="Impact query">
          <div className="row">
            <input style={{ flex: 1 }} value={nodeId} onChange={(e) => setNodeId(e.target.value)} />
            <button className="btn primary" onClick={() => inspect()}>Trace impact</button>
          </div>
        </Panel>

        <Panel span={7} title="Graph canvas" subtitle="Click a node to inspect downstream blast radius">
          <div className="graph-canvas">
            {nodes.map((n) => (
              <button key={n.id} className="node-pill" onClick={() => inspect(n.id)}>
                <span className="dim">{n.node_type || "node"} · </span>{n.label || n.id}
              </button>
            ))}
          </div>
        </Panel>

        <Panel span={5} title="Impact report" subtitle={impact ? String(impact.node_id) : "Select a node"}>
          {!impact && <div className="empty">No node selected</div>}
          {impact && (
            <>
              <h3 style={{ marginTop: 0 }}>Downstream by type</h3>
              <pre className="mono" style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(impact.impact, null, 2)}</pre>
              <h3>Upstream</h3>
              <div className="lane">
                {((impact.upstream as Array<Record<string, string>>) || []).slice(0, 12).map((u) => (
                  <div key={u.id} className="lane-item fact mono">{u.id}</div>
                ))}
              </div>
            </>
          )}
        </Panel>
      </div>
    </div>
  );
}
