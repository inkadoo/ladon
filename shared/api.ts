export type RiskLevel = "low" | "medium" | "high";
export type Outcome = "likely rug" | "active" | "unknown";

export type TokenReason = { label: string; explanation: string; points: number };

export type TokenRisk = {
  mint: string;
  deployer: string | null;
  funder: string | null;
  score: number;
  level: RiskLevel;
  reasons: TokenReason[];
  past_tokens: { mint: string; created_at: string; outcome: Outcome; created_by: "deployer" | "linked wallet" }[];
  checked_at: string;
};

export type AddressRisk = {
  address: string;
  token_account?: string | null;
  risk: number;
  confidence: "none" | "low" | "medium" | "high";
  flagged: boolean;
  reasons: { code: string; text: string }[];
  cluster_size: number;
  reports: number;
};

export type WalletLevel = RiskLevel | "none";

export function walletLevel(result: AddressRisk): WalletLevel {
  if (result.confidence === "none") return "none";
  if (result.flagged && result.risk >= 0.8) return "high";
  if (result.flagged) return "medium";
  return "low";
}

export type Check = { kind: "token"; result: TokenRisk } | { kind: "wallet"; result: AddressRisk };

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

const MESSAGES: Record<number, string> = {
  429: "You've done a lot of checks in a short time. Please wait a minute and try again.",
  503: "Checks aren't available right now. Please try again later.",
};

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError("We couldn't reach Ladon just now. Check your connection and try again.", 0);
  }
  if (response.ok) return (await response.json()) as T;
  const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
  const detail = typeof body?.detail === "string" ? body.detail : null;
  throw new ApiError(detail ?? MESSAGES[response.status] ?? "Something went wrong on our side. Please try again.", response.status);
}

export function checkToken(api: string, mint: string, signal?: AbortSignal): Promise<TokenRisk> {
  return request<TokenRisk>(`${api}/v1/token/${encodeURIComponent(mint)}/risk`, { signal });
}

export function checkWallet(api: string, address: string, signal?: AbortSignal): Promise<AddressRisk> {
  return request<AddressRisk>(`${api}/v1/address/${encodeURIComponent(address)}`, { signal });
}

export async function check(api: string, address: string, signal?: AbortSignal): Promise<Check> {
  try {
    return { kind: "token", result: await checkToken(api, address, signal) };
  } catch (error) {
    if (error instanceof ApiError && error.status === 400) {
      return { kind: "wallet", result: await checkWallet(api, address, signal) };
    }
    throw error;
  }
}

export function report(api: string, body: { address: string; description: string; signature: string }): Promise<{ status: string; message: string }> {
  return request(`${api}/v1/reports`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
