// The scam graph drawn as Draco, the constellation Hera made of Ladon. Wallets are stars along
// the serpent's body; `stage` follows the four steps in HowItWorks:
// 0 one star reported, 1 confirmed by evidence, 2 its neighbours light up with fading risk,
// 3 the whole serpent is traced, its eye opens, and your payment is stopped.
// Reduced motion drops transitions and loops, leaving each stage as a still frame.

import { useEffect, useState, type CSSProperties, type ReactNode } from "react";

export type Point = { x: number; y: number };

// Draco's body from tail to head, then the four stars of the head.
const BODY: Point[] = [
  { x: 260, y: 178 },
  { x: 222, y: 184 },
  { x: 186, y: 172 },
  { x: 160, y: 154 },
  { x: 132, y: 132 },
  { x: 114, y: 104 },
  { x: 114, y: 74 },
  { x: 132, y: 48 },
  { x: 162, y: 62 },
  { x: 186, y: 88 },
  { x: 212, y: 74 },
  { x: 230, y: 50 },
];
const HEAD: Point[] = [BODY[11], { x: 254, y: 44 }, { x: 250, y: 20 }, { x: 224, y: 24 }];
const EYE = HEAD[2];
const REPORTED = 8;
const EXCHANGE: Point = { x: 224, y: 126 };
const YOU: Point = { x: 24, y: 92 };
const PAYEE = 7;
// I: the victim who files the report. II: a drainer contract already known to Ladon.
const VICTIM: Point = { x: 58, y: 184 };
const DRAINER: Point = { x: 44, y: 60 };
// Where your payment is stopped, a little under halfway to the linked wallet.
const STOP: Point = { x: 73, y: 72 };

const RISK_BY_STEP = [0.94, 0.71, 0.38, 0.12];
const hops = (i: number) => Math.abs(i - REPORTED);

const SKY = [
  [12, 12], [44, 22], [60, 150], [116, 14], [136, 30], [186, 110], [214, 120], [236, 12], [306, 100], [308, 140], [40, 186], [96, 190],
  [120, 170], [150, 190], [230, 140], [284, 150], [310, 70], [12, 160], [72, 132], [128, 120], [300, 12], [290, 96], [110, 100], [28, 60],
];

const EASE = "cubic-bezier(0.25, 1, 0.5, 1)";
const MOTION = "motion-reduce:transition-none motion-reduce:animate-none";

function fade(show: boolean, delay = 0, visible = 1, duration = 450): CSSProperties {
  return {
    opacity: show ? visible : 0,
    transition: `opacity ${duration}ms ${EASE}`,
    transitionDelay: show ? `${delay}ms` : "0ms",
  };
}

// A line that draws itself from `from` to `to` when shown.
function Trace({ from, to, show, delay = 0, stroke, width = 2, visible = 1, duration = 600 }: { from: Point; to: Point; show: boolean; delay?: number; stroke: string; width?: number; visible?: number; duration?: number }) {
  return (
    <line
      x1={from.x}
      y1={from.y}
      x2={to.x}
      y2={to.y}
      pathLength={1}
      stroke={stroke}
      strokeWidth={width}
      strokeDasharray="1 1"
      className={MOTION}
      style={{
        strokeDashoffset: show ? 0 : 1,
        opacity: show ? visible : 0,
        transition: `stroke-dashoffset ${duration}ms ${EASE}, opacity 200ms ${EASE}`,
        transitionDelay: show ? `${delay}ms` : "0ms",
      }}
    />
  );
}

// Four-point star sprites with a square core, sized so they read at a glance.
export function starPath({ x, y }: Point, size: "sm" | "md" | "lg") {
  const arm = { sm: 3, md: 5, lg: 7 }[size];
  const core = { sm: 1, md: 2, lg: 3 }[size];
  return `M${x - 1} ${y - arm}h2v${arm * 2}h-2z M${x - arm} ${y - 1}h${arm * 2}v2h-${arm * 2}z M${x - core} ${y - core}h${core * 2}v${core * 2}h-${core * 2}z`;
}

function Star({ at, size, fill, show = true, delay = 0, visible = 1, glow = false, className = "" }: { at: Point; size: "sm" | "md" | "lg"; fill: string; show?: boolean; delay?: number; visible?: number; glow?: boolean; className?: string }) {
  return (
    <g className={MOTION} style={fade(show, delay, visible)}>
      {glow && <circle cx={at.x} cy={at.y} r={13} fill={fill} opacity={0.2} />}
      <path d={starPath(at, size)} fill={fill} className={className} />
    </g>
  );
}

