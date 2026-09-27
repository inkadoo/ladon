import { GITHUB_URL } from "@/lib/links";
import { SolanaMark } from "./SolanaMark";

const EXAMPLE = `GET /v1/address/7xKX…9fQm

{
  "address": "7xKX…9fQm",
  "token_account": null,
  "risk": 0.92,
  "confidence": "high",
  "flagged": true,
  "reasons": [
    {
      "code": "linked_to_scam",
      "text": "Received money directly from a high risk wallet."
    },
    {
      "code": "reported",
      "text": "Reported by 3 people. Reports alone are never treated as proof."
    }
  ],
  "cluster_size": 8,
  "reports": 3
}`;

const ENDPOINTS = [
  ["GET /v1/address/{address}", "Wallet risk, with the reasons"],
  ["GET /v1/token/{mint}/risk", "Rug risk for any token"],
  ["GET /v1/phishing/domains", "Known scam sites"],
  ["POST /v1/reports", "Report a wallet that scammed you"],
];

export function OpenData() {
  return (
    <section id="api" aria-labelledby="api-title" className="px-5 py-24 sm:px-10 lg:px-16">
      <div className="mx-auto grid max-w-6xl grid-cols-1 gap-12 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
        <div>
          <h2 id="api-title" className="font-serif text-4xl leading-tight sm:text-5xl">
            The map belongs to everyone.
          </h2>
          <p className="mt-5 max-w-[34rem] text-marble/90">
            Every wallet and security company keeps its own private blocklist, and scammers switch wallets faster than
            those lists update. Ladon is open source, and the scam map is open too.
          </p>
          <p className="mt-4 max-w-[34rem] text-marble/90">
            Any wallet, exchange or trading site can check an address against it through a public API, and get the
            same score and reasons the extension shows.
          </p>
          <ul className="mt-6 grid max-w-[34rem] gap-2 font-plain text-sm text-marble/85">
            {ENDPOINTS.map(([route, what]) => (
              <li key={route} className="flex flex-wrap items-baseline gap-x-3">
                <code className="font-mono text-gold">{route}</code>
                <span>{what}</span>
              </li>
            ))}
          </ul>
          <a href={GITHUB_URL} className="mt-7 inline-block font-caps text-lg text-gold underline decoration-2 underline-offset-4 hover:text-marble">
            Read the code on GitHub
          </a>
        </div>

        <figure>
          <pre className="overflow-x-auto border-2 border-marble/25 bg-navy p-6 font-mono text-[13px] leading-relaxed text-marble">
            <code>{EXAMPLE}</code>
          </pre>
          <figcaption className="mt-3 flex items-center gap-2 font-plain text-base text-marble/80">
            <SolanaMark className="text-marble/60" />
            A wallet lookup, exactly as the API returns it. Example data.
          </figcaption>
        </figure>
      </div>
    </section>
  );
}
