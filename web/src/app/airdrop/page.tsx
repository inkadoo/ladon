"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Wordmark } from "@/components/Wordmark";
import { EXTENSION_URL } from "@/lib/links";
import { airApi, AirApiError, SESSION_KEY } from "@/lib/airdrop";
import type { Leader, Profile, Quests } from "@/lib/airdrop";
import { signInWallet } from "@/lib/wallet";
import type { WalletName, WalletProvider } from "@/lib/wallet";
import { isSolanaAddress, shortAddress } from "../../../../shared/solana";
import type { AddressRisk } from "../../../../shared/api";

const inputClass = "w-full min-w-0 border-2 border-marble/35 bg-ink px-4 py-3 font-plain text-base text-marble placeholder:text-marble/55 focus:border-gold";
const buttonClass = "inline-flex items-center justify-center gap-2 border-2 border-gold bg-gold px-5 py-2.5 font-caps text-lg font-bold text-ink shadow-[3px_3px_0_var(--color-marble)] hover:bg-marble hover:border-marble disabled:cursor-not-allowed disabled:opacity-45 disabled:shadow-none";
const secondaryClass = "inline-flex items-center justify-center border border-marble/45 px-4 py-2.5 font-caps text-lg text-marble hover:border-gold hover:text-gold disabled:cursor-not-allowed disabled:opacity-45";

function QuestCard({ number, title, reward, done, children }: { number: string; title: string; reward: string; done?: boolean; children: ReactNode }) {
  return <article className={`flex flex-col border-2 p-6 ${done ? "border-dragon-light/70 bg-dragon/10" : "border-marble/25 bg-navy/40"}`}>
    <div className="flex items-center justify-between gap-3 font-caps text-sm"><span className="text-marble/65">QUEST {number}</span><span className={done ? "text-dragon-light" : "text-gold"}>{done ? "✓ Completed" : reward}</span></div>
    <h3 className="mt-4 text-3xl leading-tight">{title}</h3>
    <div className="mt-3 flex flex-1 flex-col gap-4 font-plain text-base text-marble/85">{children}</div>
  </article>;
}

