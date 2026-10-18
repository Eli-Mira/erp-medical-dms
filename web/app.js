/* Invoice desk — vanilla JS PWA (no framework, per D37).
 *
 * Flow: sign in -> load master data (customers/products/branches/warehouses)
 * -> build a draft with live estimated totals -> POST /invoices (the server
 * recalculates and stores the authoritative totals) -> render the saved draft
 * and its status. Posting is deliberately left to the server's 409 gate.
 */
(function () {
  "use strict";

  var state = {
    token: null,
    user: null,
    lang: "ar",
    branches: [],
    warehouses: [],
    customers: [],
    products: [],
    lines: [],
    draft: null,
    seq: 0,
  };

  var el = {};
  var dict = {};

  function $(id) { return document.getElementById(id); }
  function t(key, fallback) {
    return dict[key] !== undefined ? dict[key] : (fallback !== undefined ? fallback : key);
  }

  // ---------------------------------------------------------------- i18n
  function applyI18n() {
    document.documentElement.lang = state.lang;
    document.documentElement.dir = state.lang === "ar" ? "rtl" : "ltr";
    document.querySelectorAll("[data-i18n]").forEach(function (node) {
      var v = dict[node.dataset.i18n];
      if (v !== undefined) node.textContent = v;
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach(function (node) {
      var v = dict[node.dataset.i18nPlaceholder];
      if (v !== undefined) node.placeholder = v;
    });
  }

  async function loadI18n(lang) {
    state.lang = lang === "en" ? "en" : "ar";
    localStorage.setItem("lang", state.lang);
    var res = await fetch("i18n/" + state.lang + ".json");
    dict = await res.json();
    applyI18n();
  }

  // ------------------------------------------------------------ API client
  async function api(path, opts) {
    opts = opts || {};
    var headers = { "Content-Type": "application/json" };
    if (state.token) headers.Authorization = "Bearer " + state.token;
    var response = await fetch(path, {
      method: opts.method || "GET",
      headers: headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    });
    var text = await response.text();
    var data = null;
    if (text) { try { data = JSON.parse(text); } catch (_e) { data = text; } }
    if (!response.ok) {
      var error = new Error("request_failed");
      error.status = response.status;
      error.data = data;
      throw error;
    }
    return data;
  }

  function fieldName(loc) {
    if (!Array.isArray(loc)) return "field";
    var parts = loc.filter(function (p) { return p !== "body"; });
    return parts.length ? parts.join(".") : "body";
  }

  function messageFor(error) {
    var d = error.data;
    if (d && Array.isArray(d.detail)) {
      return d.detail.map(function (item) {
        return fieldName(item.loc) + ": " + (item.msg || "invalid");
      }).join(" · ");
    }
    if (d && typeof d.detail === "string") return d.detail;
    if (typeof d === "string" && d) return d;
    return t("err_request") + " (" + (error.status || "?") + ")";
  }

  function showNotice(node, message, kind) {
    node.textContent = message;
    node.dataset.kind = kind || "error";
    node.classList.remove("hidden");
  }
  function showError(node, message) {
    showNotice(node, message, "error");
  }
  function clearError(node) {
    node.textContent = "";
    node.classList.add("hidden");
  }

  // ------------------------------------------------------------- numbers
  function round2(n) { return Math.round((n + Number.EPSILON) * 100) / 100; }
  function fmt(n) { return (Math.round((Number(n) + Number.EPSILON) * 100) / 100).toFixed(2); }
  function todayLocal() {
    var now = new Date();
    return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  }

  function productById(id) {
    for (var i = 0; i < state.products.length; i++) {
      if (state.products[i].id === id) return state.products[i];
    }
    return null;
  }
  function customerById(id) {
    for (var i = 0; i < state.customers.length; i++) {
      if (state.customers[i].id === id) return state.customers[i];
    }
    return null;
  }
  function branchLabel(id) {
    for (var i = 0; i < state.branches.length; i++) {
      if (state.branches[i].id === id) {
        return state.branches[i].name_ar || state.branches[i].name_en || state.branches[i].code;
      }
    }
    return "";
  }
  function productLabel(product) {
    if (!product) return "";
    return (product.name_ar || product.name_en || product.sku) + " — " + product.sku;
  }

  // Mirrors app/sales/calc.py for the *estimate only*; the server is authoritative.
  function linePreview(line) {
    var product = productById(line.productId);
    if (!product) return null;
    var price = Number(product.base_price);
    var rate = Number(product.vat_rate);
    var disc = Number(line.discount) || 0;
    var qty = Number(line.quantity) || 0;
    var net = round2(price * (1 - disc / 100));
    var total = round2(qty * net);
    var vat = rate > 0 ? round2(total * (rate / 100) / (1 + rate / 100)) : 0;
    return { price: price, net: net, total: total, vat: vat, qty: qty };
  }

  function recalcPreview() {
    var before = 0, grand = 0, vat = 0;
    state.lines.forEach(function (line) {
      var calc = linePreview(line);
      if (!calc || calc.qty <= 0) return;
      before += round2(calc.qty * calc.price);
      grand += calc.total;
      vat += calc.vat;
    });
    before = round2(before); grand = round2(grand); vat = round2(vat);
    el.prevBefore.textContent = fmt(before);
    el.prevDiscount.textContent = fmt(round2(before - grand));
    el.prevNet.textContent = fmt(round2(grand - vat));
    el.prevVat.textContent = fmt(vat);
    el.prevGrand.textContent = fmt(grand);
  }

  // ---------------------------------------------------------- master data
  function fillSelect(select, items, label, placeholderKey) {
    select.innerHTML = "";
    var placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = t(placeholderKey, "—");
    select.appendChild(placeholder);
    items.forEach(function (item) {
      var option = document.createElement("option");
      option.value = item.id;
      option.textContent = label(item);
      select.appendChild(option);
    });
  }

  async function loadMaster() {
    var results = await Promise.all([
      api("/master/branches"),
      api("/master/customers"),
      api("/master/products"),
    ]);
    state.branches = results[0];
    state.customers = results[1];
    state.products = results[2];
    fillSelect(el.customer, state.customers, function (c) {
      return (c.name_ar || c.name_en || c.code) + " — " + c.code;
    }, "select_customer");
    refreshProductSelects();
  }

  async function loadWarehouses(branchId) {
    var path = "/master/warehouses";
    if (branchId) path += "?branch_id=" + encodeURIComponent(branchId);
    state.warehouses = await api(path);
    fillSelect(el.warehouse, state.warehouses, function (w) {
      return (w.name_ar || w.name_en || w.code) + " — " + w.code;
    }, "select_warehouse");
  }

  function refreshProductSelects() {
    document.querySelectorAll("select[data-role='product']").forEach(function (select) {
      var current = select.value;
      fillSelect(select, state.products, productLabel, "select_product");
      select.value = current;
    });
  }

  // ----------------------------------------------------------- line editor
  function addLine(existing) {
    var index = existing ? existing.key : state.seq++;
    var line = existing || { key: index, productId: "", quantity: "1", discount: "0" };
    if (!existing) state.lines.push(line);

    var row = document.createElement("div");
    row.className = "line";
    row.dataset.key = String(index);

    var productField = document.createElement("div");
    productField.className = "field product";
    var productLabelEl = document.createElement("label");
    productLabelEl.textContent = t("product");
    productLabelEl.htmlFor = "line-product-" + index;
    var productSelect = document.createElement("select");
    productSelect.id = "line-product-" + index;
    productSelect.dataset.role = "product";
    productField.appendChild(productLabelEl);
    productField.appendChild(productSelect);

    var qtyField = document.createElement("div");
    qtyField.className = "field";
    var qtyLabel = document.createElement("label");
    qtyLabel.textContent = t("quantity");
    qtyLabel.htmlFor = "line-qty-" + index;
    var qtyInput = document.createElement("input");
    qtyInput.id = "line-qty-" + index;
    qtyInput.type = "number";
    qtyInput.min = "0.001";
    qtyInput.step = "0.001";
    qtyInput.value = line.quantity === "" || line.quantity === undefined ? "1" : String(line.quantity);
    qtyInput.dataset.role = "qty";
    qtyField.appendChild(qtyLabel);
    qtyField.appendChild(qtyInput);

    var discField = document.createElement("div");
    discField.className = "field";
    var discLabel = document.createElement("label");
    discLabel.textContent = t("discount_pct");
    discLabel.htmlFor = "line-disc-" + index;
    var discInput = document.createElement("input");
    discInput.id = "line-disc-" + index;
    discInput.type = "number";
    discInput.min = "0";
    discInput.max = "100";
    discInput.step = "0.01";
    discInput.value = line.discount === "" || line.discount === undefined ? "0" : String(line.discount);
    discInput.dataset.role = "disc";
    discField.appendChild(discLabel);
    discField.appendChild(discInput);

    var computed = document.createElement("div");
    computed.className = "computed num";
    computed.dataset.role = "computed";
    computed.textContent = "0.00";

    var remove = document.createElement("button");
    remove.type = "button";
    remove.className = "ghost danger";
    remove.textContent = "✕";
    remove.setAttribute("aria-label", t("remove_line"));
    remove.addEventListener("click", function () {
      state.lines = state.lines.filter(function (l) { return l.key !== index; });
      row.remove();
      recalcPreview();
    });

    row.appendChild(productField);
    row.appendChild(qtyField);
    row.appendChild(discField);
    row.appendChild(computed);
    row.appendChild(remove);
    el.lines.appendChild(row);

    fillSelect(productSelect, state.products, productLabel, "select_product");
    if (line.productId) productSelect.value = line.productId;
    productSelect.addEventListener("change", function () {
      var current = lineByKey(index); if (current) current.productId = productSelect.value;
      updateLine(index); recalcPreview();
    });
    qtyInput.addEventListener("input", function () {
      var current = lineByKey(index); if (current) current.quantity = qtyInput.value;
      updateLine(index); recalcPreview();
    });
    discInput.addEventListener("input", function () {
      var current = lineByKey(index); if (current) current.discount = discInput.value;
      updateLine(index); recalcPreview();
    });
    updateLine(index);
  }

  function rebuildLines() {
    el.lines.innerHTML = "";
    state.lines.forEach(function (line) { addLine(line); });
    recalcPreview();
  }

  function lineByKey(key) {
    for (var i = 0; i < state.lines.length; i++) {
      if (state.lines[i].key === key) return state.lines[i];
    }
    return null;
  }

  function updateLine(index) {
    var row = el.lines.querySelector("[data-key='" + index + "']");
    if (!row) return;
    var line = lineByKey(index);
    var calc = line ? linePreview(line) : null;
    row.querySelector("[data-role='computed']").textContent = calc ? fmt(calc.total) : "0.00";
  }

  // ------------------------------------------------------------- submit
  function collectLines() {
    var out = [];
    var incomplete = false;
    state.lines.forEach(function (line) {
      var hasProduct = Boolean(line.productId);
      var qty = Number(line.quantity);
      var hasQty = line.quantity !== "" && line.quantity !== undefined && !isNaN(qty) && qty > 0;
      if (!hasProduct && (line.quantity === "" || qty === 0)) return;  // untouched blank row
      if (!hasProduct || !hasQty) { incomplete = true; return; }       // half-filled row
      out.push({
        product_id: line.productId,
        quantity: String(line.quantity),
        discount_pct: line.discount ? String(line.discount) : "0",
      });
    });
    return { lines: out, incomplete: incomplete };
  }

  async function saveDraft(event) {
    event.preventDefault();
    clearError(el.formError);
    var customer = customerById(el.customer.value);
    if (!customer) return showError(el.formError, t("err_customer"));
    if (!el.invoiceNo.value.trim()) return showError(el.formError, t("err_invoice_no"));
    if (!el.warehouse.value) return showError(el.formError, t("err_warehouse"));
    var collected = collectLines();
    if (collected.incomplete) return showError(el.formError, t("err_line_incomplete"));
    var lines = collected.lines;
    if (!lines.length) return showError(el.formError, t("err_lines"));

    var payload = {
      invoice_no: el.invoiceNo.value.trim(),
      invoice_date: el.invoiceDate.value,
      branch_id: customer.branch_id,
      warehouse_id: el.warehouse.value,
      customer_id: customer.id,
      notes: el.notes.value.trim() || null,
      lines: lines,
    };

    el.saveDraft.disabled = true;
    try {
      var draft = await api("/invoices", { method: "POST", body: payload });
      renderDraft(draft);
    } catch (error) {
      showError(el.formError, messageFor(error));
    } finally {
      el.saveDraft.disabled = false;
    }
  }

  function badgeClass(status) {
    if (status === "Posted") return "badge posted";
    if (status === "Voided") return "badge voided";
    return "badge draft";
  }

  function renderDraft(draft) {
    state.draft = draft;
    el.draftNo.textContent = draft.invoice_no;
    el.draftCustomer.textContent = customerName(draft.customer_id);
    el.draftWarehouse.textContent = warehouseName(draft.warehouse_id);
    el.draftStatus.textContent = t("status_" + String(draft.posting_status).toLowerCase(), draft.posting_status);
    el.draftStatus.className = badgeClass(draft.posting_status);
    el.draftBefore.textContent = draft.total_before_discount;
    el.draftDiscount.textContent = draft.total_discount;
    el.draftNet.textContent = draft.total_net;
    el.draftVat.textContent = draft.vat_amount;
    el.draftGrand.textContent = draft.grand_total;

    el.draftLines.innerHTML = "";
    (draft.lines || []).forEach(function (line) {
      var tr = document.createElement("tr");
      var name = productById(line.product_id);
      [productLabel(name) || line.product_id, line.quantity, line.discount_pct, line.unit_price, line.line_total]
        .forEach(function (value, i) {
          var td = document.createElement("td");
          td.textContent = value;
          if (i > 0) td.className = "num";
          tr.appendChild(td);
        });
      el.draftLines.appendChild(tr);
    });

    clearError(el.draftError);
    el.appView.classList.add("hidden");
    el.draftView.classList.remove("hidden");
  }

  function customerName(id) {
    var customer = customerById(id);
    return customer ? (customer.name_ar || customer.name_en || customer.code) : id;
  }
  function warehouseName(id) {
    for (var i = 0; i < state.warehouses.length; i++) {
      if (state.warehouses[i].id === id) {
        var w = state.warehouses[i];
        return w.name_ar || w.name_en || w.code;
      }
    }
    return id;
  }

  async function postDraft() {
    if (!state.draft) return;
    clearError(el.draftError);
    el.postDraft.disabled = true;
    try {
      var draft = await api("/invoices/" + state.draft.id + "/post", { method: "POST" });
      renderDraft(draft);
    } catch (error) {
      showError(el.draftError, messageFor(error));
    } finally {
      el.postDraft.disabled = false;
    }
  }

  function newDraft() {
    el.invoiceForm.reset();
    state.lines = [];
    el.lines.innerHTML = "";
    el.branchDisplay.value = "";
    el.warehouse.innerHTML = "";
    addLine();
    recalcPreview();
    clearError(el.formError);
    el.draftView.classList.add("hidden");
    el.appView.classList.remove("hidden");
    el.invoiceNo.focus();
  }

  // --------------------------------------------------------------- auth
  async function boot() {
    el.me = await api("/auth/me");
    state.user = el.me;
    el.whoName.textContent = el.me.username;
    el.whoRole.textContent = el.me.role;
    el.who.classList.remove("hidden");
    el.logout.classList.remove("hidden");
    el.loginView.classList.add("hidden");
    el.appView.classList.remove("hidden");
    el.invoiceDate.value = todayLocal();
    el.invoiceNo.value = "INV-" + Date.now().toString().slice(-8);
    await loadMaster();
    newDraft();
    if (el.me.role === "read_only_auditor") {
      el.saveDraft.disabled = true;
      el.addLine.disabled = true;
      showNotice(el.formError, t("read_only_role"), "warn");
    }
  }

  async function login(event) {
    event.preventDefault();
    clearError(el.loginError);
    el.loginSubmit.disabled = true;
    try {
      var out = await api("/auth/login", {
        method: "POST",
        body: { username: el.loginUsername.value.trim(), password: el.loginPassword.value },
      });
      state.token = out.access_token;
      localStorage.setItem("token", state.token);
      el.loginPassword.value = "";
      await boot();
    } catch (error) {
      showError(el.loginError, messageFor(error));
    } finally {
      el.loginSubmit.disabled = false;
    }
  }

  async function logout() {
    try { await api("/auth/logout", { method: "POST" }); } catch (_e) { /* best effort */ }
    state.token = null;
    state.user = null;
    localStorage.removeItem("token");
    el.who.classList.add("hidden");
    el.logout.classList.add("hidden");
    el.draftView.classList.add("hidden");
    el.appView.classList.add("hidden");
    el.loginView.classList.remove("hidden");
  }

  // --------------------------------------------------------------- init
  function cacheElements() {
    el.loginView = $("login-view");
    el.appView = $("app-view");
    el.draftView = $("draft-view");
    el.loginForm = $("login-form");
    el.loginUsername = $("login-username");
    el.loginPassword = $("login-password");
    el.loginSubmit = $("login-submit");
    el.loginError = $("login-error");
    el.who = $("who");
    el.whoName = $("who-name");
    el.whoRole = $("who-role");
    el.logout = $("logout");
    el.invoiceForm = $("invoice-form");
    el.invoiceNo = $("invoice-no");
    el.invoiceDate = $("invoice-date");
    el.customer = $("customer");
    el.branchDisplay = $("branch-display");
    el.warehouse = $("warehouse");
    el.notes = $("notes");
    el.lines = $("lines");
    el.addLine = $("add-line");
    el.saveDraft = $("save-draft");
    el.formError = $("form-error");
    el.prevBefore = $("prev-before");
    el.prevDiscount = $("prev-discount");
    el.prevNet = $("prev-net");
    el.prevVat = $("prev-vat");
    el.prevGrand = $("prev-grand");
    el.draftNo = $("draft-no");
    el.draftStatus = $("draft-status");
    el.draftCustomer = $("draft-customer");
    el.draftWarehouse = $("draft-warehouse");
    el.draftLines = $("draft-lines");
    el.draftBefore = $("draft-before");
    el.draftDiscount = $("draft-discount");
    el.draftNet = $("draft-net");
    el.draftVat = $("draft-vat");
    el.draftGrand = $("draft-grand");
    el.draftError = $("draft-error");
    el.postDraft = $("post-draft");
    el.newDraft = $("new-draft");
    el.lang = $("lang");
  }

  function wire() {
    el.loginForm.addEventListener("submit", login);
    el.logout.addEventListener("click", logout);
    el.invoiceForm.addEventListener("submit", saveDraft);
    el.addLine.addEventListener("click", function () { addLine(); recalcPreview(); });
    el.postDraft.addEventListener("click", postDraft);
    el.newDraft.addEventListener("click", newDraft);
    el.customer.addEventListener("change", async function () {
      var customer = customerById(el.customer.value);
      el.branchDisplay.value = customer ? branchLabel(customer.branch_id) : "";
      clearError(el.formError);
      await loadWarehouses(customer ? customer.branch_id : null);
    });
    el.lang.addEventListener("click", function () {
      loadI18n(state.lang === "ar" ? "en" : "ar").then(function () {
        if (state.user) rebuildLines();
      });
    });
  }

  async function init() {
    cacheElements();
    await loadI18n(localStorage.getItem("lang") || "ar");
    wire();
    addLine();
    recalcPreview();
    var token = localStorage.getItem("token");
    if (token) {
      state.token = token;
      try { await boot(); } catch (_e) { await logout(); }
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
