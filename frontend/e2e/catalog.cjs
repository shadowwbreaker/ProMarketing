// E2E: catalog against demo data (`python manage.py seed_demo`).
const { chromium } = require("playwright");
(async () => {
  const base = process.env.E2E_BASE_URL ?? "http://localhost:3000";
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const errors = [];
  page.on("console", (m) => m.type() === "error" && !m.text().includes("404") && errors.push(m.text()));
  await page.goto(base);
  await page.getByText("Популярные предложения").waitFor();
  await page.getByRole("link", { name: /Юмор/ }).first().waitFor();
  await page.getByLabel("Поиск по каталогу").fill("Мемы");
  await page.getByRole("button", { name: "Найти" }).click();
  await page.waitForURL("**/catalog?q=*");
  await page.getByText("Мемы про офис").waitFor();
  if (await page.getByText("Кухня за 60 секунд").count()) throw new Error("search should filter");
  // combined filters: category + max price (rubles) → only cheaper humour account
  await page.goto(`${base}/catalog?category=${encodeURIComponent("Юмор")}&price_max=2000000`);
  await page.getByText("Мемы про учёбу").waitFor();
  if (await page.getByText("Мемы про офис").count()) throw new Error("price filter not applied");
  // filter sheet: opens from the top, applies, closes; active filters counted on the button
  await page.goto(`${base}/catalog`);
  await page.getByRole("button", { name: /Фильтры/ }).click();
  const sheet = page.getByRole("dialog", { name: "Фильтры каталога" });
  await sheet.waitFor({ state: "visible" });
  await sheet.getByLabel("Платформа").selectOption("youtube");
  await sheet.getByRole("button", { name: "Применить" }).click();
  await page.waitForURL(/platform=youtube/);
  await sheet.waitFor({ state: "hidden" });
  await page.getByText("Гаджеты без воды").waitFor();
  if (await page.getByText("Мемы про офис").count()) throw new Error("platform filter not applied");
  // YouTube average hidden until approval (D-016)
  await page.goto(`${base}/catalog?platform=youtube`);
  await page.getByText("Гаджеты без воды").click();
  await page.waitForURL("**/catalog/*");
  await page.getByText("скрыто до одобрения YouTube").first().waitFor();
  await page.getByRole("link", { name: "Заказать" }).first().waitFor();
  await page.getByRole("link", { name: /Демо-продавец/ }).click();
  await page.waitForURL("**/sellers/*");
  await page.getByText("выполнено заказов").waitFor();
  await page.goto(`${base}/catalog?kind=networks`);
  await page.getByText("Сетка юмора").click();
  await page.getByText("Заказать всю сетку").waitFor();
  await page.setViewportSize({ width: 375, height: 800 });
  await page.goto(`${base}/catalog`);
  await page.getByText("Мемы про офис").waitFor();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  await browser.close();
  if (overflow) throw new Error("horizontal overflow on mobile");
  if (errors.length) throw new Error(errors.join("; "));
  console.log("E2E CATALOG OK");
})().catch((e) => { console.error(e); process.exit(1); });
