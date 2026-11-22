// Isolated local TOTP test. Never creates users on public hosting.
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const { execFileSync } = require("node:child_process");
const { chromium } = require("playwright");
const sharp = require("sharp");
const jsQR = require("jsqr");
const base = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const api = process.env.E2E_API_URL ?? "http://localhost:8000";
for (const url of [base, api]) {
  assert.ok(["localhost", "127.0.0.1"].includes(new URL(url).hostname), "2FA E2E must use a disposable local service");
}
function otp(secret, step) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  const bits = [...secret].map(char => alphabet.indexOf(char).toString(2).padStart(5, "0")).join("");
  const key = Buffer.from((bits.match(/.{8}/g) ?? []).map(byte => parseInt(byte, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(step));
  const digest = crypto.createHmac("sha1", key).update(counter).digest();
  const offset = digest[digest.length - 1] & 15;
  return String((digest.readUInt32BE(offset) & 0x7fffffff) % 1000000).padStart(6, "0");
}
(async () => {
  const browser = await chromium.launch({ channel: process.env.E2E_BROWSER_CHANNEL });
  try {
    const context = await browser.newContext({ viewport: { width: 375, height: 900 } });
    await context.request.get(api + "/api/v1/auth/csrf");
    const cookies = await context.cookies(api);
    const csrf = cookies.find(cookie => cookie.name === "csrftoken").value;
    const email = "qr-" + Date.now() + "@example.com";
    const password = "Qr-local-test-password-2026";
    const registered = await context.request.post(api + "/api/v1/auth/register", {
      headers: { "X-CSRFToken": csrf },
      data: { email, password, display_name: "QR-проверка", accept_terms: true, as_seller: false },
    });
    assert.equal(registered.status(), 201);
    const page = await context.newPage();
    const urls = [];
    page.on("request", request => urls.push(request.url()));
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.goto(base + "/account?tab=security");
    await page.getByRole("button", { name: "Включить", exact: true }).waitFor();
    const provisioning = page.waitForResponse(response => response.url().endsWith("/api/v1/me/2fa/setup"));
    await page.getByRole("button", { name: "Включить", exact: true }).click();
    const response = await provisioning;
    assert.ok(response.headers()["cache-control"].includes("no-store"));
    const setup = await response.json();
    const qr = page.getByRole("img", { name: "QR-код для подключения двухфакторной защиты" });
    await qr.waitFor();
    const { data, info } = await sharp(await qr.screenshot()).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    const decoded = jsQR(new Uint8ClampedArray(data), info.width, info.height);
    assert.ok(decoded && decoded.data === setup.otpauth_url, "QR must decode to the server's unchanged provisioning URI");
    const uri = new URL(decoded.data);
    assert.equal(uri.protocol, "otpauth:");
    assert.equal(uri.hostname, "totp");
    assert.equal(uri.searchParams.get("issuer"), "YourVideoTeam");
    assert.ok(uri.searchParams.get("secret") === setup.secret, "QR and manual key must match");
    assert.ok(decodeURIComponent(uri.pathname).includes(email));
    await page.getByText(setup.secret, { exact: true }).waitFor();
    for (const width of [320, 375, 1280]) {
      await page.setViewportSize({ width, height: 900 });
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "QR setup must fit the viewport");
    }
    if (process.env.E2E_SCREENSHOT) {
      await page.setViewportSize({ width: 375, height: 900 });
      await page.screenshot({ path: process.env.E2E_SCREENSHOT, fullPage: true,
        mask: [qr, page.getByText(setup.secret, { exact: true })] });
    }
    const input = page.getByLabel("Шестизначный код из приложения");
    let step = Math.floor(Date.now() / 30000);
    const valid = new Set([-1, 0, 1].map(offset => otp(setup.secret, step + offset)));
    let wrong = "000000";
    while (valid.has(wrong)) wrong = String(Number(wrong) + 1).padStart(6, "0");
    await input.fill(wrong);
    const rejected = page.waitForResponse(response => response.url().endsWith("/api/v1/me/2fa/confirm"));
    await page.getByRole("button", { name: "Подтвердить", exact: true }).click();
    assert.equal((await rejected).status(), 400);
    await qr.waitFor();
    step = Math.floor(Date.now() / 30000);
    await input.fill(otp(setup.secret, step));
    await page.getByRole("button", { name: "Подтвердить", exact: true }).click();
    await page.getByRole("button", { name: "Отключить", exact: true }).waitFor();
    assert.equal(await qr.count(), 0);
    assert.equal(await page.getByText(setup.secret, { exact: true }).count(), 0);
    assert.ok(urls.every(url => !url.includes(setup.secret) && !url.includes("otpauth")), "Provisioning data must not be sent in network URLs");
    const fresh = await browser.newContext();
    await fresh.request.get(api + "/api/v1/auth/csrf");
    const freshCsrf = (await fresh.cookies(api)).find(cookie => cookie.name === "csrftoken").value;
    const credentials = { email, password };
    const postLogin = data => fresh.request.post(api + "/api/v1/auth/login", {
      headers: { "X-CSRFToken": freshCsrf }, data,
    });
    assert.equal((await postLogin(credentials)).status(), 401);
    assert.equal((await postLogin({ ...credentials, otp: otp(setup.secret, step + 1) })).status(), 200);
    if (process.env.E2E_BACKEND_CONTAINER) {
      const logs = execFileSync("docker", ["logs", process.env.E2E_BACKEND_CONTAINER], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
      assert.ok(!logs.includes(setup.secret) && !logs.includes(setup.otpauth_url), "Backend logs must not contain provisioning data");
    }
    assert.deepEqual(errors, []);
    console.log("E2E 2FA QR OK: decoded URI, fallback, invalid/valid code, login, mobile, private setup");
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
