import { collect, signers, type Target } from "./transaction.ts";

type Fn = (...args: unknown[]) => unknown;
type Bag = Record<string, unknown>;

const ASK = "ladon:check";
const ANSWER = "ladon:answer";
const SIGNED = "ladon:signed";
const ACK_MS = 1500;
const CLEARED_MS = 5000;

const pending = new Map<string, { ack: () => void; done: (proceed: boolean) => void }>();

window.addEventListener("message", (event) => {
  if (event.source !== window) return;
  const data = event.data as { channel?: unknown; id?: unknown; type?: unknown; proceed?: unknown } | null;
  if (data?.channel !== ANSWER || typeof data.id !== "string") return;
  const waiter = pending.get(data.id);
  if (!waiter) return;
  if (data.type === "ack") waiter.ack();
  if (data.type === "result") waiter.done(data.proceed !== false);
});

function requestId(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (b) => b.toString(16).padStart(2, "0")).join("");
}

function ask(targets: Target[]): Promise<boolean> {
  const id = requestId();
  return new Promise((resolve) => {
    const finish = (proceed: boolean) => {
      clearTimeout(timer);
      pending.delete(id);
      resolve(proceed);
    };
    const timer = setTimeout(() => finish(true), ACK_MS);
    pending.set(id, { ack: () => clearTimeout(timer), done: finish });
    window.postMessage({ channel: ASK, id, targets }, "*");
  });
}

function rejection(): Error {
  return Object.assign(new Error("User rejected the request."), { code: 4001 });
}

let cleared = { key: "", until: 0 };

async function guard(transactions: unknown[], bare = false): Promise<void> {
  const targets = collect(transactions, bare);
  if (targets.length === 0) return;
  const key = targets.map((t) => `${t.kind}:${t.address}`).join(",");
  if (cleared.key === key && cleared.until > Date.now()) return;
  if (!(await ask(targets))) throw rejection();
  cleared = { key, until: Date.now() + CLEARED_MS };
}

function remember(transactions: unknown[], bare: boolean): void {
  const paid = collect(transactions, bare).filter((t) => t.kind === "payment").map((t) => t.address);
  const addresses = [...new Set([...paid, ...signers(transactions, bare)])];
  if (addresses.length > 0) window.postMessage({ channel: SIGNED, addresses }, "*");
}

async function guarded(transactions: unknown[], bare: boolean, call: () => unknown): Promise<unknown> {
  await guard(transactions, bare);
  const result = await call();
  remember(transactions, bare);
  return result;
}

const LEGACY: Record<string, (args: unknown[]) => unknown[]> = {
  signTransaction: (args) => [args[0]],
  signAndSendTransaction: (args) => [args[0]],
  signAllTransactions: (args) => (Array.isArray(args[0]) ? args[0] : []),
  signAndSendAllTransactions: (args) => (Array.isArray(args[0]) ? args[0] : []),
};

function requested(args: unknown[]): { transactions: unknown[]; bare: boolean } {
  const body = args[0] as { method?: unknown; params?: { message?: unknown; messages?: unknown; transaction?: unknown } } | undefined;
  const params = body?.params;
  if (typeof body?.method !== "string" || !(body.method in LEGACY) || !params) return { transactions: [], bare: false };
  if (Array.isArray(params.messages)) return { transactions: params.messages, bare: true };
  if (params.message !== undefined) return { transactions: [params.message], bare: true };
  return { transactions: params.transaction === undefined ? [] : [params.transaction], bare: false };
}

const wrapped = new WeakSet<object>();

function wrapProvider(provider: unknown): void {
  if (!provider || typeof provider !== "object" || wrapped.has(provider)) return;
  wrapped.add(provider);
  const target = provider as Bag;
  const hook = (name: string, pick: (args: unknown[]) => { transactions: unknown[]; bare: boolean }) => {
    const original = target[name];
    if (typeof original !== "function") return;
    try {
      Object.defineProperty(target, name, {
        configurable: true,
        writable: true,
        value: async function (this: unknown, ...args: unknown[]) {
          const { transactions, bare } = pick(args);
          return guarded(transactions, bare, () => (original as Fn).apply(this, args));
        },
      });
    } catch {}
  };
  for (const [name, pick] of Object.entries(LEGACY)) hook(name, (args) => ({ transactions: pick(args), bare: false }));
  hook("request", requested);
}

