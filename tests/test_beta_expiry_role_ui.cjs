const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const app = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, '../web/index.html'), 'utf8');
const start = app.indexOf('  var ROLE_OK = {');
const end = app.indexOf('\n  function applyRoleGating()', start);
assert.ok(start >= 0 && end > start);
function allowed(role) {
  const context = { state: { user: { role } } };
  vm.runInNewContext(app.slice(start, end), context, { timeout: 1000 });
  return context.roleAllowed('batches');
}
test('batches client guard accepts every already-declared navigation role', () => {
  const tag = html.match(/<button\b[^>]*data-view="batches"[^>]*>/)[0];
  const roles = tag.match(/data-roles="([^"]+)"/)[1].split(',');
  assert.deepEqual(roles, ['owner', 'finance', 'sales_manager', 'district_manager', 'read_only_auditor']);
  roles.forEach(role => assert.equal(allowed(role), true, role + ' must reach the declared batches view'));
});
test('batches remains denied to undeclared roles', () => {
  ['medical_rep', 'admin', 'private_owner', 'unknown'].forEach(role => assert.equal(allowed(role), false, role));
});
