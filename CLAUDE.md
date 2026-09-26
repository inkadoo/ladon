# CLAUDE.md

Project brief for Claude Code. Read this fully before making changes.

## What Ladon is

Ladon is an open source scam and rug pull protection layer for Solana. It maps wallets belonging to scammers, drainers and serial rug pullers, and warns people before they send money to them or buy their tokens.

It is named after Ladon, the serpent dragon of Greek myth who never slept while guarding the golden apples of the Hesperides. The product's promise is the same: a guardian that is always watching.

It has three parts:

1. **The graph engine (the core).** A backend that ingests reported scam addresses and Solana transaction data, then uses ML to confirm, score and expand them into a map of connected scammer wallets.
2. **The browser extension.** Warns users before they send funds to a flagged address, and flags tokens deployed by wallets linked to past rug pulls.
3. **The website (this repo's frontend).** Explains Ladon, hosts the extension download, lets victims report the address that scammed them, and lets anyone look up an address or token.

## Why it exists

Crypto users lose money to drainers, phishing and rug pulls every day, and the tooling that protects them is fragmented. Every wallet and security firm keeps a private blocklist, scammers rotate addresses faster than lists update, and victims have nowhere useful to report. Serial ruggers also launch "new" tokens from fresh wallets that are funded by their old ones, so basic dev history checks miss them.

Ladon's edge is linking wallets together. One report, confirmed with onchain evidence, can expose a whole cluster of connected wallets, and a fresh deployer wallet can be traced back to its past rugs through funding trails.

## Context and deadlines

- Built for the Colosseum Crypto World's Fair hackathon. Submissions close **12 October 2026, 11:59pm PT**. Target the Solana track and the overall prizes.
- Solo builder, so scope must stay tight. Ship the core loop first.
- Judging criteria, in the order to optimise for: functionality and code quality, potential impact, novelty, UX, open source and composability, business plan.
- Everything is open source. Composability with other Solana tools is a judging criterion, so the scam data must be available through a public API, not locked inside the extension.

## Who it is for

- **Everyday Solana users** who want a warning before sending money or aping into a token. They are not security experts. Copy must be plain English.
- **Scam victims** who want to report what happened and help protect others.
- **Wallets and trading platforms** (the future paying customers) who want the scam graph as an API. The free extension proves the data works; the API is the business.

## Build priority

Build in this order. Do not start a later item until the earlier one works end to end.

1. **Scam graph engine.** Ingest reports, pull transactions, score addresses, expose a lookup API.
2. **Extension send warning.** Before a user signs a transfer to a flagged address, show a large, unmissable warning with the confidence score and the reason.
3. **Rug dev check.** Score any token by its deployer's history and funding links. Build this as a lookup on the website first. Overlaying warnings on trading sites like Axiom comes last, because scraping their pages is fragile and may break their terms.
4. **Website.** Hero, download, report form, address and token lookup.

## How the ML and data should work

These rules exist to stop the graph from being poisoned. Follow them in every change.

- **Reports are weak signals, never ground truth.** Anyone can report any address, including scammers reporting innocent people and victims reporting the wrong address. A report alone must never mark an address as a scammer.
- **Confirm with onchain evidence.** Raise a score only with evidence such as interactions with known drainer contracts, sweeper bot patterns (funds swept out within seconds of arriving), links to known phishing, or rug patterns (liquidity pulled, deployer dumps).
- **Always output a confidence score and a reason,** never a bare yes or no. The UI shows both.
- **Stop contamination at shared infrastructure.** Exchange deposit and hot wallets, major protocols, bridges and program addresses must be on an exclusion list and must never inherit risk through the graph. A scammer cashing out through an exchange must not make the exchange look like a scammer.
- **Risk decays with distance.** Wallets one hop from a confirmed scammer inherit some risk; wallets further away inherit much less. Tune thresholds to keep false positives low, because a wrong warning on an innocent wallet destroys trust faster than a missed scam.
- **Rug dev scoring** uses deployer history, funding source clustering, liquidity setup and holder concentration. Linking a new deployer to old rugs through shared funding wallets is the main differentiator.

## Security rules

- Ladon **never** holds private keys, seed phrases or funds, and never asks for them. No feature may require a user to connect a wallet with signing permissions just to look something up.
- The extension only reads transactions to warn about them. It never modifies, blocks or signs anything on the user's behalf.
- Treat every report, address and token name as untrusted input. Validate Solana addresses before use, sanitise all text, and rate limit the report endpoint.
- Never commit API keys (Helius, RPC providers). Use environment variables and keep `.env` in `.gitignore`.
- Do not log reporter IP addresses or personal data beyond what is needed for rate limiting.

## Tech stack

Assumed stack. Confirm with me before adding new frameworks or services.

- **Website:** Next.js (App Router), TypeScript, Tailwind CSS.
- **Extension:** Chrome Manifest V3, TypeScript.
- **ML and graph service:** Python, FastAPI, async. Graph work in NetworkX to start.
- **Solana data:** Helius (webhooks and enhanced transactions API). Free tier is enough for the hackathon.
- **Database:** Postgres for reports, scores and the address graph.
- **Deploy:** Vercel for the website, any small host for the FastAPI service.

## Brand and design

The look is classical painting meets 8 bit. A 19th century academic oil painting of the Garden of the Hesperides carries the imagery; pixel built details (the wordmark, ornaments, borders, the wallet graph) sit on top of it. It should feel like a guardian, calm and watchful, not aggressive or edgy.

Take the approach of the Crypto World's Fair site, never its layout, colours or branding. Ladon's page must read as its own.

**Palette** (use these tokens for all UI, do not invent new colours; the hero painting keeps its own colours):

| Token | Hex | Use |
|---|---|---|
| terracotta | `#B8552F` | Primary background, Greek pottery orange |
| navy | `#14213D` | Night sky, dark sections, text on light |
| dragon | `#2F6B3A` | Ladon's scales, success states |
| dragon-light | `#5FA35A` | Highlights |
| gold | `#F2C14E` | Golden apples, eyes, key accents, safe status |
| marble | `#EDE8DC` | Light text on dark, columns |
| ink | `#1A1A1A` | Pixel outlines |

Warnings are the one place that breaks the calm. A flagged address warning must be loud, high contrast and impossible to miss.

**Typography:** the LADON wordmark is hand built pixel serif lettering (SVG), with an ouroboros in place of the O. Alegreya for headings and body, Alegreya SC for short labels. Atkinson Hyperlegible Next for warnings, forms and anything the user must read carefully. Never set long text in pixel lettering.

**Pixel rules:** always use `image-rendering: pixelated` (and `shape-rendering: crispEdges` on SVG) for pixel assets and canvases. Never blur, smooth or apply CSS filters to pixel elements. Scale them by whole number multiples where possible.

**Hero:** `LadonHero.tsx` is one still picture with no motion and no scroll effects. The painting fills exactly one screen, never zoomed or cropped further; below it, a strip mirroring its ground extends the scene past the fold, and only that strip is frozen mid-fall, so the first view is fully intact: along a ragged line it breaks into blocks, each a single pixel of its own colour, which trail down into ink black below the painting like a waterfall, thinning out as they go. It is drawn once per screen width on a canvas, with a fixed random seed so the shape never changes, and scrolls like any image. Do not add animation or replace it with a video.

## Copy and tone

- Plain, direct English. Write for a normal person who just wants to know if an address is safe.
- Explain what a warning means and what to do next, in one or two sentences.
- No hype, no crypto slang in the product UI, no fear mongering. Calm confidence, like a good guard.
- Always make clear that scores are probabilities, not accusations.

## Code conventions

- TypeScript strict mode. No `any` unless there is no alternative, with a comment explaining why.
- Keep components small and focused. Shared logic for address validation and score formatting lives in one place and is reused by the site and the extension.
- Accessible by default: semantic HTML, visible keyboard focus, sufficient contrast, reduced motion respected.
- Write tests for the scoring logic and address validation. These are the parts where bugs hurt users.
- Only make changes directly requested. Do not refactor, add features or add dependencies beyond the task without asking first.

## Out of scope

- Building a wallet. Ladon watches from outside and never touches keys.
- Protocol level exploit monitoring. That is a possible future product, not this one.
- Chains other than Solana until the Solana version works.
- Any paid token or tokenomics. Ladon has no token.