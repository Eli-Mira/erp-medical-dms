'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Synthetic transport/DOM controls execute the real shell handlers, not copied UI logic.
const source = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const en = JSON.parse(fs.readFileSync(path.join(__dirname, '../web/i18n/en.json'), 'utf8'));
function deferred() {
  let resolve, reject;
  const promise = new Promise((a, b) => { resolve = a; reject = b; });
  return { promise, resolve, reject };
}
class Element {
  constructor(tag = 'div') {
    this.tagName = tag.toUpperCase(); this.children = []; this.dataset = {};
    this.style = {}; this.value = ''; this.disabled = false; this.open = false;
    this.attributes = {}; this._text = ''; this.listeners = {};
    const classes = new Set();
    this.classList = { add: x => classes.add(x), remove: x => classes.delete(x),
      contains: x => classes.has(x), toggle: (x, on) => on ? classes.add(x) : classes.delete(x) };
  }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(x => x.textContent).join(''); }
  set innerHTML(value) { assert.equal(value, ''); this.replaceChildren(); }
  get innerHTML() { return ''; }
  appendChild(child) { this.children.push(child); return child; }
  append(...children) { children.forEach(x => this.appendChild(x)); }
  replaceChildren(...children) { this.children = []; this._text = ''; this.append(...children); }
  get options() { return this.children; }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  addEventListener(name, handler) { this.listeners[name] = handler; }
  reset() { this.value = ''; }
  close() { this.open = false; }
  checkValidity() { return true; }
  setCustomValidity(message) { this.validationMessage = String(message); }
  focus() {}
}
function storage() {
  const values = new Map();
  return { getItem: key => values.get(key) || null,
    setItem: (key, value) => values.set(key, String(value)), removeItem: key => values.delete(key) };
}
function reply(data, status = 200) {
  return { ok: status >= 200 && status < 300, status, text: async () => JSON.stringify(data) };
}
function setup(sharedStorage = storage()) {
  const roots = new Map();
  function find(node, id) {
    if (node.id === id) return node;
    for (const child of node.children) { const match = find(child, id); if (match) return match; }
  }
  function get(id) {
    for (const root of roots.values()) { const match = find(root, id); if (match) return match; }
    if (!roots.has(id)) { const element = new Element(); element.id = id; roots.set(id, element); }
    return roots.get(id);
  }
  const calls = [], rows = [];
  const refs = {
    '/master/customers': [{ id: 'customer-a', name_ar: 'CUSTOMER_PRIVATE', is_active: true }],
    '/master/products?limit=500': [{ id: 'product-a', name_ar: 'Product', sku: 'SKU' }],
    '/master/warehouses': [{ id: 'warehouse-a', name_ar: 'Warehouse', is_active: true }],
    '/inventory/batches': [{ id: 'batch-a', product_id: 'product-a', warehouse_id: 'warehouse-a', batch_no: 'B', expiry_date: '2027-01-01' }],
  };
  const transport = { override: null };
  const context = vm.createContext({
    document: { currentScript: null, addEventListener() {}, getElementById: get,
      createElement: tag => new Element(tag), querySelectorAll: () => [], documentElement: {} },
    window: {}, localStorage: storage(), sessionStorage: sharedStorage,
    URL, Date, console, setTimeout, clearTimeout, crypto: require('node:crypto').webcrypto,
    fetch: async (url, options = {}) => {
      calls.push({ url, options });
      if (transport.override) {
        const result = transport.override(url, options);
        if (result !== undefined) return await result;
      }
      if (Object.hasOwn(refs, url)) return reply(refs[url]);
      if (url.startsWith('/returns?')) {
        const offset = Number(new URL(url, 'https://fixture.invalid').searchParams.get('offset'));
        return reply(rows.slice(offset, offset + 200));
      }
      if (url === '/returns' && options.method === 'POST') {
        const payload = JSON.parse(options.body);
        const row = { ...payload, id: 'saved-return', status: 'quarantined' };
        rows.unshift(row); return reply(row, 201);
      }
      if (url === '/auth/logout') return reply(null);
      throw new Error('Unexpected fixture request: ' + url);
    },
  });
  const end = '  document.addEventListener("DOMContentLoaded", init);';
  assert.equal(source.split(end).length, 2, 'unique shell instrumentation anchor');
  vm.runInContext(source.replace(end,
    '  globalThis.controls = {state, el, api, logout, clearSession, loadReturns, roleAllowed, submitReturn: typeof submitReturn === "function" ? submitReturn : null, returnPayload: typeof returnPayload === "function" ? returnPayload : null};'), context);
  const controls = context.controls;
  // Populate element references from the owning cache function without invoking application boot.
  const mappings = [...source.matchAll(/el\.(\w+) = \$\("([^"]+)"\);/g)];
  for (const [, name, id] of mappings) controls.el[name] = get(id);
  controls.state.token = 'session-a';
  controls.state.user = { id: 'user-a', role: 'finance', is_active: true, is_owner: false };
  return { ...controls, get, calls, rows, refs, transport, sharedStorage };
}
const event = () => ({ preventDefault() {} });
function fill(h, quantity = '1.2300') {
  h.get('return-customer').value = 'customer-a';
  h.get('return-product').value = 'product-a';
  h.get('return-warehouse').value = 'warehouse-a';
  h.get('return-batch').value = '';
  h.get('return-quantity').value = quantity;
  h.get('return-date').value = '2026-10-30';
  h.get('return-reason').value = '';
}
function writes(h) { return h.calls.filter(c => c.url === '/returns' && c.options.method === 'POST'); }
function openButton(h) { return h.el.returnRows.children[0].children[6].children[0]; }

test('actual create handler keeps Decimal text, optional reason and null batch; reopen rereads list', async () => {
  const h = setup();
  await h.loadReturns();
  assert.equal(typeof h.get('return-form').onsubmit, 'function', 'missing return intake form');
  fill(h, '+123456789.123400e-2');
  await h.get('return-form').onsubmit(event());
  assert.equal(writes(h).length, 1);
  const payload = JSON.parse(writes(h)[0].options.body);
  assert.deepEqual(payload, { customer_id: 'customer-a', product_id: 'product-a', warehouse_id: 'warehouse-a', batch_id: null, quantity: '+123456789.123400e-2', return_date: '2026-10-30', reason: null });
  assert.equal(h.el.returnRows.children[0].children[3].textContent, payload.quantity);
  assert.equal(h.el.returnRows.children[0].children[5].textContent, 'return_quarantined');
  h.rows[0].reason = 'SERVER_READBACK';
  await openButton(h).onclick();
  assert.match(h.get('return-detail').textContent, /SERVER_READBACK/);
  assert.equal(h.calls.some(c => /^\/returns\//.test(c.url)), false, 'no fabricated detail route');
  assert.equal(h.calls.some(c => /approve|release|settle/.test(c.url)), false);
});

test('actual submit rejects foreign references, mismatched batches and nonpositive/nonfinite quantities', async () => {
  const h = setup(); await h.loadReturns();
  assert.equal(typeof h.get('return-form').onsubmit, 'function', 'missing return intake form');
  for (const quantity of ['0', '-1', 'NaN', 'Infinity', '0e999', '1,2']) {
    fill(h, quantity); await h.get('return-form').onsubmit(event());
  }
  fill(h); h.get('return-customer').value = 'not-loaded'; await h.get('return-form').onsubmit(event());
  fill(h); h.get('return-batch').value = 'foreign-batch'; await h.get('return-form').onsubmit(event());
  assert.equal(writes(h).length, 0);
  fill(h); h.get('return-batch').value = 'batch-a';
  h.get('return-reason').value = 'Damaged';
  await h.get('return-form').onsubmit(event());
  assert.equal(writes(h).length, 1);
  assert.equal(JSON.parse(writes(h)[0].options.body).batch_id, 'batch-a');
});

test('double-submit is blocked while the actual POST body is awaiting consumption', async () => {
  const h = setup(); await h.loadReturns();
  assert.equal(typeof h.get('return-form').onsubmit, 'function', 'missing return intake form');
  fill(h);
  const body = deferred();
  h.transport.override = (url, options) => url === '/returns' && options.method === 'POST' ?
    { ok: true, status: 201, text: () => body.promise } : undefined;
  const submit = h.get('return-form').onsubmit;
  const first = submit(event());
  await submit(event());
  assert.equal(writes(h).length, 1);
  h.rows.push({ id: 'saved-return', quantity: '1.2300', status: 'quarantined' });
  body.resolve(JSON.stringify(h.rows[0])); await first;
  assert.equal(h.sharedStorage.getItem('return-pending'), null);
});

test('ambiguous write remains locked through refresh and a new shell with the same tab storage', async () => {
  const h = setup(); await h.loadReturns();
  assert.equal(typeof h.get('return-form').onsubmit, 'function', 'missing return intake form');
  fill(h);
  h.transport.override = (url, options) => {
    if (url === '/returns' && options.method === 'POST') throw new Error('transport lost');
  };
  await h.get('return-form').onsubmit(event());
  assert.ok(h.sharedStorage.getItem('return-pending'));
  await h.loadReturns(); fill(h); await h.get('return-form').onsubmit(event());
  assert.equal(writes(h).length, 1);
  const reloaded = setup(h.sharedStorage); await reloaded.loadReturns();
  fill(reloaded); await reloaded.get('return-form').onsubmit(event());
  assert.equal(writes(reloaded).length, 0);
  assert.equal(reloaded.get('return-fields').disabled, true);
});

test('definitive 422 permits correction, while saved-but-readback-failed never resends quantity', async () => {
  const h = setup(); await h.loadReturns();
  assert.equal(typeof h.get('return-form').onsubmit, 'function', 'missing return intake form');
  fill(h);
  h.transport.override = (url, options) => url === '/returns' && options.method === 'POST' ? reply({ detail: 'invalid' }, 422) : undefined;
  await h.get('return-form').onsubmit(event());
  assert.equal(h.sharedStorage.getItem('return-pending'), null);
  assert.equal(h.get('return-fields').disabled, false);
  h.transport.override = (url) => url.startsWith('/returns?') ? reply({ detail: 'read failed' }, 500) : undefined;
  await h.get('return-form').onsubmit(event());
  assert.equal(h.get('return-quantity').value, '');
  assert.match(h.el.returnsError.textContent, /return_saved_refresh_failed/);
  await h.get('return-form').onsubmit(event());
  assert.equal(writes(h).length, 2);
});

test('real logout tears down returns before transport settles; stale body cannot repopulate the next session', async () => {
  const h = setup(); await h.loadReturns();
  assert.equal(typeof h.get('return-form').onsubmit, 'function', 'missing return intake form');
  const body = deferred(), logout = deferred();
  h.transport.override = url => {
    if (url.startsWith('/returns?')) return { ok: true, status: 200, text: () => body.promise };
    if (url === '/auth/logout') return logout.promise;
  };
  const read = h.loadReturns();
  // loadReturns awaits references before requesting its history.
  while (!h.calls.some(c => c.url.startsWith('/returns?') && c !== h.calls.find(x => x.url.startsWith('/returns?')))) await Promise.resolve();
  const leaving = h.logout();
  assert.equal(h.state.token, null);
  assert.equal(h.get('return-editor').textContent, '');
  assert.equal(h.get('return-detail').textContent, '');
  assert.equal(h.el.returnRows.children.length, 0);
  h.state.token = 'session-b'; h.state.user = { id: 'b', role: 'finance', is_active: true };
  body.resolve(JSON.stringify([{ id: 'old', customer_id: 'PRIVATE_OLD_ACCOUNT', quantity: '1' }]));
  await read;
  assert.equal(h.el.returnRows.children.length, 0, 'stale result consumed without rendering');
  logout.reject(new Error('logout network failed')); await leaving;
  assert.equal(h.state.token, 'session-b');
});

test('old 401 cannot invalidate a replacement session even if its token text is reused', async () => {
  const h = setup();
  const body = deferred();
  h.transport.override = () => ({ ok: false, status: 401, text: () => body.promise });
  const pending = h.api('/returns');
  h.clearSession();
  h.state.token = 'session-a'; h.state.user = { id: 'replacement', role: 'finance' };
  body.resolve(JSON.stringify({ detail: 'expired old session' }));
  await assert.rejects(pending);
  assert.equal(h.state.user.id, 'replacement');
  assert.equal(h.state.token, 'session-a');
});

test('warehouse_staff receives truthful reference blocker without invented grants or master calls', async () => {
  const h = setup(); h.state.user.role = 'warehouse_staff';
  h.rows.push({ id: 'existing', quantity: '0.0100', status: 'quarantined' });
  assert.equal(h.roleAllowed('returns'), true, 'returns role must match committed backend');
  await h.loadReturns();
  assert.equal(h.calls.some(c => c.url.startsWith('/master/')), false);
  assert.equal(h.el.returnRows.children.length, 1);
  assert.match(h.el.returnsError.textContent, /return_staff_blocked/);
  assert.equal(h.get('return-editor').children.length, 0);
});

test('history pagination and reload use the existing collection contract and preserve exact quantity text', async () => {
  const h = setup();
  for (let i = 0; i < 201; i++) h.rows.push({ id: 'r-' + i, quantity: '0.000100', status: 'quarantined' });
  await h.loadReturns();
  assert.equal(h.el.returnRows.children.length, 201);
  assert.ok(h.calls.some(c => c.url === '/returns?limit=200&offset=200'));
  assert.equal(h.el.returnRows.children[200].children[3].textContent, '0.000100');
  await h.loadReturns();
  assert.equal(h.el.returnRows.children.length, 201);
  h.rows.length = 0; await h.loadReturns();
  assert.equal(h.el.returnRows.children.length, 1, 'append-only emptyRow leaves exactly one empty row');
});

test('new bilingual strings exist and optional reason is not a required HTML field', () => {
  const ar = JSON.parse(fs.readFileSync(path.join(__dirname, '../web/i18n/ar.json'), 'utf8'));
  for (const key of ['return_create', 'return_scope', 'return_reason', 'return_quarantined', 'return_staff_blocked', 'return_uncertain']) {
    assert.equal(typeof en[key], 'string', key); assert.equal(typeof ar[key], 'string', key);
  }
  assert.match(en.return_scope, /no approval, release or financial settlement/);
});

test('pending request marker never persists a bearer credential', async () => {
  const h = setup(); await h.loadReturns();
  assert.equal(typeof h.get('return-form').onsubmit, 'function');
  fill(h);
  const body = deferred();
  h.transport.override = (url, options) => url === '/returns' && options.method === 'POST' ?
    { ok: true, status: 201, text: () => body.promise } : undefined;
  const pending = h.get('return-form').onsubmit(event());
  const marker = h.sharedStorage.getItem('return-pending');
  assert.ok(marker, 'unresolved write must have a safety marker');
  assert.equal(marker.includes(h.state.token), false, 'never persist the authentication credential');
  assert.match(marker, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
  body.resolve(JSON.stringify({ id: 'saved-return', status: 'quarantined' })); await pending;
  assert.equal(h.sharedStorage.getItem('return-pending'), null);
});

test('existing read-only return roles can read history without an intake editor or writes', async () => {
  for (const role of ['read_only_auditor', 'district_manager']) {
    const h = setup(); h.state.user.role = role;
    assert.equal(h.roleAllowed('returns'), true, 'existing backend read permission must be reachable');
    h.rows.push({id: 'readable-return', quantity: '1.125', status: 'quarantined'});
    await h.loadReturns();
    assert.equal(h.el.returnRows.children.length, 1);
    assert.equal(h.get('return-editor').children.length, 0);
    assert.equal(writes(h).length, 0);
    assert.ok(h.calls.some(call => call.url.startsWith('/returns?')));
  }
});

test('current-session 401 still clears the actual authenticated session', async () => {
  const h = setup(); await h.loadReturns();
  h.transport.override = () => reply({detail: 'synthetic current session expired'}, 401);
  await assert.rejects(h.api('/returns'));
  assert.equal(h.state.token, null);
  assert.equal(h.state.user, null);
  assert.equal(h.get('return-editor').children.length, 0);
});

test('late success or rejection never clears a newer pending ownership marker', async () => {
  for (const status of [201, 422]) {
    const h = setup(); await h.loadReturns(); fill(h);
    const body = deferred();
    h.transport.override = (url, options) => url === '/returns' && options.method === 'POST' ?
      {ok: status < 400, status, text: () => body.promise} : undefined;
    const pending = h.get('return-form').onsubmit(event());
    const old = h.sharedStorage.getItem('return-pending');
    assert.ok(old);
    h.clearSession();
    const newer = require('node:crypto').randomUUID();
    h.sharedStorage.setItem('return-pending', newer);
    body.resolve(JSON.stringify(status < 400 ? {id: 'old-return'} : {detail: 'old rejection'}));
    await pending;
    assert.equal(h.sharedStorage.getItem('return-pending'), newer);
  }
});
