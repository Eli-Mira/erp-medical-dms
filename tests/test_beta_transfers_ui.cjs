'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const start = source.indexOf('  var transferUI = {');
const end = source.indexOf('  async function loadWarehousesView()', start);
assert.ok(start >= 0 && end > start);
const block = source.slice(start, end);

function element() {
  return {
    value: '', textContent: '', disabled: false, children: [], options: [],
    set innerHTML(value) { this.children = []; this.options = []; },
    appendChild(child) { this.children.push(child); this.options.push(child); },
    reset() {},
  };
}
function harness(api = async () => [], storage = new Map()) {
  const nodes = new Map();
  const get = id => {
    if (!nodes.has(id)) nodes.set(id, element());
    return nodes.get(id);
  };
  const c = {
    state: { token: 'session-a', user: { role: 'finance', is_owner: false }, lang: 'en' },
    el: { transfersError: get('transfers-error'), transferRows: get('transfer-rows') },
    document: { createElement: element }, $: get, api, t: key => key,
    sessionStorage: {
      getItem: key => storage.get(key) || null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: key => storage.delete(key),
    },
    clearError: node => { node.textContent = ''; },
    showError: (node, message) => { node.textContent = message; },
    messageFor: error => error.message || 'request failed', fmtDate: value => value,
    cell: (label, text) => ({ label, textContent: text }),
    renderRows: (tbody, rows, build) => {
      tbody.innerHTML = '';
      rows.forEach(row => tbody.appendChild(build(row)));
    },
    emptyRow: (tbody, count, key) => tbody.appendChild({ textContent: key }),
    fillSelect: (select, rows, label) => {
      select.innerHTML = ''; select.value = '';
      rows.forEach(row => select.appendChild({ value: row.id, textContent: label(row) }));
    },
  };
  vm.createContext(c);
  vm.runInContext(block, c);
  const ui = c.transferUI;
  ui.token = c.state.token; ui.ready = true;
  const warehouses = [
    { id: 'src', branch_id: 'branch-src', code: 'SRC', name_ar: 'مصدر', name_en: 'Source', is_active: true },
    { id: 'dst', branch_id: 'branch-dst', code: 'DST', name_ar: 'وجهة', name_en: 'Destination', is_active: true },
  ];
  const products = [{ id: 'product', sku: 'P', name_ar: 'صنف', name_en: 'Product' }];
  const batches = [{ id: 'batch', warehouse_id: 'src', product_id: 'product',
    batch_no: 'B-007', manufacture_date: '2026-01-02', expiry_date: '2028-03-04', quantity: '10.125' }];
  ui.warehouses = warehouses; ui.products = products; ui.batches = batches;
  function select() {
    get('transfer-source').value = 'src'; get('transfer-destination').value = 'dst';
    get('transfer-product').value = 'product'; get('transfer-batch').value = 'batch';
    get('transfer-quantity').value = '1.125'; get('transfer-note').value = 'synthetic note';
  }
  select();
  function reference(url) {
    if (url === '/master/warehouses') return warehouses;
    if (url === '/master/products?limit=500') return products;
    if (url === '/inventory/batches') return batches;
    return [];
  }
  return { c, ui, get, select, reference, storage };
}
const event = { preventDefault() {} };
const plain = value => JSON.parse(JSON.stringify(value));

test('payload preserves IDs, decimal text and note without metadata overrides', () => {
  const h = harness();
  h.get('transfer-quantity').value = '123456789.125';
  assert.deepEqual(plain(h.c.transferPayload()), {
    source_warehouse_id: 'src', destination_warehouse_id: 'dst', product_id: 'product',
    batch_id: 'batch', quantity: '123456789.125', note: 'synthetic note',
  });
  h.get('transfer-batch').value = '';
  assert.equal(h.c.transferPayload().batch_id, null);
});

test('positive finite decimal syntax does not use binary-float magnitude limits', async () => {
  const calls = [];
  const h = harness(async (...args) => { calls.push(args); return []; });
  for (const value of ['', ' ', '0', '+0.000e999', '0e-999', '-1', 'NaN', 'sNaN', 'Infinity', '0x10', '1,2', '1e', '.']) {
    h.get('transfer-quantity').value = value;
    assert.throws(() => h.c.transferPayload(), value);
    await h.c.submitTransfer(event);
  }
  assert.equal(calls.length, 0);
  for (const value of ['.125', '1.', '+1.125', '1e999', '1e-999', '0.0000000000000000000000001', '999999999999999999999.125']) {
    h.get('transfer-quantity').value = value;
    assert.equal(h.c.transferPayload().quantity, value);
  }
});

test('same, forged, inactive and mismatched references fail closed; owner boundary preserved', () => {
  const h = harness();
  for (const value of ['src', 'branch-dst', 'forged']) {
    h.get('transfer-destination').value = value;
    assert.throws(() => h.c.transferPayload());
  }
  h.select(); h.ui.warehouses[1].is_active = false;
  assert.throws(() => h.c.transferPayload());
  h.ui.warehouses[1].is_active = true;
  h.get('transfer-product').value = 'forged';
  assert.throws(() => h.c.transferPayload());
  h.select(); h.ui.batches[0].warehouse_id = 'dst';
  assert.throws(() => h.c.transferPayload());
  h.ui.batches[0].warehouse_id = 'src'; h.ui.batches[0].product_id = 'other';
  assert.throws(() => h.c.transferPayload());
  h.ui.batches[0].product_id = 'product';
  for (const role of ['warehouse_staff', 'admin', 'read_only_auditor', 'owner']) {
    h.c.state.user.role = role;
    assert.throws(() => h.c.transferPayload());
  }
  h.c.state.user.is_owner = true;
  assert.equal(h.c.transferPayload().source_warehouse_id, 'src');
  h.c.state.token = 'session-b';
  assert.throws(() => h.c.transferPayload());
});

test('batch choices retain exact metadata as text and clear incompatible selections', () => {
  const h = harness();
  h.ui.batches[0].batch_no = '<img src=x onerror=alert(1)>';
  h.c.refreshTransferBatches();
  const option = h.get('transfer-batch').options[1];
  assert.equal(option.value, 'batch');
  for (const text of [h.ui.batches[0].batch_no, 'batch', '2026-01-02', '2028-03-04', '10.125']) {
    assert.ok(option.textContent.includes(text));
  }
  h.get('transfer-source').value = 'dst'; h.c.refreshTransferBatches();
  assert.equal(h.get('transfer-batch').value, '');
  assert.equal(h.get('transfer-batch').options.length, 1);
});

test('owner and finance load references, create once, refresh both balances and reopen persisted history', async () => {
  for (const role of ['finance', 'owner']) {
    const calls = [];
    let release;
    let committed = false;
    const pending = new Promise(resolve => { release = resolve; });
    const h = harness(async (url, opts) => {
      calls.push({ url, opts });
      if (opts) { await pending; committed = true; return { id: 'transfer-reference' }; }
      if (url === '/transfers') return committed ? [{
        id: 'outgoing-movement-id', source_warehouse_id: 'src', product_id: 'product',
        quantity: '1.125', created_at: '2026-10-30',
      }] : [];
      if (url.startsWith('/inventory/stock?')) return [{
        warehouse_id: url.includes('warehouse_id=src') ? 'src' : 'dst', batch_id: null, quantity: '8.875',
      }];
      return h.reference(url);
    });
    h.c.state.user = { role, is_owner: role === 'owner' };
    await h.c.loadTransfers();
    assert.equal(h.ui.ready, true); assert.equal(h.get('transfer-fields').disabled, false);
    h.select();
    const first = h.c.submitTransfer(event);
    assert.equal(h.get('transfer-fields').disabled, true);
    assert.equal(h.storage.get('transfer-pending'), '1');
    await h.c.submitTransfer(event);
    assert.equal(calls.filter(call => call.opts).length, 1);
    release(); await first;
    assert.equal(h.storage.has('transfer-pending'), false);
    assert.equal(h.get('transfer-quantity').value, '');
    assert.equal(h.get('transfer-fields').disabled, false);
    for (const id of ['src', 'dst']) {
      assert.ok(calls.some(call => call.url === '/inventory/stock?warehouse_id=' + id + '&product_id=product'));
    }
    assert.equal(h.get('transfer-balance-rows').children.length, 2);
    await h.c.loadTransfers();
    assert.equal(h.get('transfer-rows').children[0].children[1].textContent, 'Source — SRC');
    assert.equal(h.get('transfer-rows').children[0].children[2].textContent, 'Product — P');
    assert.equal(h.get('transfer-rows').children[0].children[3].textContent, '1.125');
    assert.equal(calls.filter(call => call.opts).length, 1);
  }
});

test('known 409 and 422 rejections retain input and release the pending marker', async () => {
  for (const status of [409, 422]) {
    const h = harness(async () => { throw Object.assign(new Error('rejected'), { status }); });
    await h.c.submitTransfer(event);
    assert.equal(h.ui.uncertain, false);
    assert.equal(h.storage.has('transfer-pending'), false);
    assert.equal(h.get('transfer-quantity').value, '1.125');
    assert.equal(h.get('transfer-fields').disabled, false);
  }
});

test('network, timeout and 5xx results stay locked across refresh, reload and token changes', async () => {
  for (const status of [undefined, 408, 500, 503]) {
    let posts = 0;
    const h = harness(async (url, opts) => {
      if (opts) { posts++; throw Object.assign(new Error('unconfirmed'), { status }); }
      return h.reference(url);
    });
    await h.c.submitTransfer(event); await h.c.submitTransfer(event);
    assert.equal(posts, 1); assert.equal(h.ui.uncertain, true);
    h.c.state.token = 'session-b'; await h.c.loadTransfers();
    assert.equal(h.get('transfer-fields').disabled, true);
    const reloaded = harness(async () => [], h.storage);
    await reloaded.c.loadTransfers();
    assert.equal(reloaded.ui.uncertain, true);
    assert.equal(reloaded.get('transfer-fields').disabled, true);
    assert.match(reloaded.get('transfers-error').textContent, /transfer_uncertain/);
  }
});

test('unavailable safety storage prevents POST', async () => {
  let calls = 0;
  const h = harness(async () => { calls++; return []; });
  h.c.sessionStorage.setItem = () => { throw new Error('storage denied'); };
  h.c.sessionStorage.getItem = () => { throw new Error('storage denied'); };
  await h.c.submitTransfer(event);
  assert.equal(calls, 0); assert.equal(h.ui.uncertain, true);
  assert.equal(h.get('transfer-fields').disabled, true);
});

test('successful POST followed by refresh failure is explicitly saved, not a retryable failed write', async () => {
  const h = harness(async (url, opts) => {
    if (opts) return { id: 'committed' };
    throw Object.assign(new Error('refresh failed'), { status: 503 });
  });
  await h.c.submitTransfer(event);
  assert.equal(h.ui.uncertain, false);
  assert.equal(h.storage.has('transfer-pending'), false);
  assert.equal(h.get('transfer-quantity').value, '');
  assert.match(h.get('transfers-error').textContent, /transfer_saved_refresh_failed/);
});

test('warehouse_staff reference denial is role-specific and does not suppress authorized history', async () => {
  const calls = [];
  const h = harness(async url => {
    calls.push(url);
    if (url.startsWith('/master/')) throw Object.assign(new Error('Master data access denied'), { status: 403 });
    if (url === '/transfers') return [{ source_warehouse_id: 'src', product_id: 'product',
      quantity: '2.125', created_at: '2026-10-30' }];
    return [];
  });
  h.c.state.user.role = 'warehouse_staff';
  await h.c.loadTransfers();
  assert.equal(h.ui.ready, false); assert.equal(h.get('transfer-fields').disabled, true);
  assert.equal(h.get('transfer-rows').children.length, 1);
  assert.ok(calls.includes('/master/warehouses'));
  assert.ok(calls.includes('/master/products?limit=500'));
  assert.ok(calls.includes('/transfers'));
  assert.match(h.get('transfers-error').textContent, /transfer_staff_blocked/);
});

test('late history and balances cannot populate another session', async () => {
  const releases = [];
  const h = harness(() => new Promise(resolve => releases.push(resolve)));
  const history = h.c.refreshTransferHistory(h.c.state.token, h.ui.generation);
  const balances = h.c.refreshTransferBalances();
  h.c.state.token = 'session-b';
  releases.forEach(resolve => resolve([{ source_warehouse_id: 'src', warehouse_id: 'src',
    product_id: 'product', batch_id: null, quantity: '9', created_at: '2026-10-30' }]));
  await Promise.all([history, balances]);
  assert.equal(h.get('transfer-rows').children.length, 0);
  assert.equal(h.get('transfer-balance-rows').children.length, 0);
});

test('latest balance request wins over an older selection', async () => {
  const releases = [];
  const h = harness(() => new Promise(resolve => releases.push(resolve)));
  const older = h.c.refreshTransferBalances();
  const newer = h.c.refreshTransferBalances();
  releases[2]([{ warehouse_id: 'src', batch_id: null, quantity: '7.125' }]); releases[3]([]);
  await newer;
  releases[0]([{ warehouse_id: 'src', batch_id: null, quantity: '99' }]); releases[1]([]);
  await older;
  assert.equal(h.get('transfer-balance-rows').children[0].children[2].textContent, '7.125');
});
