// E2E: register -> cabinet -> logout -> login, against running backend (:8000) and frontend (:3000).
const { chromium } = require("playwright");
(async () => {
  const base = process.env.E2E_BASE_URL ?? "http://localhost:3000";
  const email = `e2e${Date.now()}@example.com`;
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto(`${base}/register`);
  await page.getByLabel("Имя или название").fill("E2E Продавец");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Пароль").fill("E2e-strong-pass-1");
  await page.getByText("Я хочу продавать").click();
  await page.getByText("Принимаю пользовательское").click();
  await page.getByRole("button", { name: "Создать аккаунт" }).click();
  await page.waitForURL("**/account");
  await page.getByText("Подтвердите email").waitFor();
  await page.getByRole("button", { name: "Мои каналы" }).waitFor(); // seller tabs visible
  await page.goto(`${base}/purchases`);
  await page.getByText("Покупок пока нет").waitFor();
  await page.goto(`${base}/account`);
  await page.getByRole("button", { name: "Выйти" }).click();
  await page.waitForURL(base + "/");
  await page.goto(`${base}/login`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Пароль").fill("wrong-password-x");
  await page.getByRole("button", { name: "Войти" }).click();
  await page.getByText("Неверный email или пароль").waitFor();
  await page.getByLabel("Пароль").fill("E2e-strong-pass-1");
  await page.getByRole("button", { name: "Войти" }).click();
  await page.waitForURL("**/account");
  await page.getByRole("button", { name: /E2E Продавец/ }).click();
  await page.getByRole("menuitem", { name: "Мой профиль" }).click();
  await page.waitForURL("**/sellers/*");
  await page.getByText("Редактировать профиль").waitFor();
  await page.getByText("Добавьте первый канал").waitFor();
  await browser.close();
  console.log("E2E AUTH OK");
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
