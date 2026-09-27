import { isSolanaAddress } from "../../shared/solana";
import { loadFonts } from "./fonts";
import { headline, ordered, type QuickRisk } from "./labels";

const ATTR = "data-pulse-token-address";
const HOST = "ladon-overlay";
const BATCH_MS = 250;

const results = new Map<string, QuickRisk | null>();
const shown = new WeakMap<Element, string>();
const queued = new Set<string>();
let timer: number | undefined;

const COLORS = {
  danger: { ink: "#ff5a5f", fill: "rgba(255, 90, 95, 0.12)" },
  warning: { ink: "#f2c14e", fill: "rgba(242, 193, 78, 0.12)" },
};

const BADGE_STYLE = `
:host { all: initial; display: inline-flex; flex-shrink: 0; align-items: center; }
.badge {
  display: inline-flex; align-items: center; gap: 4px; height: 18px; padding: 0 7px 0 5px;
  border: 1px solid var(--ink); border-radius: 999px; background: var(--fill); color: var(--ink);
  font: 600 12px/1 system-ui, -apple-system, "Segoe UI", sans-serif; white-space: nowrap; cursor: default;
}
svg { width: 12px; height: 12px; flex-shrink: 0; }
`;

const RING_STYLE = `
:host { all: initial; position: absolute; inset: 0; z-index: 25; pointer-events: none; }
.ring { position: absolute; inset: 0; border: 2px solid var(--ink); border-radius: 5px; }
`;

const CHIP_STYLE = `
:host { all: initial; display: inline-flex; flex-shrink: 0; align-items: center; margin-right: 6px; }
.chip {
  display: inline-flex; align-items: center; justify-content: center; width: 16px; height: 16px;
  border-radius: 999px; background: rgba(9, 9, 9, 0.82); color: var(--ink);
}
svg { width: 10px; height: 10px; }
`;

const HALO_STYLE = `
:host { all: initial; position: absolute; inset: -3px; pointer-events: none; }
.halo { position: absolute; inset: 0; border: 1.5px solid var(--ink); border-radius: 999px; opacity: 0.85; }
`;

const ICON = `<svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M7.13 1.5a1 1 0 0 1 1.74 0l6.5 11.5a1 1 0 0 1-.87 1.5H1.5a1 1 0 0 1-.87-1.5z"/><path fill="#0b0b0f" d="M7.25 5.5h1.5l-.25 4.5h-1zM8 11.25a.9.9 0 1 1 0 1.8.9.9 0 0 1 0-1.8z"/></svg>`;

const TIP_STYLE = `
:host { all: initial; position: fixed; z-index: 2147483647; pointer-events: none; }
.tip {
  width: 230px; padding: 10px 12px 12px; box-sizing: border-box;
  background: #14213d; color: #ede8dc; border: 2px solid #1a1a1a; box-shadow: inset 0 0 0 1px rgba(242, 193, 78, 0.35), 3px 3px 0 #1a1a1a;
  font: 400 13px/1.4 "Ladon Plain", system-ui, -apple-system, "Segoe UI", sans-serif;
}
.head { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; }
.name { font: 700 15px/1 "Ladon Caps", Georgia, serif; color: #f2c14e; letter-spacing: 0.02em; }
.score { font-weight: 700; font-size: 18px; line-height: 1; font-variant-numeric: tabular-nums; }
.score small { font-size: 11px; font-weight: 500; opacity: 0.7; }
.level { margin-top: 3px; font-weight: 600; font-size: 12px; }
.high { color: #f5b38f; }
.medium { color: #f2c14e; }
.low { color: #9fd49a; }
.rule { height: 2px; margin: 9px 0 8px; background: repeating-linear-gradient(90deg, rgba(242, 193, 78, 0.45) 0 2px, transparent 2px 4px); }
ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 5px; }
li { display: flex; align-items: baseline; gap: 8px; }
li::before { content: ""; flex-shrink: 0; width: 6px; height: 6px; transform: translateY(-1px); }
li.danger::before { background: #e0663d; }
li.warning::before { background: #f2c14e; }
`;

let tipHost: HTMLElement | undefined;
let tipBox: HTMLElement | undefined;

function tooltip(): { host: HTMLElement; box: HTMLElement } {
  if (!tipHost || !tipBox || !tipHost.isConnected) {
    loadFonts();
    tipHost = document.createElement(HOST);
    tipHost.style.display = "none";
    const root = tipHost.attachShadow({ mode: "closed" });
    const style = document.createElement("style");
    style.textContent = TIP_STYLE;
    tipBox = document.createElement("div");
    tipBox.className = "tip";
    root.append(style, tipBox);
    document.body.append(tipHost);
  }
  return { host: tipHost, box: tipBox };
}

