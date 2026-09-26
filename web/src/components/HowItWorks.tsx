"use client";

import { useEffect, useRef, useState } from "react";
import { DracoPanel } from "./DracoPanel";

const STEPS = [
  {
    numeral: "I",
    title: "A victim reports the address.",
    body: "Someone who lost money tells Ladon which wallet took it. On its own a report proves nothing, because anyone can report anyone, so it only starts the check.",
  },
  {
    numeral: "II",
    title: "The chain has to agree.",
    body: "Ladon looks for evidence in the wallet's own history: money received from known drainers, money swept out seconds after it lands, liquidity pulled from a token. Only evidence raises the score.",
  },
  {
    numeral: "III",
    title: "The linked wallets light up.",
    body: "Scammers move money between wallets they control. Ladon follows those trails, so one confirmed report can expose a whole group. Risk fades with every step away, and exchanges never inherit it.",
  },
  {
    numeral: "IV",
    title: "You get warned before you sign.",
    body: "If you are about to pay any wallet in that group, the extension tells you how likely it is to be a scam and why. It never blocks or signs anything. The choice stays yours.",
  },
];

export function HowItWorks() {
  const [stage, setStage] = useState(-1);
  const stepRefs = useRef<(HTMLElement | null)[]>([]);

  useEffect(() => {
    const pickClosest = () => {
      const mid = window.innerHeight / 2;
      let best = 0;
      let bestDistance = Infinity;
      stepRefs.current.forEach((el, i) => {
        if (!el) return;
        const r = el.getBoundingClientRect();
        const distance = Math.abs(r.top + r.height / 2 - mid);
        if (distance < bestDistance) {
          bestDistance = distance;
          best = i;
        }
      });
      const first = stepRefs.current[0]?.getBoundingClientRect();
      setStage(first && first.top > window.innerHeight * 0.75 ? -1 : best);
    };
    let frame = 0;
    const schedule = () => {
      if (!frame)
        frame = requestAnimationFrame(() => {
          frame = 0;
          pickClosest();
        });
    };
    pickClosest();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
    };
  }, []);

  return (
    <section id="how" aria-labelledby="how-title" className="starfield relative px-5 py-24 sm:px-10 lg:px-16">
      <h2 id="how-title" className="max-w-2xl font-serif text-4xl leading-tight sm:text-5xl">
        One report can expose a whole ring of wallets.
      </h2>
      <p className="mt-4 max-w-xl text-marble/85">
        In the myth, Hera set Ladon among the stars as Draco. Here, the stars are wallets.
      </p>

      <div className="mt-10 lg:mt-0 lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] lg:gap-16">
        <div className="sticky top-0 py-4 max-lg:bg-navy lg:order-2 lg:flex lg:h-svh lg:items-center lg:py-0" style={{ zIndex: 5 }}>
          <DracoPanel stage={stage} />
        </div>

        <ol className="lg:order-1">
          {STEPS.map((step, i) => (
            <li
              key={step.numeral}
              ref={(el) => {
                stepRefs.current[i] = el;
              }}
              data-step={i}
              className="flex min-h-[60svh] flex-col justify-center py-10 lg:min-h-[85svh]"
            >
              <div
                className={`transition-opacity duration-500 ease-(--ease-out-quart) motion-reduce:transition-none ${stage === i ? "opacity-100" : "opacity-50"}`}
              >
                <p
                  aria-hidden="true"
                  className={`grid h-11 min-w-11 place-items-center justify-self-start border-2 px-2 font-caps text-2xl leading-none shadow-[3px_3px_0_var(--color-ink)] transition-colors duration-300 motion-reduce:transition-none ${
                    stage === i ? "border-gold bg-gold text-ink" : i < stage ? "border-gold text-gold" : "border-marble/50 text-marble"
                  }`}
                  style={{ width: "fit-content" }}
                >
                  {step.numeral}
                </p>
                <h3 className="mt-4 font-serif text-3xl leading-tight">{step.title}</h3>
                <p className="mt-4 max-w-[34rem] text-marble/90">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
