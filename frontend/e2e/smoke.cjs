(async () => {
// Smoke e2e: frontend talks to a running backend. Requires: backend on :8000, `npm run start` on :3000.
// Locally: npm i -D playwright && npx playwright install chromium && node e2e/smoke.mjs
const { chromium } = require("playwright");

const base = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const browser = await chromium.launch();
const page = await browser.newPage();
const errors = [];
// 404s for routes of later phases (catalog, login) are expected until those phases are built
page.on("console", (m) => m.type() === "error" && !m.text().includes("404") && errors.push(m.text()));
await page.goto(`${base}/status`);
await page.getByText("работает").waitFor({ timeout: 15000 });
const text = await page.locator("main").innerText();
console.log(text);
await page.goto(base);
await page.getByRole("heading", { level: 1 }).waitFor();
await page.setViewportSize({ width: 375, height: 800 });
const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
await browser.close();
if (overflow) throw new Error("horizontal overflow on mobile");
if (errors.length) throw new Error("console errors: " + errors.join("; "));
console.log("E2E SMOKE OK");

})().catch((e) => { console.error(e); process.exit(1); });
