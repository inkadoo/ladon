import { walletLevel, type AddressRisk } from "../../shared/api";
import { isSolanaAddress, shortAddress } from "../../shared/solana";
import { loadFonts } from "./fonts";
import { sharedEnds } from "./poison";
import type { SiteVerdict } from "./sites";
import type { Target, TargetKind } from "./transaction";

const ASK = "ladon:check";
const ANSWER = "ladon:answer";
const SIGNED = "ladon:signed";
const KINDS = new Set<TargetKind>(["payment", "approval", "authority"]);
const QUIET_MS = 600;
const GIVE_UP_MS = 15000;

type Flagged = { target: Target; risk: AddressRisk; level: "high" | "medium" };

const STYLE = `
:host { all: initial; position: fixed; inset: 0; z-index: 2147483647; }
* { box-sizing: border-box; }
.backdrop {
  position: fixed; inset: 0; display: grid; place-items: center; padding: 16px; overflow-y: auto;
  background: rgba(10, 14, 28, 0.72);
  font: 400 15px/1.45 "Ladon Plain", system-ui, -apple-system, "Segoe UI", sans-serif; color: #1a1a1a;
}
.card {
  width: min(100%, 340px); background: #14213d; color: #ede8dc;
  border: 2px solid #1a1a1a; box-shadow: inset 0 0 0 1px var(--line), 4px 4px 0 #1a1a1a;
}
.card.high { --accent: #e0663d; --soft: #f5b38f; --line: rgba(224, 102, 61, 0.55); }
.card.medium { --accent: #f2c14e; --soft: #f2c14e; --line: rgba(242, 193, 78, 0.45); }
.hazard { height: 6px; background: repeating-linear-gradient(90deg, var(--accent) 0 6px, transparent 6px 12px); image-rendering: pixelated; }
.inner { display: grid; gap: 12px; padding: 16px 18px 18px; }
.top { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.name { font: 700 16px/1 "Ladon Caps", Georgia, serif; color: #f2c14e; letter-spacing: 0.02em; }
.score { font-weight: 700; font-size: 20px; line-height: 1; color: var(--soft); font-variant-numeric: tabular-nums; }
.score small { font-size: 12px; font-weight: 500; opacity: 0.8; margin-left: 3px; }
h2 { margin: 0; font: 700 19px/1.3 "Ladon Plain", system-ui, sans-serif; color: #ede8dc; }
p { margin: 0; }
ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 6px; }
li { display: flex; align-items: baseline; gap: 10px; font-size: 14px; }
li::before { content: ""; flex-shrink: 0; width: 6px; height: 6px; background: var(--accent); transform: translateY(-2px); }
.to { font-size: 13px; color: rgba(237, 232, 220, 0.65); }
.to code { font: 500 13px/1.4 ui-monospace, "SF Mono", Menlo, monospace; color: #ede8dc; }
.actions { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; padding-top: 4px; }
button { font: inherit; cursor: pointer; }
.cancel { border: 2px solid #1a1a1a; background: #ede8dc; color: #1a1a1a; padding: 9px 18px; font-weight: 700; box-shadow: 3px 3px 0 #1a1a1a; }
.cancel:hover { background: #fff; }
.cancel:active { transform: translate(2px, 2px); box-shadow: 1px 1px 0 #1a1a1a; }
.continue { border: 0; background: none; padding: 6px 0; color: rgba(237, 232, 220, 0.7); text-decoration: underline; text-underline-offset: 3px; font-size: 14px; }
.continue:hover { color: #ede8dc; }
button:focus-visible { outline: 2px solid #f2c14e; outline-offset: 3px; }
.checking { width: min(100%, 360px); background: #14213d; color: #ede8dc; border: 2px solid #1a1a1a; box-shadow: inset 0 0 0 1px rgba(242, 193, 78, 0.35), 4px 4px 0 #1a1a1a; padding: 16px 18px; display: grid; gap: 10px; }
.checking .continue { justify-self: start; padding: 4px 0; color: rgba(237, 232, 220, 0.85); }
@keyframes rise { from { opacity: 0; transform: translateY(6px); } }
@keyframes fade { from { opacity: 0; } }
.backdrop.solid { background: rgba(10, 14, 28, 0.94); }
.badge { font-weight: 700; font-size: 13px; line-height: 1; color: var(--soft); letter-spacing: 0.02em; }
.pair { display: grid; grid-template-columns: auto 1fr; gap: 6px 10px; align-items: baseline; font-size: 12px; color: rgba(237, 232, 220, 0.65); }
.pair code { font: 500 12px/1.45 ui-monospace, "SF Mono", Menlo, monospace; color: rgba(237, 232, 220, 0.75); word-break: break-all; }
.pair .diff { color: var(--soft); background: rgba(224, 102, 61, 0.2); }
.backdrop { animation: fade 150ms ease-out both; }
.card, .checking { animation: rise 180ms ease-out both; }
@media (prefers-reduced-motion: reduce) { .backdrop, .card, .checking { animation: none; } .cancel:active { transform: none; } }
`;

