export default function ExperimentsPage() {
  return (
    <div>
      <h1 className="page-title">Experiments</h1>
      <p className="page-sub">Ablation studies and research questions for agentic data/ML systems.</p>
      <div className="panel">
        <ul>
          <li>Do structured diagnostic tools outperform LLM-only root cause analysis?</li>
          <li>Does lineage improve diagnostic accuracy?</li>
          <li>How much does tool-use reduce hallucination?</li>
          <li>Accuracy vs token cost tradeoff under model routing</li>
        </ul>
        <p className="muted">Run: <code className="mono">make evaluate</code> and see <code className="mono">experiments/</code>.</p>
      </div>
    </div>
  );
}
