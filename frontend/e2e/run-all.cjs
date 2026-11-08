// Runs every e2e scenario sequentially. Requires: backend :8000 (+ celery worker), `python manage.py seed_demo`, frontend :3000.
const { execFileSync } = require("node:child_process");
const path = require("node:path");
const suites = ["smoke", "auth", "accounts", "catalog", "order", "dispute", "staff", "insights", "profile", "journey", "responsive"];
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
