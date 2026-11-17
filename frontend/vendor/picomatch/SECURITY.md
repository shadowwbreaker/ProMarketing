# Local picomatch security fork

Base: upstream MIT-licensed picomatch 4.0.7, fetched from the npm registry.
Local version: 4.0.8-yvt.1. This is not an upstream release.

GHSA-fc5q-39xc-vjpf / CVE-2026-112366 has no patched npm release at the time of this change.
The local fork rejects unescaped repeated extglobs +(...) and *(...) before parsing or regex
compilation, including the fast path. This intentionally disables this optional pattern syntax;
ordinary stars, globstars, braces, character classes and @(...) remain available.
The repository build/test configuration does not require repeated extglobs.

Changes to upstream: lib/safe-pattern.js, guards in lib/parse.js and lib/picomatch.js, package metadata.
The upstream MIT license is preserved in LICENSE.
Regression checks: node --test scripts/secure-globs.test.mjs; full ESLint, Vitest and Next.js build.
A zero registry audit for this local package is not a substitute for these tests.
Replace the local override with a verified upstream release once available.

Primary advisory: https://github.com/advisories/GHSA-fc5q-39xc-vjpf
