import { isSolanaAddress } from "../../shared/solana";
import { headline, ordered, type QuickRisk } from "./labels";

const ATTR = "data-pulse-token-address";
const HOST = "ladon-overlay";
const BATCH_MS = 250;
const ROOM_FOR_COUNT = 9;

const results = new Map<string, QuickRisk | null>();
const shown = new WeakMap<Element, string>();
const queued = new Set<string>();
let timer: number | undefined;

const STYLE = `
:host { all: initial; }
.bar { position: absolute; left: 0; top: 0; bottom: 0; width: 3px; pointer-events: none; }
.pill {
  position: absolute; left: 17px; top: 14px; z-index: 30; max-width: 74px;
  display: flex; align-items: center; gap: 3px; padding: 1px 4px;
  font: 700 10px/1.35 system-ui, -apple-system, "Segoe UI", sans-serif; letter-spacing: 0;
  border: 1.5px solid #1a1a1a; box-shadow: 2px 2px 0 #1a1a1a; cursor: default; white-space: nowrap;
}
.pill span { overflow: hidden; text-overflow: ellipsis; }
.danger .bar { background: #b8552f; }
.danger .pill { background: #b8552f; color: #ede8dc; }
.warning .bar { background: #f2c14e; }
.warning .pill { background: #f2c14e; color: #1a1a1a; }
.more { opacity: .85; font-weight: 600; }
`;

const TIP_STYLE = `
.ladon-tip {
  position: fixed; z-index: 2147483647; max-width: 260px; padding: 10px 12px;
  background: #14213d; color: #ede8dc; border: 2px solid #f2c14e; box-shadow: 3px 3px 0 #1a1a1a;
  font: 400 12.5px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; pointer-events: none;
}
.ladon-tip b { display: block; margin-bottom: 4px; font-size: 13px; }
.ladon-tip ul { margin: 0; padding: 0 0 0 16px; }
.ladon-tip li.danger { color: #f5b38f; }
.ladon-tip p { margin: 6px 0 0; font-size: 11px; opacity: .8; }
`;

function tooltip(): HTMLElement {
  let tip = document.querySelector<HTMLElement>(".ladon-tip");
  if (!tip) {
    const style = document.createElement("style");
    style.textContent = TIP_STYLE;
    document.head.append(style);
    tip = document.createElement("div");
    tip.className = "ladon-tip";
    tip.hidden = true;
    document.body.append(tip);
  }
  return tip;
}

function showTip(risk: QuickRisk, anchor: DOMRect): void {
  const tip = tooltip();
  const title = document.createElement("b");
  title.textContent = `Ladon: ${risk.score}/100, ${risk.level} risk`;
  const list = document.createElement("ul");
  for (const label of ordered(risk.labels)) {
    const item = document.createElement("li");
    item.className = label.severity;
    item.textContent = label.text;
    list.append(item);
  }
  const note = document.createElement("p");
  note.textContent = "Based on the creator's onchain history. Scores are probabilities, not accusations.";
  tip.replaceChildren(title, list, note);
  tip.hidden = false;
  const left = Math.min(anchor.left, window.innerWidth - 280);
  tip.style.left = `${Math.max(8, left)}px`;
  tip.style.top = `${anchor.bottom + 6 + 150 > window.innerHeight ? anchor.top - 6 - tip.offsetHeight : anchor.bottom + 6}px`;
}

function hideTip(): void {
  const tip = document.querySelector<HTMLElement>(".ladon-tip");
  if (tip) tip.hidden = true;
}

function clear(card: Element): void {
  card.querySelector(`:scope > ${HOST}`)?.remove();
}

function render(card: Element, mint: string): void {
  clear(card);
  const risk = results.get(mint);
  const top = risk ? headline(risk) : null;
  if (!risk || !top) return;
  const host = document.createElement(HOST);
  const root = host.attachShadow({ mode: "closed" });
  const style = document.createElement("style");
  style.textContent = STYLE;
  const wrap = document.createElement("div");
  wrap.className = top.severity;
  const bar = document.createElement("div");
  bar.className = "bar";
  const pill = document.createElement("div");
  pill.className = "pill";
  pill.setAttribute("role", "note");
  pill.setAttribute("aria-label", `Ladon: ${ordered(risk.labels).map((l) => l.text).join(", ")}`);
  const text = document.createElement("span");
  text.textContent = top.text;
  pill.append(text);
  if (top.more > 0 && top.text.length <= ROOM_FOR_COUNT) {
    const more = document.createElement("span");
    more.className = "more";
    more.textContent = `+${top.more}`;
    pill.append(more);
  }
  for (const type of ["click", "mousedown", "mouseup", "pointerdown", "pointerup"]) {
    pill.addEventListener(type, (event) => {
      event.stopPropagation();
      event.preventDefault();
    });
  }
  pill.addEventListener("mouseenter", () => showTip(risk, pill.getBoundingClientRect()));
  pill.addEventListener("mouseleave", hideTip);
  wrap.append(bar, pill);
  root.append(style, wrap);
  card.append(host);
}

function flush(): void {
  timer = undefined;
  const mints = [...queued];
  queued.clear();
  for (const mint of mints) {
    chrome.runtime.sendMessage({ type: "ladon:risk", mints: [mint] }, (reply: Record<string, QuickRisk | null> | undefined) => {
      if (chrome.runtime.lastError || !reply) return;
      const risk = reply[mint] ?? null;
      results.set(mint, risk);
      for (const card of document.querySelectorAll(`[${ATTR}="${mint}"]`)) render(card, mint);
    });
  }
}

function update(card: Element): void {
  const mint = card.getAttribute(ATTR)?.trim() ?? "";
  if (!isSolanaAddress(mint)) {
    clear(card);
    return;
  }
  if (shown.get(card) === mint && card.querySelector(`:scope > ${HOST}`)) return;
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

new MutationObserver((changes) => {
  for (const change of changes) {
    if (change.type === "attributes" && change.target instanceof Element) update(change.target);
    for (const node of change.addedNodes) if (node instanceof Element && node.localName !== HOST) scan(node);
  }
}).observe(document.documentElement, { subtree: true, childList: true, attributes: true, attributeFilter: [ATTR] });

scan(document);
