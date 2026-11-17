// Runs every e2e scenario sequentially. Requires: backend :8000 (+ celery worker), `python manage.py seed_demo`, frontend :3000.
const { execFileSync } = require("node:child_process");
const path = require("node:path");
const suites = ["smoke", "auth", "security", "accounts", "catalog", "order", "dispute", "staff", "staff-customization", "support", "insights", "profile", "journey", "responsive"];
(async () => {
const api = process.env.E2E_API_URL ?? "http://localhost:8000";
let ready = false;
for (let attempt = 0; attempt < 30; attempt++) {
  try { ready = (await fetch(api + "/api/v1/health/ready", { signal: AbortSignal.timeout(2000) })).ok; } catch {}
  if (ready) break;
  await new Promise((resolve) => setTimeout(resolve, 500));
}
if (!ready) throw new Error("Local backend is not ready; wait for migrations and fixture creation.");
let failed = 0;
for (const s of suites) {
  try {
    const out = execFileSync(process.execPath, [path.join(__dirname, `${s}.cjs`)], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
    console.log(out.trim().split("\n").pop());
  } catch (e) {
    failed++;
    console.error(`FAILED ${s}\n${(e.stderr || e.stdout || "").toString().slice(0, 1500)}`);
  }
}
console.log(failed ? `${failed} suite(s) failed` : `All ${suites.length} e2e suites passed`);
process.exit(failed ? 1 : 0);

})().catch((error) => { console.error(error); process.exitCode = 1; });
