export function EvidenceBadge({ kind }: { kind: string }) {
  const map: Record<string, [string, string]> = {
    observed_fact: ["fact", "Observed fact"],
    model_inference: ["inference", "Model inference"],
    agent_hypothesis: ["hypothesis", "Agent hypothesis"],
    recommended_action: ["action", "Recommended action"],
    tool_result: ["fact", "Tool result"],
    statistical_test: ["inference", "Statistical test"],
    retrieved_knowledge: ["inference", "Retrieved knowledge"],
  };
  const [cls, label] = map[kind] || ["fact", kind];
  return <span className={`badge ${cls}`}>{label}</span>;
}
