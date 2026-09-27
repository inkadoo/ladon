import { LadonHero } from "@/components/LadonHero";
import { HowItWorks } from "@/components/HowItWorks";
import { WarningPreview } from "@/components/WarningPreview";
import { OpenData } from "@/components/OpenData";
import Link from "next/link";
import { EXTENSION_URL } from "@/lib/links";
import { SolanaMark } from "@/components/SolanaMark";

export default function Home() {
  return (
    <>
      <main>
        <LadonHero />

        <section aria-labelledby="myth-title" className="px-5 pt-16 pb-24 sm:px-10 lg:px-16">
          <div className="mx-auto max-w-3xl">
            <h2 id="myth-title" className="font-serif text-4xl leading-tight italic sm:text-6xl">
              In the myth, Ladon never slept.
            </h2>
            <p className="mt-8 text-xl text-marble/90 sm:text-2xl sm:leading-relaxed">
              The serpent coiled around the tree of golden apples and watched it day and night. We built Ladon to do the
              same for your wallet. It checks every address you are about to pay, and warns you when it is linked to
              scams, drainers or rug pulls.
            </p>
          </div>
        </section>

        <div aria-hidden="true" className="meander" />
        <HowItWorks />
        <WarningPreview />
        <OpenData />
        <div aria-hidden="true" className="meander" />

        <section aria-labelledby="cta-title" className="px-5 py-28 text-center sm:px-10">
          <h2 id="cta-title" className="font-serif text-4xl leading-tight sm:text-5xl">
            Keep watch with us.
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-marble/90">
            Add Ladon to Chrome and it keeps watch every time you sign. If a scammer got you, report them from the
            extension and help protect the next person.
          </p>
          <a
            href={EXTENSION_URL}
            className="mt-9 inline-flex border-2 border-ink bg-gold px-6 py-3 font-caps text-lg font-bold text-ink shadow-[4px_4px_0_var(--color-marble)] transition-transform duration-150 ease-(--ease-out-quart) hover:-translate-y-0.5 active:translate-y-0.5"
          >
            Get the Chrome extension
          </a>
        </section>
      </main>

      <footer className="flex flex-wrap items-center justify-between gap-x-8 gap-y-3 border-t border-marble/15 px-5 py-8 font-plain text-sm text-marble/75 sm:px-10 lg:px-16">
        <p>Ladon never asks for your seed phrase, private keys or funds. Anyone who does is not us.</p>
        <p className="flex items-center gap-6">
          <Link href="/privacy" className="underline underline-offset-4 hover:text-gold">
            Privacy
          </Link>
          <span className="flex items-center gap-2">
            <SolanaMark className="text-marble/60" />
            Built for Solana
          </span>
        </p>
      </footer>
    </>
  );
}
