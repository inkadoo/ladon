export type Label = { kind: string; text: string; severity: "danger" | "warning" };

export type QuickRisk = { mint: string; score: number; level: "low" | "medium" | "high"; labels: Label[] };

const PRIORITY = ["serial_rugger", "dev_dumped", "bundle_sold", "linked_rugger", "high_risk", "bundled", "top_holders"];

export function ordered(labels: Label[]): Label[] {
  const rank = (l: Label) => {
    const i = PRIORITY.indexOf(l.kind);
    return i < 0 ? PRIORITY.length : i;
  };
  return [...labels].sort((a, b) => rank(a) - rank(b));
}

const SHORT: Record<string, (n: string) => string> = {
  serial_rugger: (n) => `Rugged ${n}`,
  linked_rugger: (n) => `Network rugged ${n}`,
  dev_dumped: () => "Dev dumped",
  bundle_sold: () => "Bundle sold",
  high_risk: () => "High risk",
  bundled: (n) => `Bundled ${n}`,
  top_holders: (n) => `Top 10: ${n}`,
};

export function short(label: Label): string {
  const make = SHORT[label.kind];
  const number = label.text.match(/\d+%?/g)?.at(-1) ?? "";
  return make ? make(number) : label.text;
}

export function headline(risk: QuickRisk): { text: string; severity: Label["severity"]; more: number } | null {
  const labels = ordered(risk.labels);
  if (labels.length === 0) return null;
  const others = labels.filter((l) => l.kind !== "high_risk" || labels.length === 1);
  const first = others[0] ?? labels[0];
  const severity = labels.some((l) => l.severity === "danger") ? "danger" : "warning";
  return { text: short(first), severity, more: labels.length - 1 };
}
