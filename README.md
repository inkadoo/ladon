# Ladon

Scam and rug pull protection for Solana. Ladon maps the wallets behind drainers, phishing and serial rug pulls, and warns you before you send money to one of them or buy a token they made.

Named after the serpent that never slept while guarding the golden apples of the Hesperides.

## How it works

1. **Reports come in.** Victims report the address that took their money. A report on its own never flags anything.
2. **The chain has to agree.** Ladon checks the wallet's own history for evidence: payments to known drainer contracts, funds swept out seconds after arriving, liquidity pulled from a token.
3. **Linked wallets are exposed.** Scammers move money between wallets they control. Ladon follows those funding trails, so one confirmed report can expose a whole group. Risk fades with every step away, and exchanges, bridges and major protocols never inherit it.
4. **You get warned before you sign.** The browser extension shows how likely a wallet is to be a scam, and why. It never blocks or signs anything for you.

Every score is a probability with its reasons, not an accusation.

## Repository

| Path | What it is |
|---|---|
| `web/` | The website (Next.js, TypeScript, Tailwind) |
| `engine/` | The scam graph engine and public API (Python, FastAPI) |
| `extension/` | The Chrome extension — planned |

## Running the website

```bash
cd web
npm install
npm run dev
```

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
- `POST /v1/reports` with `{"address": "...", "description": "..."}` reports a wallet. A report starts a check of its onchain history; it never flags a wallet on its own.

## Research

The launch bundle checks (wallets funded by the creator, or several wallets buying in one transaction) follow the methods described in Hu et al., *MemeTrans: A Dataset for Detecting High-Risk Memecoin Launches on Solana* (arXiv:2602.13480). No data from that dataset is used or distributed here.

## Open data

The scam graph is available through a public API so any wallet, exchange or trading tool can use it. Ladon never holds keys or funds, and never asks for your seed phrase.
