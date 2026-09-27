import assert from "node:assert/strict";
import { test } from "node:test";
import { decodeBase58, encodeBase58, isSolanaAddress, isTransactionSignature, shortAddress } from "./solana.ts";

test("accepts real Solana public keys", () => {
  for (const address of [
    "11111111111111111111111111111111",
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "  EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v\n",
  ]) {
    assert.ok(isSolanaAddress(address), address);
  }
});

test("rejects anything that is not a public key", () => {
  for (const value of ["", "abc", "0".repeat(44), "O".repeat(44), "I".repeat(44), "l".repeat(44), "<script>alert(1)</script>", "1".repeat(31), "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DAxxxx"]) {
    assert.equal(isSolanaAddress(value), false, value);
  }
});

test("recognises transaction signatures and nothing else", () => {
  const signature = "5keT61KU7SeBLgz4FJTY9QESTHyDvHGVJDmha1wKsMk5U5nzTsLfHZqCAFA47Q797RhXUanqdjWxyufi3pxtCkE1";
  assert.ok(isTransactionSignature(signature));
  assert.equal(isTransactionSignature("DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"), false);
  assert.equal(isSolanaAddress(signature), false);
});

test("shortens long addresses for display", () => {
  assert.equal(shortAddress("DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"), "DezX…B263");
  assert.equal(shortAddress("short"), "short");
});

test("base58 round trips keys, including leading zero bytes", () => {
  for (const address of ["11111111111111111111111111111111", "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA", "1112jQ5uPX9gv7C3v3gU2zDmr8mGqS8HzNL6H2cgJ3bM"]) {
    const bytes = decodeBase58(address);
    assert.ok(bytes);
    assert.equal(encodeBase58(bytes), address);
  }
  assert.equal(decodeBase58("0OIl"), null);
});
