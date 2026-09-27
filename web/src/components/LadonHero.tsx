"use client";

import Image from "next/image";
import { useEffect, useRef } from "react";
import { Wordmark } from "./Wordmark";
import { SolanaMark } from "./SolanaMark";
import { EXTENSION_URL, GITHUB_URL } from "@/lib/links";

const BLOCK_CSS_PX = 8;
const GROUND_EXTENSION = 0.14;
const FROZEN_AT = 0.12;
const EDGE_SPAN = 0.08;
const LONGEST_FALL = 0.5;
const GRAVITY = (2 * LONGEST_FALL) / (FROZEN_AT * FROZEN_AT);
const INK = "#1a1a1a";

function clamp01(v: number) {
  return Math.min(1, Math.max(0, v));
}

function coverRect(img: HTMLImageElement, w: number, h: number) {
  const scale = Math.max(w / img.naturalWidth, h / img.naturalHeight);
  const dw = img.naturalWidth * scale;
  const dh = img.naturalHeight * scale;
  return { dx: (w - dw) / 2, dy: (h - dh) / 2, dw, dh };
}

function seededRandom(seed: number) {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function paint(canvas: HTMLCanvasElement, img: HTMLImageElement, paintingCssHeight: number) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = Math.round(canvas.clientWidth * dpr);
  const h = Math.round(canvas.clientHeight * dpr);
  const paintingH = Math.round(paintingCssHeight * dpr);
  canvas.width = w;
  canvas.height = h;

  const block = Math.max(2, Math.round(BLOCK_CSS_PX * dpr));
  const cols = Math.ceil(w / block);
  const sceneH = paintingH + Math.round(paintingH * GROUND_EXTENSION);
  const rows = Math.ceil(sceneH / block);

  const scene = document.createElement("canvas");
  scene.width = w;
  scene.height = sceneH;
  const small = document.createElement("canvas");
  small.width = cols;
  small.height = rows;
  const sc = scene.getContext("2d");
  const smc = small.getContext("2d");
  if (!sc || !smc) return;
  const { dx, dy, dw, dh } = coverRect(img, w, paintingH);
  sc.drawImage(img, dx, dy, dw, dh);
  const extension = sceneH - paintingH;
  sc.save();
  sc.translate(0, 2 * paintingH);
  sc.scale(1, -1);
  sc.drawImage(scene, 0, paintingH - extension, w, extension, 0, paintingH - extension, w, extension);
  sc.restore();
  smc.drawImage(scene, 0, 0, cols * block, rows * block, 0, 0, cols, rows);
  const colors = smc.getImageData(0, 0, cols, rows).data;

  const rand = seededRandom(7);
  const phaseA = rand() * 6;
  const phaseB = rand() * 6;

  ctx.fillStyle = INK;
  ctx.fillRect(0, 0, w, h);

  for (let x = 0; x < cols; x++) {
    const u = x / cols;
    const edge = clamp01(0.5 + 0.25 * Math.sin(u * 23 + phaseA) + 0.15 * Math.sin(u * 7 + phaseB) + (rand() - 0.5) * 0.2);
    const px = x * block;

    let attached = rows;
    for (let y = rows - 1; y >= 0; y--) {
      const release = (rows - 1 - y) / rows + edge * EDGE_SPAN;
      if (release > FROZEN_AT) break;
      attached = y;
    }
    if (attached > 0) ctx.drawImage(scene, px, 0, block, attached * block, px, 0, block, attached * block);

    for (let y = attached; y < rows; y++) {
      const release = (rows - 1 - y) / rows + edge * EDGE_SPAN;
      const t = FROZEN_AT - release;
      const progress = t / FROZEN_AT;
      if (rand() < 0.1 + Math.pow(progress, 1.2) * 0.8) continue;
      const speed = 0.8 + rand() * 0.4;
      const top = Math.round(y * block + 0.5 * GRAVITY * speed * t * t * sceneH);
      if (top >= h) continue;
      const shade = 1 - progress * 0.6;
      const i = y * cols + x;
      ctx.fillStyle = `rgb(${(colors[i * 4] * shade) | 0}, ${(colors[i * 4 + 1] * shade) | 0}, ${(colors[i * 4 + 2] * shade) | 0})`;
      ctx.fillRect(px, top - (top % block), block, block);
    }
  }
}

