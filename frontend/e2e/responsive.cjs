// E2E: key pages render without horizontal scroll or runtime errors at phone (375) and desktop (1280) widths.
const { chromium } = require("playwright");
const PUBLIC = ["/", "/catalog", "/catalog?kind=networks", "/login", "/register", "/forgot-password", "/support", "/compare", "/status"];
const PRIVATE = ["/account", "/account?tab=analytics", "/messages", "/favorites", "/account/accounts/new", "/account/networks", "/orders/new?offer=x", "/staff", "/staff/disputes", "/staff/users", "/staff/accounts", "/staff/orders", "/staff/audit", "/staff/fraud", "/staff/reviews", "/staff/tickets"];
(async () => {
  const base = process.env.E2E_BASE_URL ?? "http://localhost:3000";
  const browser = await chromium.launch();
  const problems = [];
  for (const width of [375, 1280]) {
    const ctx = await browser.newContext({ viewport: { width, height: 900 } });
    const page = await ctx.newPage();
    const errs = [];
    page.on("pageerror", (e) => errs.push(e.message));
    const check = async (path) => {
      errs.length = 0;
      await page.goto(base + path);
      await page.waitForLoadState("networkidle").catch(() => {});
      await page.waitForTimeout(400);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (overflow > 1) problems.push(`${width}px ${path}: horizontal overflow ${overflow}px`);
      if (errs.length) problems.push(`${width}px ${path}: ${errs.join("; ")}`);
    };
    for (const p of PUBLIC) await check(p);
    await page.goto(`${base}/login`);
    await page.getByLabel("Email").fill("demo-admin@example.com");
    await page.getByLabel("Пароль").fill("Demo-password-1");
    await page.getByRole("button", { name: "Войти" }).click();
    await page.waitForURL("**/account");
    for (const p of PRIVATE) await check(p);
    const first = await page.evaluate(async (api) => {
      const r = await fetch(`${api}/api/v1/catalog/accounts`, { credentials: "include" });
      return (await r.json()).results[0]?.id;
    }, process.env.E2E_API_URL ?? "http://localhost:8000");
    if (first) await check(`/catalog/${first}`);
    await ctx.close();
  }
  await browser.close();
  if (problems.length) {
    console.error(problems.join("\n"));
    process.exit(1);
  }
  console.log("E2E RESPONSIVE OK");
})().catch((e) => { console.error(e); process.exit(1); });
