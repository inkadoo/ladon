import type { Metadata } from "next";
import { Alegreya, Alegreya_SC, Atkinson_Hyperlegible_Next } from "next/font/google";
import "./globals.css";

const alegreya = Alegreya({
  variable: "--font-alegreya",
  subsets: ["latin"],
  style: ["normal", "italic"],
});

const alegreyaSC = Alegreya_SC({
  variable: "--font-alegreya-sc",
  subsets: ["latin"],
  weight: ["500", "700"],
});

const atkinson = Atkinson_Hyperlegible_Next({
  variable: "--font-atkinson",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Ladon: scam protection for Solana",
  description:
    "Ladon warns you before you send money to a wallet linked to scams, drainers or rug pulls. Open source, with a public API.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${alegreya.variable} ${alegreyaSC.variable} ${atkinson.variable} antialiased`}
    >
      <body>{children}</body>
    </html>
  );
}
