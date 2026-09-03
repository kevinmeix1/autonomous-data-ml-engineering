"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const NAV = [
  { section: "Operate", items: [
    ["Overview", "/"],
    ["Incidents", "/incidents"],
    ["Agents", "/agents"],
    ["Approvals", "/approvals"],
  ]},
  { section: "Platform", items: [
    ["Pipelines", "/pipelines"],
    ["Data Quality", "/data-quality"],
    ["dbt", "/dbt"],
    ["Snowflake", "/snowflake"],
    ["Lineage", "/lineage"],
  ]},
  { section: "ML", items: [
    ["Models", "/ml"],
    ["Features", "/features"],
    ["Deployments", "/deployments"],
    ["Cost", "/cost"],
  ]},
  { section: "Governance", items: [
    ["Experiments", "/experiments"],
    ["Audit Log", "/audit"],
  ]},
];

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const [clock, setClock] = useState("");
  const [online, setOnline] = useState(false);

  useEffect(() => {
    const tick = () => setClock(new Date().toLocaleTimeString());
    tick();
    const id = setInterval(tick, 1000);
    fetch("/api/health").then((r) => setOnline(r.ok)).catch(() => setOnline(false));
    return () => clearInterval(id);
  }, []);

  return (
    <div className="shell">
      <aside className="rail">
        <div className="rail-brand">
          <div className="mark">A</div>
          <div>
            <div className="brand-title">ADME</div>
            <div className="brand-sub">Engineering OS</div>
          </div>
        </div>
        {NAV.map((group) => (
          <div key={group.section} className="nav-group">
            <div className="nav-label">{group.section}</div>
            {group.items.map(([label, href]) => (
              <Link key={href} href={href} className={path === href ? "nav-item active" : "nav-item"}>
                <span className="nav-dot" />
                {label}
              </Link>
            ))}
          </div>
        ))}
        <div className="rail-foot">
          <div className={`pulse ${online ? "on" : "off"}`} />
          <span>{online ? "API connected" : "API offline"}</span>
          <span className="mono dim">{clock}</span>
        </div>
      </aside>
      <div className="workspace">
        <div className="sim-banner">
          <strong>LOCAL_SIMULATION</strong>
          <span>
            Synthetic insurance platform · no real AWS/Snowflake writes · agents are deterministic
            diagnostic workflows with typed tools (optional LLM planner not required)
          </span>
        </div>
        <header className="topbar">
          <div>
            <div className="eyebrow">Synthetic commercial insurance lab</div>
            <div className="topbar-title">Data & ML Engineering Agent Lab</div>
          </div>
          <div className="topbar-meta">
            <span className="chip warn">LOCAL_SIMULATION</span>
            <span className="chip warn">Approval gates on</span>
            <span className="chip">12 agents</span>
          </div>
        </header>
        <div className="content">{children}</div>
      </div>
    </div>
  );
}
