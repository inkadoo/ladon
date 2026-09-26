// A faithful picture of the extension's send warning. It is an illustration on the
// landing page, so the "buttons" are drawn, not interactive.

import { SolanaMark } from "./SolanaMark";

export function WarningPreview() {
  return (
    <section id="warning" aria-labelledby="warning-title" className="bg-ink px-5 py-24 sm:px-10 lg:px-16">
      <div className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div>
          <h2 id="warning-title" className="font-serif text-4xl leading-tight sm:text-5xl">
            Calm until it matters.
          </h2>
          <p className="mt-5 max-w-[34rem] text-marble/90">
            Most of the time you won&rsquo;t know Ladon is there. When you are about to pay a wallet with strong links
            to scams, it interrupts you with a warning you can&rsquo;t miss, says how sure it is, and explains why.
          </p>
          <p className="mt-4 max-w-[34rem] text-marble/90">
            Every score is a probability, not an accusation. If we are wrong about a wallet, the reason is right there
            for you to judge.
          </p>
        </div>

        <figure className="font-plain">
          <div className="border-4 border-ink bg-marble text-ink shadow-[8px_8px_0_var(--color-ink)]">
            <div className="flex items-center gap-3 bg-terracotta px-5 py-4 text-marble sm:px-6">
              <svg aria-hidden="true" viewBox="0 0 7 7" width="28" height="28" className="pixel shrink-0">
                <path fill="var(--color-gold)" d="M3 0h1v1H3zM2 1h3v1H2zM2 2h3v1H2zM1 3h5v1H1zM1 4h5v1H1zM0 5h7v2H0z" />
                <path fill="var(--color-ink)" d="M3 2h1v2H3zM3 5h1v1H3z" />
              </svg>
              <p className="text-xl font-bold leading-tight sm:text-2xl">Stop. This wallet is linked to scams.</p>
            </div>

            <div className="space-y-5 px-5 py-6 sm:px-6">
              <div>
                <div className="flex items-baseline justify-between gap-4">
                  <p className="text-lg font-bold">92% likely to be a scam wallet</p>
                  <p className="text-sm text-ink/75">High confidence</p>
                </div>
                <div aria-hidden="true" className="mt-2 flex gap-0.5">
                  {Array.from({ length: 20 }, (_, i) => (
                    <span key={i} className={`h-3 flex-1 ${i < 18 ? "bg-terracotta" : "bg-ink/15"}`} />
                  ))}
                </div>
              </div>

              <div>
                <p className="text-sm font-bold uppercase tracking-wide text-ink/75">Why</p>
                <ul className="mt-1 list-disc space-y-1 pl-5">
                  <li>Received money from 3 wallets confirmed as drainers.</li>
                  <li>Moved every payment out within 10 seconds of it arriving, 214 times.</li>
                </ul>
              </div>

              <p className="border-2 border-ink bg-gold/60 px-4 py-3">
                <strong>Don&rsquo;t send.</strong> If someone asked you to pay this address, stop replying to them.
              </p>

              <p className="flex items-center gap-2 break-all text-sm text-ink/75">
                <SolanaMark title="Solana" className="text-ink/60" />
                To: 7xKX…9fQm
              </p>

              <div aria-hidden="true" className="flex flex-wrap gap-3 pt-1">
                <span className="border-2 border-ink bg-ink px-5 py-2.5 font-bold text-marble">Cancel transfer</span>
                <span className="px-2 py-2.5 text-ink/75 underline">I understand the risk</span>
              </div>
            </div>
          </div>
          <figcaption className="mt-6 text-base text-marble/80">
            The warning the extension shows before you sign. Example data.
          </figcaption>
        </figure>
      </div>
    </section>
  );
}
