// Renders the stage-2 desktop design previews (docs/design/desktop-mockup.html):
//   node tools/desktop-preview.js OUTDIR
const path = require("path");
const { chromium } = require(process.env.PLAYWRIGHT || "playwright");
const out = process.argv[2] || "docs/screenshots";
const page = path.resolve(__dirname, "../docs/design/desktop-mockup.html");
const fonts = path.resolve(__dirname, "../assets/fonts");
(async () => {
  const browser = await chromium.launch({ args: ["--allow-file-access-from-files"] });
  const tab = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  for (const style of ["dock", "taskbar", "rail"]) {
    for (const open of ["none", "launcher", "quick"]) {
      await tab.goto(`file://${page}?style=${style}&open=${open}`);
      await tab.addStyleTag({ content: ["Regular:400", "SemiBold:600", "Bold:700", "ExtraBold:800"].map((w) => {
        const [n, weight] = w.split(":");
        return `@font-face{font-family:Nunito;font-weight:${weight};src:url("file://${fonts}/Nunito-${n}.ttf")}`;
      }).join("") });
      await tab.waitForTimeout(500);
      await tab.screenshot({ path: `${out}/desktop-${style}-${open}.png` });
    }
  }
  await browser.close();
  console.log("saved desktop previews to " + out);
})();
