// Run against a local Docker stack seeded with demo users.
const { chromium } = require("playwright");

const base = process.env.E2E_BASE_URL ?? "http://localhost:3000";
async function login(page, email, staff = false) {
  await page.goto(base + (staff ? "/support/login" : "/login"));
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Пароль", { exact: true }).fill("Demo-password-1");
  await page.getByRole("button", { name: "Войти", exact: true }).click();
}

(async () => {
  const browser = await chromium.launch({ channel: process.env.E2E_BROWSER_CHANNEL });
  try {
    const buyerContext = await browser.newContext();
    const buyer = await buyerContext.newPage();
    await buyer.goto(base + "/support");
    await buyer.getByRole("link", { name: "Войти, чтобы отправить обращение" }).waitFor();
    if (await buyer.getByText("Вход для сотрудников", { exact: true }).count()) {
      throw new Error("The public help page links to staff login");
    }
    await login(buyer, "demo-buyer@example.com", true);
    await buyer.getByText("Вход доступен сотрудникам технической поддержки и администраторам").waitFor();
    await login(buyer, "demo-buyer@example.com");
    await buyer.waitForURL("**/account");
    await buyer.getByRole("button", { name: /Демо-покупатель/ }).hover();
    await buyer.getByRole("menuitem", { name: "Обращения в поддержку" }).click();
    await buyer.getByRole("link", { name: "Создать обращение" }).click();

    await buyer.goto(base + "/catalog?q=" + encodeURIComponent("Кухня"));
    await buyer.getByText("Кухня за 60 секунд", { exact: true }).click();
    await buyer.getByRole("link", { name: /Купить за/ }).click();
    await buyer.getByLabel("Бренд или продукт").fill("Пекарня");
    await buyer.getByLabel("Техническое задание").fill("Показать выпечку и название пекарни.");
    await buyer.getByRole("button", { name: /Создать заказ/ }).click();
    await buyer.waitForURL(/\/orders\/[0-9a-f-]{36}$/);
    const orderId = new URL(buyer.url()).pathname.split("/").pop();
    const number = orderId.slice(0, 8);
    await buyer.getByRole("button", { name: "Перейти к оплате" }).click();
    await buyer.getByRole("button", { name: "Оплатить (тест)" }).click();
    await buyer.getByText("Ждёт принятия продавцом").first().waitFor();
    const buyerChat = await buyer.context().newPage();
    await buyerChat.goto(base + "/orders/" + orderId);

    await buyer.goto(base + "/support");
    await buyer.getByRole("combobox", { name: /Тема/ }).selectOption("payment");
    await buyer.getByLabel("Вопрос", { exact: true }).fill("Прошу уточнить условия именно этого заказа.");
    await buyer.getByLabel("Номер заказа").fill("#" + number);
    await buyer.getByRole("button", { name: "Отправить", exact: true }).click();
    await buyer.waitForURL(/\/support\/tickets\/[0-9a-f-]{36}$/);
    const ticketId = new URL(buyer.url()).pathname.split("/").pop();

    const staff = await browser.newPage();
    await login(staff, "demo-support@example.com", true);
    await staff.waitForURL("**/staff/tickets");
    await staff.getByRole("combobox", { name: /Категория/ }).selectOption("other");
    const ticketLink = staff.locator('a[href="/staff/tickets/' + ticketId + '"]');
    await ticketLink.click();
    await staff.getByRole("button", { name: "Взять в работу" }).click();
    await staff.getByLabel("Сообщение", { exact: true }).waitFor();
    await staff.getByRole("link", { name: "К запросам" }).click();
    await staff.getByRole("button", { name: "Запросы", exact: true }).waitFor();
    await ticketLink.waitFor({ state: "hidden" });
    await staff.getByRole("button", { name: "Мои запросы" }).click();
    await ticketLink.click();

    const reply = "Уточняю условия заказа у исполнителя.";
    await staff.getByLabel("Сообщение", { exact: true }).fill(reply);
    await staff.getByRole("button", { name: "Отправить", exact: true }).click();
    await buyer.getByText(reply, { exact: true }).waitFor();

    await staff.getByRole("link", { name: "К запросам" }).click();
    await staff.getByRole("link", { name: "Найти заказ" }).click();
    const search = staff.getByLabel("Номер заказа или email, Enter");
    await search.fill("#" + number);
    await search.press("Enter");
    await staff.getByRole("link", { name: "#" + number, exact: true }).click();
    const staffChat = staff.getByRole("log", { name: "Чат заказа" });
    await staffChat.getByText("Техническое задание к заказу").waitFor();
    const message = "Поддержка уточнит сроки размещения заказа #" + number + ".";
    await staff.getByLabel("Сообщение", { exact: true }).fill(message);
    await staff.getByRole("button", { name: "Отправить", exact: true }).click();
    await buyerChat.getByText(message, { exact: true }).waitFor();
    await staff.goto(base + "/staff/tickets/" + ticketId);
    await staff.getByRole("link", { name: /Открыть заказ/ }).click();
    await staff.getByRole("button", { name: "Закрыть запрос" }).click();
    await buyer.getByText("Закрыто", { exact: true }).waitFor();

    const owner = await browser.newPage();
    await login(owner, "demo-owner@example.com", true);
    await owner.waitForURL("**/staff/tickets");
    await owner.getByRole("link", { name: "Роли сотрудников" }).click();
    await owner.getByLabel("Email пользователя").fill("demo-seller2@example.com");
    await owner.getByRole("button", { name: "Сохранить" }).click();
    await owner.getByText("Права для demo-seller2@example.com обновлены.", { exact: true }).waitFor();
    await owner.getByLabel("Действие").selectOption("revoke");
    await owner.getByRole("button", { name: "Сохранить" }).click();
    await owner.getByText("Права для demo-seller2@example.com обновлены.", { exact: true }).waitFor();
    console.log("E2E SUPPORT OK");
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
