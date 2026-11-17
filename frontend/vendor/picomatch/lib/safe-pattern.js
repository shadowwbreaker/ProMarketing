'use strict';

// Repeated extglobs can compile to exponentially backtracking regular expressions.
// Build/test tooling in this repository does not require this syntax.
module.exports = input => {
  if (typeof input !== 'string') return;
  let bracket = false;
  for (let i = 0; i < input.length; i++) {
    const ch = input[i];
    if (ch === '\\') { i++; continue; }
    if (ch === '[') { bracket = true; continue; }
    if (ch === ']') { bracket = false; continue; }
    if (!bracket && (ch === '+' || ch === '*') && input[i + 1] === '(') {
      throw new SyntaxError('Repeated extglob patterns are disabled by the local security policy');
    }
  }
};
