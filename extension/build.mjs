import { cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import * as esbuild from "esbuild";

const watch = process.argv.includes("--watch");

async function readEnv() {
  if (!existsSync(".env")) return {};
  const pairs = (await readFile(".env", "utf8"))
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#") && line.includes("="))
    .map((line) => [line.slice(0, line.indexOf("=")).trim(), line.slice(line.indexOf("=") + 1).trim()]);
  return Object.fromEntries(pairs);
}

const env = { ...(await readEnv()), ...process.env };
const api = (env.LADON_API_URL || "http://localhost:8000").replace(/\/$/, "");
const posthogHost = (env.POSTHOG_HOST || "https://us.i.posthog.com").replace(/\/$/, "");

function manifest() {
  return {
    manifest_version: 3,
    name: "Ladon",
    version: "0.1.0",
    description: "Check a Solana wallet or token before you pay it or buy it, and report the address that scammed you.",
    action: { default_popup: "popup.html", default_title: "Ladon", default_icon: { 16: "icons/icon-16.png", 32: "icons/icon-32.png", 48: "icons/icon-48.png", 128: "icons/icon-128.png" } },
    icons: { 16: "icons/icon-16.png", 32: "icons/icon-32.png", 48: "icons/icon-48.png", 128: "icons/icon-128.png" },
    host_permissions: [`${api}/*`, ...(env.POSTHOG_KEY ? [`${posthogHost}/*`] : [])],
  };
}

await rm("dist", { recursive: true, force: true });
await mkdir("dist", { recursive: true });
await cp("public", "dist", { recursive: true });
await cp("src/popup.html", "dist/popup.html");
await cp("src/popup.css", "dist/popup.css");
await writeFile("dist/manifest.json", JSON.stringify(manifest(), null, 2));

const options = {
  entryPoints: ["src/popup.ts"],
  bundle: true,
  format: "iife",
  target: "chrome120",
  outfile: "dist/popup.js",
  minify: !watch,
  define: {
    LADON_API_URL: JSON.stringify(api),
    POSTHOG_KEY: JSON.stringify(env.POSTHOG_KEY || ""),
    POSTHOG_HOST: JSON.stringify(posthogHost),
  },
};

if (watch) {
  const context = await esbuild.context(options);
  await context.watch();
  console.log(`Watching. Load extension/dist in chrome://extensions (API: ${api})`);
} else {
  await esbuild.build(options);
  console.log(`Built extension/dist (API: ${api}, analytics: ${env.POSTHOG_KEY ? "on" : "off"})`);
}
