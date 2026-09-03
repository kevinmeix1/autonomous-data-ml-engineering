import { Suspense } from "react";

export default function AgentsLayout({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<div className="panel">Loading agents…</div>}>{children}</Suspense>;
}