const TITLE: Record<"high" | "medium", Record<TargetKind, string>> = {
  high: {
    payment: "This wallet is linked to scams.",
    approval: "This gives a scam wallet your tokens.",
    authority: "This gives a scam wallet your tokens.",
  },
  medium: {
    payment: "This wallet looks risky.",
    approval: "This gives a risky wallet your tokens.",
    authority: "This gives a risky wallet your tokens.",
  },
};

const STOP: Record<TargetKind, [string, string]> = {
  payment: ["Don’t send", "Send anyway"],
  approval: ["Don’t sign", "Sign anyway"],
  authority: ["Don’t sign", "Sign anyway"],
};

function el(tag: string, className = "", text = ""): HTMLElement {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text) node.textContent = text;
  return node;
}

function button(className: string, text: string, onClick: () => void): HTMLButtonElement {
  const node = el("button", className, text) as HTMLButtonElement;
  node.type = "button";
  node.addEventListener("click", onClick);
  return node;
}

type Screen = { close: () => void; root: ShadowRoot; backdrop: HTMLElement };

function screen(): Screen {
  loadFonts();
  const host = document.createElement("ladon-guard");
  const root = host.attachShadow({ mode: "closed" });
  const style = document.createElement("style");
  style.textContent = STYLE;
  const backdrop = el("div", "backdrop");
  root.append(style, backdrop);
  const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  (document.body ?? document.documentElement).append(host);
  return {
    root,
    backdrop,
    close: () => {
      host.remove();
      previous?.focus({ preventScroll: true });
    },
  };
}

function trapFocus(root: ShadowRoot, container: HTMLElement, onEscape: () => void): void {
  container.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      onEscape();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = [...container.querySelectorAll<HTMLElement>("button")];
    if (focusable.length === 0) return;
    const index = focusable.indexOf(root.activeElement as HTMLElement);
    const next = event.shiftKey ? (index <= 0 ? focusable.length - 1 : index - 1) : (index + 1) % focusable.length;
    event.preventDefault();
    focusable[next].focus();
  });
}

function checking(onSkip: () => void): Screen {
  const view = screen();
  const box = el("div", "checking");
  box.setAttribute("role", "status");
  box.append(el("span", "name", "Ladon"), el("p", "", "Checking who this transaction pays before your wallet opens…"));
  const skip = button("continue", "Continue without the check", onSkip);
  box.append(skip);
  trapFocus(view.root, box, onSkip);
  view.backdrop.append(box);
  skip.focus();
  return view;
}

type Alert = {
  level: "high" | "medium";
  badge: Node;
  title: string;
  reason?: string;
  details: Node[];
  stop: string;
  go: string;
  solid?: boolean;
};

