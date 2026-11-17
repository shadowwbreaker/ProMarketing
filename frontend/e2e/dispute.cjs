// E2E: complaint → support referral → arbitration claim → partial refund (demo data).
const { chromium } = require("playwright");
async function login(browser, base, email) {
  const p = await (await browser.newContext()).newPage();
  await p.goto(`${base}/login`);
  await p.getByLabel("Email").fill(email);
  await p.getByLabel("Пароль").fill("Demo-password-1");
  await p.getByRole("button", { name: "Войти" }).click();
  await p.waitForURL("**/account");
  return p;
}
(async () => {
  const base = process.env.E2E_BASE_URL ?? "http://localhost:3000";
  const browser = await chromium.launch({ channel: process.env.E2E_BROWSER_CHANNEL });
  const buyer = await login(browser, base, "demo-buyer@example.com");
  await buyer.goto(`${base}/catalog?q=${encodeURIComponent("Утренний")}`);
  await buyer.getByText("Утренний фитнес").click();
  await buyer.getByRole("link", { name: /Купить за/ }).click();
  await buyer.getByLabel("Бренд или продукт").fill("Спортпит");
  await buyer.getByLabel("Техническое задание").fill("Показать протеин в кадре 10 секунд");
  await buyer.getByRole("button", { name: /Создать заказ/ }).click();
  await buyer.waitForURL(/\/orders\/[0-9a-f-]{36}$/);
  const orderUrl = buyer.url();
  await buyer.getByRole("button", { name: "Перейти к оплате" }).click();
  await buyer.getByRole("button", { name: "Оплатить (тест)" }).click();
  await buyer.getByText("Ждёт принятия продавцом").first().waitFor();

  const seller = await login(browser, base, "demo-seller1@example.com");
  await seller.goto(orderUrl);
  await seller.getByRole("button", { name: "Принять заказ" }).click();
  await seller.getByLabel("Ссылка на видео").fill("https://www.tiktok.com/@demo_2/video/555");
  await seller.getByRole("button", { name: "Отправить ссылку на публикацию" }).click();
  await seller.getByText("Ждёт подтверждения покупателем").first().waitFor();

  await buyer.reload();
  await buyer.getByRole("link", { name: "Пожаловаться", exact: true }).click();
  await buyer.waitForURL("**/support?order=*");
  await buyer.getByRole("combobox", { name: /Причина/ }).selectOption({ label: "Реклама не соответствует техническому заданию" });
  await buyer.getByLabel("Опишите проблему").fill("Протеин был в кадре 2 секунды вместо 10, как в ТЗ");
  await buyer.getByRole("button", { name: "Отправить жалобу" }).click();
  await buyer.getByText("Ждём ответа продавца").waitFor();

  await seller.reload();
  await seller.getByLabel("Ответ по жалобе").fill("Сняли 6 секунд, готов частично вернуть");
  await seller.getByRole("button", { name: "Отправить ответ" }).click();
  await seller.getByText("На рассмотрении").first().waitFor();

  const staff = await login(browser, base, "demo-support@example.com");
  await staff.goto(base + "/staff/tickets");
  await staff.getByRole("combobox", { name: /Категория/ }).selectOption("complaint");
  const orderNumber = orderUrl.split("/orders/")[1].slice(0, 8);
  const requestLink = staff.getByRole("link", { name: new RegExp("Реклама не соответствует.*" + orderNumber) });
  await requestLink.click();
  await staff.getByText("Протеин был в кадре 2 секунды вместо 10, как в ТЗ").waitFor();
  await staff.getByRole("button", { name: "Взять в работу" }).click();
  await staff.getByLabel("Сообщение", { exact: true }).waitFor();
  await staff.getByRole("link", { name: /Открыть заказ/ }).click();
  await staff.getByRole("log", { name: "Чат заказа" }).waitFor();
  await staff.getByRole("button", { name: "Передать арбитражу" }).click();
  await staff.waitForURL("**/staff/tickets");
  await staff.getByRole("button", { name: "Мои запросы" }).click();
  await requestLink.waitFor({ state: "hidden" });

  const arbiter = await login(browser, base, "demo-arbitrator@example.com");
  await arbiter.goto(base + "/staff/orders");
  await arbiter.getByRole("button", { name: new RegExp("Заказ #" + orderNumber) }).click();
  await arbiter.waitForURL("**/staff/orders/*");
  await arbiter.getByText("Переписка сторон").waitFor();
  await arbiter.getByRole("link", { name: "К заказам" }).click();
  await arbiter.getByRole("button", { name: "Мои заказы" }).click();
  await arbiter.getByRole("link", { name: new RegExp("Заказ #" + orderNumber) }).click();
  const update = "Дополнение к жалобе: исходное техническое задание остаётся без изменений.";
  await buyer.getByLabel("Сообщение", { exact: true }).fill(update);
  await buyer.getByRole("button", { name: "Отправить", exact: true }).click();
  await arbiter.bringToFront();
  await arbiter.locator("li").filter({ hasText: update }).waitFor({ timeout: 15000 });
  await arbiter.locator('select[name="decision"]').selectOption("partial_refund");
  await arbiter.getByLabel("Сумма частичного возврата, ₽").fill("3000");
  await arbiter.getByLabel("Комментарий (обязательно)").fill("ТЗ выполнено частично, по переписке продавец согласен");
  await arbiter.getByRole("button", { name: "Вернуть деньги" }).click();
  await arbiter.getByText(/Решён/).first().waitFor();

  await buyer.reload();
  await buyer.getByText("Частичный возврат · 3").waitFor();
  await buyer.getByText("Частично возвращён").first().waitFor();
  await browser.close();
  console.log("E2E DISPUTE OK");
})().catch((e) => { console.error(e); process.exit(1); });
