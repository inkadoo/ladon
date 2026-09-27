import type { Metadata } from "next";
import Link from "next/link";
import { GITHUB_URL } from "@/lib/links";

export const metadata: Metadata = {
  title: "Privacy | Ladon",
  description: "What the Ladon extension and API see, store and share. In short: very little, and never your keys.",
};

const SECTIONS: { title: string; body: string[] }[] = [
  {
    title: "The short version",
    body: [
      "Ladon never sees your seed phrase, private keys or funds, and never asks for them. It cannot sign, send or block anything.",
      "The only thing the extension sends to Ladon is the address it is checking. Your browsing history, the pages you visit and your balances stay on your device.",
    ],
  },
  {
    title: "What the extension sends",
    body: [
      "When a site asks your wallet to sign a transaction, Ladon sends the addresses that transaction pays or hands control to (up to five) to the Ladon API, so it can check them.",
      "When you check an address in the toolbar popup, that address is sent to the API.",
      "On Axiom, the token addresses shown on the page are sent to the API so their rug risk can be labelled.",
      "Nothing else is sent. This version of the extension includes no analytics.",
    ],
  },
  {
    title: "What stays on your device",
    body: [
      "A list of the addresses you have paid and your own wallet addresses, used only to spot poisoned lookalikes. It holds up to 500 addresses and never leaves your browser.",
      "A list of known scam websites. Ladon downloads the whole list and checks sites inside your browser, so the sites you visit are never sent anywhere.",
      "The sites you chose to stay on after a warning. This is cleared when you close your browser.",
      "You can delete all of it at any time by removing the extension.",
    ],
  },
  {
    title: "Reports",
    body: [
      "If you report a scam, we store the address you report, the transaction signature and anything you write about what happened. Please do not include personal details.",
      "To stop spam and duplicate reports, we also store a scrambled code made from your IP address. It cannot be turned back into your IP address. We do not store the IP address itself.",
    ],
  },
  {
    title: "Who else is involved",
    body: [
      "Helius provides the Solana data Ladon uses. When an address is checked, the Ladon API asks Helius about that address, never about you.",
      "Vercel hosts the website and the API, and keeps standard server logs, including IP addresses, for a short time.",
      "Supabase stores Ladon's database of reports and scores.",
      "We never sell or share data for advertising.",
    ],
  },
  {
    title: "Scores are not accusations",
    body: [
      "Every Ladon score is a probability with its reasons. If you think Ladon is wrong about an address you own, open an issue on GitHub and we will look at the evidence again.",
    ],
  },
];

export default function Privacy() {
  return (
    <main className="px-5 py-20 sm:px-10 lg:px-16">
      <article className="mx-auto max-w-2xl font-plain">
        <Link href="/" className="font-caps text-lg text-gold underline decoration-2 underline-offset-4 hover:text-marble">
          Ladon
        </Link>
        <h1 className="mt-8 font-serif text-4xl leading-tight sm:text-5xl">Privacy</h1>
        <p className="mt-3 text-sm text-marble/70">Last updated 27 September 2026</p>

        {SECTIONS.map((section) => (
          <section key={section.title} className="mt-10">
            <h2 className="font-serif text-2xl leading-snug">{section.title}</h2>
            {section.body.map((paragraph) => (
              <p key={paragraph} className="mt-3 leading-relaxed text-marble/90">
                {paragraph}
              </p>
            ))}
          </section>
        ))}

        <p className="mt-12 leading-relaxed text-marble/90">
          Questions? Open an issue on{" "}
          <a href={`${GITHUB_URL}/issues`} className="text-gold underline underline-offset-4 hover:text-marble">
            GitHub
          </a>
          . Ladon is open source, so you can also read exactly what the extension does.
        </p>
      </article>
    </main>
  );
}