function alert(content: Alert, decide: (proceed: boolean) => void): Screen {
  const view = screen();
  if (content.solid) view.backdrop.classList.add("solid");
  const card = el("div", `card ${content.level}`);
  card.setAttribute("role", "alertdialog");
  card.setAttribute("aria-modal", "true");
  card.setAttribute("aria-labelledby", "ladon-title");

  const hazard = el("div", "hazard");
  hazard.setAttribute("aria-hidden", "true");
  const inner = el("div", "inner");
  const head = el("div", "top");
  head.append(el("span", "name", "Ladon"), content.badge);
  const title = el("h2", "", content.title);
  title.id = "ladon-title";
  inner.append(head, title);

  if (content.reason) {
    const list = el("ul");
    list.append(el("li", "", content.reason));
    inner.append(list);
  }
  inner.append(...content.details);

  const actions = el("div", "actions");
  const cancel = button("cancel", content.stop, () => decide(false));
  actions.append(cancel, button("continue", content.go, () => decide(true)));
  inner.append(actions);

  card.append(hazard, inner);
  trapFocus(view.root, card, () => decide(false));
  view.backdrop.append(card);
  cancel.focus();
  return view;
}

function line(label: string, value: string, full = value): HTMLElement {
  const row = el("p", "to", `${label} `);
  const code = el("code", "", value);
  code.title = full;
  row.append(code);
  return row;
}

function riskAlert(top: Flagged): Alert {
  const kind = top.target.kind;
  const percent = Math.round(top.risk.risk * 100);
  const score = el("span", "score", `${percent}%`);
  score.append(el("small", "", "likely"));
  score.title = "Scores are probabilities, not accusations.";
  const shown = top.risk.address || top.target.address;
  const [stop, go] = STOP[kind];
  return { level: top.level, badge: score, title: TITLE[top.level][kind], reason: top.risk.reasons[0]?.text, details: [line("To", shortAddress(shown), shown)], stop, go };
}

function marked(address: string, start: number, end: number): HTMLElement {
  const code = el("code");
  code.append(address.slice(0, start), el("span", "diff", address.slice(start, address.length - end)), address.slice(address.length - end));
  return code;
}

function poisonAlert(address: string, used: string): Alert {
  const { start, end } = sharedEnds(address, used);
  const pair = el("div", "pair");
  pair.append(el("span", "", "New"), marked(address, start, end), el("span", "", "Yours"), marked(used, start, end));
  return {
    level: "high",
    badge: el("span", "badge", "Lookalike"),
    title: "Not the address you’ve used before.",
    details: [pair],
    stop: "Don’t send",
    go: "Send anyway",
  };
}

function siteTitle(site: SiteVerdict): string {
  return site.kind === "blocked" ? "This site is a known scam." : `This isn’t the real ${site.brand}.`;
}

function siteAlert(site: SiteVerdict, signing: boolean): Alert {
  const details = [line("Site", site.host)];
  if (site.kind === "lookalike") details.push(line("Real", site.official));
  const [stop, go] = signing
    ? ["Don’t sign", "Sign anyway"]
    : [site.kind === "lookalike" ? `Go to ${site.official}` : "Leave site", "Stay anyway"];
  return {
    level: "high",
    badge: el("span", "badge", site.kind === "blocked" ? "Scam site" : "Fake site"),
    title: siteTitle(site),
    details,
    stop,
    go,
    solid: !signing,
  };
}

function send<T>(message: Record<string, unknown>): Promise<T | null> {
  return new Promise((resolve) => {
    if (!chrome.runtime?.id) return resolve(null);
    try {
      chrome.runtime.sendMessage(message, (reply: T | undefined) => resolve(chrome.runtime.lastError || reply === undefined ? null : reply));
    } catch {
      resolve(null);
    }
  });
}

function lookup(addresses: string[]): Promise<Record<string, AddressRisk | null> | null> {
  return send({ type: "ladon:address", addresses });
}

function flaggedIn(targets: Target[], results: Record<string, AddressRisk | null>): Flagged[] {
  const found: Flagged[] = [];
  for (const target of targets) {
    const risk = results[target.address];
    const level = risk ? walletLevel(risk) : "none";
    if (risk && (level === "high" || level === "medium")) found.push({ target, risk, level });
  }
  return found.sort((a, b) => b.risk.risk - a.risk.risk);
}

