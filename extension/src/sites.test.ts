import assert from "node:assert/strict";
import { test } from "node:test";
import { isBlocked, lookalike, verdict } from "./sites.ts";

const blocked = new Set(["phantom-app.online", "solana-claim.xyz"]);

test("blocks listed domains and their subdomains, not unrelated hosts", () => {
  assert.ok(isBlocked("phantom-app.online", blocked));
  assert.ok(isBlocked("WWW.Phantom-App.Online.", blocked));
  assert.ok(isBlocked("mint.solana-claim.xyz", blocked));
  assert.equal(isBlocked("claim.xyz", blocked), false);
  assert.equal(isBlocked("online", blocked), false);
});

test("never flags the official sites or their subdomains", () => {
  for (const host of ["phantom.app", "www.phantom.com", "help.phantom.com", "jup.ag", "station.jup.ag", "raydium.io", "pump.fun", "solscan.io", "dexscreener.com", "solflare.com"]) {
    assert.equal(lookalike(host), null, host);
  }
});

test("catches typosquats and homoglyphs", () => {
  assert.deepEqual(lookalike("raydlum.io"), { brand: "Raydium", official: "raydium.io" });
  assert.deepEqual(lookalike("phantorn.app"), { brand: "Phantom", official: "phantom.app" });
  assert.deepEqual(lookalike("so1flare.com"), { brand: "Solflare", official: "solflare.com" });
  assert.deepEqual(lookalike("phahtom.com"), { brand: "Phantom", official: "phantom.app" });
  assert.deepEqual(lookalike("jup-ag.com"), { brand: "Jupiter", official: "jup.ag" });
  assert.deepEqual(lookalike("pump-fun.io"), { brand: "Pump.fun", official: "pump.fun" });
});

test("catches brand names dressed up with lure words", () => {
  assert.equal(lookalike("phantom-app.online")?.brand, "Phantom");
  assert.equal(lookalike("claim-phantom-airdrop.xyz")?.brand, "Phantom");
  assert.equal(lookalike("phantomwallet.net")?.brand, "Phantom");
  assert.equal(lookalike("solflare.wallet-sync.com")?.brand, "Solflare");
});

test("leaves ordinary sites that happen to share a word alone", () => {
  for (const host of ["phantomjs.org", "phantomoftheopera.com", "elephantom.net", "google.com", "solana.com", "raydiumfans.blog", "localhost", "pumpkin.fun"]) {
    assert.equal(lookalike(host), null, host);
  }
});

test("skips punycode hosts rather than guessing", () => {
  assert.equal(lookalike("xn--phntom-8ve.app"), null);
});

test("a listed domain is reported as blocked before any lookalike guess", () => {
  assert.deepEqual(verdict("phantom-app.online", blocked), { kind: "blocked", host: "phantom-app.online" });
  assert.deepEqual(verdict("phantomwallet.net", blocked), { kind: "lookalike", host: "phantomwallet.net", brand: "Phantom", official: "phantom.app" });
  assert.equal(verdict("example.com", blocked), null);
  assert.equal(verdict("localhost", blocked), null);
});
