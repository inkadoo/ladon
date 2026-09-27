import { checkWallet, type AddressRisk } from "../../shared/api";
import { isSolanaAddress } from "../../shared/solana";
import type { QuickRisk } from "./labels";
import { lookalikeOf } from "./poison";
import { verdict } from "./sites";

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

const addresses = new Map<string, { until: number; value: Promise<AddressRisk | null> }>();

function address(value: string): Promise<AddressRisk | null> {
  const hit = addresses.get(value);
  if (hit && hit.until > Date.now()) return hit.value;
  const job = checkWallet(LADON_API_URL, value).catch(() => null);
  addresses.set(value, { until: Date.now() + CACHE_MS, value: job });
  job.then((result) => {
    if (!result) addresses.set(value, { until: Date.now() + FAILURE_CACHE_MS, value: job });
  });
  return job;
}

const PHISHING_KEY = "ladon:phishing";
const KNOWN_KEY = "ladon:known";
const PHISHING_MS = 6 * 60 * 60 * 1000;
const MAX_KNOWN = 500;

let blocked: Promise<Set<string>> | undefined;
let blockedAt = 0;

async function fetchBlocked(): Promise<Set<string>> {
  const stored = (await chrome.storage.local.get(PHISHING_KEY))[PHISHING_KEY] as { domains?: unknown; at?: unknown } | undefined;
  const cached = Array.isArray(stored?.domains) ? stored.domains.filter((d): d is string => typeof d === "string") : [];
  if (cached.length > 0 && typeof stored?.at === "number" && Date.now() - stored.at < PHISHING_MS) return new Set(cached);
  try {
    const response = await fetch(`${LADON_API_URL}/v1/phishing/domains`);
    if (!response.ok) throw new Error(String(response.status));
    const body = (await response.json()) as { domains?: unknown };
    const domains = Array.isArray(body.domains) ? body.domains.filter((d): d is string => typeof d === "string" && d.length <= 253) : [];
    await chrome.storage.local.set({ [PHISHING_KEY]: { domains, at: Date.now() } });
    return new Set(domains);
  } catch {
    return new Set(cached);
  }
}

function blockedDomains(): Promise<Set<string>> {
  if (!blocked || Date.now() - blockedAt > PHISHING_MS) {
    blockedAt = Date.now();
    blocked = fetchBlocked();
  }
  return blocked;
}

const STAY_KEY = "ladon:stayed";

async function stayed(): Promise<string[]> {
  const stored = (await chrome.storage.session.get(STAY_KEY))[STAY_KEY];
  return Array.isArray(stored) ? stored.filter((h): h is string => typeof h === "string") : [];
}

async function known(): Promise<string[]> {
  const stored = (await chrome.storage.local.get(KNOWN_KEY))[KNOWN_KEY];
  return Array.isArray(stored) ? stored.filter((a): a is string => typeof a === "string") : [];
}

let remembering = Promise.resolve();

function rememberAddresses(addresses: string[]): void {
  remembering = remembering.then(async () => {
    const fresh = addresses.filter(isSolanaAddress);
    const merged = [...fresh, ...(await known()).filter((a) => !fresh.includes(a))].slice(0, MAX_KNOWN);
    await chrome.storage.local.set({ [KNOWN_KEY]: merged });
  });
}

async function lookalikes(addresses: string[]): Promise<Record<string, string>> {
  const list = await known();
  const found: Record<string, string> = {};
  for (const address of addresses) {
    const match = lookalikeOf(address, list);
    if (match) found[address] = match;
  }
  return found;
}

function addressList(value: unknown, limit: number): string[] {
  return Array.isArray(value) ? value.filter((a): a is string => typeof a === "string" && isSolanaAddress(a)).slice(0, limit) : [];
}

chrome.runtime.onMessage.addListener((message: unknown, sender, reply) => {
  const request = message as { type?: string; mints?: unknown; addresses?: unknown; host?: unknown };
  if (request?.type === "ladon:site" && typeof request.host === "string") {
    const host = request.host.slice(0, 253);
    Promise.all([blockedDomains(), stayed()]).then(([domains, hosts]) => {
      const found = verdict(host, domains);
      reply(found ? { ...found, stayed: hosts.includes(found.host) } : null);
    });
    return true;
  }
  if (request?.type === "ladon:stay" && typeof request.host === "string") {
    const host = request.host.slice(0, 253);
    stayed().then((hosts) => chrome.storage.session.set({ [STAY_KEY]: [...new Set([...hosts, host])].slice(-100) }));
    return false;
  }
  if (request?.type === "ladon:leave") {
    if (sender.tab?.id !== undefined) chrome.tabs.update(sender.tab.id, { url: "chrome://newtab" });
    return false;
  }
  if (request?.type === "ladon:lookalikes") {
    lookalikes(addressList(request.addresses, 5)).then(reply);
    return true;
  }
  if (request?.type === "ladon:remember") {
    rememberAddresses(addressList(request.addresses, 10));
    return false;
  }
  if (request?.type === "ladon:address" && Array.isArray(request.addresses)) {
    const list = addressList(request.addresses, 5);
    Promise.all(list.map(async (a) => [a, await address(a)] as const)).then((pairs) => reply(Object.fromEntries(pairs)));
    return true;
  }
  if (request?.type !== "ladon:risk" || !Array.isArray(request.mints)) return false;
  const mints = request.mints.filter((m): m is string => typeof m === "string" && isSolanaAddress(m)).slice(0, 50);
  Promise.all(mints.map(async (m) => [m, await risk(m)] as const)).then((pairs) => reply(Object.fromEntries(pairs)));
  return true;
});
