# Chrome Web Store listing

Everything the Chrome Web Store developer dashboard asks for, ready to paste. Upload `extension/ladon-extension.zip` (build it with `npm run package`).

## Store listing tab

**Name:** Ladon

**Summary** (from the manifest, 120 characters):
Warns you before you pay a scam wallet, sign a drainer transaction, paste a poisoned address or open a fake Solana site.

**Description:**

Ladon is scam and rug pull protection for Solana. It stays quiet until something is wrong, then steps in before your wallet even opens.

What it catches:

• Scam wallets. When a site asks your wallet to sign, Ladon reads the transaction and checks every wallet it pays or hands control to. If one is linked to scams, you see how likely that is and why.
• Poisoned addresses. Scammers send you dust from a lookalike of an address you use. Ladon spots the copy and shows exactly where it differs.
• Scam and fake sites. Known phishing sites, and sites dressed up as Phantom, Solflare, Jupiter, Raydium, Pump.fun, Solscan or DEX Screener, get a warning before you connect.
• Rugs on Axiom. Coins on Axiom Pulse made by serial ruggers are labelled, with the reasons on hover.
• Check or report any wallet or token from the toolbar.

Every score is a probability with its reasons, never an accusation. Ladon never signs, blocks or changes anything, never holds funds and never asks for your seed phrase. The choice is always yours.

Ladon is open source: https://github.com/inkadoo/ladon

**Category:** Tools (or Privacy & Security if offered)

**Language:** English

**Store icon:** `public/icons/icon-128.png`

**Screenshots** (1280×800): `store/01-scam-wallet.png`, `store/02-poisoned-address.png`, `store/03-fake-site.png`, `store/04-axiom.png`

**Small promo tile** (440×280): `store/promo-tile-440x280.png`

**Official URL / homepage:** https://getladon.vercel.app

**Support URL:** https://github.com/inkadoo/ladon/issues

## Privacy tab

**Single purpose:**
Warn Solana users before they send money to scam wallets, sign transactions that hand control of their tokens to scammers, pay a poisoned lookalike address or use a fake or known scam website.

**Permission justifications:**

- **storage:** Keeps Ladon's list of known scam websites, the addresses the user has already paid (to detect poisoned lookalikes) and the sites the user chose to stay on after a warning. All of it stays on the device.
- **Host permission (https://ladon-api.vercel.app/\*):** The extension asks Ladon's own API for the risk of the addresses a transaction pays, and downloads the scam website list.
- **Content scripts on all sites:** Wallet drainers and fake sites can be on any domain. Ladon has to see a signing request on the page to check who it pays before the wallet opens, and has to recognise a scam site wherever it is. It does not read or change page content otherwise.

**Remote code:** No. All code ships in the package. The extension only fetches data (risk scores and the scam site list) as JSON.

**Data usage** (what leaves the device):

- Collected: the Solana addresses being checked (transaction recipients, addresses checked in the popup, token addresses shown on Axiom), and anything the user types into the report form.
- Not collected: personally identifiable information, health, financial account credentials, authentication info, personal communications, location, web history (sites are checked locally), user activity or website content.
- Certify: not sold to third parties, not used or transferred for purposes unrelated to the single purpose, not used to determine creditworthiness or for lending.

**Privacy policy URL:** https://getladon.vercel.app/privacy

## Before you submit

- Pay the one time $5 developer registration fee.
- Test the zip once more: unzip it, load it unpacked in Chrome and check a wallet from the popup.
- Review usually takes a few days. Extensions with content scripts on all sites can take longer. When it's approved, set `EXTENSION_URL` in `web/src/lib/links.ts` to the store link and redeploy the site.
