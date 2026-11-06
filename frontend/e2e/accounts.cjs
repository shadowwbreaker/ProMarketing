// E2E: seller adds a YouTube account (dev fake provider), sees statistics, refresh limit, history.
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
  await page.goto(`${base}/account/accounts/new`);
  await page.getByLabel("Ссылка на профиль").fill(`https://www.youtube.com/@e2e${Date.now()}`);
  await page.getByLabel("Название").fill("Мой канал");
  await page.getByRole("button", { name: "Добавить", exact: true }).click();
  await page.waitForURL("**/account/accounts/*");
  await page.getByText("по 15 видео").waitFor({ timeout: 20000 });
  await page.getByText("Подтверждено").first().waitFor();
  await page.getByText("История статистики").waitFor();
  const disabled = await page.getByRole("button", { name: "Обновить статистику" }).isDisabled();
  if (!disabled) throw new Error("refresh should be limited right after first fetch");
  await page.getByText("Доступно с").waitFor();
  await browser.close();
  console.log("E2E ACCOUNTS OK");
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
