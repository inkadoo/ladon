import { ApiError, check, report, walletLevel, type AddressRisk, type RiskLevel, type TokenRisk } from "../../shared/api";
import { isSolanaAddress, isTransactionSignature, shortAddress } from "../../shared/solana";
import { track } from "./analytics";

const TITLES: Record<RiskLevel, string> = { high: "High risk", medium: "Medium risk", low: "Low risk" };

const TOKEN_MEANING: Record<RiskLevel, string> = {
  high: "Strong signs of a rug pull from this token's creator or the wallets around them. We would not buy it.",
  medium: "Some warning signs. Read why before you buy.",
  low: "We found no strong warning signs. That is not a guarantee the token is safe.",
};

const WALLET_MEANING: Record<RiskLevel, string> = {
  high: "Strong onchain evidence links this wallet to scams. We would not send money to it.",
  medium: "This wallet shows warning signs. Read why before you send anything.",
  low: "We found no strong warning signs for this wallet. That is not a guarantee it is safe.",
};

type Child = Node | string | null | undefined | false;

function el(tag: string, props: { class?: string; text?: string } = {}, children: Child[] = []): HTMLElement {
  const node = document.createElement(tag);
  if (props.class) node.className = props.class;
  if (props.text !== undefined) node.textContent = props.text;
  for (const child of children) {
    if (child) node.append(child);
  }
  return node;
}

function byId<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id);
  if (!node) throw new Error(`missing #${id}`);
  return node as T;
}

function show(target: HTMLElement, node: Node | null): void {
  target.replaceChildren(...(node ? [node] : []));
}

function message(kind: "plain" | "error" | "done", title: string, body: string): HTMLElement {
  return el("div", { class: `panel ${kind}` }, [el("b", { text: title }), el("p", { class: "meaning", text: body })]);
}

function scorePanel(level: RiskLevel, score: string, unit: string, meaning: string, what: string): HTMLElement {
  return el("div", { class: `panel ${level}` }, [
    el("div", { class: "score" }, [el("strong", { text: score }), el("span", { text: unit }), el("b", { class: "badge", text: TITLES[level] })]),
    el("p", { class: "meaning", text: meaning }),
    el("p", { class: "what", text: what }),
  ]);
}

function tokenResult(result: TokenRisk): HTMLElement {
  const counted = result.reasons.filter((r) => r.points > 0);
  const others = result.reasons.filter((r) => r.points === 0);
  const item = (r: TokenRisk["reasons"][number]) =>
    el("li", {}, [r.points > 0 && el("span", { class: "points", text: `+${r.points}` }), el("div", {}, [el("b", { text: r.label }), el("p", { text: r.explanation })])]);
  return el("div", {}, [
    scorePanel(result.level, String(result.score), "/100", TOKEN_MEANING[result.level], `Token ${shortAddress(result.mint)}. Scores are probabilities, not accusations.`),
    counted.length > 0 && el("ul", { class: "reasons" }, counted.map(item)),
    others.length > 0 &&
      el("details", {}, [el("summary", { text: `${others.length} other ${others.length === 1 ? "check" : "checks"}` }), el("ul", { class: "reasons" }, others.map(item))]),
  ]);
}

function walletResult(result: AddressRisk): HTMLElement {
  const level = walletLevel(result);
  if (level === "none") {
    return message("plain", "Nothing known about this wallet", "Ladon has no reports or onchain evidence about it yet. That is not a guarantee it is safe.");
  }
  return el("div", {}, [
    scorePanel(level, `${Math.round(result.risk * 100)}%`, "risk", WALLET_MEANING[level], `Wallet ${shortAddress(result.address)}. Scores are probabilities, not accusations.`),
    el("ul", { class: "reasons" }, result.reasons.map((r) => el("li", {}, [el("div", {}, [el("p", { text: r.text })])]))),
  ]);
}

function errorText(error: unknown): string {
  return error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
}

