const FONTS = () => `
@font-face { font-family: "Ladon Caps"; src: url("${chrome.runtime.getURL("fonts/AlegreyaSC-700.woff2")}") format("woff2"); font-weight: 700; font-display: swap; }
@font-face { font-family: "Ladon Plain"; src: url("${chrome.runtime.getURL("fonts/AtkinsonHyperlegibleNext.woff2")}") format("woff2"); font-weight: 200 800; font-display: swap; }
`;

export function loadFonts(): void {
  if (document.getElementById("ladon-fonts")) return;
  const style = document.createElement("style");
  style.id = "ladon-fonts";
  style.textContent = FONTS();
  (document.head ?? document.documentElement).append(style);
}
