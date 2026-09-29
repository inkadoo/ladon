export type Profile = {
  wallet: string; points: number; streak: number; last_checkin: string | null;
  checks_today: number; referral_code: string; referral_count: number;
  rank: number; next_milestone: number; season_status: string;
};
export type Quests = {
  enabled: boolean; username: string | null; connected: boolean;
  completed: string[]; post_text: string; rewards: Record<string, number>;
};
export type Leader = { rank: number; wallet: string; points: number };
export const SESSION_KEY = "ladon_season1_session";
export const API = process.env.NEXT_PUBLIC_LADON_API_URL?.replace(/\/$/, "") ?? "";

export class AirApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export async function airApi<T>(path: string, body?: object): Promise<T> {
  if (!API) throw new Error("Ladon is unavailable right now. Please try again later.");
  const token = sessionStorage.getItem(SESSION_KEY);
  const response = await fetch(`${API}/v1/airdrop${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: { ...(body === undefined ? {} : { "Content-Type": "application/json" }), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    ...(body === undefined ? { cache: "no-store" } : { body: JSON.stringify(body) }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new AirApiError(typeof data.detail === "string" ? data.detail : "Ladon could not complete that request.", response.status);
  return data as T;
}
