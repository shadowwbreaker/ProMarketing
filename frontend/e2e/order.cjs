// E2E: full deal on demo data (python manage.py seed_demo). Buyer and seller in separate browser contexts.
const { chromium } = require("playwright");
async function login(ctx, base, email) {
  const p = await ctx.newPage();
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
  const buyer = await login(await browser.newContext(), base, "demo-buyer@example.com");
  await buyer.goto(`${base}/catalog?q=${encodeURIComponent("Кухня")}`);
  await buyer.getByText("Кухня за 60 секунд").click();
  await buyer.waitForURL("**/catalog/*");
  await buyer.getByRole("link", { name: "Заказать" }).first().click();
  await buyer.waitForURL("**/orders/new*");
  await buyer.getByLabel("Бренд или продукт").fill("Кофейня Зерно");
  await buyer.getByLabel("Техническое задание").fill("Показать латте, упомянуть скидку 20%");
  await buyer.getByRole("button", { name: /Создать заказ/ }).click();
  await buyer.waitForURL(/\/orders\/[0-9a-f-]{36}$/);
  const orderUrl = buyer.url();
  await buyer.getByText("Ожидает оплаты").first().waitFor();
  await buyer.getByRole("button", { name: "Перейти к оплате" }).click();
  await buyer.waitForURL("**mock_payment=*");
  await buyer.getByRole("button", { name: "Оплатить (тест)" }).click();
  await buyer.getByText("Ждёт принятия продавцом").first().waitFor();

  const seller = await login(await browser.newContext(), base, "demo-seller1@example.com");
  await seller.goto(orderUrl);
  await seller.getByText("Оплата получена платёжным провайдером.").waitFor(); // system message in chat
  await seller.getByLabel("Сообщение").fill("Здравствуйте! Сниму завтра.");
  await seller.getByRole("button", { name: "Отправить", exact: true }).click();
  await buyer.getByText("Здравствуйте! Сниму завтра.").waitFor({ timeout: 10000 }); // buyer sees it via polling
  await buyer.getByLabel("Сообщение").fill("Напишите мне в телеграм");
  await buyer.getByRole("button", { name: "Отправить", exact: true }).click();
  await buyer.getByText(/Договариваться и платить вне платформы запрещено/).waitFor();
  await seller.getByRole("button", { name: "Принять заказ" }).click();
  await seller.getByText("Опубликовать до").waitFor();
  await seller.getByLabel("Ссылка на видео").fill("https://www.tiktok.com/@demo_0/video/777");
  await seller.getByRole("button", { name: "Отправить ссылку на публикацию" }).click();
  await seller.getByText("Ждёт подтверждения покупателем").first().waitFor();

  await buyer.reload();
  await buyer.getByRole("button", { name: "Подтвердить выполнение" }).click();
  await buyer.getByText("Выполнен").first().waitFor();
  await buyer.getByLabel("Текст отзыва").fill("Всё по ТЗ и вовремя");
  await buyer.getByRole("button", { name: "Оставить отзыв" }).click();
  await buyer.getByText("Всё по ТЗ и вовремя").waitFor();

  await seller.goto(`${base}/account`);
  await seller.getByRole("button", { name: "Выплаты" }).click();
  await seller.getByText("Ожидание 48 ч").first().waitFor();
  await seller.getByRole("link", { name: /Уведомления: [1-9]/ }).waitFor();
  await browser.close();
  console.log("E2E ORDER OK");
})().catch((e) => { console.error(e); process.exit(1); });
