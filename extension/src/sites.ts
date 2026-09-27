export type SiteVerdict = { kind: "blocked"; host: string } | { kind: "lookalike"; host: string; brand: string; official: string };

type Brand = { name: string; token: string; official: string[] };

const BRANDS: Brand[] = [
  { name: "Phantom", token: "phantom", official: ["phantom.app", "phantom.com"] },
  { name: "Solflare", token: "solflare", official: ["solflare.com"] },
  { name: "Raydium", token: "raydium", official: ["raydium.io"] },
  { name: "Solscan", token: "solscan", official: ["solscan.io"] },
  { name: "Jupiter", token: "jupag", official: ["jup.ag"] },
  { name: "Pump.fun", token: "pumpfun", official: ["pump.fun"] },
  { name: "DEX Screener", token: "dexscreener", official: ["dexscreener.com"] },
];

const LURES = new Set([
  "app", "web", "wallet", "wallets", "claim", "claims", "airdrop", "airdrops", "drop", "connect", "support", "sync",
  "mint", "reward", "rewards", "verify", "official", "dapp", "dapps", "login", "secure", "restore", "recover",
  "recovery", "portal", "bonus", "event", "extension", "sol", "solana", "fix", "validate", "help", "io", "fi",
]);

const CONFUSABLE: [RegExp, string][] = [
  [/rn/g, "m"],
  [/vv/g, "w"],
  [/0/g, "o"],
  [/[1i]/g, "l"],
  [/3/g, "e"],
  [/5/g, "s"],
  [/-/g, ""],
];

function fold(label: string): string {
  return CONFUSABLE.reduce((value, [pattern, to]) => value.replace(pattern, to), label);
}

export function normalizeHost(host: string): string {
  return host.trim().toLowerCase().replace(/\.$/, "").replace(/^www\./, "");
}

function within(host: string, domain: string): boolean {
  return host === domain || host.endsWith(`.${domain}`);
}

export function isBlocked(host: string, blocked: ReadonlySet<string>): boolean {
  const labels = normalizeHost(host).split(".");
  for (let i = 0; i < labels.length - 1; i++) {
    if (blocked.has(labels.slice(i).join("."))) return true;
  }
  return false;
}

function oneEditApart(a: string, b: string): boolean {
  if (Math.abs(a.length - b.length) > 1 || a === b) return false;
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) i++;
  if (a.length === b.length) return a.slice(i + 1) === b.slice(i + 1);
  return a.length > b.length ? a.slice(i + 1) === b.slice(i) : a.slice(i) === b.slice(i + 1);
}

const FOLDED_LURES = [...LURES].map(fold);

function lureOnly(rest: string): boolean {
  if (rest === "") return true;
  for (const lure of FOLDED_LURES) {
    if (rest.startsWith(lure) && lureOnly(rest.slice(lure.length))) return true;
  }
  return false;
}

function imitates(label: string, token: string): boolean {
  const folded = fold(label);
  const target = fold(token);
  if (folded === target || (target.length >= 6 && oneEditApart(folded, target))) return true;
  const at = folded.indexOf(target);
  if (at < 0) return false;
  return lureOnly(folded.slice(0, at)) && lureOnly(folded.slice(at + target.length));
}

export function lookalike(host: string): { brand: string; official: string } | null {
  const clean = normalizeHost(host);
  const labels = clean.split(".");
  if (labels.length < 2 || labels.some((l) => l.startsWith("xn--"))) return null;
  const site = labels.slice(0, -1);
  for (const brand of BRANDS) {
    if (brand.official.some((domain) => within(clean, domain))) return null;
  }
  for (const brand of BRANDS) {
    if (site.some((label) => imitates(label, brand.token))) return { brand: brand.name, official: brand.official[0] };
  }
  return null;
}

export function verdict(host: string, blocked: ReadonlySet<string>): SiteVerdict | null {
  const clean = normalizeHost(host);
  if (!clean.includes(".")) return null;
  if (isBlocked(clean, blocked)) return { kind: "blocked", host: clean };
  const match = lookalike(clean);
  return match ? { kind: "lookalike", host: clean, ...match } : null;
}
