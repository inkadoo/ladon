import { encodeBase58, isSolanaAddress } from "../../../shared/solana";
import { airApi } from "./airdrop";

type PublicKey = { toString(): string };
export type WalletProvider = {
  publicKey?: PublicKey;
  connect(): Promise<{ publicKey?: PublicKey } | void>;
  disconnect?(): Promise<void>;
  signMessage(message: Uint8Array, encoding?: string): Promise<{ signature: Uint8Array } | Uint8Array>;
  on?(event: string, callback: (key?: PublicKey | null) => void): void;
  removeListener?(event: string, callback: (key?: PublicKey | null) => void): void;
};
export type WalletName = "Phantom" | "Solflare" | "Backpack";
type WalletWindow = Window & {
  phantom?: { solana?: WalletProvider };
  solflare?: WalletProvider;
  backpack?: WalletProvider;
};

export async function signInWallet(name: WalletName): Promise<{ provider: WalletProvider; wallet: string; token: string }> {
  const browser = window as WalletWindow;
  const provider = name === "Phantom" ? browser.phantom?.solana : name === "Solflare" ? browser.solflare : browser.backpack;
  if (!provider?.signMessage) throw new Error(`Open Ladon in ${name}'s browser on your phone, or install its browser extension to connect.`);
  const connection = await provider.connect();
  const wallet = (connection?.publicKey ?? provider.publicKey)?.toString();
  if (!wallet || !isSolanaAddress(wallet)) throw new Error("The wallet did not return a valid Solana address.");
  const challenge = await airApi<{ nonce: string; message: string }>("/auth/challenge", { wallet });
  const signed = await provider.signMessage(new TextEncoder().encode(challenge.message), "utf8");
  const signature = signed instanceof Uint8Array ? signed : signed.signature;
  const session = await airApi<{ token: string }>("/auth/verify", { wallet, nonce: challenge.nonce, signature: encodeBase58(signature) });
  return { provider, wallet, token: session.token };
}