export default function AirdropPage() {
  const [wallet, setWallet] = useState("");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [quests, setQuests] = useState<Quests | null>(null);
  const [xEnabled, setXEnabled] = useState(false);
  const [leaders, setLeaders] = useState<Leader[]>([]);
  const [leaderError, setLeaderError] = useState(false);
  const [target, setTarget] = useState("");
  const [postUrl, setPostUrl] = useState("");
  const [risk, setRisk] = useState<AddressRisk | null>(null);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [restoring, setRestoring] = useState(true);
  const [provider, setProvider] = useState<WalletProvider | null>(null);
  const callbackStarted = useRef(false);

  const loadProfile = useCallback(async (address: string) => {
    try {
      const data = await airApi<Profile>(`/profile/${encodeURIComponent(address)}`);
      setProfile(data);
      const tasks = await airApi<Quests>("/quests");
      setQuests(tasks);
      setXEnabled(tasks.enabled);
    } catch (error) {
      if (error instanceof AirApiError && error.status === 404) { setProfile(null); setQuests(null); }
      else throw error;
    }
  }, []);

  const refresh = useCallback(async (address: string) => {
    await loadProfile(address);
    const data = await airApi<{ leaders: Leader[] }>("/leaderboard");
    setLeaders(data.leaders);
    setLeaderError(false);
  }, [loadProfile]);

  useEffect(() => {
    let active = true;
    const params = new URLSearchParams(window.location.search);
    const referral = params.get("ref");
    if (referral) sessionStorage.setItem("ladon_referral", referral.slice(0, 32));
    airApi<{ leaders: Leader[] }>("/leaderboard").then((data) => { if (active) setLeaders(data.leaders); }).catch(() => { if (active) setLeaderError(true); });
    async function restore() {
      const campaign = await airApi<{ x_enabled: boolean }>("/campaign");
      if (!active) return;
      setXEnabled(campaign.x_enabled);
      if (!sessionStorage.getItem(SESSION_KEY)) return;
      const session = await airApi<{ wallet: string }>("/auth/session");
      if (!active) return;
      setWallet(session.wallet);
      if ((params.has("code") || params.has("error")) && !callbackStarted.current) {
        callbackStarted.current = true;
        const state = params.get("state");
        const expected = sessionStorage.getItem("ladon_x_state");
        sessionStorage.removeItem("ladon_x_state");
        const clean = new URL(window.location.href);
        ["code", "state", "error", "error_description"].forEach((key) => clean.searchParams.delete(key));
        window.history.replaceState({}, "", clean.pathname + clean.search);
        if (params.has("error")) setNotice("X connection was cancelled. You can try again whenever you are ready.");
        else if (!state || state !== expected) setNotice("This X connection could not be matched to your session. Please connect X again.");
        else {
          try {
            await airApi("/x/complete", { state, code: params.get("code") });
            setNotice("X connected. Your account reward has been added.");
          } catch (error) {
            setNotice(error instanceof Error ? error.message : "X could not finish connecting. Please try again.");
          }
        }
      }
      await refresh(session.wallet);
    }
    void restore().catch((error) => {
      if (!active) return;
      if (error instanceof AirApiError && error.status === 401) { sessionStorage.removeItem(SESSION_KEY); setWallet(""); }
      else setNotice(error instanceof Error ? error.message : "Ladon is unavailable right now.");
    }).finally(() => { if (active) setRestoring(false); });
    return () => { active = false; };
  }, [refresh]);

  useEffect(() => {
    if (!provider) return;
    const changed = (key?: { toString(): string } | null) => {
      if (key?.toString() === wallet) return;
      void airApi("/auth/logout", {}).catch(() => {});
      sessionStorage.removeItem(SESSION_KEY);
      setWallet(""); setProfile(null); setQuests(null); setRisk(null); setProvider(null);
      setNotice("Your wallet changed or disconnected. Connect again to secure this session.");
    };
    provider.on?.("accountChanged", changed);
    provider.on?.("disconnect", changed);
    return () => { provider.removeListener?.("accountChanged", changed); provider.removeListener?.("disconnect", changed); };
  }, [provider, wallet]);

  async function run(work: () => Promise<void>) {
    setBusy(true); setNotice("");
    try { await work(); }
    catch (error) {
      if (error instanceof AirApiError && error.status === 401) {
        sessionStorage.removeItem(SESSION_KEY); setWallet(""); setProfile(null); setQuests(null);
      }
      if (error instanceof AirApiError && error.status === 409) setQuests((current) => current ? { ...current, connected: false } : null);
      setNotice(error instanceof Error ? error.message : "The request was cancelled or could not be completed.");
    } finally { setBusy(false); }
  }

  function connect(name: WalletName) {
    void run(async () => {
      const session = await signInWallet(name);
      sessionStorage.setItem(SESSION_KEY, session.token);
      setWallet(session.wallet); setProvider(session.provider); setRisk(null);
      await loadProfile(session.wallet);
      setNotice("Wallet verified. Your points account is secured by your signature.");
    });
  }

  function disconnect() {
    void run(async () => {
      try { await airApi("/auth/logout", {}); }
      finally {
        sessionStorage.removeItem(SESSION_KEY); sessionStorage.removeItem("ladon_x_state");
        setWallet(""); setProfile(null); setQuests(null); setRisk(null); setProvider(null);
        await provider?.disconnect?.();
      }
    });
  }

  function join() {
    void run(async () => {
      const referral = sessionStorage.getItem("ladon_referral") || undefined;
      await airApi("/join", { wallet, referral_code: referral });
      sessionStorage.removeItem("ladon_referral");
      await refresh(wallet);
      setNotice("Welcome to Season 1. Your join reward is recorded.");
    });
  }

  function checkin() {
    void run(async () => {
      const data = await airApi<{ awarded: boolean }>("/checkin", { wallet });
      await refresh(wallet);
      setNotice(data.awarded ? "+10 Ladon Points. Come back tomorrow." : "You have already checked in today.");
    });
  }

  function checkTarget() {
    void run(async () => {
      if (!isSolanaAddress(target.trim())) throw new Error("Enter a valid Solana wallet address to check.");
      const data = await airApi<{ result: AddressRisk; awarded: boolean }>("/wallet-check", { wallet, target: target.trim() });
      setRisk(data.result); await refresh(wallet);
      setNotice(data.awarded ? "Wallet checked. +5 Ladon Points." : "Wallet checked. This target or today's five-check limit has already been rewarded.");
    });
  }

  function connectX() {
    void run(async () => {
      const data = await airApi<{ state: string; url: string }>("/x/start", {});
      sessionStorage.setItem("ladon_x_state", data.state);
      window.location.assign(data.url);
    });
  }

  function claim(task: "x_follow" | "x_post") {
    void run(async () => {
      const data = await airApi<{ awarded: boolean }>("/quests/claim", { task, url: task === "x_post" ? postUrl : "" });
      await refresh(wallet);
      setNotice(data.awarded ? "Verified. Your Ladon Points have been added." : "You have already earned this reward.");
    });
  }

  const today = new Date().toISOString().slice(0, 10);
  const checkedIn = profile?.last_checkin === today;
  const referralLink = profile ? `https://getladon.vercel.app/airdrop?ref=${profile.referral_code}` : "";
  const done = (task: string) => quests?.completed.includes(task) ?? false;
  const canClaim = !!profile && !!quests?.connected && !busy;
  const points = profile?.points ?? 0;

  return <main className="min-h-screen bg-ink text-marble">
    <div className="meander-sm" aria-hidden="true" />
    <div className="mx-auto max-w-6xl px-5 pb-20 sm:px-10">
      <header className="flex flex-wrap items-center justify-between gap-4 py-7">
        <Link href="/" aria-label="Ladon home"><Wordmark scale={3} /></Link>
        <nav aria-label="Airdrop" className="flex gap-5 font-caps"><a href="https://x.com/ladon_sol" target="_blank" rel="noopener noreferrer" className="hover:text-gold">@ladon_sol ↗</a><Link href="/" className="hover:text-gold">Home</Link></nav>
      </header>
      <section className="grid gap-8 border-y border-gold/50 py-12 lg:grid-cols-[1.3fr_1fr] lg:py-16">
        <div><p className="font-caps text-lg tracking-widest text-gold">✦ Ladon Airdrop · Season 1</p>
          <h1 className="mt-4 text-5xl leading-tight sm:text-7xl">Join the first watch.</h1>
          <p className="mt-5 max-w-xl text-xl text-marble/90">Connect your wallet. Spread the word. Earn Ladon Points for helping make Solana safer.</p>
          <div className="mt-8 flex flex-wrap gap-x-6 gap-y-2 font-caps text-gold"><span>01 Connect</span><span>02 Complete quests</span><span>03 Earn points</span></div>
          <p className="mt-5 max-w-xl font-plain text-sm text-marble/70">Season 1 tracks participation points. A future token allocation is not guaranteed.</p>
        </div>
        <section aria-labelledby="wallet-title" className="border-2 border-gold/70 bg-navy p-6 shadow-[6px_6px_0_var(--color-gold)] sm:p-7">
          <p className="font-caps text-gold">Your season passport</p>
          <h2 id="wallet-title" className="mt-2 text-3xl">{wallet ? "Wallet verified" : "Connect your wallet"}</h2>
          {wallet ? <><p className="mt-4 break-all font-plain text-sm">{wallet}</p><p className="mt-3 text-5xl text-gold">{points}<span className="ml-3 font-caps text-lg text-marble">Ladon Points</span></p>
            {!profile && <button className={`${buttonClass} mt-5 w-full`} onClick={join} disabled={busy}>Join Season 1 · +50 points</button>}
            <button className="mt-5 font-plain text-sm text-marble/75 underline underline-offset-4" onClick={disconnect} disabled={busy}>Disconnect</button>
          </> : <><p className="mt-3 font-plain text-base text-marble/80">Choose your Solana wallet, then sign a message to prove it belongs to you.</p><div className="mt-5 grid gap-3">{(["Phantom", "Solflare", "Backpack"] as const).map((name) => <button key={name} className={name === "Phantom" ? buttonClass : secondaryClass} disabled={busy || restoring} onClick={() => connect(name)}>Connect {name} ↗</button>)}</div>
            <p className="mt-4 font-plain text-xs text-marble/65">On mobile, open this page in your wallet’s browser.</p></>}
          <p className="mt-5 border-t border-marble/20 pt-4 font-plain text-sm text-marble/75">The signature secures your account. It costs no SOL and gives Ladon no access to your funds.</p>
        </section>
      </section>
      {notice && <p role="status" className="mt-6 border-l-4 border-gold bg-navy px-4 py-3 font-plain">{notice}</p>}
      {profile && <section aria-label="Your Season 1 progress" className="mt-9"><div className="grid grid-cols-2 gap-3 md:grid-cols-4">{[["Your rank", `#${profile.rank}`], ["Daily streak", `${profile.streak} days`], ["Wallet checks", `${profile.checks_today} / 5 today`], ["Friends joined", profile.referral_count]].map(([label, value]) => <div key={label} className="border border-marble/30 bg-navy p-4"><p className="font-caps text-sm text-gold">{label}</p><p className="mt-1 text-2xl">{value}</p></div>)}</div><p className="mt-5 font-plain text-sm text-marble/75">{profile.next_milestone - points} points to your next milestone</p><progress aria-label="Points towards next milestone" className="mt-2 h-2 w-full accent-gold" value={points % 100} max={100} /></section>}
      <section aria-labelledby="quests-title" className="mt-14">
        <div className="flex flex-wrap items-end justify-between gap-3"><div><p className="font-caps tracking-widest text-gold">The watch grows with you</p><h2 id="quests-title" className="mt-2 text-4xl sm:text-5xl">Your Season 1 quests</h2></div><p className="max-w-sm font-plain text-sm text-marble/70">One wallet and one X account per participant. Social rewards are earned once.</p></div>
        <div className="mt-7 grid gap-4 md:grid-cols-2">
          <QuestCard number="01" title="Join Season 1" reward="+50 points" done={!!profile}><p>Secure your place in the first season with a verified Solana wallet.</p>{profile ? <p className="mt-auto text-dragon-light">You’re part of the first watch.</p> : <button className={`${buttonClass} mt-auto self-start`} disabled={!wallet || busy} onClick={join}>{wallet ? "Join Season 1" : "Connect your wallet above"}</button>}</QuestCard>
          <QuestCard number="02" title="Connect your X account" reward="+25 points" done={done("x_connect")}><p>Link your X identity so Ladon can verify your promotional quests.</p><p className="text-sm text-marble/65">Read access to your profile, follows, and posts. You choose what to publish.</p>{!xEnabled ? <p className="mt-auto font-caps text-gold">X rewards opening soon</p> : <button className={`${buttonClass} mt-auto self-start`} disabled={!profile || busy || quests?.connected} onClick={connectX}>{quests?.connected ? `Connected @${quests.username}` : "Connect X"}</button>}{quests?.connected && <button className="self-start text-sm underline underline-offset-4" disabled={busy} onClick={() => void run(async () => { setQuests(await airApi<Quests>("/x/disconnect", {})); setNotice("X access removed. Your completed rewards stay recorded."); })}>Remove X access</button>}</QuestCard>
          <QuestCard number="03" title="Follow @ladon_sol" reward="+50 points" done={done("x_follow")}><p>Follow Ladon for security updates and news from the watch.</p><div className="mt-auto flex flex-wrap gap-3"><a className={secondaryClass} href="https://x.com/intent/follow?screen_name=ladon_sol" target="_blank" rel="noopener noreferrer">Follow on X ↗</a><button className={buttonClass} disabled={!canClaim || done("x_follow")} onClick={() => claim("x_follow")}>{done("x_follow") ? "Reward earned" : "Verify follow"}</button></div></QuestCard>
          <QuestCard number="04" title="Spread the word" reward="+150 points" done={done("x_post")}><p>Publish the prepared post about @ladon_sol. It includes your invitation link and discloses the points incentive.</p>{quests && <><blockquote className="border-l-2 border-gold bg-ink p-4 text-sm leading-relaxed">{quests.post_text}</blockquote><a className={`${secondaryClass} self-start`} href={`https://x.com/intent/post?text=${encodeURIComponent(quests.post_text)}`} target="_blank" rel="noopener noreferrer">Open prepared post ↗</a></>}<form className="mt-auto space-y-3" onSubmit={(event) => { event.preventDefault(); claim("x_post"); }}><label className="block text-sm" htmlFor="post-url">Paste your published X post link</label><input id="post-url" type="url" className={inputClass} value={postUrl} onChange={(event) => setPostUrl(event.target.value)} placeholder="https://x.com/you/status/…" disabled={!profile || done("x_post")} /><button className={buttonClass} disabled={!canClaim || !postUrl || done("x_post")}>{done("x_post") ? "Reward earned" : "Verify post"}</button></form></QuestCard>
          <QuestCard number="05" title="Invite a friend" reward="+100 you · +25 friend"><p>Share your invitation. When a new wallet signs in and joins through your link, you both earn points.</p>{profile ? <><label htmlFor="referral" className="text-sm">Your invitation link</label><input id="referral" className={inputClass} value={referralLink} readOnly onFocus={(event) => event.target.select()} /><button className={`${secondaryClass} self-start`} onClick={() => void run(async () => { await navigator.clipboard.writeText(referralLink); setNotice("Invitation link copied."); })}>Copy invitation</button></> : <p className="mt-auto text-sm text-marble/65">Your personal link appears after you join.</p>}</QuestCard>
          <QuestCard number="06" title={checkedIn ? "Return tomorrow" : "Keep a daily watch"} reward="+10 points / day" done={checkedIn}><p>Check in once per UTC day and build your streak.</p><button className={`${buttonClass} mt-auto self-start`} onClick={checkin} disabled={!profile || busy || checkedIn}>{checkedIn ? "Completed today" : "Daily check-in"}</button></QuestCard>
          <QuestCard number="07" title="Check a wallet" reward="+5 points / unique check"><p>Check a Solana address with Ladon. Up to five unique successful checks earn points per UTC day.</p><form className="mt-auto space-y-3" onSubmit={(event) => { event.preventDefault(); checkTarget(); }}><label className="sr-only" htmlFor="target">Wallet to check</label><input id="target" className={inputClass} value={target} onChange={(event) => setTarget(event.target.value)} placeholder="Solana wallet address" /><button className={buttonClass} disabled={!profile || busy}>Check wallet</button></form></QuestCard>
          <QuestCard number="08" title="Help protect the next person" reward="Future verified reports"><p>Use Ladon to report suspected scams. Reports start an investigation; submitting one does not automatically earn points.</p><a className={`${secondaryClass} mt-auto self-start`} href={EXTENSION_URL}>Get the Ladon extension ↗</a></QuestCard>
        </div>
      </section>
      {risk && <section aria-labelledby="result-title" className="mt-12 border-2 border-gold bg-navy p-6"><h2 id="result-title" className="text-3xl">Wallet check</h2><p className="mt-2 break-all font-plain text-sm">{risk.address}</p><p className="mt-4 font-caps text-xl">{risk.flagged ? "Ladon found a warning" : risk.confidence === "none" ? "No clear evidence yet" : "No strong warning found"}</p><p className="mt-2 font-plain text-base">Risk: {Math.round(risk.risk * 100)}% · Confidence: {risk.confidence}. A score is a probability, not an accusation.</p><ul className="mt-3 list-inside list-disc font-plain text-base">{risk.reasons.map((reason) => <li key={reason.code}>{reason.text}</li>)}</ul></section>}
      <section aria-labelledby="leaders-title" className="mt-14"><h2 id="leaders-title" className="text-4xl">The first watch</h2><p className="mt-2 font-plain text-base text-marble/75">Top 20 contributors by Ladon Points.</p><ol className="mt-5 border-t border-marble/30">{leaders.map((leader) => <li key={leader.rank} className="flex items-center justify-between border-b border-marble/30 py-3 font-plain"><span><span className="mr-4 text-gold">#{leader.rank}</span>{shortAddress(leader.wallet)}</span><span>{leader.points} pts</span></li>)}</ol>{leaders.length === 0 && <p className="mt-4 font-plain text-sm text-marble/65">{leaderError ? "The leaderboard is unavailable right now." : "The first places are waiting to be filled."}</p>}</section>
      <footer className="mt-16 border-t border-gold/50 pt-6 font-plain text-sm text-marble/65"><p>Ladon Points are participation points only. They are not tokens, have no cash value, and do not guarantee a future token allocation.</p><Link href="/privacy" className="mt-3 inline-block underline underline-offset-4">Privacy</Link></footer>
    </div>
  </main>;
}
