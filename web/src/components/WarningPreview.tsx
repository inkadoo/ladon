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
          <div className="mx-auto max-w-[400px] border-2 border-ink bg-navy text-marble shadow-[inset_0_0_0_1px_rgba(224,102,61,0.55),6px_6px_0_var(--color-ink)]">
            <div
              aria-hidden="true"
              className="pixel h-1.5 bg-[repeating-linear-gradient(90deg,#e0663d_0_6px,transparent_6px_12px)]"
            />
            <div className="grid gap-3.5 px-5 pt-4 pb-5">
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-caps text-lg font-bold leading-none tracking-wide text-gold">Ladon</span>
                <span className="text-2xl font-bold leading-none text-[#f5b38f] tabular-nums">
                  92%<small className="ml-1 text-sm font-medium opacity-80">likely</small>
                </span>
              </div>
              <p className="text-[1.3rem] font-bold leading-snug">This wallet is linked to scams.</p>
              <p className="flex items-baseline gap-2.5 text-[0.95rem] before:size-1.5 before:shrink-0 before:-translate-y-0.5 before:bg-[#e0663d]">
                Received money from 3 wallets confirmed as drainers.
              </p>
              <p className="flex items-center gap-2 text-sm text-marble/65">
                <SolanaMark title="Solana" className="text-marble/60" />
                To <code className="font-mono text-marble">7xKX…9fQm</code>
              </p>
              <div aria-hidden="true" className="flex flex-wrap items-center justify-between gap-3 pt-1">
                <span className="border-2 border-ink bg-marble px-5 py-2.5 font-bold text-ink shadow-[3px_3px_0_var(--color-ink)]">
                  Don&rsquo;t send
                </span>
                <span className="py-1.5 text-marble/70 underline underline-offset-4">Send anyway</span>
              </div>
            </div>
          </div>
          <figcaption className="mx-auto mt-6 max-w-[400px] text-base text-marble/80">
            The warning the extension shows before you sign. Example data.
          </figcaption>
        </figure>
      </div>
    </section>
  );
}
