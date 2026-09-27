import { decodeBase58, encodeBase58 } from "../../shared/solana.ts";

export type TargetKind = "payment" | "approval" | "authority";

export type Target = { address: string; kind: TargetKind };

const SYSTEM = "11111111111111111111111111111111";
const TOKEN = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA";
const TOKEN_2022 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb";
const ASSOCIATED = "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL";

const MAX_TARGETS = 5;

type Instruction = { program: string | undefined; accounts: (string | undefined)[]; data: Uint8Array };

type Message = { signers: Set<string>; instructions: Instruction[] };

class Reader {
  offset = 0;
  readonly bytes: Uint8Array;

  constructor(bytes: Uint8Array) {
    this.bytes = bytes;
  }

  byte(): number {
    if (this.offset >= this.bytes.length) throw new RangeError("truncated");
    return this.bytes[this.offset++];
  }

  length(): number {
    let value = 0;
    for (let shift = 0; shift < 21; shift += 7) {
      const byte = this.byte();
      value |= (byte & 0x7f) << shift;
      if ((byte & 0x80) === 0) return value;
    }
    throw new RangeError("bad length");
  }

  take(count: number): Uint8Array {
    if (this.offset + count > this.bytes.length) throw new RangeError("truncated");
    const slice = this.bytes.subarray(this.offset, this.offset + count);
    this.offset += count;
    return slice;
  }
}

function readMessage(reader: Reader): Message {
  if (reader.bytes[reader.offset] & 0x80) reader.byte();
  const required = reader.byte();
  reader.byte();
  reader.byte();
  const keys = Array.from({ length: reader.length() }, () => encodeBase58(reader.take(32)));
  reader.take(32);
  const instructions = Array.from({ length: reader.length() }, () => {
    const program = keys[reader.byte()];
    const accounts = Array.from(reader.take(reader.length()), (i) => keys[i]);
    const data = reader.take(reader.length());
    return { program, accounts, data };
  });
  return { signers: new Set(keys.slice(0, required)), instructions };
}

function parse(bytes: Uint8Array, bare: boolean): Message | null {
  try {
    const reader = new Reader(bytes);
    if (bare) return readMessage(reader);
    const signatures = reader.length();
    reader.take(signatures * 64);
    const message = readMessage(reader);
    return message.signers.size === signatures ? message : null;
  } catch {
    return null;
  }
}

function u32(data: Uint8Array): number {
  return data.length >= 4 ? new DataView(data.buffer, data.byteOffset, 4).getUint32(0, true) : -1;
}

function system(ix: Instruction): Target[] {
  const code = u32(ix.data);
  if (code === 2) return [{ address: ix.accounts[1] ?? "", kind: "payment" }];
  if (code === 11) return [{ address: ix.accounts[2] ?? "", kind: "payment" }];
  if (code === 1 && ix.data.length >= 36) return [{ address: encodeBase58(ix.data.subarray(4, 36)), kind: "authority" }];
  return [];
}

function token(ix: Instruction, owners: Map<string, string>): Target[] {
  const payTo = (account: string | undefined): Target => ({ address: owners.get(account ?? "") ?? account ?? "", kind: "payment" });
  switch (ix.data[0]) {
    case 3:
      return [payTo(ix.accounts[1])];
    case 12:
      return [payTo(ix.accounts[2])];
    case 4:
      return [{ address: ix.accounts[1] ?? "", kind: "approval" }];
    case 13:
      return [{ address: ix.accounts[2] ?? "", kind: "approval" }];
    case 6:
      return ix.data.length >= 35 && ix.data[2] === 1 ? [{ address: encodeBase58(ix.data.subarray(3, 35)), kind: "authority" }] : [];
    default:
      return [];
  }
}

function fromMessage(message: Message): Target[] {
  const owners = new Map<string, string>();
  for (const ix of message.instructions) {
    if (ix.program === ASSOCIATED && ix.data.length <= 1 && ix.accounts[1] && ix.accounts[2]) owners.set(ix.accounts[1], ix.accounts[2]);
  }
  const found: Target[] = [];
  for (const ix of message.instructions) {
    if (ix.program === SYSTEM) found.push(...system(ix));
    else if (ix.program === TOKEN || ix.program === TOKEN_2022) found.push(...token(ix, owners));
  }
  return found.filter((t) => t.address.length > 0 && !message.signers.has(t.address));
}

export function targets(bytes: Uint8Array, bare = false): Target[] {
  const message = parse(bytes, bare);
  return message ? fromMessage(message) : [];
}

function isBytes(value: unknown): value is Uint8Array {
  return value instanceof Uint8Array;
}

type Encoded = { bytes: Uint8Array; bare: boolean };

export function encoded(transaction: unknown, bare = false): Encoded | null {
  if (isBytes(transaction)) return { bytes: transaction, bare };
  if (typeof transaction === "string") {
    const bytes = decodeBase58(transaction);
    return bytes ? { bytes, bare } : null;
  }
  if (!transaction || typeof transaction !== "object") return null;
  const tx = transaction as { serialize?: unknown; serializeMessage?: unknown; messageBytes?: unknown };
  if (isBytes(tx.messageBytes)) return { bytes: tx.messageBytes, bare: true };
  if (typeof tx.serialize === "function") {
    try {
      const bytes: unknown = tx.serialize.call(transaction, { requireAllSignatures: false, verifySignatures: false });
      if (isBytes(bytes)) return { bytes, bare: false };
    } catch {}
  }
  if (typeof tx.serializeMessage === "function") {
    try {
      const bytes: unknown = tx.serializeMessage.call(transaction);
      if (isBytes(bytes)) return { bytes, bare: true };
    } catch {}
  }
  return null;
}

export function collect(transactions: unknown[], bare = false): Target[] {
  const seen = new Map<string, Target>();
  for (const transaction of transactions) {
    const found = encoded(transaction, bare);
    if (!found) continue;
    for (const target of targets(found.bytes, found.bare)) {
      const existing = seen.get(target.address);
      if (!existing || (existing.kind === "payment" && target.kind !== "payment")) seen.set(target.address, target);
    }
  }
  return [...seen.values()].slice(0, MAX_TARGETS);
}

export function signers(transactions: unknown[], bare = false): string[] {
  const found = new Set<string>();
  for (const transaction of transactions) {
    const encodedTx = encoded(transaction, bare);
    const message = encodedTx ? parse(encodedTx.bytes, encodedTx.bare) : null;
    for (const signer of message?.signers ?? []) found.add(signer);
  }
  return [...found];
}
