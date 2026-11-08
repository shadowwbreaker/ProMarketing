// E2E: seller adds a YouTube account via the wizard (dev fake provider), sees statistics, refresh limit, history.
// Requires backend :8000, celery worker, frontend :3000.
const { chromium } = require("playwright");
(async () => {
  const base = process.env.E2E_BASE_URL ?? "http://localhost:3000";
  const browser = await chromium.launch();
  const page = await browser.newPage();
  const email = `seller${Date.now()}@example.com`;
  await page.goto(`${base}/register`);
  await page.getByLabel("Имя или название").fill("Продавец");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Пароль").fill("E2e-strong-pass-1");
  await page.getByText("Я хочу продавать").click();
  await page.getByText("Принимаю пользовательское").click();
  await page.getByRole("button", { name: "Создать аккаунт" }).click();
  await page.waitForURL("**/account");
  // Wizard: platform -> link -> statistics -> offer -> create
  await page.goto(`${base}/account/accounts/new`);
  await page.getByLabel("Платформа").selectOption("youtube");
  if (!(await page.locator("option[value=instagram]").evaluate((o) => o.disabled))) throw new Error("instagram must be unavailable");
  await page.getByRole("button", { name: "Далее" }).click();
  await page.getByLabel("Ссылка на страницу Shorts канала").fill(`https://www.youtube.com/@e2e${Date.now()}`);
  await page.getByRole("button", { name: "Далее" }).click();
  await page.getByText("Нужна ссылка на страницу Shorts").waitFor(); // /shorts is required
  await page.getByLabel("Ссылка на страницу Shorts канала").fill(`https://www.youtube.com/@e2e${Date.now()}/shorts`);
  await page.getByRole("button", { name: "Далее" }).click();
  await page.getByText("(15 видео)").waitFor({ timeout: 20000 });
  await page.getByText("подписчиков").waitFor();
  await page.getByRole("button", { name: "Далее" }).click();
  await page.getByLabel("Название объявления").fill("Реклама в моих Shorts");
  await page.getByLabel("Условия работы").fill("Интеграция до 30 секунд, одна правка");
  await page.getByLabel("Цена, ₽").fill("15000");
  await page.getByRole("button", { name: "Создать" }).click();
  await page.waitForURL("**/account/accounts/*");
  await page.getByText("подтвердите email").waitFor(); // unverified seller: offer saved, not listed
  await page.getByText("Интеграция внутри ролика · 15").waitFor();
  await page.getByText("Подтверждено").first().waitFor();
  await page.getByText("История статистики").waitFor();
  const disabled = await page.getByRole("button", { name: "Обновить статистику" }).isDisabled();
  if (!disabled) throw new Error("refresh should be limited right after first fetch");
  await page.getByText("Доступно с").waitFor();
  // D-020: ownership by a code in the channel description (fake provider accepts it)
  await page.getByRole("button", { name: "Получить код" }).click();
  await page.getByText(/PM-[0-9A-F]{6}/).waitFor();
  await page.getByRole("button", { name: "Проверить" }).click();
  await page.getByText("владение подтверждено").first().waitFor();
  await page.goto(`${base}/account/networks`);
  await page.getByLabel("Название").fill("Моя сетка");
  await page.getByRole("button", { name: "Создать" }).click();
  await page.getByText("Моя сетка").click();
  await page.waitForURL("**/account/networks/*");
  await page.getByRole("button", { name: "Добавить", exact: true }).click();
  await page.getByRole("button", { name: "Убрать" }).waitFor();
  await browser.close();
  console.log("E2E ACCOUNTS OK");
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
