const ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";

function base58Length(value: string): number | null {
  const bytes: number[] = [];
  for (const char of value) {
    let carry = ALPHABET.indexOf(char);
    if (carry < 0) return null;
    for (let i = 0; i < bytes.length; i++) {
      carry += bytes[i] * 58;
      bytes[i] = carry & 0xff;
      carry >>= 8;
    }
    while (carry > 0) {
      bytes.push(carry & 0xff);
      carry >>= 8;
    }
  }
  const leadingZeros = value.length - value.replace(/^1+/, "").length;
  return bytes.length + leadingZeros;
}

export function isSolanaAddress(value: string): boolean {
  const candidate = value.trim();
  return candidate.length >= 32 && candidate.length <= 44 && base58Length(candidate) === 32;
}

export function isTransactionSignature(value: string): boolean {
  const candidate = value.trim();
  return candidate.length >= 64 && candidate.length <= 88 && base58Length(candidate) === 64;
}

export function shortAddress(address: string): string {
  return address.length > 12 ? `${address.slice(0, 4)}…${address.slice(-4)}` : address;
}
