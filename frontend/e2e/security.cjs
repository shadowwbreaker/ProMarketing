// Credential forms must never put values in a URL, including before React loads.
const assert = require("node:assert/strict");
const { chromium } = require("playwright");

(async () => {
  const base = process.env.E2E_BASE_URL ?? "http://localhost:3000";
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ javaScriptEnabled: false });
    const password = "Synthetic-password-123";
    for (const path of ["/login", "/register", "/reset-password?token=synthetic-token"]) {
      await page.goto(base + path);
      const form = page.locator("form");
      if (path.startsWith("/reset-password") && !(await form.count())) continue; // Suspense may render only its fallback.
      await form.locator('input[type="password"]').fill(password);
      const [request] = await Promise.all([
        page.waitForRequest((entry) => entry.isNavigationRequest()),
        form.evaluate((element) => element.submit()),
      ]);
      assert.equal(request.method(), "POST");
      assert.equal(new URL(request.url()).search.includes(password), false);
    }
    console.log("E2E SECURITY OK");
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
