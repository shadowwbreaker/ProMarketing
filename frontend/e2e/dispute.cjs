// E2E: complaint → seller reply → admin partial refund (demo data).
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
  const browser = await chromium.launch();
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
  await buyer.getByRole("button", { name: "Пожаловаться" }).click();
  await buyer.getByLabel("Причина").selectOption({ label: "Реклама не соответствует техническому заданию" });
  await buyer.getByLabel("Опишите проблему").fill("Протеин был в кадре 2 секунды вместо 10, как в ТЗ");
  await buyer.getByRole("button", { name: "Отправить жалобу" }).click();
  await buyer.getByText("Ждём ответа продавца").waitFor();

  await seller.reload();
  await seller.getByLabel("Ответ по жалобе").fill("Сняли 6 секунд, готов частично вернуть");
  await seller.getByRole("button", { name: "Отправить ответ" }).click();
  await seller.getByText("На рассмотрении").first().waitFor();

  const admin = await login(browser, base, "demo-admin@example.com");
  await admin.goto(`${base}/staff/disputes`);
  await admin.getByText("Споры").first().waitFor();
  const orderId = orderUrl.split("/orders/")[1];
  const api = process.env.E2E_API_URL ?? "http://localhost:8000";
  const disputeId = await admin.evaluate(async ([a, o]) => {
    const r = await fetch(`${a}/api/v1/orders/${o}/disputes`, { credentials: "include" });
    return (await r.json())[0].id;
  }, [api, orderId]);
  await admin.goto(`${base}/staff/disputes/${disputeId}`);
  await admin.getByText("Переписка сторон").waitFor();
  await admin.getByRole("button", { name: "Взять в работу" }).click();
  await admin.locator('select[name="decision"]').selectOption("partial_refund");
  await admin.getByLabel("Сумма частичного возврата, ₽").fill("3000");
  await admin.getByLabel("Комментарий (обязательно)").fill("ТЗ выполнено частично, по переписке продавец согласен");
  await admin.getByRole("button", { name: "Принять решение" }).click();
  await admin.getByText(/Решён/).first().waitFor();

  await buyer.reload();
  await buyer.getByText("Частичный возврат · 3").waitFor();
  await buyer.getByText("Частично возвращён").first().waitFor();
  await browser.close();
  console.log("E2E DISPUTE OK");
})().catch((e) => { console.error(e); process.exit(1); });
