import { DESCRIPTIONS, TEMPLE, WatchGraph, starPath } from "./WatchGraph";

const STEPS = ["Report", "Verify", "Link", "Warn"];
const NUMERALS = ["I", "II", "III", "IV"];

function StarIcon({ size = "md", fill }: { size?: "sm" | "md"; fill: string }) {
  return (
    <svg viewBox="-6 -6 12 12" aria-hidden="true" className="size-4 shrink-0">
      <path d={starPath({ x: 0, y: 0 }, size)} fill={fill} />
    </svg>
  );
}

function TempleIcon() {
  return (
    <svg viewBox="0 0 9 7" aria-hidden="true" className="pixel h-3.5 w-4.5 shrink-0">
      <path d={TEMPLE} fill="var(--color-marble)" />
    </svg>
  );
}

function Stepper({ stage }: { stage: number }) {
  return (
    <ol className="flex items-stretch border-b-2 border-marble/25 bg-ink/60">
      {STEPS.map((label, i) => {
        const state = i === stage ? "current" : i < stage ? "done" : "next";
        return (
          <li
            key={label}
            aria-current={state === "current" ? "step" : undefined}
            className={`flex flex-1 items-center justify-center gap-1.5 border-r-2 border-marble/25 px-1 py-2 font-caps text-sm transition-colors duration-300 last:border-r-0 motion-reduce:transition-none sm:gap-2 sm:text-base ${
              state === "current" ? "bg-gold text-ink" : state === "done" ? "text-gold" : "text-marble/55"
            }`}
          >
            <span aria-hidden="true">{state === "done" ? "✓" : NUMERALS[i]}</span>
            {label}
          </li>
        );
      })}
    </ol>
  );
}

function Legend() {
  return (
    <ul aria-label="Legend" className="flex flex-wrap gap-x-4 gap-y-1.5 border-t-2 border-marble/25 bg-ink/60 px-3 py-2.5 font-plain text-xs text-marble/85 sm:text-sm">
      <li className="flex items-center gap-1.5"><StarIcon size="sm" fill="var(--color-marble)" />Unknown wallet</li>
      <li className="flex items-center gap-1.5"><StarIcon fill="var(--color-terracotta)" />Scam risk</li>
      <li className="flex items-center gap-1.5"><TempleIcon />Exchange</li>
      <li className="flex items-center gap-1.5"><StarIcon fill="var(--color-dragon-light)" />You</li>
      <li className="flex items-center gap-1.5"><StarIcon fill="var(--color-gold)" />Ladon</li>
    </ul>
  );
}

export function DracoPanel({ stage }: { stage: number }) {
  return (
    <figure className="mx-auto w-full max-w-[44rem] border-4 border-gold bg-navy p-1.5 shadow-[6px_6px_0_var(--color-ink)]">
      <div className="border-2 border-marble/25">
        <Stepper stage={stage} />
        <div role="img" aria-label={DESCRIPTIONS[Math.max(stage, 0)]} className="px-1 sm:px-2">
          <WatchGraph stage={stage} />
        </div>
        <Legend />
      </div>
    </figure>
  );
}
