"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Wordmark } from "@/components/Wordmark";
import { EXTENSION_URL } from "@/lib/links";
import { isSolanaAddress, shortAddress } from "../../../../shared/solana";
import type { AddressRisk } from "../../../../shared/api";

type Profile = {
  wallet: string; points: number; streak: number; last_checkin: string | null;
  checks_today: number; referral_code: string; referral_count: number;
  rank: number; next_milestone: number; season_status: string;
};
type Leader = { rank: number; wallet: string; points: number };

const API = process.env.NEXT_PUBLIC_LADON_API_URL?.replace(/\/$/, "") ?? "";
const inputClass = "w-full min-w-0 border-2 border-marble/35 bg-ink px-4 py-3 font-plain text-base text-marble placeholder:text-marble/55 focus:border-gold focus:outline-none";
const buttonClass = "shrink-0 whitespace-nowrap border-2 border-ink bg-gold px-5 py-3 font-caps text-lg font-bold text-ink shadow-[4px_4px_0_var(--color-marble)] disabled:cursor-not-allowed disabled:opacity-50";

async function api<T>(path: string, body?: object): Promise<T> {
  if (!API) throw new Error("The Ladon API is not configured for this site.");
  const response = await fetch(`${API}${path}`, body ? {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  } : { cache: "no-store" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Ladon could not complete that request.");
  return data as T;
}

export default function AirdropPage() {
  const [entry, setEntry] = useState("");
  const [wallet, setWallet] = useState("");
  const ref = typeof window === "undefined" ? "" : new URLSearchParams(window.location.search).get("ref") ?? "";
  const [profile, setProfile] = useState<Profile | null>(null);
  const [leaders, setLeaders] = useState<Leader[]>([]);
  const [target, setTarget] = useState("");
  const [risk, setRisk] = useState<AddressRisk | null>(null);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<{ leaders: Leader[] }>("/v1/airdrop/leaderboard").then((data) => setLeaders(data.leaders)).catch(() => {});
  }, []);

  async function run(work: () => Promise<void>) {
    setBusy(true);
    setNotice("");
    try { await work(); } catch (error) { setNotice(error instanceof Error ? error.message : "Something went wrong."); }
    finally { setBusy(false); }
  }

  function loadWallet() {
    void run(async () => {
      const candidate = entry.trim();
      if (!isSolanaAddress(candidate)) throw new Error("Enter a valid Solana wallet address.");
      setWallet(candidate);
      setRisk(null);
      try { setProfile(await api<Profile>(`/v1/airdrop/profile/${encodeURIComponent(candidate)}`)); }
      catch (error) {
        if (error instanceof Error && error.message.includes("not joined")) setProfile(null);
        else throw error;
      }
    });
  }

  function join() {
    void run(async () => {
      const data = await api<{ joined: boolean; profile: Profile }>("/v1/airdrop/join", { wallet, referral_code: ref || undefined });
      setProfile(data.profile);
      setNotice(data.joined ? "Welcome to Season 1. You earned 50 Ladon Points." : "This wallet has already joined Season 1.");
    });
  }

  function checkin() {
    void run(async () => {
      const data = await api<{ awarded: boolean; profile: Profile }>("/v1/airdrop/checkin", { wallet });
      setProfile(data.profile);
      setNotice(data.awarded ? "You earned 10 Ladon Points. Come back tomorrow." : "You have already checked in today.");
    });
  }

  function checkTarget() {
    void run(async () => {
      const candidate = target.trim();
      if (!isSolanaAddress(candidate)) throw new Error("Enter a valid Solana wallet address to check.");
      const data = await api<{ result: AddressRisk; awarded: boolean; profile: Profile }>("/v1/airdrop/wallet-check", { wallet, target: candidate });
      setRisk(data.result);
      setProfile(data.profile);
      setNotice(data.awarded ? "Wallet checked. You earned 5 Ladon Points." : "Wallet checked. The daily reward limit or this wallet's reward has already been reached.");
    });
  }

  const today = new Date().toISOString().slice(0, 10);
  const checkedIn = profile?.last_checkin === today;
  const referralLink = profile ? `https://getladon.vercel.app/airdrop?ref=${profile.referral_code}` : "";

  return (
    <main className="min-h-screen bg-ink text-marble">
      <div className="meander-sm" aria-hidden="true" />
      <div className="mx-auto max-w-6xl px-5 pb-20 sm:px-10">
        <header className="flex flex-wrap items-center justify-between gap-4 py-7">
          <Link href="/" aria-label="Ladon home"><Wordmark scale={3} /></Link>
          <nav aria-label="Airdrop"><Link href="/" className="font-caps text-lg hover:text-gold">← Return to Ladon</Link></nav>
        </header>

        <section className="border-y border-gold/50 py-12 sm:py-16">
          <p className="font-caps text-lg tracking-widest text-gold">Season 1 · Early contributor</p>
          <h1 className="mt-3 max-w-3xl font-serif text-5xl leading-tight sm:text-7xl">Keep watch. Earn Ladon Points.</h1>
          <p className="mt-5 max-w-2xl text-xl">Earn Ladon Points by helping make Solana safer.</p>
          <p className="mt-3 max-w-2xl font-plain text-base text-marble/80">Points recognise early contributors. They do not represent a guaranteed token allocation.</p>
        </section>

        <section aria-labelledby="wallet-title" className="mt-10 border-2 border-marble/30 bg-navy p-6 sm:p-8">
          <h2 id="wallet-title" className="font-serif text-3xl">Your wallet</h2>
          <p className="mt-2 font-plain text-base text-marble/80">Enter a public Solana wallet address. Ladon never asks for private keys or seed phrases.</p>
          <form className="mt-5 flex flex-col gap-3 sm:flex-row" onSubmit={(event) => { event.preventDefault(); loadWallet(); }}>
            <label className="sr-only" htmlFor="wallet">Solana wallet address</label>
            <input id="wallet" value={entry} onChange={(event) => setEntry(event.target.value)} className={inputClass} placeholder="Solana wallet address" autoComplete="off" />
            <button className={buttonClass} disabled={busy}>View points</button>
          </form>
          <p className="mt-3 font-plain text-sm text-marble/70">Address entry does not prove wallet ownership. Anyone who knows an address can use it here.</p>
          {wallet && !profile && <div className="mt-6 border-t border-marble/25 pt-6">
            <p className="mb-3">This wallet has not joined Season 1.</p>
            <button type="button" className={buttonClass} onClick={join} disabled={busy}>Join Season 1 · +50 points</button>
          </div>}
        </section>

        {notice && <p role="status" className="mt-5 border-l-4 border-gold bg-navy px-4 py-3 font-plain">{notice}</p>}

        {profile && <>
          <section aria-labelledby="summary-title" className="mt-12">
            <h2 id="summary-title" className="font-serif text-3xl">Your watch</h2>
            <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
              {[["Ladon Points", profile.points], ["Current streak", `${profile.streak} days`], ["Checks today", `${profile.checks_today} / 5`], ["Rank", `#${profile.rank}`], ["Referrals", profile.referral_count], ["Season", "Active"], ["Referral code", profile.referral_code], ["Next milestone", `${profile.next_milestone} points`]].map(([label, value]) =>
                <div key={label} className="border border-marble/35 bg-navy p-4"><p className="font-caps text-sm text-gold">{label}</p><p className="mt-1 break-all font-serif text-2xl">{value}</p></div>
              )}
            </div>
            <div className="mt-5"><p className="font-plain text-sm">{profile.points} of {profile.next_milestone} points towards the next milestone</p><div className="mt-2 h-3 border border-gold" role="progressbar" aria-valuenow={profile.points % 100} aria-valuemin={0} aria-valuemax={100}><div className="h-full bg-gold" style={{ width: `${profile.points % 100}%` }} /></div></div>
          </section>

          <section aria-labelledby="quests-title" className="mt-14">
            <h2 id="quests-title" className="font-serif text-3xl">Ways to help</h2>
            <div className="mt-5 grid gap-4 md:grid-cols-2">
              <article className="border-2 border-marble/30 p-6"><p className="font-caps text-gold">+50 points · Once</p><h3 className="mt-2 text-2xl">Join Season 1</h3><p className="mt-2 font-plain text-base text-marble/80">You are part of the first watch.</p><p className="mt-5 font-caps text-lg text-dragon-light">Completed</p></article>
              <article className="border-2 border-marble/30 p-6"><p className="font-caps text-gold">+10 points · Once per UTC day</p><h3 className="mt-2 text-2xl">{checkedIn ? "Return tomorrow" : "Return today"}</h3><p className="mt-2 font-plain text-base text-marble/80">Keep a steady watch. Your streak grows when you return on consecutive days.</p><button type="button" className={`${buttonClass} mt-5`} onClick={checkin} disabled={busy || checkedIn}>{checkedIn ? "Completed today" : "Check in"}</button></article>
              <article className="border-2 border-marble/30 p-6"><p className="font-caps text-gold">+5 points · Up to five unique checks per UTC day</p><h3 className="mt-2 text-2xl">Check a wallet</h3><p className="mt-2 font-plain text-base text-marble/80">Look up a public wallet. A successful check can earn points once per wallet each day.</p><form className="mt-5 space-y-3" onSubmit={(event) => { event.preventDefault(); checkTarget(); }}><label className="sr-only" htmlFor="target">Wallet to check</label><input id="target" className={inputClass} value={target} onChange={(event) => setTarget(event.target.value)} placeholder="Wallet to check" /><button className={buttonClass} disabled={busy}>Check wallet</button></form></article>
              <article className="border-2 border-marble/30 p-6"><p className="font-caps text-gold">+100 inviter · +25 invitee</p><h3 className="mt-2 text-2xl">Invite an active user</h3><p className="mt-2 font-plain text-base text-marble/80">Share your Season 1 link. Points are awarded when a new wallet joins with it.</p><label className="mt-4 block font-plain text-sm" htmlFor="referral">Your referral link</label><input id="referral" className={`${inputClass} mt-2`} value={referralLink} readOnly onFocus={(event) => event.target.select()} /></article>
              <article className="border-2 border-marble/30 p-6"><p className="font-caps text-gold">+250 points · After verification</p><h3 className="mt-2 text-2xl">Submit a scam report</h3><p className="mt-2 font-plain text-base text-marble/80">Reports start an investigation. Points are awarded only after a report is verified; submission alone earns none.</p><a className="mt-5 inline-block font-caps text-lg text-gold underline underline-offset-4" href={EXTENSION_URL}>Get Ladon to report</a></article>
            </div>
          </section>

          {risk && <section aria-labelledby="result-title" className="mt-12 border-2 border-gold bg-navy p-6"><h2 id="result-title" className="font-serif text-3xl">Wallet check</h2><p className="mt-2 break-all font-plain text-sm">{risk.address}</p><p className="mt-4 font-caps text-xl">{risk.flagged ? "Ladon found a warning" : risk.confidence === "none" ? "No clear evidence yet" : "No strong warning found"}</p><p className="mt-2 font-plain text-base">Risk score: {Math.round(risk.risk * 100)}% · Confidence: {risk.confidence}. A score is a probability, not an accusation.</p><ul className="mt-3 list-inside list-disc font-plain text-base">{risk.reasons.map((reason) => <li key={reason.code}>{reason.text}</li>)}</ul></section>}
        </>}

        <section aria-labelledby="leaders-title" className="mt-14"><h2 id="leaders-title" className="font-serif text-3xl">Season watchlist</h2><p className="mt-2 font-plain text-base text-marble/75">Top 20 contributors by Ladon Points.</p><ol className="mt-5 border-t border-marble/30">{leaders.map((leader) => <li key={`${leader.rank}-${leader.wallet}`} className="flex items-center justify-between border-b border-marble/30 py-3 font-plain"><span><span className="mr-4 text-gold">#{leader.rank}</span>{shortAddress(leader.wallet)}</span><span>{leader.points} pts</span></li>)}</ol></section>
        <footer className="mt-16 border-t border-gold/50 pt-6 font-plain text-sm text-marble/75">Ladon Points are participation points only. They are not tokens, have no cash value, and do not guarantee a future token allocation.</footer>
      </div>
    </main>
  );
}
