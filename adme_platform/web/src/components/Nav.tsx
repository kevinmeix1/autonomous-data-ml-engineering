"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  ["Overview", "/"],
  ["Incidents", "/incidents"],
  ["Pipelines", "/pipelines"],
  ["Data Quality", "/data-quality"],
  ["dbt", "/dbt"],
  ["Snowflake", "/snowflake"],
  ["ML Models", "/ml"],
  ["Features", "/features"],
  ["Lineage", "/lineage"],
  ["Agents", "/agents"],
  ["Experiments", "/experiments"],
  ["Cost", "/cost"],
  ["Deployments", "/deployments"],
  ["Audit Log", "/audit"],
];

export function Nav() {
  const path = usePathname();
  return (
    <aside className="sidebar">
      <div className="brand">
        ADME <span>OS</span>
      </div>
      <div className="brand-sub">Autonomous Data & ML Engineering</div>
      <nav className="nav">
        {LINKS.map(([label, href]) => (
          <Link key={href} href={href} className={path === href ? "active" : ""}>
            {label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