function el(tag: string, className: string, text = ""): HTMLElement {
  const node = document.createElement(tag);
  node.className = className;
  node.textContent = text;
  return node;
}

function showTip(risk: QuickRisk, anchor: DOMRect): void {
  const { host, box } = tooltip();
  const score = el("span", `score ${risk.level}`, String(risk.score));
  score.append(el("small", "", "/100"));
  const head = el("div", "head");
  head.append(el("span", "name", "Ladon"), score);
  const parts: HTMLElement[] = [head, el("div", `level ${risk.level}`, `${risk.level[0].toUpperCase()}${risk.level.slice(1)} risk`)];
  const details = ordered(risk.labels).filter((l) => l.kind !== "high_risk");
  if (details.length > 0) {
    const list = document.createElement("ul");
    for (const label of details) list.append(el("li", label.severity, label.text));
    parts.push(el("div", "rule"), list);
  }
  box.replaceChildren(...parts);
  host.style.display = "block";
  const height = box.offsetHeight;
  host.style.left = `${Math.max(8, Math.min(anchor.left, window.innerWidth - 240))}px`;
  const above = anchor.bottom + 6 + height > window.innerHeight;
  host.style.top = `${above ? anchor.top - 6 - height : anchor.bottom + 6}px`;
  if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    box.animate([{ opacity: 0, transform: `translateY(${above ? 4 : -4}px)` }, { opacity: 1, transform: "none" }], { duration: 150, easing: "ease-out" });
  }
}

function hideTip(): void {
  if (tipHost) tipHost.style.display = "none";
}

function clear(card: Element): void {
  for (const host of card.querySelectorAll(HOST)) host.remove();
}

function nameRow(card: Element): Element | null {
  const ticker = card.querySelector("div.tracking-\\[-0\\.02em\\]");
  return ticker?.parentElement?.parentElement ?? null;
}

function avatar(card: Element): Element | null {
  return card.querySelector("div.relative.h-\\[74px\\].w-\\[74px\\]");
}

function part(css: string, severity: keyof typeof COLORS): { host: HTMLElement; root: ShadowRoot } {
  const host = document.createElement(HOST);
  host.style.setProperty("--ink", COLORS[severity].ink);
  host.style.setProperty("--fill", COLORS[severity].fill);
  const root = host.attachShadow({ mode: "closed" });
  const style = document.createElement("style");
  style.textContent = css;
  root.append(style);
  return { host, root };
}

function render(card: Element, mint: string): void {
  clear(card);
  const risk = results.get(mint);
  const top = risk ? headline(risk) : null;
  const row = nameRow(card);
  if (!risk || !top || !row) return;

  const badge = part(BADGE_STYLE, top.severity);
  const pill = document.createElement("span");
  pill.className = "badge";
  pill.setAttribute("role", "note");
  pill.setAttribute("aria-label", `Ladon: ${ordered(risk.labels).map((l) => l.text).join(", ")}`);
  pill.innerHTML = ICON;
  pill.append(top.text);
  for (const type of ["click", "mousedown", "mouseup", "pointerdown", "pointerup"]) {
    pill.addEventListener(type, (event) => {
      event.stopPropagation();
      event.preventDefault();
    });
  }
  pill.addEventListener("mouseenter", () => showTip(risk, pill.getBoundingClientRect()));
  pill.addEventListener("mouseleave", hideTip);
  badge.root.append(pill);
  row.append(badge.host);

  const frame = avatar(card);
  if (frame && top.severity === "danger") {
    const ring = part(RING_STYLE, top.severity);
    const line = document.createElement("div");
    line.className = "ring";
    ring.root.append(line);
    frame.append(ring.host);
  }
}

let coinButton: HTMLElement | null = null;
let coinKey = "";
let coinHover: AbortController | undefined;
let coinTimer: number | undefined;
const asked = new Set<string>();

function coinMint(): string | null {
  if (!location.pathname.startsWith("/meme/")) return null;
  const link = document.querySelector<HTMLAnchorElement>('a[href*="solscan.io/token/"]');
  const mint = link ? (new URL(link.href).pathname.split("/")[2] ?? "") : "";
  return isSolanaAddress(mint) ? mint : null;
}

