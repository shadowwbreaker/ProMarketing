// E2E beta (D-025): needs the backend started with BETA_MODE=true. "Купить" → payment confirmed at once → chat shows it.
const { chromium } = require("playwright");
(async () => {
  const base = process.env.E2E_BASE_URL ?? "http://localhost:3000";
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto(`${base}/login`);
  await page.getByText("Бета-версия ProMarketing").waitFor();
  await page.getByLabel("Email").fill("demo-buyer@example.com");
  await page.getByLabel("Пароль").fill("Demo-password-1");
  await page.getByRole("button", { name: "Войти" }).click();
  await page.waitForURL("**/account*");
  await page.goto(`${base}/catalog`);
  await page.getByRole("link", { name: "Мемы про офис" }).click();
  await page.getByRole("link", { name: /Купить за/ }).click();
  await page.getByLabel("Бренд или продукт").fill("Бета-тест");
  await page.getByLabel("Техническое задание").fill("Проверка бета-оплаты");
  await page.getByRole("button", { name: /Создать заказ/ }).click();
  await page.waitForURL(/\/orders\/[0-9a-f-]{36}\/paid$/);
  await page.getByText("Оплата подтверждена").waitFor();
  await page.getByText("оплата имитирована").waitFor();
  await page.getByRole("link", { name: "Вернуться к заказу и чату" }).click();
  await page.getByText("Ждёт принятия продавцом").first().waitFor();
  await page.getByText("Оплата получена платёжным провайдером").first().waitFor();
  await browser.close();
  console.log("E2E BETA OK");
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
