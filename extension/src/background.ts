import { isSolanaAddress } from "../../shared/solana";
import type { QuickRisk } from "./labels";

const CACHE_MS = 10 * 60 * 1000;
const FAILURE_CACHE_MS = 60 * 1000;
const CONCURRENCY = 3;

const cache = new Map<string, { until: number; value: QuickRisk | null }>();
const inflight = new Map<string, Promise<QuickRisk | null>>();
const waiting: (() => void)[] = [];
let running = 0;

async function slot<T>(work: () => Promise<T>): Promise<T> {
  if (running >= CONCURRENCY) await new Promise<void>((resolve) => waiting.push(resolve));
  running++;
  try {
    return await work();
  } finally {
    running--;
    waiting.shift()?.();
  }
}

async function fetchRisk(mint: string): Promise<QuickRisk | null> {
  try {
    const response = await fetch(`${LADON_API_URL}/v1/token/${encodeURIComponent(mint)}/risk?quick=true`);
    if (!response.ok) return null;
    const body = (await response.json()) as QuickRisk;
    return { mint: body.mint, score: body.score, level: body.level, labels: Array.isArray(body.labels) ? body.labels : [] };
  } catch {
    return null;
  }
}

function risk(mint: string): Promise<QuickRisk | null> {
  const hit = cache.get(mint);
  if (hit && hit.until > Date.now()) return Promise.resolve(hit.value);
  const pending = inflight.get(mint);
  if (pending) return pending;
  const job = slot(() => fetchRisk(mint)).then((value) => {
    cache.set(mint, { until: Date.now() + (value ? CACHE_MS : FAILURE_CACHE_MS), value });
    inflight.delete(mint);
    return value;
  });
  inflight.set(mint, job);
  return job;
}

chrome.runtime.onMessage.addListener((message: unknown, _sender, reply) => {
  const request = message as { type?: string; mints?: unknown };
  if (request?.type !== "ladon:risk" || !Array.isArray(request.mints)) return false;
  const mints = request.mints.filter((m): m is string => typeof m === "string" && isSolanaAddress(m)).slice(0, 50);
  Promise.all(mints.map(async (m) => [m, await risk(m)] as const)).then((pairs) => reply(Object.fromEntries(pairs)));
  return true;
});
