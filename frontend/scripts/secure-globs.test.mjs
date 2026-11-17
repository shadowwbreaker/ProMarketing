import { test } from "node:test";
import assert from "node:assert/strict";
import picomatch from "picomatch";
test("known repeated-extglob ReDoS inputs are rejected before regex compilation", () => {
  for (const glob of ["+(*)", "+(*a)", "*(a*)", "folder/+(*a).js", "@(x|+(*))", "+(a|aa)"]) {
    assert.throws(() => picomatch.makeRe(glob), /Repeated extglob/);
    assert.throws(() => picomatch.parse(glob), /Repeated extglob/);
  }
});
test("normal build/test patterns retain their matching behavior", () => {
  assert.equal(picomatch("**/*.{js,ts}")("app/test.ts"), true);
  assert.equal(picomatch("**/node_modules/**")("a/node_modules/x/index.js"), true);
  assert.equal(picomatch("*.@(js|ts)")("page.ts"), true);
  assert.equal(picomatch("*.ts")("page.js"), false);
});
