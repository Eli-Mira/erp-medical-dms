// Function-level controls; real browser/API acceptance is a separate gate.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const app = fs.readFileSync(process.env.BATCHES_SOURCE_PATH || path.join(__dirname, '../web/app.js'), 'utf8');
const start = app.indexOf('  function loadBatches() {');
const end = app.indexOf('\n  function loadCover()', start);
assert.ok(start >= 0 && end > start, 'existing batch-loader function boundaries');
const source = app.slice(start, end);
const row = name => ({ batch_no: name, product_id: 'synthetic-product', warehouse_id: 'synthetic-warehouse', expiry_date: '2026-11-01', quantity: '2.000' });

function fixture() {
  const requests = [];
  const body = { rows: [], appendChild(node) { this.rows.push(node); }, replaceChildren() { this.rows = []; } };
  Object.defineProperty(body, 'innerHTML', { get() { return ''; }, set(value) { assert.equal(value, ''); this.rows = []; } });
  const error = { message: null };
  const context = {
    batchesSeq: 0,
    state: { token: 'synthetic-session-a' },
    el: { batchRows: body, batchesError: error, batchesFilter: { value: 'all' } },
    document: { createElement() { return { cells: [], appendChild(node) { this.cells.push(node); } }; } },
    clearError(target) { target.message = null; },
    showError(target, message) { target.message = message; },
    messageFor(value) { return value.message; },
    api(url) { return new Promise((resolve, reject) => requests.push({ url, resolve, reject })); },
    renderRows(target, rows, make) { target.rows = rows.map(make); },
    emptyRow(target, columns, key) { target.rows.push({ empty: key, columns }); },
    cell(label, value) { return { label, value }; },
    t(key) { return key; },
    productLineLabel(id) { return id; },
    warehouseLabel(id) { return id; },
    fmtDate(value) { return value; },
    fmtQty(value) { return value; },
  };
  vm.createContext(context);
  vm.runInContext(source, context, { timeout: 1000 });
  return { context, requests, body, error, load: () => context.loadBatches(), near() { context.el.batchesFilter.value = 'near_expiry'; } };
}

function displayed(f) { return f.body.rows[0]?.cells?.[0]?.value; }

test('all_batches_uses_existing_api_and_renders_five_columns', async () => {
  const f = fixture(); const pending = f.load();
  assert.equal(f.requests[0].url, '/inventory/batches');
  f.requests[0].resolve([row('SYNTHETIC-ALL')]); await pending;
  assert.equal(displayed(f), 'SYNTHETIC-ALL'); assert.equal(f.body.rows[0].cells.length, 5);
});

test('near_expiry_selects_warning_api', async () => {
  const f = fixture(); f.near(); const pending = f.load();
  assert.equal(f.requests[0].url, '/inventory/expiry-warnings');
  f.requests[0].resolve([row('SYNTHETIC-NEAR')]); await pending;
  assert.equal(displayed(f), 'SYNTHETIC-NEAR');
});

test('near_expiry_empty_state_has_distinct_translation_key', async () => {
  const f = fixture(); f.near(); const pending = f.load();
  f.requests[0].resolve([]); await pending;
  assert.equal(f.body.rows.length, 1, 'loading row is replaced by one empty row');
  assert.equal(f.body.rows[0].empty, 'batches_empty_near_expiry');
});

test('all_batches_empty_state_keeps_existing_translation_key', async () => {
  const f = fixture(); const pending = f.load();
  f.requests[0].resolve([]); await pending;
  assert.equal(f.body.rows.length, 1, 'loading row is replaced by one empty row');
  assert.equal(f.body.rows[0].empty, 'empty_rows');
});

test('older_success_cannot_replace_newer_filter_result', async () => {
  const f = fixture(); const old = f.load(); f.near(); const current = f.load();
  f.requests[1].resolve([row('SYNTHETIC-NEWER')]); await current;
  f.requests[0].resolve([row('SYNTHETIC-OLDER')]); await old;
  assert.equal(displayed(f), 'SYNTHETIC-NEWER');
});

test('older_error_cannot_clear_newer_filter_result', async () => {
  const f = fixture(); const old = f.load(); f.near(); const current = f.load();
  f.requests[1].resolve([row('SYNTHETIC-NEWER')]); await current;
  f.requests[0].reject(new Error('synthetic old failure')); await old;
  assert.equal(displayed(f), 'SYNTHETIC-NEWER'); assert.equal(f.error.message, null);
});

test('session_change_rejects_old_success', async () => {
  const f = fixture(); const pending = f.load();
  f.context.state.token = 'synthetic-session-b'; f.body.replaceChildren();
  f.requests[0].resolve([row('SYNTHETIC-OLD-SESSION')]); await pending;
  assert.equal(f.body.rows.length, 0);
});

test('session_change_rejects_old_error', async () => {
  const f = fixture(); const pending = f.load();
  f.context.state.token = 'synthetic-session-b'; f.body.replaceChildren();
  f.requests[0].reject(new Error('synthetic old session failure')); await pending;
  assert.equal(f.error.message, null); assert.equal(f.body.rows.length, 0);
});

test('generation_invalidation_rejects_pending_response', async () => {
  const f = fixture(); const pending = f.load();
  f.context.batchesSeq += 1; f.body.replaceChildren();
  f.requests[0].resolve([row('SYNTHETIC-INVALIDATED')]); await pending;
  assert.equal(f.body.rows.length, 0);
});

test('current_error_clears_loading_and_refresh_recovers_selected_filter', async () => {
  const f = fixture(); f.near(); const pending = f.load();
  f.requests[0].reject(new Error('synthetic current failure')); await pending;
  assert.equal(f.body.rows.length, 0); assert.equal(f.error.message, 'synthetic current failure');
  const retry = f.load(); assert.equal(f.error.message, null);
  assert.equal(f.requests[1].url, '/inventory/expiry-warnings');
  f.requests[1].resolve([row('SYNTHETIC-RECOVERED')]); await retry;
  assert.equal(displayed(f), 'SYNTHETIC-RECOVERED');
});