const PROVIDERS: (() => unknown)[] = [
  () => (window as unknown as Bag).solana,
  () => ((window as unknown as Bag).phantom as Bag | undefined)?.solana,
  () => (window as unknown as Bag).solflare,
  () => ((window as unknown as Bag).backpack as Bag | undefined)?.solana ?? (window as unknown as Bag).backpack,
  () => (window as unknown as Bag).glowSolana,
  () => (window as unknown as Bag).braveSolana,
  () => ((window as unknown as Bag).exodus as Bag | undefined)?.solana,
  () => ((window as unknown as Bag).okxwallet as Bag | undefined)?.solana,
  () => ((window as unknown as Bag).trustwallet as Bag | undefined)?.solana,
  () => (window as unknown as Bag).coinbaseSolana,
];

function scanProviders(): void {
  for (const get of PROVIDERS) {
    try {
      wrapProvider(get());
    } catch {}
  }
}

const STANDARD: Record<string, { method: string; pick: (args: unknown[]) => unknown[] }> = {
  "solana:signTransaction": { method: "signTransaction", pick: (args) => args.map((i) => (i as Bag | undefined)?.transaction) },
  "solana:signAndSendTransaction": { method: "signAndSendTransaction", pick: (args) => args.map((i) => (i as Bag | undefined)?.transaction) },
  "solana:signAndSendAllTransactions": {
    method: "signAndSendAllTransactions",
    pick: (args) => (Array.isArray(args[0]) ? args[0].map((i) => (i as Bag | undefined)?.transaction) : []),
  },
};

function wrapFeatures(features: Bag): Bag {
  const copy: Bag = { ...features };
  for (const [name, { method, pick }] of Object.entries(STANDARD)) {
    const feature = features[name] as Bag | undefined;
    const original = feature?.[method];
    if (!feature || typeof original !== "function") continue;
    copy[name] = {
      ...feature,
      [method]: (...args: unknown[]) => guarded(pick(args), false, () => (original as Fn).apply(feature, args)),
    };
  }
  return copy;
}

const wallets = new WeakMap<object, object>();

function wrapWallet(wallet: unknown): unknown {
  if (!wallet || typeof wallet !== "object") return wallet;
  const known = wallets.get(wallet);
  if (known) return known;
  const proxy = new Proxy(wallet, {
    get(target, prop) {
      const value: unknown = Reflect.get(target, prop, target);
      if (prop === "features" && value && typeof value === "object") return wrapFeatures(value as Bag);
      return typeof value === "function" ? (value as Fn).bind(target) : value;
    },
  });
  wallets.set(wallet, proxy);
  return proxy;
}

type Api = { register: (...wallets: unknown[]) => unknown };

function wrapApi(api: Api): Api {
  return { ...api, register: (...list: unknown[]) => api.register(...list.map(wrapWallet)) };
}

const replayed = new WeakSet<Event>();
const stop = Event.prototype.stopImmediatePropagation;

function relay(type: string, detail: (original: unknown) => unknown): void {
  window.addEventListener(
    type,
    (event) => {
      if (replayed.has(event)) return;
      const original = (event as Event & { detail?: unknown }).detail;
      if (!original) return;
      stop.call(event);
      const replay = new CustomEvent(type, { detail: detail(original) });
      replayed.add(replay);
      window.dispatchEvent(replay);
    },
    true,
  );
}

relay("wallet-standard:register-wallet", (callback) =>
  typeof callback === "function" ? (api: Api) => (callback as Fn)(wrapApi(api)) : callback,
);
relay("wallet-standard:app-ready", (api) =>
  api && typeof (api as Api).register === "function" ? wrapApi(api as Api) : api,
);

scanProviders();
let scans = 0;
const poll = setInterval(() => {
  scanProviders();
  if (++scans >= 40) clearInterval(poll);
}, 250);
window.addEventListener("load", scanProviders, { once: true });
