// E2E: FunPay-style public profile + "write to the seller before paying" (direct messages).
const { chromium } = require("playwright");
(async () => {
  const base = process.env.E2E_BASE_URL ?? "http://localhost:3000";
  const browser = await chromium.launch();
  const login = async (email) => {
    const p = await (await browser.newContext()).newPage();
    await p.goto(`${base}/login`);
    await p.getByLabel("Email").fill(email);
    await p.getByLabel("Пароль").fill("Demo-password-1");
    await p.getByRole("button", { name: "Войти" }).click();
    await p.waitForURL("**/account*");
    return p;
  };
  const buyer = await login("demo-buyer@example.com");
  await buyer.goto(`${base}/catalog`);
  await buyer.getByRole("link", { name: /Демо-продавец/ }).first().click();
  await buyer.waitForURL("**/sellers/*");
  const sellerUrl = buyer.url();
  for (const t of ["Дата регистрации", "Рейтинг продавца", "Предложения"]) await buyer.getByText(t).first().waitFor();
  const text = `Здравствуйте! ${Date.now()}`;
  await buyer.getByLabel("Сообщение продавцу").fill(text);
  await buyer.getByRole("button", { name: "Отправить" }).click();
  await buyer.getByText(text).waitFor();
  // the seller sees the thread in "Сообщения"
  const sellerName = await buyer.locator("h1").innerText();
  const n = (sellerName.match(/(\d+)/) ?? ["", "1"])[1];
  const seller = await login(`demo-seller${n}@example.com`);
  await seller.goto(`${base}/account?tab=messages`);
  await seller.getByText(text).first().waitFor();
  // profile photo upload (re-encoded by the server) shows up in the header
  const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGP8z8DAwMDAxMDAwMDAAAANHQEDK+mmyAAAAABJRU5ErkJggg==", "base64");
  await seller.goto(`${base}/account?tab=profile`);
  await seller.getByLabel("Фото профиля").setInputFiles({ name: "me.png", mimeType: "image/png", buffer: png });
  await seller.getByText("Фото обновлено").waitFor();
  await seller.locator("header img").waitFor();
  await seller.goto(sellerUrl);
  await browser.close();
  console.log("E2E PROFILE OK");
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