function buyButton(): HTMLElement | null {
  for (const button of document.querySelectorAll("button")) {
    if (/^Buy \S/.test(button.textContent?.trim() ?? "")) return button;
  }
  return null;
}

function unmarkCoin(): void {
  coinHover?.abort();
  coinHover = undefined;
  if (coinButton) {
    for (const host of coinButton.querySelectorAll(`:scope > ${HOST}`)) host.remove();
    if (coinButton.dataset.ladonPositioned) {
      coinButton.style.position = "";
      delete coinButton.dataset.ladonPositioned;
    }
  }
  coinButton = null;
  coinKey = "";
}

function markCoin(): void {
  coinTimer = undefined;
  const mint = coinMint();
  if (mint && !results.has(mint) && !asked.has(mint)) {
    asked.add(mint);
    queued.add(mint);
    timer ??= window.setTimeout(flush, BATCH_MS);
  }
  const button = mint ? buyButton() : null;
  const risk = mint ? results.get(mint) : null;
  const top = risk ? headline(risk) : null;
  const key = button && risk && top ? `${mint}:${risk.score}:${top.severity}` : "";
  if (key === coinKey && button === coinButton && (!key || button?.querySelector(`:scope > ${HOST}`))) return;
  unmarkCoin();
  if (!button || !risk || !top) return;

  const chip = part(CHIP_STYLE, top.severity);
  const dot = document.createElement("span");
  dot.className = "chip";
  dot.setAttribute("role", "img");
  dot.setAttribute("aria-label", `Ladon: ${risk.level} risk, ${ordered(risk.labels).map((l) => l.text).join(", ")}`);
  dot.innerHTML = ICON;
  chip.root.append(dot);
  button.prepend(chip.host);

  const halo = part(HALO_STYLE, top.severity);
  const line = document.createElement("div");
  line.className = "halo";
  halo.root.append(line);
  if (getComputedStyle(button).position === "static") {
    button.style.position = "relative";
    button.dataset.ladonPositioned = "true";
  }
  button.append(halo.host);

  coinHover = new AbortController();
  button.addEventListener("mouseenter", () => showTip(risk, button.getBoundingClientRect()), { signal: coinHover.signal });
  button.addEventListener("mouseleave", hideTip, { signal: coinHover.signal });
  coinButton = button;
  coinKey = key;
}

function checkCoin(): void {
  coinTimer ??= window.setTimeout(markCoin, 200);
}

function alive(): boolean {
  if (chrome.runtime?.id) return true;
  observer.disconnect();
  queued.clear();
  return false;
}

function flush(): void {
  timer = undefined;
  const mints = [...queued];
  queued.clear();
  for (const mint of mints) {
    if (!alive()) return;
    chrome.runtime.sendMessage({ type: "ladon:risk", mints: [mint] }, (reply: Record<string, QuickRisk | null> | undefined) => {
      if (chrome.runtime.lastError || !reply) return;
      const risk = reply[mint] ?? null;
      results.set(mint, risk);
      for (const card of document.querySelectorAll(`[${ATTR}="${mint}"]`)) render(card, mint);
      checkCoin();
    });
  }
}

function labelled(mint: string): boolean {
  const risk = results.get(mint);
  return Boolean(risk && headline(risk));
}

function update(card: Element): void {
  const mint = card.getAttribute(ATTR)?.trim() ?? "";
  if (!isSolanaAddress(mint)) {
    clear(card);
    return;
  }
  if (shown.get(card) === mint && labelled(mint) === Boolean(card.querySelector(HOST))) return;
  shown.set(card, mint);
  if (results.has(mint)) {
    render(card, mint);
    return;
  }
  clear(card);
  queued.add(mint);
  timer ??= window.setTimeout(flush, BATCH_MS);
}

function scan(root: ParentNode): void {
  if (root instanceof Element && root.hasAttribute(ATTR)) update(root);
  for (const card of root.querySelectorAll(`[${ATTR}]`)) update(card);
}

const observer = new MutationObserver((changes) => {
  if (!alive()) return;
  for (const change of changes) {
    if (change.type === "attributes" && change.target instanceof Element) update(change.target);
    for (const node of change.addedNodes) if (node instanceof Element && node.localName !== HOST) scan(node);
    const card = change.target instanceof Element ? change.target.closest(`[${ATTR}]`) : null;
    if (card && change.type === "childList") update(card);
  }
  checkCoin();
});
observer.observe(document.documentElement, { subtree: true, childList: true, attributes: true, attributeFilter: [ATTR] });

scan(document);
checkCoin();
