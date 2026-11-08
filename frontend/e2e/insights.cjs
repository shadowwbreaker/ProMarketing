// E2E Phase 13: favorites, viewed, compare, recommendations, analytics, referral link (demo data).
const { chromium } = require("playwright");
(async () => {
  const base = process.env.E2E_BASE_URL ?? "http://localhost:3000";
  const browser = await chromium.launch();
  const page = await (await browser.newContext()).newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(`${base}/login`);
  await page.getByLabel("Email").fill("demo-buyer@example.com");
  await page.getByLabel("Пароль").fill("Demo-password-1");
  await page.getByRole("button", { name: "Войти" }).click();
  await page.waitForURL("**/account");
  for (const name of ["Мемы про офис", "Мемы про учёбу"]) {
    await page.goto(`${base}/catalog?q=${encodeURIComponent(name)}`);
    await page.getByText(name).click();
    await page.waitForURL("**/catalog/*");
    await page.getByRole("button", { name: "Добавить к сравнению" }).click();
  }
  // Toggle until the account is in favorites (idempotent across repeated runs)
  for (let i = 0; i < 2; i++) {
    const [resp] = await Promise.all([
      page.waitForResponse((r) => r.url().endsWith("/me/favorites") && r.request().method() === "POST"),
      page.getByRole("button", { name: "♥ В избранное" }).click(),
    ]);
    if ((await resp.json()).favorite) break;
  }
  await page.goto(`${base}/compare`);
  await page.getByText("Цена за 1000 средних просмотров").waitFor();
  await page.getByRole("link", { name: "Мемы про офис" }).waitFor();
  await page.goto(`${base}/favorites`);
  await page.getByText("Мемы про учёбу").waitFor();
  await page.goto(`${base}/account`);
  await page.getByRole("button", { name: "Аналитика" }).click();
  await page.getByText("Оплачено заказов").waitFor();
  await page.getByRole("button", { name: "Пригласить" }).click();
  await page.getByText("/register?ref=").waitFor();
  await page.getByRole("button", { name: "Рекомендации" }).click();
  await page.waitForTimeout(1000);
  await browser.close();
  if (errors.length) throw new Error(errors.join("; "));
  console.log("E2E INSIGHTS OK");
})().catch((e) => { console.error(e); process.exit(1); });
