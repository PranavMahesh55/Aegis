export function TrustBadge({ tone, label }: { tone: string; label?: string }) {
  const normalized = tone.toLowerCase();
  const display = label ?? {
    RE_EVALUATED: "RE-EVALUATED",
    REMEDIATION_APPLIED: "REMEDIATED",
    CONTEXT_CHANGED: "CHANGED",
  }[tone] ?? tone.replaceAll("_", " ");
  return <span className={`trust-badge ${normalized}`}>{display}</span>;
}
