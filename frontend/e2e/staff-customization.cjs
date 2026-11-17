// Local Beta-tex: public footer, staff review access, owner role assignment and revocation.
const assert = require("node:assert/strict");
const { chromium } = require("playwright");
const base = process.env.E2E_BASE_URL ?? "http://localhost:3000";

async function login(browser, email) {
  const page = await (await browser.newContext()).newPage();
  await page.goto(base + "/support/login");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page.getByLabel("Пароль", { exact: true }).fill("Demo-password-1");
  await page.getByRole("button", { name: "Войти", exact: true }).click();
  await page.waitForURL("**/staff/tickets");
  return page;
}
async function fits(page) {
  await page.evaluate(async () => { await document.fonts.ready; });
  const size = await page.evaluate(() => ({ content: document.documentElement.scrollWidth, view: window.innerWidth }));
  assert.ok(size.content <= size.view + 1, "Horizontal overflow: " + JSON.stringify(size));
}
(async () => {
  const browser = await chromium.launch({ channel: process.env.E2E_BROWSER_CHANNEL });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(base);
    assert.equal(await page.getByText(/Комиссия 5%/).count(), 0);
    const footer = page.getByRole("contentinfo");
    const links = await footer.getByRole("link").evaluateAll((rows) => rows.map((row) => row.getAttribute("href")));
    assert.deepEqual(links, ["/catalog", "/terms", "/rules", "/privacy"]);
    for (const width of [320, 375, 1280]) {
      await page.setViewportSize({ width, height: 900 });
      await fits(page);
    }
    await footer.getByRole("link", { name: "Пользовательское соглашение" }).click();
    await page.getByRole("heading", { name: "Пользовательское соглашение", exact: true }).waitFor();
    await page.getByRole("contentinfo").getByRole("link", { name: "Политика конфиденциальности" }).click();
    await page.getByRole("heading", { name: "Политика конфиденциальности", exact: true }).waitFor();

    const support = await login(browser, "demo-support@example.com");
    support.on("pageerror", (error) => errors.push(error.message));
    await support.getByRole("link", { name: "Модерация отзывов", exact: true }).click();
    await support.getByRole("heading", { name: "Модерация отзывов" }).waitFor();
    await support.getByRole("checkbox", { name: "только с жалобами" }).uncheck();
    await support.getByRole("heading", { name: "Модерация отзывов" }).waitFor();
    await support.getByRole("link", { name: "Пользователи", exact: true }).click();
    const find = support.getByLabel("Email или имя, Enter");
    await find.fill("demo-seller2@example.com");
    await find.press("Enter");
    await support.getByRole("link", { name: "demo-seller2@example.com", exact: true }).click();
    await support.getByRole("heading", { name: /demo-seller2@example.com/ }).waitFor();
    assert.equal(await support.getByRole("heading", { name: "Управление ролями", exact: true }).count(), 0);

    const owner = await login(browser, "demo-owner@example.com");
    owner.on("pageerror", (error) => errors.push(error.message));
    await owner.getByRole("link", { name: "Роли сотрудников", exact: true }).click();
    await owner.getByRole("link", { name: "Выбрать пользователя и изменить его роли" }).click();
    const search = owner.getByLabel("Email или имя, Enter");
    await search.fill("demo-seller2@example.com");
    await search.press("Enter");
    await owner.getByRole("link", { name: "demo-seller2@example.com", exact: true }).click();
    await owner.getByRole("heading", { name: "Управление ролями", exact: true }).waitFor();
    const role = owner.getByRole("checkbox", { name: "Арбитраж", exact: true });
    assert.equal(await role.isChecked(), false);
    const comment = owner.getByLabel("Комментарий к изменению ролей (обязательно)");
    await role.check();
    await comment.fill("E2E: назначение арбитра из карточки пользователя.");
    await owner.getByRole("button", { name: "Сохранить роли" }).click();
    await owner.getByText("Роли пользователя обновлены.", { exact: true }).waitFor();
    await owner.reload();
    await role.waitFor();
    assert.equal(await role.isChecked(), true);
    try {
      for (const width of [320, 375, 640, 768, 1024, 1280]) {
        await owner.setViewportSize({ width, height: 900 });
        await fits(owner);
      }
      // Effective CSS viewport of a 1280px window at 200% browser zoom.
      // CSS body.zoom does not update media queries and is not equivalent.
      const zoomContext = await browser.newContext({
        storageState: await owner.context().storageState(),
        viewport: { width: 640, height: 450 }, deviceScaleFactor: 2,
      });
      try {
        const zoomed = await zoomContext.newPage();
        await zoomed.goto(owner.url());
        await zoomed.getByRole("heading", { name: "Управление ролями", exact: true }).waitFor();
        try { await fits(zoomed); }
        catch (error) {
          console.error(await zoomed.evaluate(() => Array.from(document.querySelectorAll("body *"))
            .map((el) => ({ tag: el.tagName, className: el.className, right: el.getBoundingClientRect().right,
              text: (el.textContent || "").slice(0, 70) })).filter((el) => el.right > innerWidth + 2).slice(0, 10)));
          if (process.env.E2E_SCREENSHOT_DIR) await zoomed.screenshot({ path: process.env.E2E_SCREENSHOT_DIR + "/zoom-viewport.png", fullPage: true, animations: "disabled" });
          throw error;
        }
      } finally { await zoomContext.close(); }
    } finally {
      await owner.setViewportSize({ width: 1280, height: 900 });
      await role.uncheck();
      await comment.fill("E2E: отзыв роли арбитра из карточки пользователя.");
      await owner.getByRole("button", { name: "Сохранить роли" }).click();
      await owner.getByText("Роли пользователя обновлены.", { exact: true }).waitFor();
    }
    await owner.reload();
    await role.waitFor();
    assert.equal(await role.isChecked(), false);
    assert.equal(errors.length, 0, errors.join("; "));
    if (process.env.E2E_SCREENSHOT_DIR) {
      await owner.screenshot({ path: process.env.E2E_SCREENSHOT_DIR + "/roles.png", fullPage: true, animations: "disabled" });
      await page.goto(base);
      await page.screenshot({ path: process.env.E2E_SCREENSHOT_DIR + "/home.png", fullPage: true, animations: "disabled" });
    }
    console.log("E2E STAFF CUSTOMIZATION OK");
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
