import assert from "node:assert/strict";
import { test } from "node:test";
import { decodeBase58, encodeBase58 } from "../../shared/solana.ts";
import { collect, signers, targets } from "./transaction.ts";

const SYSTEM = "11111111111111111111111111111111";
const TOKEN = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA";
const ASSOCIATED = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL";

const key = (n: number) => encodeBase58(new Uint8Array(32).fill(n));
const user = key(1);
const scammer = key(2);
const scammerTokens = key(3);
const userTokens = key(4);
const mint = key(5);

type Ix = { program: string; accounts: string[]; data: number[] };

const u32 = (n: number) => [n & 0xff, (n >> 8) & 0xff, (n >> 16) & 0xff, (n >> 24) & 0xff];
const bytesOf = (address: string) => [...(decodeBase58(address) ?? [])];

function message(instructions: Ix[], { signers = [user], versioned = false, extraIndex }: { signers?: string[]; versioned?: boolean; extraIndex?: number } = {}): number[] {
  const keys = [...signers];
  for (const ix of instructions) for (const k of [...ix.accounts, ix.program]) if (!keys.includes(k)) keys.push(k);
  const out: number[] = versioned ? [0x80] : [];
  out.push(signers.length, 0, 0, keys.length, ...keys.flatMap(bytesOf), ...new Array(32).fill(9), instructions.length);
  for (const ix of instructions) {
    const accounts = ix.accounts.map((a) => keys.indexOf(a));
    if (extraIndex !== undefined) accounts.push(extraIndex);
    out.push(keys.indexOf(ix.program), accounts.length, ...accounts, ix.data.length, ...ix.data);
  }
  if (versioned) out.push(0);
  return out;
}

const signed = (msg: number[], count = 1) => Uint8Array.from([count, ...new Array(64 * count).fill(0), ...msg]);

const solTransfer = (to: string): Ix => ({ program: SYSTEM, accounts: [user, to], data: [...u32(2), ...new Array(8).fill(1)] });

test("finds the recipient of a SOL transfer", () => {
  assert.deepEqual(targets(signed(message([solTransfer(scammer)]))), [{ address: scammer, kind: "payment" }]);
});

test("never reports the signer's own wallet", () => {
  assert.deepEqual(targets(signed(message([solTransfer(user)]))), []);
});

test("names the owner when the transaction creates the recipient's token account", () => {
  const create: Ix = { program: ASSOCIATED, accounts: [user, scammerTokens, scammer, mint, SYSTEM, TOKEN], data: [1] };
  const send: Ix = { program: TOKEN, accounts: [userTokens, mint, scammerTokens, user], data: [12, ...new Array(8).fill(1), 6] };
  assert.deepEqual(targets(signed(message([create, send]))), [{ address: scammer, kind: "payment" }]);
});

test("falls back to the token account when its owner is not in the transaction", () => {
  const send: Ix = { program: TOKEN, accounts: [userTokens, scammerTokens, user], data: [3, ...new Array(8).fill(1)] };
  assert.deepEqual(targets(signed(message([send]))), [{ address: scammerTokens, kind: "payment" }]);
});

test("flags token approvals and authority changes as handing over control", () => {
  const approve: Ix = { program: TOKEN, accounts: [userTokens, scammer, user], data: [4, ...new Array(8).fill(255)] };
  const takeover: Ix = { program: TOKEN, accounts: [userTokens, user], data: [6, 2, 1, ...bytesOf(key(7))] };
  assert.deepEqual(targets(signed(message([approve, takeover]))), [
    { address: scammer, kind: "approval" },
    { address: key(7), kind: "authority" },
  ]);
});

test("reads versioned transactions and skips accounts only found in lookup tables", () => {
  const msg = message([{ program: SYSTEM, accounts: [user], data: [...u32(2), ...new Array(8).fill(1)] }], { versioned: true, extraIndex: 40 });
  assert.deepEqual(targets(signed(msg)), []);
  assert.deepEqual(targets(signed(message([solTransfer(scammer)], { versioned: true }))), [{ address: scammer, kind: "payment" }]);
});

test("reads a bare message when the wallet is handed one", () => {
  const bare = Uint8Array.from(message([solTransfer(scammer)]));
  assert.deepEqual(collect([{ serializeMessage: () => bare }]), [{ address: scammer, kind: "payment" }]);
  assert.deepEqual(collect([encodeBase58(bare)], true), [{ address: scammer, kind: "payment" }]);
});

test("ignores bytes that are not a transaction", () => {
  assert.deepEqual(targets(Uint8Array.from([1, 2, 3])), []);
  assert.deepEqual(targets(new Uint8Array(0)), []);
  assert.deepEqual(collect([null, 42, {}, "not base58 0OIl"]), []);
});

test("rejects a transaction whose signature count does not match its header", () => {
  assert.deepEqual(targets(signed(message([solTransfer(scammer)]), 2)), []);
});

test("merges repeats across a batch, keeps the most serious kind, and caps the lookups", () => {
  const approve: Ix = { program: TOKEN, accounts: [userTokens, scammer, user], data: [4, ...new Array(8).fill(1)] };
  const many = [10, 11, 12, 13, 14, 15].map((n) => signed(message([solTransfer(key(n))])));
  assert.deepEqual(collect([signed(message([solTransfer(scammer)])), signed(message([approve]))]), [{ address: scammer, kind: "approval" }]);
  assert.equal(collect(many).length, 5);
});

test("lists the wallets that sign, so Ladon can remember them", () => {
  assert.deepEqual(signers([signed(message([solTransfer(scammer)]))]), [user]);
  assert.deepEqual(signers([Uint8Array.from([9, 9])]), []);
});