function decideOn(content: Alert): Promise<boolean> {
  return new Promise((resolve) => {
    const shown = alert(content, (proceed) => {
      shown.close();
      resolve(proceed);
    });
  });
}

async function review(targets: Target[]): Promise<boolean> {
  const payments = targets.filter((t) => t.kind === "payment").map((t) => t.address);
  const similar = send<Record<string, string>>({ type: "ladon:lookalikes", addresses: payments });
  let view: Screen | undefined;
  let skipped: (() => void) | undefined;
  const skip = new Promise<null>((resolve) => (skipped = () => resolve(null)));
  const quiet = setTimeout(() => (view = checking(() => skipped?.())), QUIET_MS);
  const giveUp = new Promise<null>((resolve) => setTimeout(() => resolve(null), GIVE_UP_MS));
  const results = await Promise.race([lookup(targets.map((t) => t.address)), skip, giveUp]);
  clearTimeout(quiet);
  view?.close();

  const flagged = results ? flaggedIn(targets, results) : [];
  if (flagged.length > 0) return decideOn(riskAlert(flagged[0]));
  const matches = (await similar) ?? {};
  const poisoned = payments.find((address) => typeof matches[address] === "string" && isSolanaAddress(matches[address]));
  if (poisoned) return decideOn(poisonAlert(poisoned, matches[poisoned]));
  const site = await siteCheck;
  if (site) return decideOn(siteAlert(site, true));
  return true;
}

function parseTargets(value: unknown): Target[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((t): t is Target => {
      const candidate = t as Partial<Target> | null;
      return typeof candidate?.address === "string" && isSolanaAddress(candidate.address) && KINDS.has(candidate.kind as TargetKind);
    })
    .slice(0, 5)
    .map((t) => ({ address: t.address.trim(), kind: t.kind }));
}

let queue = Promise.resolve();

window.addEventListener("message", (event) => {
  if (event.source !== window) return;
  const data = event.data as { channel?: unknown; id?: unknown; targets?: unknown; addresses?: unknown } | null;
  if (data?.channel === SIGNED && Array.isArray(data.addresses)) {
    const addresses = data.addresses.filter((a): a is string => typeof a === "string" && isSolanaAddress(a)).slice(0, 10);
    if (addresses.length > 0) send({ type: "ladon:remember", addresses });
    return;
  }
  if (data?.channel !== ASK || typeof data.id !== "string" || data.id.length > 64) return;
  const id = data.id;
  const targets = parseTargets(data.targets);
  window.postMessage({ channel: ANSWER, id, type: "ack" }, "*");
  queue = queue.then(async () => {
    const proceed = targets.length === 0 ? true : await review(targets).catch(() => true);
    window.postMessage({ channel: ANSWER, id, type: "result", proceed }, "*");
  });
});

type Site = SiteVerdict & { stayed?: boolean };

function isSiteVerdict(value: unknown): value is Site {
  const v = value as Partial<{ kind: unknown; host: unknown; brand: unknown; official: unknown }> | null;
  if (!v || typeof v.host !== "string") return false;
  return v.kind === "blocked" || (v.kind === "lookalike" && typeof v.brand === "string" && typeof v.official === "string");
}

const siteCheck: Promise<Site | null> =
  window === window.top && /^https?:$/.test(location.protocol)
    ? send<unknown>({ type: "ladon:site", host: location.hostname }).then((v) => (isSiteVerdict(v) ? v : null))
    : Promise.resolve(null);

siteCheck.then(async (site) => {
  if (!site || site.stayed) return;
  const stay = await decideOn(siteAlert(site, false));
  if (stay) {
    send({ type: "ladon:stay", host: site.host });
    return;
  }
  if (site.kind === "lookalike") location.replace(`https://${site.official}`);
  else send({ type: "ladon:leave" });
});
