// Function-level drill-down checks; browser/role E2E remains a separate gate.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const app = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const html = fs.readFileSync(path.join(__dirname, '../web/index.html'), 'utf8');
const marker = '    document.querySelectorAll("#ms-kpis [data-ms-view]").forEach(function (button) {';
const start = app.indexOf(marker);
const end = app.indexOf('\n    });', start) + '\n    });'.length;
assert.ok(start >= 0 && end > start, 'actual dashboard handler boundaries');
const buttons = [...html.matchAll(/<button\b[^>]*data-ms-view="([^"]+)"[^>]*>/g)];
const targets = ['salesreport', 'collections', 'balances', 'inventoryalerts'];

function fixture() {
  const navigated = [];
  const controls = targets.map(msView => ({ dataset: { msView }, listeners: {}, addEventListener(event, handler) { this.listeners[event] = handler; } }));
  const context = {
    document: { querySelectorAll(selector) { assert.equal(selector, '#ms-kpis [data-ms-view]'); return controls; } },
    showView(view) { navigated.push(view); },
  };
  vm.runInNewContext(app.slice(start, end), context, { timeout: 1000 });
  return { controls, navigated };
}

test('dashboard binds four existing destinations without automatic navigation', () => {
  const f = fixture();
  assert.equal(f.controls.length, 4);
  assert.deepEqual(f.navigated, []);
  assert.deepEqual(buttons.map(match => match[1]), targets);
  targets.forEach(target => assert.ok(html.includes('id="' + target + '-view"')));
});

test('clicking each dashboard drill-down invokes the existing router', () => {
  const f = fixture();
  f.controls.forEach(control => control.listeners.click());
  assert.deepEqual(f.navigated, targets);
});

test('drill-down markup retains role gates and resolvable translations', () => {
  const dictionaries = ['ar', 'en'].map(language => JSON.parse(fs.readFileSync(path.join(__dirname, '../web/i18n/' + language + '.json'), 'utf8')));
  buttons.forEach(match => {
    assert.match(match[0], /type="button"/);
    assert.match(match[0], /data-roles="[^"]+"/);
    const key = match[0].match(/data-i18n="([^"]+)"/)[1];
    dictionaries.forEach(dictionary => assert.equal(typeof dictionary[key], 'string'));
  });
});
