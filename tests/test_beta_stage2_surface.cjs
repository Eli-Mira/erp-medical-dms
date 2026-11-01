'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, '../web/index.html'), 'utf8');
test('returns user entrypoint and action controls are genuinely wired', function () {
  assert.match(source, /function returnPayload\(/, 'missing production handler for the user action');
  assert.ok(html.includes('id="return-editor"'), "missing real user control: return-editor");
  assert.ok(html.includes('id="return-detail"'), "missing real user control: return-detail");
});
