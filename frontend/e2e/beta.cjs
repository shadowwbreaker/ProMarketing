// Local beta with seed_demo and BETA_MODE=true. Buyer and seller use separate browser sessions.
const assert = require("node:assert/strict");
const { chromium } = require("playwright");

(async () => {
  const base = process.env.E2E_BASE_URL ?? "http://localhost:3000";
  const browser = await chromium.launch({ channel: process.env.E2E_BROWSER_CHANNEL });
  const token = Date.now();
  try {
    const buyer = await browser.newPage();
    const seller = await browser.newPage();
    await seller.addInitScript(() => {
      window.pmPlayedNotes = 0;
      const start = OscillatorNode.prototype.start;
      OscillatorNode.prototype.start = function (...args) {
        if (this.context.state === "running") window.pmPlayedNotes++;
        return start.apply(this, args);
      };
    });
    async function login(page, email) {
      await Promise.all([
        page.waitForResponse((response) => new URL(response.url()).pathname === "/api/v1/auth/session"),
        page.goto(`${base}/login`),
      ]);
      await page.getByLabel("Email").fill(email);
      await page.getByLabel("Пароль").fill("Demo-password-1");
      await page.getByRole("button", { name: "Войти", exact: true }).click();
      await page.waitForURL("**/account*");
    }
    await login(seller, "demo-seller1@example.com");
    await seller.goto(`${base}/messages`);
    await seller.getByRole("button", { name: /Демо-продавец 1/ }).click();
    await seller.getByRole("menuitemcheckbox", { name: /Звук сообщений: выкл/ }).click();

    await login(buyer, "demo-buyer@example.com");
    await buyer.goto(`${base}/catalog`);
    await buyer.getByRole("link", { name: "Мемы про офис" }).click();
    const context = buyer.getByLabel("К заказу");
    if (await context.count()) await context.selectOption("");
    const question = `Личное сообщение ${token}`;
    await buyer.getByLabel("Сообщение", { exact: true }).fill(question);
    await buyer.getByRole("button", { name: "Отправить", exact: true }).click();
    const row = seller.locator('a[href^="/messages?u="]').filter({ hasText: "Демо-покупатель" });
    await row.getByText(question).waitFor({ timeout: 10000 });
    await seller.waitForFunction(() => window.pmPlayedNotes >= 1);
    await row.click();
    const log = seller.getByRole("log", { name: "Переписка" });
    await log.getByText(question).waitFor();

    await buyer.getByRole("link", { name: /Купить за/ }).first().click();
    await buyer.getByText("Оплата тестовая. Деньги не списываются.").waitFor();
    const brief = `ТЗ к заказу ${token}`;
    await buyer.getByLabel("Бренд или продукт").fill("Бета-тест");
    await buyer.getByLabel("Техническое задание").fill(brief);
    await buyer.getByRole("button", { name: /Создать заказ/ }).click();
    await buyer.waitForURL(/\/orders\/[0-9a-f-]{36}\/paid$/);
    const id = new URL(buyer.url()).pathname.split("/")[2];
    await buyer.getByRole("link", { name: "Открыть переписку" }).click();
    await log.getByText(brief, { exact: true }).waitFor({ timeout: 10000 });
    await seller.waitForFunction(() => window.pmPlayedNotes >= 3);
    assert.equal(await row.count(), 1);
    assert.equal(await log.getByText(/Заказ создан\. Условия|Оплата получена платёжным провайдером/).count(), 0);
    assert.equal(await log.getByText(question).count(), 1);

    await seller.getByRole("link", { name: "Детали заказа" }).click();
    await seller.waitForURL(`**/orders/${id}`);
    await seller.getByRole("button", { name: "Принять заказ" }).click();
    const orderLog = seller.getByRole("log", { name: "Чат заказа" });
    await orderLog.getByText(question).waitFor();
    await orderLog.getByText(brief).waitFor();
    await orderLog.getByText("Продавец принял заказ.").waitFor();
    const buyerLog = buyer.getByRole("log", { name: "Чат заказа" });
    await buyerLog.getByText("Продавец принял заказ.").waitFor({ timeout: 10000 });

    const reply = `Ответ продавца ${token}`;
    await seller.getByLabel("Сообщение", { exact: true }).fill(reply);
    await seller.getByRole("button", { name: "Отправить", exact: true }).click();
    await buyerLog.getByText(reply).waitFor({ timeout: 10000 });
    await seller.setViewportSize({ width: 360, height: 780 });
    await seller.getByRole("link", { name: "В сообщениях" }).click();
    await seller.getByRole("log").getByText(reply).waitFor();
    assert.ok(await seller.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    console.log("E2E BETA OK: merged dialog, live delivery, message and order sounds, acceptance, mobile");
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
