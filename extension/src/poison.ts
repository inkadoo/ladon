const MIN_END = 3;
const MIN_TOTAL = 7;

export function sharedEnds(a: string, b: string): { start: number; end: number } {
  let start = 0;
  while (start < a.length && start < b.length && a[start] === b[start]) start++;
  let end = 0;
  while (end < a.length - start && end < b.length - start && a[a.length - 1 - end] === b[b.length - 1 - end]) end++;
  return { start, end };
}

export function lookalikeOf(address: string, known: Iterable<string>): string | null {
  let best: { address: string; score: number } | null = null;
  for (const candidate of known) {
    if (candidate === address) return null;
    const { start, end } = sharedEnds(address, candidate);
    if (start < MIN_END || end < MIN_END || start + end < MIN_TOTAL) continue;
    if (!best || start + end > best.score) best = { address: candidate, score: start + end };
  }
  return best?.address ?? null;
}