export function LadonHero() {
  const sectionRef = useRef<HTMLElement>(null);
  const paintingRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const section = sectionRef.current;
    const painting = paintingRef.current;
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!section || !painting || !canvas || !img) return;

    let lastWidth = 0;
    const draw = () => {
      if (!img.complete || !img.naturalWidth) return;
      paint(canvas, img, painting.clientHeight);
      canvas.style.opacity = "1";
    };
    const observer = new ResizeObserver(() => {
      if (section.clientWidth === lastWidth) return;
      lastWidth = section.clientWidth;
      draw();
    });
    observer.observe(section);
    img.addEventListener("load", draw);
    return () => {
      observer.disconnect();
      img.removeEventListener("load", draw);
    };
  }, []);

  return (
    <section ref={sectionRef} aria-labelledby="hero-title" className="relative">
      <div ref={paintingRef} className="absolute inset-x-0 top-0 h-svh">
        <Image
          ref={imgRef}
          src="/hesperides.jpg"
          alt="An oil painting of the Garden of the Hesperides at dusk: the serpent Ladon coiled beneath a tree of golden apples, a temple and the sea behind. Its lower edge breaks into pixels that fall away into darkness."
          fill
          priority
          sizes="100vw"
          className="object-cover"
        />
      </div>
      <canvas ref={canvasRef} aria-hidden="true" className="pixel absolute inset-0 h-full w-full opacity-0" />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-svh bg-[linear-gradient(100deg,rgb(20_33_61/0.72)_0%,rgb(20_33_61/0.35)_38%,transparent_62%)] [mask-image:linear-gradient(to_bottom,black_55%,transparent_80%)]"
      />

      <div className="relative flex h-svh flex-col px-5 sm:px-10 lg:px-16">
        <nav aria-label="Main" className="flex items-center justify-end gap-6 pt-6 font-caps text-lg sm:gap-10">
          <a href="#how" className="rounded-sm hover:text-gold">How it works</a>
          <a href="#warning" className="rounded-sm hover:text-gold">The warning</a>
          <a href="#api" className="hidden rounded-sm hover:text-gold sm:inline">API</a>
          <a href={GITHUB_URL} className="rounded-sm hover:text-gold">GitHub</a>
        </nav>

        <div className="mt-[14svh] max-w-xl sm:mt-[18svh]">
          <h1 id="hero-title">
            <Wordmark scale={9} className="w-[min(100%,34rem)]" />
          </h1>
          <p className="mt-7 max-w-md text-xl leading-snug text-marble [text-shadow:0_1px_0_var(--color-ink)] sm:text-2xl">
            Ladon warns you before you send money to a scammer&rsquo;s wallet, or buy a token made by one.
          </p>
          <div className="mt-9 flex flex-wrap items-center gap-x-6 gap-y-3">
            <a
              href={EXTENSION_URL}
              className="inline-flex items-center gap-3 border-2 border-ink bg-gold px-6 py-3 font-caps text-lg font-bold text-ink shadow-[4px_4px_0_var(--color-ink)] transition-transform duration-150 ease-(--ease-out-quart) hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-[2px_2px_0_var(--color-ink)]"
            >
              Get the Chrome extension
            </a>
            <p className="font-plain text-base text-marble/90 [text-shadow:0_1px_0_var(--color-ink)]">
              Free and open source
            </p>
          </div>
          <p className="mt-8 flex items-center gap-2.5 font-caps text-base tracking-wide text-marble/80 [text-shadow:0_1px_0_var(--color-ink)]">
            <SolanaMark className="text-marble/80" />
            Built for Solana
          </p>
        </div>
      </div>
      <div aria-hidden="true" className="h-[80svh]" />
    </section>
  );
}
