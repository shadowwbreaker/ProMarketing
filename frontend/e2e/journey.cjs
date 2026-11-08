// E2E "like a person": a visitor becomes a buyer, talks to a seller, buys, the seller delivers, the buyer confirms.
// Measures how long each step takes for the user and fails on any browser error. Demo data required.
const { chromium } = require("playwright");
const base = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const steps = [];
const errors = [];

async function step(name, fn) {
  const t = Date.now();
  await fn();
  steps.push([name, Date.now() - t]);
}
function watch(page, who) {
  page.on("pageerror", (e) => errors.push(`${who}: ${e.message}`));
  page.on("console", (m) => m.type() === "error" && !/40[1349]|429/.test(m.text()) && errors.push(`${who}: ${m.text()}`));
}
async function login(page, email) {
  await page.goto(`${base}/login`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Пароль").fill("Demo-password-1");
  await page.getByRole("button", { name: "Войти" }).click();
  await page.waitForURL("**/account*");
}

(async () => {
  const browser = await chromium.launch();
  const buyer = await (await browser.newContext({ viewport: { width: 1366, height: 860 } })).newPage();
  watch(buyer, "buyer");
  const text = `Добрый день! Есть окно на этой неделе? ${Date.now()}`;

  await step("Гость открывает главную", async () => {
    await buyer.goto(base);
    await buyer.getByText("Как проходит сделка").waitFor();
  });
  await step("Переходит в каталог", async () => {
    await buyer.getByRole("link", { name: /Найти канал/ }).click();
    await buyer.getByText("Кухня за 60 секунд").waitFor();
  });
  await step("Фильтрует: только TikTok", async () => {
    await buyer.getByRole("button", { name: /Фильтры/ }).click();
    const sheet = buyer.getByRole("dialog", { name: "Фильтры каталога" });
    await sheet.getByLabel("Платформа").selectOption("tiktok");
    await sheet.getByRole("button", { name: "Применить" }).click();
    await buyer.waitForURL(/platform=tiktok/);
    await sheet.waitFor({ state: "hidden" });
  });
  await step("Открывает объявление", async () => {
    await buyer.getByRole("link", { name: "Кухня за 60 секунд" }).click();
    await buyer.getByText("Оформление заказа").waitFor();
    await buyer.getByText("Войдите").first().waitFor(); // a guest is asked to sign in before writing
  });
  const offerUrl = buyer.url();
  await step("Входит в аккаунт", async () => login(buyer, "demo-buyer@example.com"));
  await step("Пишет продавцу до оплаты", async () => {
    await buyer.goto(offerUrl);
    await buyer.getByLabel(/Сообщение для/).fill(text);
    await buyer.getByRole("button", { name: "Отправить" }).click();
    await buyer.getByText(text).waitFor();
  });

  const seller = await (await browser.newContext({ viewport: { width: 1366, height: 860 } })).newPage();
  watch(seller, "seller");
  await step("Продавец входит и видит красную точку у «Сообщений»", async () => {
    await login(seller, "demo-seller1@example.com");
    await seller.getByText(/непрочитанных: [1-9]/).waitFor({ state: "attached", timeout: 35000 });
  });
  await step("Продавец отвечает в «Сообщениях»", async () => {
    await seller.getByRole("link", { name: /Сообщения/ }).click();
    await seller.getByText(text).first().click();
    await seller.getByLabel(/Сообщение для/).fill("Да, могу снять в четверг.");
    await seller.getByRole("button", { name: "Отправить" }).click();
    await seller.getByText("Да, могу снять в четверг.").waitFor();
  });
  await step("Покупатель оформляет и оплачивает заказ", async () => {
    await buyer.goto(offerUrl);
    await buyer.getByRole("link", { name: /Купить за/ }).click();
    await buyer.getByLabel("Бренд или продукт").fill("Пекарня «Утро»");
    await buyer.getByLabel("Техническое задание").fill("Показать круассаны, ссылка в описании");
    await buyer.getByRole("button", { name: /Создать заказ/ }).click();
    await buyer.waitForURL(/\/orders\/[0-9a-f-]{36}$/);
    await buyer.getByRole("button", { name: "Перейти к оплате" }).click();
    await buyer.getByRole("button", { name: "Оплатить (тест)" }).click();
    await buyer.getByText("Ждёт принятия продавцом").first().waitFor();
  });
  const orderUrl = buyer.url().split("?")[0];
  await step("Продавец принимает заказ и публикует ролик", async () => {
    await seller.goto(orderUrl);
    await seller.getByRole("button", { name: "Принять заказ" }).click();
    await seller.getByLabel("Ссылка на видео").fill("https://www.tiktok.com/@demo_0/video/9001");
    await seller.getByRole("button", { name: "Отправить ссылку на публикацию" }).click();
    await seller.getByText("Ждёт подтверждения покупателем").first().waitFor();
  });
  await step("Покупатель подтверждает и оставляет отзыв", async () => {
    await buyer.goto(orderUrl);
    await buyer.getByRole("button", { name: "Подтвердить выполнение" }).click();
    await buyer.getByText("Выполнен").first().waitFor();
    await buyer.getByLabel("Текст отзыва").fill("Быстро и аккуратно");
    await buyer.getByRole("button", { name: "Оставить отзыв" }).click();
    await buyer.getByText("Быстро и аккуратно").waitFor();
  });
  await step("Покупатель видит заказ в «Моих покупках»", async () => {
    await buyer.getByRole("link", { name: "Покупки" }).click();
    await buyer.getByText("Мои покупки").waitFor();
    await buyer.getByText("Выполнен").first().waitFor();
  });
  await step("Продавец открывает «Безопасность»", async () => {
    await seller.goto(`${base}/account?tab=security`);
    await seller.getByText("Сменить пароль").waitFor();
    await seller.getByText(/двухфакторн/i).first().waitFor();
  });

  await browser.close();
  console.log("Шаг пользователя".padEnd(58) + "мс");
  for (const [n, ms] of steps) console.log(n.padEnd(58) + String(ms).padStart(6));
  if (errors.length) throw new Error("browser errors:\n" + errors.join("\n"));
  const slow = steps.filter(([, ms]) => ms > 15000);
  if (slow.length) throw new Error("too slow: " + slow.map(([n]) => n).join(", "));
  console.log("E2E JOURNEY OK");
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