function setupTabs(): void {
  const tabs = [byId<HTMLButtonElement>("tab-check"), byId<HTMLButtonElement>("tab-report")];
  const select = (chosen: HTMLButtonElement) => {
    for (const tab of tabs) {
      const on = tab === chosen;
      tab.setAttribute("aria-selected", String(on));
      tab.tabIndex = on ? 0 : -1;
      byId(tab.getAttribute("aria-controls") ?? "").hidden = !on;
    }
  };
  for (const tab of tabs) {
    tab.addEventListener("click", () => select(tab));
    tab.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      const next = tabs[(tabs.indexOf(tab) + 1) % tabs.length];
      select(next);
      next.focus();
    });
  }
}

function setupCheck(): void {
  const form = byId<HTMLFormElement>("check-form");
  const input = byId<HTMLInputElement>("check-address");
  const hint = byId("check-hint");
  const button = byId<HTMLButtonElement>("check-button");
  const output = byId("check-result");
  const defaultHint = hint.textContent ?? "";

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const address = input.value.trim();
    const valid = isSolanaAddress(address);
    input.setAttribute("aria-invalid", String(!valid));
    hint.classList.toggle("bad", !valid);
    hint.textContent = valid ? defaultHint : "That doesn't look like a Solana address. Copy it again and paste the whole thing.";
    if (!valid) return;
    button.disabled = true;
    button.textContent = "Checking…";
    show(output, message("plain", `Checking ${shortAddress(address)}…`, "Looking at its onchain history. This takes a few seconds."));
    try {
      const found = await check(LADON_API_URL, address);
      show(output, found.kind === "token" ? tokenResult(found.result) : walletResult(found.result));
      track(found.kind === "token" ? { name: "token_checked", mint: address } : { name: "address_checked", address });
    } catch (error) {
      show(output, message("error", "We couldn't check that address", errorText(error)));
    } finally {
      button.disabled = false;
      button.textContent = "Check";
    }
  });
}

function setupReport(): void {
  const form = byId<HTMLFormElement>("report-form");
  const address = byId<HTMLInputElement>("report-address");
  const addressHint = byId("report-address-hint");
  const signature = byId<HTMLInputElement>("report-signature");
  const signatureHint = byId("report-signature-hint");
  const description = byId<HTMLTextAreaElement>("report-description");
  const button = byId<HTMLButtonElement>("report-button");
  const output = byId("report-result");
  const hints = new Map([
    [addressHint, addressHint.textContent ?? ""],
    [signatureHint, signatureHint.textContent ?? ""],
  ]);

  const flag = (input: HTMLInputElement, hint: HTMLElement, ok: boolean, problem: string) => {
    input.setAttribute("aria-invalid", String(!ok));
    hint.classList.toggle("bad", !ok);
    hint.textContent = ok ? (hints.get(hint) ?? "") : problem;
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const target = address.value.trim();
    const tx = signature.value.trim();
    const addressOk = isSolanaAddress(target);
    const signatureOk = isTransactionSignature(tx);
    flag(address, addressHint, addressOk, "That doesn't look like a Solana address. Copy it again and paste the whole thing.");
    flag(signature, signatureHint, signatureOk, tx === "" ? "Paste the signature of the transaction where you lost funds." : "That doesn't look like a transaction signature. Copy it again and paste the whole thing.");
    if (!addressOk || !signatureOk) return;
    button.disabled = true;
    button.textContent = "Sending…";
    try {
      const reply = await report(LADON_API_URL, { address: target, signature: tx, description: description.value.trim() });
      form.reset();
      show(output, message("done", "Report received", reply.message));
      track({ name: "report_submitted" });
    } catch (error) {
      show(output, message("error", "We couldn't send your report", errorText(error)));
    } finally {
      button.disabled = false;
      button.textContent = "Send report";
    }
  });
}

setupTabs();
setupCheck();
setupReport();
track({ name: "popup_opened" });