// A small tag pinned to a star, for its risk score or its role.
function Chip({ at, show, delay = 0, tone, children, width = 30 }: { at: Point; show: boolean; delay?: number; tone: string; children: ReactNode; width?: number }) {
  return (
    <g className={MOTION} style={fade(show, delay)}>
      <rect x={at.x - width / 2} y={at.y - 7} width={width} height={14} fill="var(--color-ink)" stroke={tone} strokeWidth={1.5} />
      <text x={at.x} y={at.y + 3.5} textAnchor="middle" fill={tone} className="font-plain font-bold" style={{ fontSize: 9.5 }}>
        {children}
      </text>
    </g>
  );
}

export const TEMPLE = "M3 0h3v1H3zM1 1h7v1H1zM0 2h9v1H0zM1 3h1v3H1zM3 3h1v3H3zM5 3h1v3H5zM7 3h1v3H7zM0 6h9v1H0z";
export const WARNING_SIGN = "M3 0h1v1H3zM2 1h3v1H2zM2 2h3v1H2zM1 3h5v1H1zM1 4h5v1H1zM0 5h7v2H0z";
export const WARNING_MARK = "M3 2h1v2H3zM3 5h1v1H3z";

export const DESCRIPTIONS = [
  "A night sky of unknown wallets. A victim's report travels to one star, which is marked with a question mark, because a report alone is not trusted.",
  "Ladon scans the reported star's history and finds it received money from a known drainer. The star locks in terracotta and its risk score counts up to 94%.",
  "Lines run from the confirmed star along the serpent to its neighbours. Risk is 71% one step away, 38% two steps away and fades further out. A line to an exchange, drawn as a temple, is stopped and the exchange stays neutral.",
  "The whole ring is traced as the serpent Draco and its golden eye opens. Your wallet starts a payment to one of the linked stars, and it is stopped by a warning before you sign.",
];

// Four corner brackets that close in on a target, like a sight settling on it.
function Brackets({ at, stage }: { at: Point; stage: number }) {
  const d = 11;
  const l = 5;
  const path = [
    `M${at.x - d} ${at.y - d + l}v-${l}h${l}`,
    `M${at.x + d - l} ${at.y - d}h${l}v${l}`,
    `M${at.x + d} ${at.y + d - l}v${l}h-${l}`,
    `M${at.x - d + l} ${at.y + d}h-${l}v-${l}`,
  ].join("");
  const on = stage === 0 || stage === 1;
  return (
    <path
      d={path}
      fill="none"
      strokeWidth={2}
      className={MOTION}
      style={{
        stroke: stage === 1 ? "var(--color-terracotta)" : "var(--color-marble)",
        opacity: on ? 1 : 0,
        transform: on ? "scale(1)" : "scale(1.9)",
        transformBox: "fill-box",
        transformOrigin: "center",
        transition: `transform 380ms ${EASE}, opacity 300ms ${EASE}, stroke 300ms ${EASE}`,
        transitionDelay: stage === 0 ? "900ms" : stage === 1 ? "1000ms" : "0ms",
      }}
    />
  );
}

