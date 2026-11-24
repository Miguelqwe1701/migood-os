// Screenshots of Migood Home with pretend data, no Migood OS needed:
//   node tools/home-preview.js docs/screenshots
// Uses the Playwright + Chromium that's on the build machine / CI.
const path = require("path");
const { chromium } = require(process.env.PLAYWRIGHT || "playwright");
const out = process.argv[2] || "docs/screenshots";
const ui = path.resolve(__dirname, "../overlay/usr/share/migood-home/index.html");
const icon = (n) => path.resolve(__dirname, "../assets/" + n);

const MOCK = {
  apps: [
    { id: "migood-games.desktop", name: "Migood Games", game: true, icon: icon("migood-square.png"), comment: "Play, chat and Remote Play with your friends." },
    { id: "steam.desktop", name: "Steam", game: true, icon: null },
    { id: "org.DolphinEmu.dolphin-emu.desktop", name: "Dolphin Emulator", game: true, icon: null },
    { id: "org.ppsspp.PPSSPP.desktop", name: "PPSSPP", game: true, icon: null },
    { id: "retroarch.desktop", name: "RetroArch", game: true, icon: null },
    { id: "org.chromium.Chromium.desktop", name: "Chromium", game: false, icon: null },
    { id: "migood-ai.desktop", name: "Migood AI", game: false, icon: icon("migood-button.png") },
    { id: "migood-settings.desktop", name: "Migood OS Settings", game: false, icon: null },
    { id: "org.gnome.Nautilus.desktop", name: "Files", game: false, icon: null },
  ],
  recent: [{ id: "migood-games.desktop" }, { id: "steam.desktop" }, { id: "org.ppsspp.PPSSPP.desktop" }],
  account: { name: "Miguel", avatar: null, signedIn: true },
  status: { online: true, volume: 60, muted: false, battery: { percent: 82, charging: false } },
  wifi: [
    { ssid: "Home Wi-Fi", signal: 88, secure: true, connected: true },
    { ssid: "Hotel Guest", signal: 61, secure: false, connected: false },
    { ssid: "Neighbor 5G", signal: 34, secure: true, connected: false },
  ],
};

(async () => {
  const browser = await chromium.launch({ args: ["--allow-file-access-from-files"] });
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  await page.addInitScript((mock) => {
    window.migoodMock = async (cmd) => mock[cmd] ?? { ok: true };
  }, MOCK);
  await page.goto("file://" + ui);
  // Nunito is installed on Migood OS; load the repo's copy here so it looks the same.
  const fonts = path.resolve(__dirname, "../assets/fonts");
  await page.addStyleTag({ content: ["Regular:400", "SemiBold:600", "Bold:700", "ExtraBold:800"].map((w) => {
    const [n, weight] = w.split(":");
    return `@font-face{font-family:Nunito;font-weight:${weight};src:url("file://${fonts}/Nunito-${n}.ttf")}`;
  }).join("") });
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${out}/home-1-home.png` });
  await page.keyboard.press("ArrowDown"); await page.keyboard.press("ArrowRight");
  await page.waitForTimeout(300);
  await page.screenshot({ path: `${out}/home-2-focus.png` });
  await page.keyboard.press("PageDown"); await page.waitForTimeout(400);
  await page.screenshot({ path: `${out}/home-3-games.png` });
  await page.keyboard.press("PageDown"); await page.keyboard.press("PageDown"); await page.waitForTimeout(500);
  await page.screenshot({ path: `${out}/home-4-settings.png` });
  await page.keyboard.press("Meta"); await page.waitForTimeout(300);
  await page.screenshot({ path: `${out}/home-5-power.png` });
  await browser.close();
  console.log("saved Migood Home screenshots to " + out);
})();
