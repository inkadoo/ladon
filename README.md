# Ladon

Scam and rug pull protection for Solana. Ladon maps the wallets behind drainers, phishing and serial rug pulls, and warns you before you send money to one of them or buy a token they made.

Named after the serpent that never slept while guarding the golden apples of the Hesperides.

## How it works

1. **Reports come in.** Victims report the address that took their money. A report on its own never flags anything.
2. **The chain has to agree.** Ladon checks the wallet's own history for evidence: payments to known drainer contracts, funds swept out seconds after arriving, liquidity pulled from a token.
3. **Linked wallets are exposed.** Scammers move money between wallets they control. Ladon follows those funding trails, so one confirmed report can expose a whole group. Risk fades with every step away, and exchanges, bridges and major protocols never inherit it.
4. **You get warned before you sign.** The browser extension shows how likely a wallet is to be a scam, and why. It never blocks or signs anything for you.

Every score is a probability with its reasons, not an accusation.

## What the extension catches

- **Scam wallets at signing time.** Before your wallet opens, Ladon reads the transaction a site asks you to sign and checks every wallet it pays or hands control to (SOL and token transfers, token approvals, authority changes).
- **Address poisoning.** Ladon remembers, only in your browser, the addresses you have used. If a new one copies the start and end of one of them, you get a warning showing where they differ.
- **Scam and fake sites.** Known phishing domains, and sites dressed up as Phantom, Solflare, Jupiter, Raydium, Pump.fun, Solscan or DEX Screener, get a warning before you connect. The domain list is checked inside your browser, so your browsing never leaves it.
- **Rug risk on Axiom.** Coins on Axiom Pulse and coin pages are labelled with their rug risk.

Ladon never signs, changes or blocks anything. Every warning leaves the choice with you.

## Repository

| Path | What it is |
|---|---|
| `web/` | The website (Next.js, TypeScript, Tailwind) |
| `engine/` | The scam graph engine and public API (Python, FastAPI) |
| `extension/` | The Chrome extension: warnings before you sign, phishing and poisoning guards, plus check and report from the toolbar |
| `shared/` | Address validation and API client shared by the extension and the site |

## Running the website

```bash
cd web
npm install
npm run dev
```

## Running the extension

```bash
cd extension
npm install
cp .env.example .env   # set the API URL, and a PostHog key if you want analytics
npm run build
npm test
```

Then open `chrome://extensions`, turn on **Developer mode**, click **Load unpacked** and choose `extension/dist`. Pin Ladon from the puzzle-piece menu and click its icon to open it. The engine must be running at the API URL. After changing the code, run `npm run build` again and press the reload arrow on the Ladon card.

## Running the engine

```bash
cd engine
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env   # then fill in your keys
.venv/bin/python -m pytest
.venv/bin/uvicorn ladon.api:app --env-file .env --reload
```

- `GET /v1/address/{address}` returns a wallet's risk (0 to 1), a confidence level, whether it is flagged, and the reasons.
- `GET /v1/address/{address}` also accepts a token account, and scores the wallet that owns it.
- `GET /v1/token/{mint}/risk` returns a token's rug risk from its deployer's history, funding links, settings and holders.
- `GET /v1/phishing/domains` returns known scam domains: Ladon's own list merged with [Phantom's public blocklist](https://github.com/phantom/blocklist) (MIT).
- `POST /v1/reports` with `{"address": "...", "description": "..."}` reports a wallet. A report starts a check of its onchain history; it never flags a wallet on its own.

To see how often Ladon wrongly warns on well-known tokens and the wallets that hold them, run `.venv/bin/python scripts/false_positives.py` (needs a Helius key).

## Research

The launch bundle checks (wallets funded by the creator, or several wallets buying in one transaction) follow the methods described in Hu et al., *MemeTrans: A Dataset for Detecting High-Risk Memecoin Launches on Solana* (arXiv:2602.13480). No data from that dataset is used or distributed here.

## Open data

The scam graph is available through a public API so any wallet, exchange or trading tool can use it. Ladon never holds keys or funds, and never asks for your seed phrase.