// II: the risk score counts up once the evidence is in, instead of simply appearing.
function useScore(stage: number, target: number) {
  const [counted, setCounted] = useState(0);
  useEffect(() => {
    if (stage !== 1) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let frame = 0;
    const start = performance.now() + (reduce ? 0 : 1000);
    const tick = (now: number) => {
      const t = reduce ? 1 : Math.min(1, Math.max(0, (now - start) / 800));
      setCounted(Math.round(target * (1 - Math.pow(1 - t, 3))));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [stage, target]);
  if (stage < 1) return 0;
  return stage === 1 ? counted : target;
}

export function WatchGraph({ stage }: { stage: number }) {
  const reported = stage === 0;
  const evidence = stage === 1;
  const confirmed = stage >= 1;
  const linked = stage >= 2;
  const traced = stage >= 3;
  const r = BODY[REPORTED];
  const score = useScore(stage, 94);

  return (
    <svg viewBox="0 0 320 200" aria-hidden="true" className="block h-auto w-full">
      <g className="pixel">
        {SKY.map(([x, y], i) => (
          <rect
            key={`${x}-${y}`}
            x={x}
            y={y}
            width={2}
            height={2}
            fill="var(--color-marble)"
            opacity={i % 3 === 0 ? 0.6 : 0.3}
            className={i % 4 === 0 ? `animate-[ladon-twinkle_3s_steps(1)_infinite] ${MOTION}` : undefined}
            style={{ animationDelay: `${(i * 370) % 3000}ms` }}
          />
        ))}
      </g>

      {/* The serpent's outline is always faintly there; step IV traces it and lights the head. */}
      {BODY.slice(0, -1).map((p, i) => (
        <line
          key={`body-${i}`}
          x1={p.x}
          y1={p.y}
          x2={BODY[i + 1].x}
          y2={BODY[i + 1].y}
          stroke="var(--color-marble)"
          strokeWidth={1.5}
          strokeDasharray="3 5"
          className={`transition-opacity duration-700 ${MOTION}`}
          opacity={traced ? 0.55 : 0.14}
        />
      ))}
      {HEAD.map((p, i) => (
        <Trace key={`head-${i}`} from={p} to={HEAD[(i + 1) % HEAD.length]} show={traced} delay={700 + i * 150} stroke="var(--color-gold)" visible={0.9} duration={400} />
      ))}

      {/* III: risk runs along the serpent from the confirmed star, fading with every step. */}
      {BODY.slice(0, -1).map((p, i) => {
        const far = Math.max(hops(i), hops(i + 1));
        if (far > 2) return null;
        const outward = hops(i) > hops(i + 1);
        return (
          <Trace
            key={`risk-${i}`}
            from={outward ? BODY[i + 1] : p}
            to={outward ? p : BODY[i + 1]}
            show={linked}
            delay={(far - 1) * 450}
            stroke="var(--color-terracotta)"
            width={far === 1 ? 3 : 2}
            visible={far === 1 ? 1 : 0.65}
          />
        );
      })}
      <line x1={BODY[9].x} y1={BODY[9].y} x2={EXCHANGE.x - 8} y2={EXCHANGE.y - 14} stroke="var(--color-marble)" strokeWidth={1.5} strokeDasharray="3 3" className={MOTION} style={fade(linked, 600, 0.6)} />
      <g transform={`translate(${EXCHANGE.x - 9} ${EXCHANGE.y - 7}) scale(2)`} className={`pixel ${MOTION}`} style={fade(true, 0, linked ? 1 : 0.3)}>
        <path d={TEMPLE} fill="var(--color-marble)" />
      </g>
      <Chip at={{ x: EXCHANGE.x, y: EXCHANGE.y + 18 }} show={linked} delay={900} tone="var(--color-marble)" width={50}>
        excluded
      </Chip>

      {/* Every wallet is a faint star until the step that reveals it. */}
      {BODY.map((p, i) => {
        if (i === REPORTED) return null;
        const h = hops(i);
        const lit = linked && h <= 3;
        const risk = RISK_BY_STEP[Math.min(h, 3)];
        return (
          <g key={`star-${i}`}>
            <Star at={p} size="sm" fill="var(--color-marble)" visible={traced ? 0.85 : 0.45} show={!lit} />
            <Star at={p} size={h === 1 ? "md" : "sm"} fill="var(--color-terracotta)" show={lit} delay={h * 450 - 100} visible={0.4 + risk * 0.65} glow={h === 1} />
          </g>
        );
      })}
      {HEAD.slice(1).map((p) => (
        <Star key={`h-${p.x}`} at={p} size="sm" fill={traced ? "var(--color-gold)" : "var(--color-marble)"} visible={traced ? 0.95 : 0.45} />
      ))}
      <Chip at={{ x: BODY[7].x, y: BODY[7].y - 17 }} show={linked} delay={450} tone="var(--color-terracotta)">71%</Chip>
      <Chip at={{ x: BODY[9].x - 4, y: BODY[9].y + 18 }} show={linked} delay={450} tone="var(--color-terracotta)">71%</Chip>
      <Chip at={{ x: BODY[10].x + 16, y: BODY[10].y + 2 }} show={linked} delay={900} tone="var(--color-terracotta)">38%</Chip>

      {/* I: a victim's report travels across the sky to the wallet, and a sight closes on it. */}
      <Star at={VICTIM} size="md" fill="var(--color-marble)" show={stage === 0 || evidence} visible={reported ? 1 : 0.4} />
      <Chip at={{ x: VICTIM.x - 32, y: VICTIM.y }} show={reported} tone="var(--color-marble)" width={40}>victim</Chip>
      <Trace from={VICTIM} to={r} show={reported || evidence} delay={reported ? 250 : 0} stroke="var(--color-marble)" width={1.5} visible={reported ? 0.8 : 0.25} duration={650} />
      <Brackets at={r} stage={stage} />
      <Star at={r} size="lg" fill="var(--color-marble)" show={reported} delay={600} className={`animate-[ladon-blink_1.2s_steps(1)_1.3s_infinite] ${MOTION}`} />
      <Chip at={{ x: r.x, y: r.y - 21 }} show={reported} delay={1150} tone="var(--color-marble)" width={18}>?</Chip>

      {/* II: Ladon scans the wallet's history, finds money it received from a known drainer, and the sight locks. */}
      {evidence && (
        <g className="motion-reduce:hidden">
          {[0, 350].map((delay) => (
            <rect
              key={delay}
              x={r.x - 8}
              y={r.y - 8}
              width={16}
              height={16}
              fill="none"
              stroke="var(--color-terracotta)"
              strokeWidth={1.5}
              className="opacity-0 [transform-box:fill-box] origin-center animate-[ladon-ping_1.1s_cubic-bezier(0.25,1,0.5,1)_2]"
              style={{ animationDelay: `${delay}ms` }}
            />
          ))}
        </g>
      )}
      <Trace from={DRAINER} to={r} show={evidence} delay={500} stroke="var(--color-terracotta)" width={2} duration={500} />
      <g className={MOTION} style={fade(evidence, 200)}>
        <circle cx={DRAINER.x} cy={DRAINER.y} r={11} fill="var(--color-terracotta)" opacity={0.2} />
        <path d={`M${DRAINER.x} ${DRAINER.y - 6}l6 6l-6 6l-6 -6z`} fill="var(--color-terracotta)" />
        <path d={`M${DRAINER.x - 1} ${DRAINER.y - 1}h2v2h-2z`} fill="var(--color-ink)" />
      </g>
      <Chip at={{ x: DRAINER.x, y: DRAINER.y - 19 }} show={evidence} delay={300} tone="var(--color-terracotta)" width={72}>known drainer</Chip>
      <Star at={r} size="lg" fill="var(--color-terracotta)" show={confirmed} delay={evidence ? 1000 : 0} glow />
      <rect x={r.x - 1} y={r.y - 1} width={2} height={2} fill="var(--color-gold)" className={MOTION} style={fade(confirmed, evidence ? 1050 : 0)} />
      <Chip at={{ x: r.x + 4, y: r.y - 21 }} show={confirmed} delay={evidence ? 1000 : 0} tone="var(--color-gold)">{`${score}%`}</Chip>

      {/* IV: Ladon's eye opens, and your payment is stopped short of the linked star. */}
      <Star at={EYE} size="lg" fill="var(--color-gold)" show={traced} delay={1300} glow className={`animate-[ladon-twinkle_2.4s_steps(1)_infinite] ${MOTION}`} />
      <text x={HEAD[3].x - 10} y={HEAD[3].y + 4} textAnchor="end" fill="var(--color-gold)" className={`font-caps ${MOTION}`} style={{ ...fade(traced, 1400), fontSize: 11 }}>
        Draco
      </text>

      <Trace from={YOU} to={STOP} show={traced} delay={200} stroke="var(--color-dragon-light)" width={2.5} duration={700} />
      <line x1={STOP.x} y1={STOP.y} x2={BODY[PAYEE].x} y2={BODY[PAYEE].y} stroke="var(--color-dragon-light)" strokeWidth={1.5} strokeDasharray="3 4" className={MOTION} style={fade(traced, 900, 0.35)} />
      <Star at={YOU} size="md" fill="var(--color-dragon-light)" show={traced} glow />
      <Chip at={{ x: YOU.x + 2, y: YOU.y - 20 }} show={traced} tone="var(--color-dragon-light)" width={28}>you</Chip>
      {traced && (
        <rect
          x={YOU.x - 2}
          y={YOU.y - 2}
          width={4}
          height={4}
          fill="var(--color-gold)"
          className="opacity-0 [transform-box:fill-box] animate-[ladon-packet_2.6s_cubic-bezier(0.5,0,0.2,1)_1.2s_infinite] motion-reduce:hidden"
          style={{ "--dx": `${STOP.x - YOU.x - 10}px`, "--dy": `${STOP.y - YOU.y + 5}px` } as CSSProperties}
        />
      )}
      <g transform={`translate(${STOP.x - 7} ${STOP.y - 18}) scale(2)`} className={`pixel ${MOTION}`} style={fade(traced, 800)}>
        <path d={WARNING_SIGN} fill="var(--color-gold)" />
        <path d={WARNING_MARK} fill="var(--color-ink)" />
      </g>
    </svg>
  );
}
