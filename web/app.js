/* Medical Company System — web shell (vanilla JS PWA, per D37).
 *
 * Real screens are wired to the live backend endpoints; every unimplemented
 * capability is an explicit, labelled "نموذج أولي / Prototype" preview that
 * keeps its simulated state entirely client-side and never calls the API.
 * POSTING stays server-gated (409); a saved draft never mutates stock or AR.
 */
(function () {
  "use strict";

  var shellScript = document.currentScript && document.currentScript.src;
  var assetVersion = shellScript ? new URL(shellScript).searchParams.get("v") : "";

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
    invoiceNos: {},
    receiptNos: {},
    entries: null, // cached /ar/entries when role allows
  };

  var el = {};
  var dict = {};

  function $(id) { return document.getElementById(id); }
  function t(key, fallback) {
    return dict[key] !== undefined ? dict[key] : (fallback !== undefined ? fallback : key);
  }
  function todayLocal() {
    var now = new Date();
    return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
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
    document.querySelectorAll("[data-i18n-aria-label]").forEach(function (node) {
      var v = dict[node.dataset.i18nAriaLabel];
      if (v !== undefined) node.setAttribute("aria-label", v);
    });
  }

  async function loadI18n(lang) {
    state.lang = lang === "en" ? "en" : "ar";
    localStorage.setItem("lang", state.lang);
    var res = await fetch("i18n/" + state.lang + ".json" + (assetVersion ? "?v=" + encodeURIComponent(assetVersion) : ""));
    dict = await res.json();
    var input = $("palette-input");
    if (input) input.placeholder = t("search_placeholder");
    applyI18n();
  }

  // ------------------------------------------------------------ API client
  async function api(path, opts) {
    opts = opts || {};
    var requestToken = state.token;
    var headers = { "Content-Type": "application/json" };
    if (state.token) headers.Authorization = "Bearer " + state.token;
    var response = await fetch(path, {
      method: opts.method || "GET",
      headers: headers,
      signal: opts.signal,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    });
    var text = await response.text();
    var data = null;
    if (text) { try { data = JSON.parse(text); } catch (_e) { data = text; } }
    if (!response.ok) {
      var error = new Error("request_failed");
      error.status = response.status;
      error.data = data;
      if (response.status === 401 && requestToken && state.token === requestToken) {
        clearSession();
        showError(el.loginError, messageFor(error));
      }
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
  function showError(node, message) { showNotice(node, message, "error"); }
  function clearError(node) {
    node.textContent = "";
    node.classList.add("hidden");
  }

  // ------------------------------------------------------------- numbers
  function round2(n) { return Math.round((n + Number.EPSILON) * 100) / 100; }
  function fmt(n) { return (Math.round((Number(n) + Number.EPSILON) * 100) / 100).toFixed(2); }
  function fmtQty(n) { return String(Number(n)); }
  function fmtDate(value) { return value ? String(value).slice(0, 10) : "—"; }
  function shortId(id) { return id ? String(id).slice(0, 8) + "…" : "—"; }

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
  function branchById(id) {
    for (var i = 0; i < state.branches.length; i++) {
      if (state.branches[i].id === id) return state.branches[i];
    }
    return null;
  }
  function branchLabel(id) {
    var b = branchById(id);
    return b ? (b.name_ar || b.name_en || b.code) : shortId(id);
  }
  function productLabel(product) {
    if (!product) return "";
    return (product.name_ar || product.name_en || product.sku) + " — " + product.sku;
  }
  function customerLabel(c) { return c ? (c.name_ar || c.name_en || c.code) : "—"; }
  function customerName(id) { var c = customerById(id); return c ? customerLabel(c) : (id || "—"); }
  var warehouseLabels = {}; // id -> best-known label; never shrinks on a branch refill
  function rememberWarehouseLabels(warehouses) {
    warehouses.forEach(function (w) {
      var label = w.name_ar || w.name_en || w.code;
      if (!warehouseLabels[w.id] || label) warehouseLabels[w.id] = label;
    });
  }
  function warehouseLabel(id) {
    if (warehouseLabels[id]) return warehouseLabels[id];
    for (var i = 0; i < state.warehouses.length; i++) {
      var warehouse = state.warehouses[i];
      if (warehouse.id === id) return warehouse.name_ar || warehouse.name_en || warehouse.code;
    }
    return shortId(id);
  }
  function productLineLabel(id) {
    var product = productById(id);
    return product ? productLabel(product) : shortId(id);
  }
  function methodLabel(method) { return t("method_" + method, method); }
  function accountTypeLabel(v) { return t("at_" + v, v); }
  function movementTypeLabel(v) { return t("mv_" + v, v); }
  function entryTypeLabel(v) { return t("et_" + v, v); }

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
    if (!select) return;
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
    var requestToken = state.token;
    var canReadReferences = roleAllowed("invoice");
    var results = await Promise.all([
      canReadReferences ? api("/master/branches") : Promise.resolve([]),
      canReadReferences ? api("/master/customers") : Promise.resolve([]),
      canReadReferences ? api("/master/products") : Promise.resolve([]),
    ]);
    if (state.token !== requestToken) return;
    state.branches = results[0];
    state.customers = results[1];
    state.products = results[2];
    refreshProductSelects();
    refreshCustomerSelects();
    fillSelect(el.visitProduct, state.products, productLabel, "select_product");
    // Warehouse fill for the invoice — best effort (a few roles get 403; the
    // invoice then shows its "choose warehouse" validation instead of dying).
    loadWarehouses().catch(function () { /* keep manual-selection UX */ });
  }

  async function loadWarehouses(branchId) {
    var requestToken = state.token;
    var path = "/master/warehouses";
    if (branchId) path += "?branch_id=" + encodeURIComponent(branchId);
    var warehouses = await api(path);
    if (state.token !== requestToken) return;
    state.warehouses = warehouses;
    rememberWarehouseLabels(state.warehouses);
    refreshWarehouseSelects();
  }

  function refreshWarehouseSelects() {
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

  function refreshCustomerSelects() {
    ["customer", "visit-customer", "ledger-customer"].forEach(function (id) {
      var select = document.getElementById(id);
      if (!select) return;
      var current = select.value;
      fillSelect(select, state.customers, function (c) {
        return (c.name_ar || c.name_en || c.code) + " — " + (c.code || "");
      }, "select_customer");
      select.value = current;
    });
  }

  // =========================================================================
  // VIEW REGISTRY — the agreed APP_FLOW §1 tree with §10 role scoping.
  // `real:` true items map to dedicated sections hitting the live API; every
  // other key renders a clearly-labelled prototype preview (module-view).
  // =========================================================================
  var REAL_VIEWS = {
    home: "home-view", invoice: "invoice-view", inventory: "inventory-view",
    ledger: "ledger-view", invoicelist: "invoicelist-view", salesreport: "salesreport-view", balances: "balances-view", collections: "collections-view",
    customers: "customers-view", products: "products-view", warehouses: "warehouses-view",
    suppliers: "suppliers-view", accounts: "accounts-view", doctors: "doctors-view",
    visits: "visits-view", targets: "targets-view", batches: "batches-view",
    cover: "cover-view", inventoryalerts: "inventoryalerts-view", mgmtsummary: "mgmtsummary-view", audit: "audit-view", transfers: "transfers-view",
    returns: "returns-view", marketing: "marketing-view",
    privateaccounts: "private-view",
  };

  var ROLE_OK = {
    home: ["*"],
    invoice: ["owner", "finance", "medical_rep", "sales_manager", "district_manager", "read_only_auditor"],
    inventory: ["owner", "finance", "sales_manager", "district_manager", "read_only_auditor"],
    ledger: ["owner", "finance", "sales_manager", "district_manager", "read_only_auditor"],
    invoicelist: ["owner", "finance", "sales_manager", "district_manager", "medical_rep", "read_only_auditor"],
    salesreport: ["owner", "finance", "sales_manager", "district_manager", "medical_rep", "read_only_auditor"],
    balances: ["owner", "finance", "sales_manager", "district_manager", "read_only_auditor"],
    collections: ["owner", "finance", "sales_manager", "district_manager", "read_only_auditor"],
    customers: ["*"],
    products: ["*"],
    warehouses: ["*"],
    suppliers: ["owner", "finance", "read_only_auditor"],
    accounts: ["owner", "finance", "read_only_auditor"],
    doctors: ["owner", "finance", "medical_rep", "sales_manager", "read_only_auditor"],
    visits: ["owner", "medical_rep", "sales_manager", "district_manager", "read_only_auditor"],
    settings: ["owner", "finance"], audit: ["owner", "finance"],
    alerts: ["*"], import: ["owner", "finance"], pwa: ["*"],
    reference: ["owner", "finance"], batches: ["owner", "finance"],
    representatives: ["owner", "finance", "sales_manager", "district_manager", "medical_rep", "read_only_auditor"],
    uom: ["owner", "finance"], credit: ["owner", "finance", "sales_manager"],
    routing: ["owner", "medical_rep", "sales_manager"],
    transfers: ["owner", "finance", "sales_manager"],
    returns: ["owner", "medical_rep", "sales_manager"],
    targets: ["owner", "medical_rep", "sales_manager", "finance"],
    cover: ["owner", "finance", "sales_manager"], overstock: ["owner", "finance", "sales_manager"],
    inventoryalerts: ["owner", "finance", "sales_manager", "district_manager", "warehouse_staff", "read_only_auditor"],
    mgmtsummary: ["owner", "finance", "sales_manager", "district_manager", "read_only_auditor"],
    cash: ["owner", "finance"], expenses: ["owner", "finance"], pnl: ["owner", "finance"],
    payroll: ["owner", "finance"], brandspend: ["owner", "finance"],
    privateaccounts: ["owner"],
    objectives: ["owner", "finance", "sales_manager"], purchases: ["owner", "finance"],
    telegram: ["*"], analytics: ["*"],
  };

  function roleAllowed(view) {
    var allowed = ROLE_OK[view] || ["*"];
    if (allowed.indexOf("*") >= 0) return true;
    return state.user && allowed.indexOf(state.user.role) >= 0;
  }

  function applyRoleGating() {
    var role = state.user ? state.user.role : null;
    document.querySelectorAll("[data-roles]").forEach(function (node) {
      // Hide screens that are still labelled prototypes (empty PROTO views)
      // so everyday users never land on an empty placeholder.
      if (node.dataset.view && !REAL_VIEWS[node.dataset.view]) {
        node.classList.add("hidden");
        return;
      }
      var allowed = node.dataset.roles === "*" ? ["*"] : node.dataset.roles.split(",");
      var ok = allowed.indexOf("*") >= 0 || (role && allowed.indexOf(role) >= 0);
      if (node.classList.contains("bnav-btn")) {
        node.style.display = ok ? "" : "none";
      } else {
        node.classList.toggle("hidden", !ok);
      }
    });
  }

  // ------------------------------------------------------------- drawers
  var drawerOpen = false;
  function setDrawer(open) {
    drawerOpen = open;
    el.sidebar.classList.toggle("open", open);
    el.scrim.classList.toggle("show", open);
    el.menuToggle.setAttribute("aria-expanded", open ? "true" : "false");
  }

  // ------------------------------------------------------------- sections
  var currentSection = "login-view";

  function setActiveNav(name) {
    document.querySelectorAll(".nav-item, .bnav-btn").forEach(function (btn) {
      btn.classList.toggle("active", btn.dataset.view === name);
    });
  }

  // Every real section comes from REAL_VIEWS so new screens cannot be
  // forgotten here again; the remaining containers are the login form, the
  // saved-draft editor and the labelled prototype preview.
  var ALL_SECTIONS = Object.keys(REAL_VIEWS).map(function (key) {
    return REAL_VIEWS[key];
  }).concat(["login-view", "draft-view", "module-view"]);

  function hideAllSections() {
    ALL_SECTIONS.forEach(function (id) {
      var node = $(id);
      if (node) node.classList.add("hidden");
    });
  }

  function showView(name, fresh) {
    if (name === "__menu" || name === "draft") return;
    if (name === "login") {
      hideAllSections();
      el.loginView.classList.remove("hidden");
      currentSection = "login-view";
      setActiveNav("");
      return;
    }
    if (!roleAllowed(name)) {
      openPreview("note_no_access");
      return;
    }
    if (REAL_VIEWS[name]) {
      var section = $(REAL_VIEWS[name]);
      if (currentSection === REAL_VIEWS[name] && fresh !== true) {
        setActiveNav(name);
        return;
      }
      hideAllSections();
      section.classList.remove("hidden");
      currentSection = REAL_VIEWS[name];
      setActiveNav(name);
      if (drawerOpen) setDrawer(false);
      if (name === "home") loadHome();
      else if (name === "inventory") loadInventory();
      else if (name === "ledger") loadLedger();
      else if (name === "invoicelist") loadInvoiceList();
      else if (name === "salesreport") loadSalesReport();
      else if (name === "targets") loadTargets();
      else if (name === "batches") loadBatches();
      else if (name === "cover") loadCover();
      else if (name === "inventoryalerts") loadInventoryAlerts();
      else if (name === "mgmtsummary") loadManagementSummary();
      else if (name === "audit") loadAudit();
      else if (name === "transfers") loadTransfers();
      else if (name === "returns") loadReturns();
      else if (name === "marketing") loadMarketing();
      else if (name === "balances") loadBalances();
      else if (name === "collections") loadCollections();
      else if (name === "privateaccounts") loadPrivate();
      else if (name === "customers") loadCustomers();
      else if (name === "products") loadProducts();
      else if (name === "warehouses") loadWarehousesView();
      else if (name === "suppliers") loadSuppliers();
      else if (name === "accounts") loadAccounts();
      else if (name === "doctors") loadDoctors();
      else if (name === "visits") { loadVisits(); }
      else if (name === "invoice" && fresh) prepareNewDraft();
      return;
    }
    openPreview(name);
    if (drawerOpen) setDrawer(false);
  }

  // =========================================================================
  // PROTOTYPE PREVIEWS — static, clearly labelled, never calling the API.
  // =========================================================================
  function node(tag, className, text) {
    var n = document.createElement(tag);
    if (className) n.className = className;
    if (text !== undefined) n.textContent = text;
    return n;
  }

  function mkTable(cols, rows) {
    var wrap = node("div", "table-wrap");
    var table = node("table", "grid-table");
    var thead = node("thead");
    var trh = node("tr");
    cols.forEach(function (c) {
      var th = node("th", c.num ? "num" : "", c.label);
      trh.appendChild(th);
    });
    thead.appendChild(trh);
    var tbody = node("tbody");
    rows.forEach(function (r) {
      var tr = node("tr");
      r.forEach(function (cell, i) {
        var td = node("td", (cols[i] && cols[i].num ? "num" : "") + (cols[i] && cols[i].codes ? " codes" : ""), cell);
        td.setAttribute("data-label", cols[i].label);
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(thead);
    table.appendChild(tbody);
    wrap.appendChild(table);
    return wrap;
  }

  function previewChrome(kind, texts) {
    var box = node("div", "");
    var chips = node("div", "chip-row");
    chips.appendChild(node("span", "badge proto", t("badge_proto")));
    (texts.chipsExtra || []).forEach(function (c) { chips.appendChild(node("span", "badge " + (c[1] || "info"), c[0])); });
    box.appendChild(chips);
    return box;
  }

  function buildPreview(container, key) {
    var pc = (PROTON[key] && PROTON[key][state.lang]) || PROTON[key]["ar"];
    container.innerHTML = "";
    container.appendChild(previewChrome(key, pc));
    var h = node("h3", "", pc.h3);
    container.appendChild(h);
    var ul = node("ul");
    pc.bullets.forEach(function (b) {
      var liName = node("li", "muted");
      liName.innerHTML = "";
      liName.textContent = b;
      ul.appendChild(liName);
    });
    container.appendChild(ul);
    if (pc.cols && pc.rows) {
      var head = node("div", "note");
      head.textContent = t("prototype_sample_note");
      container.appendChild(head);
      container.appendChild(mkTable(pc.cols, pc.rows));
    }
    if (pc.note) {
      var n = node("div", "note");
      n.textContent = pc.note;
      container.appendChild(n);
    }
  }

  function openPreview(key) {
    hideAllSections();
    el.moduleView.classList.remove("hidden");
    currentSection = "module-view";
    setActiveNav(key);
    var pc = (PROTON[key] && PROTON[key][state.lang]) || (PROTON[key] && PROTON[key]["ar"]);
    if (!pc) { key = "analytics"; pc = PROTON[key][state.lang]; }
    el.moduleTitle.textContent = pc.title;
    el.moduleDesc.textContent = pc.desc;
    var badges = $("module-badges"); badges.innerHTML = "";
    badges.appendChild(node("span", "badge " + (key === "pwa" ? "real" : "proto"), key === "pwa" ? t("badge_real_status") : t("badge_proto")));
    if (key === "pwa") {
      buildPwaPreview(el.moduleContent);
    } else {
      buildPreview(el.moduleContent, key);
    }
  }

  /* Bilingual preview content — all sample values are illustrative only. */
  var PROTON = {
    note_no_access: {
      ar: {
        title: "غير متاح لدورك",
        desc: "هذه الشاشة غير مرئية لهذا الدور في هيكلة الصلاحيات المعتمدة.",
        h3: "دورك الحالي",
        bullets: ["تُحدد الأدوار (CEO/مالية/مبيعات/مستخدم ميداني) الوحدات الظاهرة لكل مستخدم.", "الخادم يتحقق من كل طلب بصرف النظر عما يظهر في القائمة."],
      },
      en: {
        title: "Not available for your role",
        desc: "This screen is hidden for this role in the approved permission model.",
        h3: "Your current role",
        bullets: ["Roles (CEO / finance / sales / field user) determine visible modules.", "The server enforces every request regardless of the shown menu."],
      },
    },
    settings: {
      ar: {
        title: "الإعدادات", desc: "إعدادات الشركة المالية: السنة المالية، ضريبة القيمة المضافة، بيانات الشركة، وتسلسلات الترقيم.",
        h3: "ما ستوفره الشاشة عند تنفيذها",
        bullets: ["السنة المالية (بداية/نهاية، مفتوحة/مغلقة) — الفترات المغلقة للقراءة فقط.",
          "ضريبة القيمة المضافة (النسبة، الرقم الضريبي)؛ النسبة المستخدمة حاليًا في العرض: 14%.",
          "بيانات الشركة (الاسم، العنوان، البطاقة الضريبية، السجل التجاري).",
          "تسلسلات الترقيم (فواتير، مستندات ائتمان، تحويلات، أوامر شراء)."],
        note: "لا توجد واجهات/نقاط خادم للإعدادات بعد — تفاصيلها موثقة في APP_FLOW A2.",
      },
      en: {
        title: "System settings", desc: "Company financial settings: fiscal year, VAT, company profile, and numbering sequences.",
        h3: "What this screen will provide",
        bullets: ["Fiscal year (start/end, open/closed) — closed periods read-only.",
          "VAT configuration (rate, registration number); the demo currently uses 14%.",
          "Company details (name, address, tax card, commercial registration).",
          "Numbering sequences (invoices, credit notes, transfers, purchase orders)."],
        note: "No settings endpoints exist yet — specified in APP_FLOW A2.",
      },
    },
    audit: {
      ar: {
        title: "سجل التدقيق", desc: "سجل غير قابل للتعديل لكل عملية (مستخدم، وقت، قيم قبل/بعد).",
        h3: "ما سيُسجل",
        bullets: ["إنشاء/تعديل/إبطال/اعتماد كل مستند مع القيم قبل وبعد.", "تسجيل الدخول الناجح/الفاشل مع IP والجهاز.", "عرض فقط — لا يوجد تعديل من الواجهة إطلاقًا."],
        cols: [{ label: "الوقت" }, { label: "المستخدم" }, { label: "العملية" }, { label: "المرجع" }],
        rows: [["2026-10-18 12:00", "demo_owner", "إنشاء", "فاتورة DEMO-INV-101"]],
        note: "قيم توضيحية فقط. الخادم يسجّل التدقيق داخليًا لكن لا توجد نقطة قراءة للسجل بعد.",
      },
      en: {
        title: "Audit log", desc: "Immutable log of every action (who, when, before/after values).",
        h3: "What gets recorded",
        bullets: ["Create/edit/void/approve for every document with old and new values.", "Login success/failure with IP and device.", "Strictly read-only."],
        cols: [{ label: "Time" }, { label: "User" }, { label: "Action" }, { label: "Reference" }],
        rows: [["2026-10-18 12:00", "demo_owner", "created", "Invoice DEMO-INV-101"]],
        note: "Illustrative values only. The server writes audit records internally but no read endpoint exists yet.",
      },
    },
    alerts: {
      ar: {
        title: "التنبيهات", desc: "مركز التنبيهات: مخزون منخفض/فائض، قرب انتهاء الصلاحية، تجاوز حد الائتمان، فاتورة متأخرة.",
        h3: "أنواع التنبيهات المتفق عليها",
        bullets: ["مخزون أقل من الحد الأدنى المُعد.", "فائض مخزون فوق حد أيام الغطاء.", "تشغيلات قريبة من انتهاء الصلاحية.", "تجاوز حد ائتمان العميل.", "فاتورة غير مسددة متأخرة."],
        cols: [{ label: "النوع" }, { label: "التفاصيل" }, { label: "القناة" }],
        rows: [["مخزون منخفض", "صنف تجريبي أ → تحت الحد", "داخل التطبيق"]],
        note: "نموذج أولي — قيم توضيحية؛ التوصيل للتليجرام اختياري لكل نوع (H2).",
      },
      en: {
        title: "Alerts", desc: "Alert center: low/overstock, near-expiry, credit-limit breach, overdue invoice.",
        h3: "The agreed alert types",
        bullets: ["Stock below configured minimum.", "Stock cover above threshold.", "Batches nearing expiry.", "Customer credit limit breach.", "Overdue unpaid invoice."],
        cols: [{ label: "Type" }, { label: "Detail" }, { label: "Channel" }],
        rows: [["Low stock", "DEMO-001 → under threshold", "In-app"]],
        note: "Prototype — illustrative values; Telegram delivery optional per alert type (H2).",
      },
    },
    import: {
      ar: {
        title: "الاستيراد (Excel/CSV)", desc: "تدفق الاستيراد اليدوي: رفع ملف، تحقق رأس بند/أنواع البيانات، أخطاء لكل صف، معاينة ثم تأكيد.",
        h3: "الخطوات",
        bullets: ["رفع ملف CSV/Excel.", "تحقق: الأعمدة المطلوبة، أنواع الحقول، القيم الناقصة.", "رسالة خطأ لكل صف + خيار إصلاح وإعادة المحاولة.", "معاينة نهائية ثم تأكيد الاستيراد."],
        note: "قاعدة التصدير (D29): الاستيراد من دفاتر إكسل الأصلية يتطلب مراجعة المالك ولا يُنفذ في هذا العرض إطلاقًا.",
      },
      en: {
        title: "Import (Excel/CSV)", desc: "Manual import flow: upload, header/data-type validation, row-level errors, preview then confirm.",
        h3: "Steps",
        bullets: ["Upload CSV/Excel file.", "Validate headers, data types, required fields.", "Row-level validation errors + fix & retry.", "Preview then confirm import."],
        note: "Per decision D29, importing from the original workbooks requires owner review and is never performed in this demo.",
      },
    },
    pwa: {
      ar: {
        title: "التطبيق على الهاتف/الجهاز (PWA)", desc: "معلومات حية عن حالة التطبيق على هذا المتصفح — بدون تثبيت من متجر.",
        h3: "الحالة الآن",
        bullets: [],
      },
      en: {
        title: "App on device (PWA)", desc: "Live status of the app in this browser — no store installation.",
        h3: "Status right now",
        bullets: [],
      },
    },
    reference: {
      ar: {
        title: "المجموعات المرجعية", desc: "فئات الأصناف، العلامات، مجموعات العملاء، فئات المصروفات، الحسابات الإيرادية.",
        h3: "ما ستدار فيه",
        bullets: ["فئات الأصناف والعلامات التجارية.", "مجموعات العملاء لأغراض الشرائح السعرية.", "فئات المصروفات وحسابات الإيراد لملء المستخدم في الوحدات الأخرى."],
        note: "لا يوجد نموذج بيانات لهذه المجموعات في قاعدة البيانات بعد (APP_FLOW B3).",
      },
      en: {
        title: "Reference sets", desc: "Product categories, brands, customer groups, expense categories, revenue accounts.",
        h3: "What it will manage",
        bullets: ["Product categories and brands.", "Customer groups for pricing tiers.", "Expense categories and revenue accounts feeding other modules."],
        note: "Not yet modelled in the database (APP_FLOW B3).",
      },
    },
    batches: {
      ar: {
        title: "التشغيلات والصلاحية", desc: "لكل صنف/مخزن: رقم تشغيلة، كمية، تاريخ إنتاج/انتهاء، وصرف FEFO — مرتبة تصاعديًا حسب الانتهاء.",
        h3: "القواعد المعتمدة",
        bullets: ["FEFO — الأنتهاء أولاً يخرج أولاً في البيع والتحويل.", "عرض الأصناف قرب الانتهاء مرتبة تصاعديًا.", "منع صرف تشغيلة منتهية؛ تحذير داخل نافذة قرب الانتهاء (العتبة قابلة للضبط، لا ثابت شنفه في الشفرة).", "التحقق الفعلي من الصلاحية مقابل تاريخ الفاتورة موجود الآن في ترحيل الفاتورة على الخادم."],
        cols: [{ label: "التشغيلة" }, { label: "الصنف" }, { label: "الانتهاء" }, { label: "الحالة" }, { label: "الكمية", num: true }],
        rows: [
          ["BAT-DEMO-X01", "صنف تجريبي أ", "2026-10-05", "منتهية — منع الصرف", "14"],
          ["BAT-DEMO-X07", "صنف تجريبي أ", "2026-11-30", "تحذير قرب الانتهاء (42 يوم)", "66"],
          ["BAT-DEMO-X12", "صنف تجريبي ب", "2027-01-15", "طبيعية (88 يوم)", "240"],
          ["BAT-DEMO-X09", "صنف تجريبي أ", "2027-03-01", "طبيعية (133 يوم)", "120"],
        ],
        note: "نموذج أولي بقيم توضيحية — لا يوجد نموذج تشغيلات/عرض صلاحية في قاعدة البيانات بعد (B4).",
      },
      en: {
        title: "Batches & expiry", desc: "Per product/warehouse: batch number, qty, produced/expiry dates, FEFO issue — sorted by expiry ascending.",
        h3: "The agreed rules",
        bullets: ["FEFO — first-expired-first-out on sales and transfers.", "'Stock by expiry' sorted ascending.", "Expired batch blocked from issue; near-expiry warning window (threshold configurable, never hardcoded).", "Real expiry-vs-invoice-date validation already exists server-side on posting."],
        cols: [{ label: "Batch" }, { label: "Product" }, { label: "Expiry" }, { label: "Status" }, { label: "Qty", num: true }],
        rows: [
          ["BAT-DEMO-X01", "DEMO-001", "2026-10-05", "Expired — blocked", "14"],
          ["BAT-DEMO-X07", "DEMO-001", "2026-11-30", "Near-expiry warning (42 days)", "66"],
          ["BAT-DEMO-X12", "DEMO-002", "2027-01-15", "Fine (88 days)", "240"],
          ["BAT-DEMO-X09", "DEMO-001", "2027-03-01", "Fine (133 days)", "120"],
        ],
        note: "Prototype with illustrative values — no batch/expiry-view model in the database yet (B4).",
      },
    },
    uom: {
      ar: {
        title: "وحدات القياس", desc: "تعريف الوحدات (عبوة، علبة، كرتون) ومعاملات التحويل لكل صنف.",
        h3: "القواعد",
        bullets: ["وحدة أساس واحدة لكل صنف.", "تعريف وحدات ثانوية مع معامل تحويل.", "رفض كمية لا تتوزع تحويلها بالتساوي إلى الأساس."],
        note: "لا يوجد جدول وحدات بعد (B5)؛ السعر الحالي في العرض لكل وحدة أساس.",
      },
      en: {
        title: "Units of measure", desc: "Define UOMs (each, box, carton) and per-product conversion factors.",
        h3: "Rules",
        bullets: ["One primary UOM per product.", "Secondary UOMs with conversion factors.", "Secondary quantities must convert cleanly."],
        note: "No UOM tables yet (B5); demo pricing is per primary unit.",
      },
    },
    credit: {
      ar: {
        title: "إدارة حدود الائتمان", desc: "حد ائتمان لكل عميل، الرصيد الحالي، المتاح، ومنع/تحذير عند تجاوز الحد.",
        h3: "ما سيحدث في الفاتورة",
        bullets: ["عرض المتاح من الائتمان أثناء إدخال الفاتورة.", "منع أو تحذير (قابل للضبط) عند تجاوز الحد.", "كشف أعمار الذمم + كشف حساب العميل (متوفرة الآن من قيود فعلية في شاشة الذمم)."],
        note: "حدود الائتمان غير ممثلة في البيانات التجريبية بعد (B6)؛ الرصيد الفعلي متاح في شاشة الذمم.",
      },
      en: {
        title: "Credit management", desc: "Per-customer credit limit, current outstanding, available balance, block/warn on breach.",
        h3: "In the invoice flow",
        bullets: ["Show available credit while typing the invoice.", "Block or warn (configurable) on breach.", "AR aging + customer statement (already real from ledger entries in the Receivables screen)."],
        note: "Credit limits are not represented in demo data yet (B6); real balances are on the Receivables screen.",
      },
    },
    representatives: {
      ar: {
        title: "المندوبون والمناطق", desc: "دليل المندوبين: منطقتهم الميدانية، المناطق الفرعية، العملاء المعتمدون، وفروع الميدان مقابل فرع الصرف (ميدان ≠ مخزن).",
        h3: "بيانات كل مندوب",
        bullets: ["المنطقة الميدانية واحدة؛ المناطق الفرعية متعددة داخلها.", "العملاء المعتمدون لكل مندوب تُدار من تعيينات المناطق.", "التوجيه للرفع يقرأ فرع الصرف — لا يُفترض تساوي الميدان مع المخزن (2B.1)."],
        cols: [{ label: "المندوب" }, { label: "الميدان" }, { label: "عدد العملاء", num: true }],
        rows: [["مندوب تجريبي", "الدقهلية", "14"], ["مندوب تجريبي ٢", "الشرقية", "9"]],
        note: "نموذج أولي — إدارة المندوبين والتعيينات (B-territories) ليست في شريحة البيانات الأساسية بعد.",
      },
      en: {
        title: "Representatives & territories", desc: "Rep directory: sales territory, sub-areas, assigned customers, and territory vs source-warehouse separation.",
        h3: "Per representative",
        bullets: ["One sales territory; multiple sub-areas inside it.", "Assigned customers managed through territory assignments.", "Fulfilment routing reads the source warehouse — territory is never assumed equal to warehouse (2B.1)."],
        cols: [{ label: "Representative" }, { label: "Territory" }, { label: "Customers", num: true }],
        rows: [["Demo rep", "Dakahlia", "14"], ["Demo rep 2", "Sharqia", "9"]],
        note: "Prototype — rep/assignment master-data management is not in the backend slice yet.",
      },
    },
    routing: {
      ar: {
        title: "توجيه المخازن", desc: "الميدان المصدر وطريق الصرف حقلا منفصلان؛ التوجيه تلقائي قابل للتجاوز من مدير المبيعات.",
        h3: "القواعد",
        bullets: ["ميدان العميل → أقرب مخزن متوفر به رصيد.", "الرجوع للمخزن الرئيسي عند عدم التوفر.", "إمكانية تجاوز التوجيه بواسطة مدير المبيعات."],
        orgBullets: ["الهيكلة: فرع ← مناطق بيع ← مجالات داخل المنطقة ← مندوبون.", "لكل مندوب مجال متعدد داخل منطقة واحدة ولمجال عملاء تابعين له.", "إدارة المجموعات كأصل بيانات أصلي يتشارك بين الوحدات (التغطية، المستهدفات، الفواتير)."],
        note: "لا يوجد منطق توجيه في الخادم بعد (C2)؛ اختيار المخزن في الفاتورة يدوي حتي تتم الأتمتة.",
      },
      en: {
        title: "Warehouse routing", desc: "Territory and source warehouse are separate fields; routing automatic, overridable.",
        h3: "Rules",
        bullets: ["Customer territory → nearest warehouse with stock.", "Fallback to main warehouse.", "Sales Manager override."],
        orgBullets: ["Hierarchy: branch → selling territories → areas within a territory → reps.", "A rep has multiple areas within one territory and assigned customers.", "Managed as a master-data set shared by coverage, targets and invoicing."],
        note: "No routing logic yet (C2); warehouse selection in the invoice is manual until automated.",
      },
    },
    transfers: {
      ar: {
        title: "تحويلات بين المخازن", desc: "حركات داخلية بين المخازن — ليست مبيعات؛ الحالة: مسودة ← أثناء النقل ← مستلم.",
        h3: "القواعد",
        bullets: ["مصدر + وجهة؛ البنود: صنف، تشغيلة اختيارية (تخصيص FEFO تلقائيًا)، كمية.", "الاستلام يضيف رصيد الوجهة ويخصم المصدر.", "سجل حركة باسم المشغل والتاريخ وخريطة التشغيلات."],
        note: "لا توجد نقاط خادم للتحويلات بعد (C3).",
      },
      en: {
        title: "Warehouse-to-warehouse transfers", desc: "Internal inventory movements — not sales; Draft → In Transit → Received.",
        h3: "Rules",
        bullets: ["Source + destination lines (product, optional batch with auto-FEFO, qty).", "Receive increments destination stock and decrements source.", "Recorded with operator, date, batch mapping."],
        note: "No transfers endpoints yet (C3).",
      },
    },
    returns: {
      ar: {
        title: "المرتجعات", desc: "مرتجع عميل صريح: عميل، صنف، تشغيلة، كمية، سبب مرمّز؛ إشعار ائتماني وتعديل الذمم.",
        h3: "الخطوات",
        bullets: ["اختيار العميل مع سحب فواتيره الأخيرة.", "اختيار الصنف/التشغيلة من ما استلمه العميل فعلًا.", "الكمية لا تتجاوز ما استلمه العميل فعلًا.", "الموافقة عند تجاوز حدها؛ ثم إشعار ائتماني يعدل الذمم."],
        note: "لا توجد نقاط خادم للمرتجعات بعد (C4)؛ أسباب الاعتباط المرتبطة موثقة في A5.",
      },
      en: {
        title: "Returns", desc: "Explicit customer return: customer, product, batch, qty, coded reason; credit note adjusts AR.",
        h3: "Steps",
        bullets: ["Pick customer, pull recent invoices.", "Product/batch limited to what the customer received.", "Return quantity capped by received quantity.", "Approval above threshold; credit note adjusts receivables."],
        note: "No returns endpoints yet (C4); reason codes specified in A5.",
      },
    },
    targets: {
      ar: {
        title: "المستهدفات", desc: "مستهدف لكل مندوب/ميدان/صنف/فترة مقابل المحقق الفعلي.",
        h3: "التفاصيل",
        bullets: ["شهري/ربع سنوي.", "المندوب يرى مستهدفه فقط؛ المدير ميدانه؛ الرئيس يرى الكل.", "شرائح تقدم في اللوحة الرئيسية عند وجود بيانات."],
        note: "لا يوجد نموذج مستهدفات بعد (C6).",
      },
      en: {
        title: "Sales targets", desc: "Target per rep/territory/product/period vs actual.",
        h3: "Details",
        bullets: ["Monthly / quarterly.", "Rep sees only their own; manager their area; CEO all.", "Progress bars on the dashboard once data exists."],
        note: "No targets model yet (C6).",
      },
    },
    cover: {
      ar: {
        title: "غطاء المخزون", desc: "أيام الغطاء = الرصيد الحالي ÷ متوسط البيع اليومي — نافذة الحساب الافتراضية 30 يومًا متحركًا (معتمدة D41، قابلة للضبط).",
        h3: "تصنيف",
        bullets: ["المتوسط اليومي يُحسب من نافذة 30 يومًا متحركًا (D41).", "غطاء منخفض → عتبة الطلب القابلة للضبط لكل صنف (UQ-5: لا افتراض عام ثابت).", "تظليل القيم الخطر بسلال التنبيه."],
        cols: [{ label: "الصنف", num: false }, { label: "الغطاء (يوم)", num: true }],
        rows: [["صنف تجريبي أ", "24"]],
        note: "نموذج بمعدلات توضيحية؛ متوسط البيع اليومي يحتاج سجل مبيعات أطول من بيانات العرض (D3).",
      },
      en: {
        title: "Stock cover", desc: "Days of cover = current stock ÷ average daily sales over a 30-day rolling window (D41 default, configurable).",
        h3: "Classification",
        bullets: ["Daily average computed from a 30-day rolling window (D41).", "Low cover → per-product configurable reorder threshold (UQ-5: no flat default).", "Threshold highlighting on watch list."],
        cols: [{ label: "Product" }, { label: "Cover (days)", num: true }],
        rows: [["DEMO-001", "24"]],
        note: "Prototype rates; computing real daily average needs a longer sales history (D3).",
      },
    },
    overstock: {
      ar: {
        title: "تنبيه فائض المخزون", desc: "تنبيه الأصناف التي تجاوز غطاؤها العتبة المعتمدة (180 يومًا — D41) مع إجراء التصريف.",
        h3: "الإجراءات",
        bullets: ["العتبة الافتراضية: غطاء يزيد عن 180 يومًا (D41)؛ قابلة للضبط لكل صنف أو على مستوى الشركة.", "تنبيه على اللوحة الرئيسية + تليجرام اختياري.", "إجراء: تحويل لمخزن التصريف."],
        note: "نموذج أولي — يحتاج بيانات فترة كاملة (D4).",
      },
      en: {
        title: "Overstock alerts", desc: "Alert products whose cover exceeds the approved threshold (180 days, D41) with disposal action.",
        h3: "Actions",
        bullets: ["Default threshold: cover above 180 days (D41); configurable per product or company-wide.", "Dashboard alert + optional Telegram.", "Action: transfer to clearance warehouse."],
        note: "Prototype — needs the full cover computation (D4).",
      },
    },
    cash: {
      ar: { title: "الصندوق والبنوك", desc: "خزائن نقد وحسابات بنكية؛ عمليات: إيداع/سحب/تحويل + تسوية كشف حساب.", h3: "النطاق", bullets: ["إدارة الحسابات (صندوق/بنك).", "معالجة الحركات وتسوية الكشف."]},
      en: { title: "Cash & bank", desc: "Cash tills and bank accounts; deposit/withdraw/transfer + reconciliation.", h3: "Scope", bullets: ["Manage cash/bank accounts.", "Process transactions and reconcile statements."]},
    },
    expenses: {
      ar: { title: "المصروفات والإيرادات", desc: "تصنيف من المجموعات المرجعية، موافقة فوق حد، ترحيل إلى الأرباح والخسائر.", h3: "الموافقات", bullets: ["حد الموافقة لكل فئة.", "رفق فاتورة (صورة من الهاتف)."],},
      en: { title: "Expenses & revenue", desc: "Category from reference sets, approval above threshold, posts to P&L.", h3: "Approvals", bullets: ["Per-category approval threshold.", "Attach receipt (phone camera)."]},
    },
    pnl: {
      ar: { title: "الأرباح والخسائر", desc: "إيرادات − مصروفات حسب الفترة; لكن الفترات المغلقة للقراءة فقط.", h3: "العلامة", bullets: ["شهري، ربع سنوي، حتى تاريخ السنة.", "سلطة الإغلاق للرئيس فقط."],},
      en: { title: "P&L & balance sheet", desc: "Revenue − expenses by period; closed years read-only.", h3: "Views", bullets: ["Monthly, quarterly, YTD.", "Fiscal close: CEO only."]},
    },
    payroll: {
      ar: {
        title: "الرواتب", desc: "دورة راتب شهري: تشغيل فترة؛ حساب صافي لكل موظف; مراجعة ثم اعتماد; قائمة دفع.",
        h3: "المعادلة المعتمدة",
        bullets: ["الصافي = الأساسي − (ضريبة/تأمين) + المتمرات.", "تشغيل/مراجعة/اعتماد ثم قائمة دفع."],
        cols: [{ label: "الموظف" }, { label: "الأساسي", num: true }, { label: "الخصومات", num: true }, { label: "الصافي", num: true }],
        rows: [["موظف تجريبي", "12,000.00", "2,400.00", "9,600.00"]],
        note: "نموذج توضيحي — تفعيل دورة الرواتب الكاملة مؤجل لبوابة قرار المالك (E4).",
      },
      en: {
        title: "Payroll", desc: "Monthly run: select period; auto net per employee; review → approve → payment list.",
        h3: "Formula",
        bullets: ["Net = base − deductions + allowances.", "Run → review → approve → payment list."],
        cols: [{ label: "Employee" }, { label: "Base", num: true }, { label: "Deductions", num: true }, { label: "Net", num: true }],
        rows: [["Demo employee", "12,000.00", "2,400.00", "0.00"]],
        note: "Illustrative model; full payroll activation is an owner gate (E4).",
      },
    },
    privateaccounts: {
      ar: {
        title: "الحسابات الخاصة", desc: "دفتر «حسابات خاصه» الحالي من الإكسل: حركات مالية داخلية لا تدخل في دفاتر شركة التوزيع.",
        h3: "ضوابط مؤقتة حتى قرار المالك",
        bullets: ["عرض فقط — لا تسجيل حركات في هذا النموذج.", "القرار المعتمد: نفس قاعدة البيانات، وحدة معزولة بمخطط وصلاحيات وتدقيق مستقل (D40).", "الوصول: المالك فقط؛ حركات الشركة (الذمم/المخزن) لا تلامس هذه الوحدة إطلاقًا."],
        cols: [{ label: "البيان" }, { label: "النوع" }, { label: "القيمة", num: true }],
        rows: [["حركة تجريبية", "تحويل", "5,000.00"]],
        note: "نموذج أولي وإحاطي فقط؛ تنفيذ الحد الأمني الفعلي (مخطط + صلاحيات + تدقيق) مطلوب في شريحة الحسابات الخاصة قبل أي تسجيل حقيقي.",
      },
      en: {
        title: "Private accounts", desc: "The current Excel 'hisaabat khassa' notebook: internal cash movements outside the distribution-company books.",
        h3: "Decided guardrails (D40)",
        bullets: ["View-only — no movements can be recorded in this prototype.", "Owner decision: same PostgreSQL database, isolated module with separate schema, permissions and audit.", "Access: owner only; company ledgers (AR/stock) never touch this module."],
        cols: [{ label: "Item" }, { label: "Type" }, { label: "Amount", num: true }],
        rows: [["Demo entry", "Transfer", "5,000.00"]],
        note: "Prototype preview only; the real security boundary (schema + permissions + audit) is a required deliverable of the private-accounts backend slice before any real recording.",
      },
    },
    kolspend: {
      ar: {
        title: "إنفاق الأطباء/KOL", desc: "كل نشاط ترويجي يُربط له: الطبيب، التخصص، الميدان/المنطقة، التاريخ، المبلغ، نوع النشاط، وملاحظات (2B.16).",
        h3: "حقول سجل الإنفاق",
        bullets: ["الربط للطبيب يتم من دليل الأطباء الفعلي أعلاه — لا إدخال حر للأسماء.", "النوع من مجموعات مرجعية (زيارة، عينة، لقاء علمي…) قابلة للضبط.", "الميدان يأتي من التعيينات الرسمية للمندوب لا من اختيار حر."],
        cols: [{ label: "الطبيب" }, { label: "التخصص" }, { label: "الميدان" }, { label: "النوع" }, { label: "التاريخ" }, { label: "المبلغ", num: true }],
        rows: [
          ["د. الطبيب التجريبي", "باطنة", "الدقهلية", "لقاء علمي", "2026-09-20", "1,200.00"],
          ["د. الطبيب التجريبي ٢", "جراحة", "الشرقية", "عينة", "2026-10-05", "450.00"],
        ],
        note: "نموذج توضيحي مرتبط بالدليل الفعلي أعلاه — لا يوجد سجل إنفاق في الخادم بعد (2B.16).",
      },
      en: {
        title: "Doctor / KOL spend", desc: "Every promotional activity links: doctor, specialty, area/territory, date, amount, activity type, notes (2B.16).",
        h3: "Spend record fields",
        bullets: ["Doctor linkage comes from the real directory above — no free-typed names.", "Type from configurable reference sets (visit, sample, scientific meeting...).", "Territory comes from official rep assignments, not free choice."],
        cols: [{ label: "Doctor" }, { label: "Specialty" }, { label: "Territory" }, { label: "Type" }, { label: "Date" }, { label: "Amount", num: true }],
        rows: [
          ["Dr. Demo doctor", "Internal medicine", "Dakahlia", "Scientific meeting", "2026-09-20", "1,200.00"],
          ["Dr. Demo doctor 2", "Surgery", "Sharqia", "Sample", "2026-10-05", "450.00"],
        ],
        note: "Illustrative prototype bound to the real directory above — no spend ledger on the server yet (2B.16).",
      },
    },
    brandspend: {
      ar: {
        title: "إنفاق المنتجات/العلامات", desc: "إنفاق مرتبط بصنف أو علامة: الحملة، النوع، التاريخ، المبلغ — رابط صارم منظم لا استنتاج من نص حر (2B.17).",
        h3: "حقول الربط المنظم",
        bullets: ["الربط بالمنتج/العلامة حقل منظم إلزامي لا يُستنتج لاحقًا من وصف حر (2B.17).", "التغذية من مصروفات النظام: المصنف، المبلغ، الموافقة فوق الحد.", "عرض مجمّع لكل علامة/صنف لمقارنة الإنفاق بالمبيعات."],
        cols: [{ label: "الحملة/النشاط" }, { label: "العلامة/الصنف" }, { label: "النوع" }, { label: "التاريخ" }, { label: "المبلغ", num: true }],
        rows: [
          ["حملة تجريبية — الدقهلية", "علامة تجريبية أ", "فساد طبي", "2026-09-14", "3,500.00"],
          ["زيارة تعريفية", "صنف تجريبي ب", "عينة", "2026-10-02", "800.00"],
        ],
        note: "نموذج توضيحي — لا يوجد سجل إنفاق مرتبط بالأصناف في الخادم بعد؛ القيم ليست من مصروفات فعلية.",
      },
      en: {
        title: "Product / brand spend", desc: "Spend linked to a product or brand: campaign, type, date, amount — an explicit structured link, never inferred from free text (2B.17).",
        h3: "Structured link fields",
        bullets: ["Product/brand linkage is a mandatory structured field, not inferred later from free text (2B.17).", "Fed from system expenses: classification, amount, above-threshold approval.", "Aggregated per brand/product to compare spend against sales."],
        cols: [{ label: "Campaign/activity" }, { label: "Brand/product" }, { label: "Type" }, { label: "Date" }, { label: "Amount", num: true }],
        rows: [
          ["Demo campaign — Dakahlia", "Demo brand A", "Medical visit", "2026-09-14", "3,500.00"],
          ["Intro visit", "Demo product B", "Sample", "2026-10-02", "800.00"],
        ],
        note: "Illustrative prototype — no product/brand-linked spend ledger on the server yet; values are not real expenses.",
      },
    },
    objectives: {
      ar: {
        title: "الأهداف و KPI", desc: "لكل نشاط تسويقي: الهدف، KPI المتوقع، النتيجة الفعلية، ملاحظات المتابعة، العلامة/الصنف، والطبيب/هدف النشاط عند وجوده (2B.18).",
        h3: "دورة النشاط",
        bullets: ["يُدخل الهدف والـ KPI المتوقع قبل النشاط؛ النتيجة الفعلية بعد الحملة.", "عائد مخصص أو معادلة فرق تقسيم — بلا نموذج ROI معقد في V1 (2B.18).", "نتائج النشاط تغذي تحليل عائد التسويق لاحقًا دون فرض نموذج معقد."],
        cols: [{ label: "النشاط" }, { label: "الهدف" }, { label: "KPI المتوقع" }, { label: "النتيجة الفعلية" }, { label: "المتابعة" }],
        rows: [
          ["حملة تجريبية — الدقهلية", "رفع مبيعات الصنف ب", "150 وحدة/شهر", "—" , "لم تبدأ"],
          ["زيارات تعريفية — الشرقية", "تعيين 10 أطباء", "10 أطباء", "7", "3 مواعيد متبقية"],
        ],
        note: "الخادم يخزن الهدف/KPI/النتيجة (GET /marketing/objectives). عرض النماذج للتوضيح فقط — سيتم ربط البيانات الفعلية لاحقًا.",
      },
      en: {
        title: "Objectives & KPIs", desc: "Per marketing activity: objective, expected KPI, actual result, follow-up notes, product/brand, and doctor/KOL or activity target where applicable (2B.18).",
        h3: "Activity cycle",
        bullets: ["Objective and expected KPI entered before the activity; actual result after the campaign.", "Custom ROI formula or variance split — no complex ROI model in V1 (2B.18).", "Results feed later marketing-ROI analysis without forcing a complex model."],
        cols: [{ label: "Activity" }, { label: "Objective" }, { label: "Expected KPI" }, { label: "Actual" }, { label: "Follow-up" }],
        rows: [
          ["Demo campaign — Dakahlia", "Lift product B sales", "150 units/month", "—", "Not started"],
          ["Intro visits — Sharqia", "Assign 10 doctors", "10 doctors", "7", "3 appointments left"],
        ],
        note: "Server stores objective/KPI/actual (GET /marketing/objectives). Prototype display only — live data binding pending.",
      },
    },
    purchases: {
      ar: {
        title: "أوامر الشراء", desc: "من المورّد، بنود بمواصفات وكميات وسعر، ثم استلام بضاعة بإنشاء تشغيلات بالمخزن.",
        h3: "الخطوات",
        bullets: ["أمر شراء → إرسال/مسودة.", "استلام بضاعة → تشغيلات في المخزن (FEFO).", "مطابقة فاتورة المورّد مع أمر الاستلام."],
        note: "لا توجد نقاط خادم للمشتريات بعد (G2).",
      },
      en: {
        title: "Purchase orders", desc: "Supplier PO with lines, then goods receipt creates batches in inventory.",
        h3: "Steps",
        bullets: ["PO → send / save draft.", "Receive goods → batches in inventory (FEFO).", "Match supplier invoice to PO + GRN."],
        note: "No purchasing endpoints yet (G2); basic visible to all, advanced by role.",
      },
    },
    telegram: {
      ar: { title: "تكامل تليجرام", desc: "ملخص مبيعات يومي لكل مخزن + دفع التنبيهات لقناتك.", h3: "التصميم المتفق", bullets: ["تليجرام أولًا ثم الواتساب لاحقًا (D6).", "ملخص نصي مختصر مع روابط للشاشات ذات العلاقة."]},
      en: { title: "Telegram integration", desc: "Daily per-warehouse sales summary + alert pushes.", h3: "Agreed design", bullets: ["Telegram first, WhatsApp later (D6).", "Compact text with links to relevant screens."]},
    },
    analytics: {
      ar: {
        title: "لوحة عبر الوحدات", desc: "مؤشرات متنوعة (مبيعات، تحصيل، ذمم، مخزون). النسخة الحالية قائمة على بيانات فعلية محدودة النطاق.",
        h3: "المتوفر الآن (بيانات فعلية)",
        bullets: ["مبيعات الشهر من قيود الفواتير المُرحّلة (لوحة الرئيسية).", "التحصيلات وأعمار الذمم من قيود الذمم.", "أرصدة المخزون وعدد الأصناف.", "بقية مؤشرات H1 (مبيعات بالفرع، Marketing vs KPI، وصافي الربح) تحتاج وحدات لم تُنفذ بعد."],
        note: "هذه الشاشة تطابق لوحة الرئيسية في النطاق الفعلي المتوفر حالى.",
      },
      en: {
        title: "Cross-module dashboard", desc: "Combined KPIs (sales, collections, AR, stock). Current build is real but limited.",
        h3: "Available now (real data)",
        bullets: ["Month sales from posted invoice entries (Home).", "Collections & AR aging from ledger entries.", "Stock balances and active product count.", "Remaining H1 widgets (sales by branch, marketing vs KPI, profit) need unbuilt modules."],
        note: "Matches the Home dashboard in currently-available real scope.",
      },
    },
  };

  /* PWA panel is REAL (live service-worker state) */
  function buildPwaPreview(container) {
    container.innerHTML = "";
    var chips = node("div", "chip-row");
    chips.appendChild(node("span", "badge real", t("badge_real_status")));
    container.appendChild(chips);
    container.appendChild(node("h3", "", t("pwa_status")));
    var ul = node("ul");
    var liInstalled = node("li", "muted", t("pwa_installed") + ": " + t("pwa_defer"));
    var liSw = node("li", "muted", t("pwa_sw_active") + ": " + t("pwa_sw_none"));
    var liCache = node("li", "muted", t("pwa_cache") + ": —");
    var liOffline = node("li", "muted", t("pwa_offline_note") + ": " + (navigator.onLine ? t("offline_no") : t("offline_yes")));
    ul.appendChild(liInstalled);
    ul.appendChild(liSw);
    ul.appendChild(liCache);
    ul.appendChild(liOffline);
    container.appendChild(ul);
    if (navigator.serviceWorker && navigator.serviceWorker.controller) {
      liSw.textContent = t("pwa_sw_active") + ": " + navigator.serviceWorker.controller.scriptURL.split("/").pop();
    }
    if (caches && caches.keys) {
      caches.keys().then(function (keys) {
        liCache.textContent = t("pwa_cache") + ": " + (keys.join(", ") || "—");
      }).catch(function () { liCache.textContent = t("pwa_cache") + ": —"; });
    }
    container.appendChild(node("h3", "", t("pwa_install_h")));
    var ol = node("ol");
    t("pwa_install_steps").split("||").forEach(function (s) { ol.appendChild(node("li", "", s)); });
    container.appendChild(ol);
    container.appendChild(node("div", "note", t("pwa_note")));
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
    qtyInput.inputMode = "decimal";
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
    discInput.inputMode = "decimal";
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
    computed.setAttribute("data-label", t("line_total"));
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
      rememberDraftLocally(draft);
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

  async function resolveInvoiceNo(id) {
    if (state.invoiceNos[id]) return state.invoiceNos[id];
    try {
      var invoice = await api("/invoices/" + id);
      state.invoiceNos[id] = invoice.invoice_no;
      return invoice.invoice_no;
    } catch (_e) {
      state.invoiceNos[id] = shortId(id);
      return state.invoiceNos[id];
    }
  }

  function computeAgingFor(entries, balance) {
    // FIFO-settle debits with credits; remaining open debits bucket by age.
    var open = [];
    entries.forEach(function (e) {
      if (Number(e.debit) > 0) open.push({ date: e.entry_date, amount: Number(e.debit) });
      if (Number(e.credit) > 0) {
        var left = Number(e.credit);
        for (var i = 0; i < open.length && left > 0; i++) {
          var use = Math.min(open[i].amount, left);
          open[i].amount -= use; left -= use;
        }
      }
    });
    open = open.filter(function (item) { return item.amount > 0.004; });
    var today = new Date();
    var buckets = [0, 0, 0, 0];
    open.forEach(function (item) {
      var age = Math.floor((today - new Date(item.date)) / 86400000);
      if (age <= 30) buckets[0] += item.amount;
      else if (age <= 60) buckets[1] += item.amount;
      else if (age <= 90) buckets[2] += item.amount;
      else buckets[3] += item.amount;
    });
    return { open: open, buckets: buckets, total: balance !== undefined ? Number(balance) : round2(buckets[0] + buckets[1] + buckets[2] + buckets[3]) };
  }

  function renderDraft(draft) {
    state.draft = draft;
    el.draftNo.textContent = draft.invoice_no;
    el.draftCustomer.textContent = customerName(draft.customer_id);
    el.draftWarehouse.textContent = warehouseName(draft.warehouse_id);
    el.draftDate.textContent = fmtDate(draft.invoice_date);
    el.draftStatus.textContent = t("status_" + String(draft.posting_status).toLowerCase(), draft.posting_status);
    el.draftStatus.className = badgeClass(draft.posting_status);
    el.draftBefore.textContent = fmt(draft.total_before_discount);
    el.draftDiscount.textContent = fmt(draft.total_discount);
    el.draftNet.textContent = fmt(draft.total_net);
    el.draftVat.textContent = fmt(draft.vat_amount);
    el.draftGrand.textContent = fmt(draft.grand_total);

    el.draftLines.innerHTML = "";
    (draft.lines || []).forEach(function (line) {
      var tr = document.createElement("tr");
      // Mark zero-quantity lines so the print stylesheet can hide them (2B.4).
      if (Number(line.quantity) === 0) tr.className = "zero-qty";
      var name = productById(line.product_id);
      var cells = [
        { label: t("product"), text: productLabel(name) || line.product_id },
        { label: t("quantity"), text: fmtQty(line.quantity), num: true },
        { label: t("unit_price"), text: fmt(line.unit_price), num: true },
        { label: t("line_total"), text: fmt(line.line_total), num: true },
      ];
      cells.forEach(function (cell) {
        var td = document.createElement("td");
        td.textContent = cell.text;
        td.setAttribute("data-label", cell.label);
        if (cell.num) td.className = "num";
        tr.appendChild(td);
      });
      el.draftLines.appendChild(tr);
    });

    clearError(el.draftError);
    hideAllSections();
    el.draftView.classList.remove("hidden");
    currentSection = "draft-view";
    setActiveNav("invoice");
  }

  function warehouseName(id) {
    for (var i = 0; i < state.warehouses.length; i++) {
      if (state.warehouses[i].id === id) {
        var w = state.warehouses[i];
        return w.name_ar || w.name_en || w.code;
      }
    }
    return id || "—";
  }

  async function postDraft() {
    if (!state.draft) return;
    clearError(el.draftError);
    el.postDraft.disabled = true;
    try {
      var draft = await api("/invoices/" + state.draft.id + "/post", { method: "POST" });
      renderDraft(draft);
    } catch (error) {
      // The 409 gate is part of the demo: show it verbatim; never fake success.
      showError(el.draftError, messageFor(error));
    } finally {
      el.postDraft.disabled = false;
    }
  }

  async function openSavedDraft(id) {
    clearError(el.draftError);
    try {
      var draft = await api("/invoices/" + id);
      renderDraft(draft);
    } catch (error) {
      forgetDraftLocally(id);
      showNotice(el.homeError, messageFor(error) + " — " + t("draft_registry_cleaned"), "warn");
      showView("home");
    }
  }

  // Local-only shortcut registry (explicitly labelled on Home).
  function readRegistry() {
    try { return JSON.parse(localStorage.getItem("medsys.drafts.v1") || "[]"); }
    catch (_e) { return []; }
  }
  function writeRegistry(rows) {
    try { localStorage.setItem("medsys.drafts.v1", JSON.stringify(rows.slice(0, 20))); } catch (_e) { }
  }
  function rememberDraftLocally(draft) {
    var rows = readRegistry().filter(function (r) { return r.id !== draft.id; });
    rows.unshift({
      id: draft.id, invoice_no: draft.invoice_no,
      customer: customerName(draft.customer_id),
      grand_total: draft.grand_total, saved_at: new Date().toISOString(),
    });
    writeRegistry(rows);
  }
  function forgetDraftLocally(id) {
    writeRegistry(readRegistry().filter(function (r) { return r.id !== id; }));
  }

  function newDraft() {
    el.invoiceForm.reset();
    // reset() also clears the boot-filled defaults — restore them, or every
    // fresh draft would save with an empty date (422 "input is too short").
    el.invoiceDate.value = todayLocal();
    el.invoiceNo.value = "INV-" + Date.now().toString().slice(-8);
    state.lines = [];
    el.lines.innerHTML = "";
    el.branchDisplay.value = "";
    el.warehouse.innerHTML = "";
    addLine();
    recalcPreview();
    clearError(el.formError);
    prepareNewDraftVm();
  }

  function prepareNewDraftVm() {
    clearError(el.formError);
    el.draftView.classList.add("hidden");
  }

  function prepareNewDraft() {
    newDraft();
    hideAllSections();
    el.invoiceView.classList.remove("hidden");
    currentSection = "invoice-view";
    setActiveNav("invoice");
  }

  // =========================================================================
  // REAL LOADERS
  // =========================================================================
  function renderRows(tbody, rows, build) {
    tbody.innerHTML = "";
    rows.forEach(function (row) { tbody.appendChild(build(row)); });
  }

  function cell(labelText, text, num, codes) {
    var td = document.createElement("td");
    td.textContent = text;
    td.setAttribute("data-label", labelText);
    td.className = (num ? "num " : "") + (codes ? "codes" : "");
    return td;
  }
  function badgeCell(labelText, text, cls) {
    var td = document.createElement("td");
    td.setAttribute("data-label", labelText);
    var span = document.createElement("span");
    span.className = cls;
    span.textContent = text;
    td.appendChild(span);
    return td;
  }

  function emptyRow(tbody, colCount, messageKey) {
    var tr = document.createElement("tr");
    tr.className = "row-empty";
    var td = document.createElement("td");
    td.colSpan = colCount;
    td.textContent = t(messageKey);
    tr.appendChild(td);
    tbody.appendChild(tr);
  }

  function receiptRow(withColumns, labels) {
    return function (row) {
      var tr = document.createElement("tr");
      tr.appendChild(cell(labels.no, row.receipt_no, false, true));
      tr.appendChild(cell(labels.date, fmtDate(row.receipt_date), true));
      if (withColumns) {
        tr.appendChild(cell(labels.invoice, state.invoiceNos[row.invoice_id] || "…"));
        tr.appendChild(cell(labels.customer, customerName(row.customer_id)));
        tr.appendChild(cell(labels.method, methodLabel(row.method)));
      } else {
        tr.appendChild(cell(labels.invoice, state.invoiceNos[row.invoice_id] || "…"));
        tr.appendChild(cell(labels.method, methodLabel(row.method)));
      }
      tr.appendChild(cell(labels.amount, fmt(row.amount), true));
      if (withColumns) {
        tr.appendChild(badgeCell(labels.status, t("badge_active", row.status), "badge posted"));
      }
      return tr;
    };
  }

  async function loadEntriesIfAllowed() {
    if (state.entries) return state.entries;
    try {
      state.entries = await api("/ar/entries");
      return state.entries;
    } catch (_e) {
      state.entries = [];
      return state.entries;
    }
  }

  async function loadReceiptsIntoCache() {
    try {
      var rows = await api("/collections");
      state.receiptNos = {};
      rows.forEach(function (r) { state.receiptNos[r.id] = r.receipt_no; });
      return rows;
    } catch (_e) {
      state.receiptNos = {};
      return [];
    }
  }

  function monthWindow() {
    var now = new Date();
    var first = new Date(now.getFullYear(), now.getMonth(), 1);
    return [first, now];
  }

  // Count-up KPI numbers (reference pattern); skipped for reduced-motion users.
  function animateCount(nodeEl, target, format) {
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      nodeEl.textContent = format(target);
      return;
    }
    var start = null, dur = 600;
    function step(ts) {
      if (start === null) start = ts;
      var k = Math.min((ts - start) / dur, 1);
      var eased = 1 - Math.pow(1 - k, 3);
      nodeEl.textContent = format(target * eased);
      if (k < 1) requestAnimationFrame(step);
      else nodeEl.textContent = format(target);
    }
    requestAnimationFrame(step);
  }

  function loadHome() {
    clearError(el.homeError);
    [el.statAr, el.statStock, el.statReceipts, el.statSales].forEach(function (n) { n.textContent = "—"; });
    var labels = {
      no: t("receipt_no"), date: t("receipt_date"), invoice: t("invoice_no"),
      customer: t("customer"), method: t("method"), amount: t("amount"), status: t("status"),
    };
    renderRows(el.homeReceipts, [], function () { return null; });
    Promise.all([
      api("/ar/balances"), api("/collections"), api("/inventory/stock").catch(function () { return []; })
    ]).then(function (results) {
      state.balancesCache = results[0];
      var receipts = results[1];
      var stock = results[2];
      var open = state.balancesCache.filter(function (row) { return Number(row.balance) > 0.004; });
      el.statArSub.textContent = t("stat_ar_sub") + " " + open.length;
      animateCount(el.statAr, open.reduce(function (total, row) {
        return total + Number(row.balance);
      }, 0), fmt);
      el.statStockSub.textContent = t("stat_stock_sub") + " " + String(state.products.length);
      animateCount(el.statStock, stock.reduce(function (total, row) {
        return total + Number(row.quantity);
      }, 0), fmtQty);
      el.statReceiptsSub.textContent = t("stat_receipts_sub") + " " + receipts.length;
      animateCount(el.statReceipts, receipts.reduce(function (total, row) {
        return total + Number(row.amount);
      }, 0), fmt);
      var recent = receipts.slice().sort(function (a, b) {
        return String(b.receipt_date).localeCompare(String(a.receipt_date));
      }).slice(0, 5);
      return Promise.all(recent.map(function (r) {
        return state.invoiceNos[r.invoice_id] ? null : resolveInvoiceNo(r.invoice_id);
      })).then(function () {
        renderRows(el.homeReceipts, recent, receiptRow(false, labels));
      });
    }).catch(function (error) { showError(el.homeError, messageFor(error)); });

    // Real-entries based widgets (role permitting) are additive: failures here
    // never block the core tiles above.
    loadReceiptsIntoCache().then(loadEntriesIfAllowed).then(function (entries) {
      var win = monthWindow();
      var sales = 0, invoicesCount = 0;
      entries.forEach(function (e) {
        if (e.entry_type !== "invoice") return;
        var d = new Date(e.entry_date);
        if (d >= win[0] && d <= win[1]) { sales += Number(e.debit); invoicesCount += 1; }
      });
      el.statSalesSub.textContent = t("stat_sales_sub") + " " + invoicesCount;
      animateCount(el.statSales, sales, fmt);
      // AR aging strip across all customers (owner/finance).
      var buckets = [0, 0, 0, 0];
      (state.balancesCache || []).forEach(function (b) {
        if (Number(b.balance) <= 0.004) return;
        var ag = computeAgingFor(entries.filter(function (e) { return e.customer_id === b.customer_id; }), b.balance);
        for (var i = 0; i < 4; i++) buckets[i] += ag.buckets[i];
      });
      var strip = $("home-aging");
      strip.innerHTML = "";
      [["a_0_30", 0, ""], ["a_31_60", 1, ""], ["a_61_90", 2, "warn"], ["a_90p", 3, "bad"]].forEach(function (def) {
        var cellEl = document.createElement("span");
        cellEl.className = "aging-cell" + (def[2] ? " " + def[2] : "");
        cellEl.appendChild(node("span", "small muted", t(def[0])));
        cellEl.appendChild(node("span", "num aging-v", fmt(buckets[def[1]])));
        strip.appendChild(cellEl);
      });
    });

    renderHomeDrafts();
  }

  function renderHomeDrafts() {
    var labels = { no: t("invoice_no"), customer: t("customer"), total: t("grand_total") };
    var rows = readRegistry();
    el.homeDrafts.innerHTML = "";
    if (!rows.length) { emptyRow(el.homeDrafts, 4, "home_drafts_empty"); return; }
    rows.forEach(function (r) {
      var tr = document.createElement("tr");
      tr.appendChild(cell(labels.no, r.invoice_no, false, true));
      tr.appendChild(cell(labels.customer, r.customer));
      tr.appendChild(cell(labels.total, fmt(r.grand_total), true));
      var td = document.createElement("td");
      td.setAttribute("data-label", t("open"));
      var open = document.createElement("button");
      open.type = "button";
      open.className = "default";
      open.textContent = t("open");
      open.addEventListener("click", function () { openSavedDraft(r.id); });
      td.appendChild(open);
      tr.appendChild(td);
      el.homeDrafts.appendChild(tr);
    });
  }

  function loadInventory() {
    clearError(el.inventoryError);
    var labels = { wh: t("warehouse"), prod: t("product"), qty: t("quantity"), up: t("updated_at") };
    return api("/inventory/stock").then(function (rows) {
      renderRows(el.stockRows, rows, function (row) {
        var tr = document.createElement("tr");
        tr.appendChild(cell(labels.wh, warehouseLabel(row.warehouse_id)));
        tr.appendChild(cell(labels.prod, productLineLabel(row.product_id)));
        tr.appendChild(cell(labels.qty, fmtQty(row.quantity), true));
        tr.appendChild(cell(labels.up, fmtDate(row.updated_at), true));
        return tr;
      });
      if (!rows.length) emptyRow(el.stockRows, 4, "empty_rows");
    }).catch(function (error) {
      renderRows(el.stockRows, [], function () { return null; });
      emptyRow(el.stockRows, 4, "empty_rows");
      showError(el.inventoryError, messageFor(error));
    });
  }

  function loadInvoiceList() {
    clearError(el.invoicelistError);
    var qs = "?limit=50";
    if (el.ilStatus.value) qs += "&status=" + encodeURIComponent(el.ilStatus.value);
    if (el.ilFrom.value) qs += "&date_from=" + el.ilFrom.value;
    if (el.ilTo.value) qs += "&date_to=" + el.ilTo.value;
    el.invoiceRows.innerHTML = "";
    var loading = document.createElement("tr");
    var tdLoad = document.createElement("td");
    tdLoad.colSpan = 6; tdLoad.className = "muted"; tdLoad.textContent = "…";
    loading.appendChild(tdLoad);
    el.invoiceRows.appendChild(loading);
    return api("/invoices" + qs).then(function (data) {
      var labels = { no: t("invoice_no"), d: t("invoice_date"), c: t("customer"), g: t("grand_total"), s: t("il_status"), o: t("open") };
      if (!data.items.length) { emptyRow(el.invoiceRows, 6, "empty_rows"); return; }
      renderRows(el.invoiceRows, data.items, function (row) {
        var tr = document.createElement("tr");
        tr.appendChild(cell(labels.no, row.invoice_no, false, true));
        tr.appendChild(cell(labels.d, fmtDate(row.invoice_date)));
        tr.appendChild(cell(labels.c, customerName(row.customer_id)));
        tr.appendChild(cell(labels.g, fmt(row.grand_total), true));
        var td = document.createElement("td");
        td.setAttribute("data-label", labels.s);
        td.appendChild(Object.assign(document.createElement("span"), { className: "badge " + badgeClass(row.posting_status), textContent: row.posting_status }));
        tr.appendChild(td);
        var open = document.createElement("td");
        open.setAttribute("data-label", labels.o);
        var btn = document.createElement("button");
        btn.type = "button"; btn.className = "default"; btn.textContent = t("open");
        btn.addEventListener("click", function () { openSavedDraft(row.id); });
        open.appendChild(btn);
        tr.appendChild(open);
        return tr;
      });
    }).catch(function (error) { showError(el.invoicelistError, messageFor(error)); });
  }

  var salesReportSeq = 0;

  function loadSalesReport() {
    var requestToken = state.token;
    var seq = ++salesReportSeq;
    clearError(el.srError);
    var qs = "";
    if (el.srFrom.value) qs += (qs ? "&" : "?") + "date_from=" + el.srFrom.value;
    if (el.srTo.value) qs += (qs ? "&" : "?") + "date_to=" + el.srTo.value;
    [el.srTotalsRows, el.srTerritoryRows, el.srRepRows, el.srProductRows].forEach(function (body) {
      body.innerHTML = "";
    });
    return api("/invoices/report" + qs).then(function (report) {
      if (!state.user || state.token !== requestToken || seq !== salesReportSeq) return;
      var totals = report.totals;
      var labels = {
        count: t("invoices_count"), net: t("total_net"), vat: t("vat_amount"),
        grand: t("grand_total"), qty: t("quantity"), line: t("line_total"),
      };
      var totalsRow = document.createElement("tr");
      totalsRow.appendChild(cell(labels.count, String(totals.invoice_count), true));
      totalsRow.appendChild(cell(labels.net, fmt(totals.total_net), true));
      totalsRow.appendChild(cell(labels.vat, fmt(totals.vat_amount), true));
      totalsRow.appendChild(cell(labels.grand, fmt(totals.grand_total), true));
      el.srTotalsRows.appendChild(totalsRow);
      if (!totals.invoice_count) {
        emptyRow(el.srTerritoryRows, 5, "sr_empty");
        emptyRow(el.srRepRows, 5, "sr_empty");
        emptyRow(el.srProductRows, 4, "sr_empty");
        return;
      }
      renderRows(el.srTerritoryRows, report.by_territory, function (row) {
        var tr = document.createElement("tr");
        tr.appendChild(cell(t("territory"), row.name_ar + " (" + row.code + ")", false, true));
        tr.appendChild(cell(labels.count, String(row.invoice_count), true));
        tr.appendChild(cell(labels.net, fmt(row.total_net), true));
        tr.appendChild(cell(labels.vat, fmt(row.vat_amount), true));
        tr.appendChild(cell(labels.grand, fmt(row.grand_total), true));
        return tr;
      });
      renderRows(el.srRepRows, report.by_rep, function (row) {
        var tr = document.createElement("tr");
        tr.appendChild(cell(t("rep"), row.username, false, true));
        tr.appendChild(cell(labels.count, String(row.invoice_count), true));
        tr.appendChild(cell(labels.net, fmt(row.total_net), true));
        tr.appendChild(cell(labels.vat, fmt(row.vat_amount), true));
        tr.appendChild(cell(labels.grand, fmt(row.grand_total), true));
        return tr;
      });
      renderRows(el.srProductRows, report.by_product, function (row) {
        var tr = document.createElement("tr");
        tr.appendChild(cell(t("product"), row.name_ar + " (" + row.sku + ")", false, true));
        tr.appendChild(cell(labels.qty, fmtQty(row.quantity), true));
        tr.appendChild(cell(labels.line, fmt(row.line_total), true));
        tr.appendChild(cell(labels.vat, fmt(row.vat_amount), true));
        return tr;
      });
    }).catch(function (error) {
      if (state.token !== requestToken || seq !== salesReportSeq) return;
      showError(el.srError, messageFor(error));
    });
  }

  function loadTargets() {
    clearError(el.targetsError);
    el.targetRows.innerHTML = "";
    var loading = document.createElement("tr");
    var tdLoad = document.createElement("td");
    tdLoad.colSpan = 5; tdLoad.className = "muted"; tdLoad.textContent = "…";
    loading.appendChild(tdLoad);
    el.targetRows.appendChild(loading);
    return api("/targets").then(function (rows) {
      if (!rows.length) { emptyRow(el.targetRows, 5, "empty_rows"); return; }
      renderRows(el.targetRows, rows, function (row) {
        var tr = document.createElement("tr");
        tr.appendChild(cell("rep", row.rep_id));
        tr.appendChild(cell("product", row.product_id ? productLineLabel(row.product_id) : "—"));
        tr.appendChild(cell("period", fmtDate(row.period_month)));
        tr.appendChild(cell("target", fmtQty(row.target_quantity), true));
        var actual = row.actual_quantity == null ? "—" : fmtQty(row.actual_quantity);
        tr.appendChild(cell("actual", actual, true));
        return tr;
      });
    }).catch(function (error) { showError(el.targetsError, messageFor(error)); });
  }

  function loadLedger() {
    clearError(el.ledgerError);
    var labels = { d: t("mv_date"), ty: t("mv_type"), wh: t("warehouse"), p: t("product"), q: t("quantity"), n: t("notes") };
    return api("/inventory/movements").then(function (rows) {
      rows = rows.slice().sort(function (a, b) { return String(b.created_at).localeCompare(String(a.created_at)); });
      renderRows(el.movementRows, rows, function (row) {
        var tr = document.createElement("tr");
        tr.appendChild(cell(labels.d, fmtDate(row.created_at), true));
        tr.appendChild(cell(labels.ty, movementTypeLabel(row.movement_type)));
        tr.appendChild(cell(labels.wh, warehouseLabel(row.warehouse_id)));
        tr.appendChild(cell(labels.p, productLineLabel(row.product_id)));
        tr.appendChild(cell(labels.q, fmtQty(row.quantity), true));
        tr.appendChild(cell(labels.n, row.note || "—"));
        return tr;
      });
      if (!rows.length) emptyRow(el.movementRows, 6, "empty_rows");
    }).catch(function (error) {
      renderRows(el.movementRows, [], function () { return null; });
      emptyRow(el.movementRows, 6, "empty_rows");
      showError(el.ledgerError, messageFor(error));
    });
  }

  function loadBatches() {
    clearError(el.batchesError);
    el.batchRows.innerHTML = "";
    var loading = document.createElement("tr");
    var tdLoad = document.createElement("td");
    tdLoad.colSpan = 5; tdLoad.className = "muted"; tdLoad.textContent = "…";
    loading.appendChild(tdLoad);
    el.batchRows.appendChild(loading);
    return api("/inventory/batches").then(function (rows) {
      if (!rows.length) { emptyRow(el.batchRows, 5, "empty_rows"); return; }
      renderRows(el.batchRows, rows, function (row) {
        var tr = document.createElement("tr");
        tr.appendChild(cell("batch", row.batch_no));
        tr.appendChild(cell("product", productLineLabel(row.product_id)));
        tr.appendChild(cell("warehouse", warehouseLabel(row.warehouse_id)));
        tr.appendChild(cell("expiry", fmtDate(row.expiry_date)));
        tr.appendChild(cell("qty", fmtQty(row.quantity), true));
        return tr;
      });
    }).catch(function (error) { showError(el.batchesError, messageFor(error)); });
  }

  function loadCover() {
    clearError(el.coverError);
    el.coverRows.innerHTML = "";
    var loading = document.createElement("tr");
    var tdLoad = document.createElement("td");
    tdLoad.colSpan = 6; tdLoad.className = "muted"; tdLoad.textContent = "…";
    loading.appendChild(tdLoad);
    el.coverRows.appendChild(loading);
    return api("/inventory/cover").then(function (rows) {
      if (!rows.length) { emptyRow(el.coverRows, 6, "empty_rows"); return; }
      renderRows(el.coverRows, rows, function (row) {
        var tr = document.createElement("tr");
        tr.appendChild(cell("wh", warehouseLabel(row.warehouse_id)));
        tr.appendChild(cell("product", productLineLabel(row.product_id)));
        tr.appendChild(cell("onhand", fmtQty(row.on_hand), true));
        tr.appendChild(cell("sold", row.sold_in_window == null ? "—" : fmtQty(row.sold_in_window), true));
        tr.appendChild(cell("cover", row.cover_days == null ? "—" : fmtQty(row.cover_days), true));
        var td = document.createElement("td");
        td.appendChild(Object.assign(document.createElement("span"), { className: "badge " + (row.status === "overstock" ? "posted" : "draft"), textContent: row.status }));
        tr.appendChild(td);
        return tr;
      });
    }).catch(function (error) { showError(el.coverError, messageFor(error)); });
  }

  // Inventory alerts: the approved overstock rule plus cover days as the
  // replenishment indicator. Rows come from GET /inventory/cover; the policy
  // line from GET /settings/inventory-policy (absent for roles that may read
  // cover but not settings, e.g. warehouse staff).
  var invalertsData = [];
  var invalertsSeq = 0;
  var invalertsPolicyData = null;

  function renderInvalertsPolicyText() {
    if (!invalertsPolicyData) {
      el.invalertsPolicy.classList.add("hidden");
      return;
    }
    el.invalertsPolicy.textContent =
      t("invalerts_policy_window") + " " + invalertsPolicyData.stock_cover_window_days +
      " · " + t("invalerts_policy_threshold") + " " + invalertsPolicyData.overstock_threshold_days;
    el.invalertsPolicy.classList.remove("hidden");
  }

  function loadInventoryAlerts() {
    var requestToken = state.token;
    clearError(el.invalertsError);
    var seq = ++invalertsSeq;
    el.invalertsRows.innerHTML = "";
    var loading = document.createElement("tr");
    var tdLoad = document.createElement("td");
    tdLoad.colSpan = 7; tdLoad.className = "muted"; tdLoad.textContent = "…";
    loading.appendChild(tdLoad);
    el.invalertsRows.appendChild(loading);
    el.invalertsPolicy.classList.add("hidden");
    return Promise.all([
      api("/inventory/cover"),
      api("/settings/inventory-policy").catch(function () { return null; }),
    ]).then(function (results) {
      if (state.token !== requestToken || seq !== invalertsSeq) return; // a newer refresh owns the table
      invalertsData = results[0] || [];
      invalertsPolicyData = results[1];
      renderInvalertsPolicyText();
      renderInventoryAlerts();
    }).catch(function (error) {
      if (state.token !== requestToken || seq !== invalertsSeq) return;
      invalertsData = [];
      invalertsPolicyData = null;
      renderInvalertsPolicyText();
      renderInventoryAlerts();
      showError(el.invalertsError, messageFor(error));
    });
  }

  function invalertsStatusLabel(status) {
    if (status === "overstock") return t("invalerts_st_overstock", "overstock");
    if (status === "no_sales_history") return t("invalerts_st_nohist", "no sales history");
    return t("invalerts_st_ok", "ok");
  }

  function invalertsBadgeClass(status) {
    if (status === "overstock") return "draft";   // amber warning
    if (status === "no_sales_history") return "info";
    return "posted";
  }

  function renderInventoryAlerts() {
    var labels = {
      product: t("product"), warehouse: t("warehouse"), onhand: t("on_hand"),
      sold: t("sold_in_window"), avg: t("invalerts_avg_daily"),
      cover: t("cover_days"), status: t("status"),
    };
    var statusFilter = el.invalertsStatus.value;
    var query = el.invalertsSearch.value.trim().toLowerCase();
    var sort = el.invalertsSort.value;
    var rows = invalertsData.filter(function (row) {
      if (statusFilter !== "all" && row.status !== statusFilter) return false;
      if (query) {
        var hay = (productLineLabel(row.product_id) + " " + warehouseLabel(row.warehouse_id)).toLowerCase();
        if (hay.indexOf(query) === -1) return false;
      }
      return true;
    });
    rows.sort(function (a, b) {
      if (sort === "onhand_desc") return Number(b.on_hand) - Number(a.on_hand);
      var ca = a.cover_days == null ? null : Number(a.cover_days);
      var cb = b.cover_days == null ? null : Number(b.cover_days);
      // Rows without a computable cover (no sales history) sort last either way.
      if (ca == null && cb == null) return 0;
      if (ca == null) return 1;
      if (cb == null) return -1;
      return sort === "cover_asc" ? ca - cb : cb - ca;
    });
    el.invalertsRows.innerHTML = "";
    if (!rows.length) { emptyRow(el.invalertsRows, 7, "invalerts_empty"); return; }
    renderRows(el.invalertsRows, rows, function (row) {
      var tr = document.createElement("tr");
      tr.appendChild(cell(labels.product, productLineLabel(row.product_id), false, true));
      tr.appendChild(cell(labels.warehouse, warehouseLabel(row.warehouse_id)));
      tr.appendChild(cell(labels.onhand, fmtQty(row.on_hand), true));
      tr.appendChild(cell(labels.sold, row.sold_in_window == null ? "—" : fmtQty(row.sold_in_window), true));
      tr.appendChild(cell(labels.avg, row.avg_daily_sales == null ? "—" : fmtQty(row.avg_daily_sales), true));
      tr.appendChild(cell(labels.cover, row.cover_days == null ? "—" : fmtQty(row.cover_days), true));
      var td = document.createElement("td");
      td.setAttribute("data-label", labels.status);
      td.appendChild(Object.assign(document.createElement("span"), {
        className: "badge " + invalertsBadgeClass(row.status),
        textContent: invalertsStatusLabel(row.status),
      }));
      tr.appendChild(td);
      return tr;
    });
  }

  // Management summary: posted-only sales / collections / receivables /
  // inventory-alert counts straight from the ledgers (GET
  // /reports/management-summary); replaces manual Excel consolidation.
  var mgmtSeq = 0;

  function loadManagementSummary() {
    var requestToken = state.token;
    clearError(el.msError);
    var seq = ++mgmtSeq;
    var qs = el.msDate.value ? "?as_of=" + el.msDate.value : "";
    el.msRows.innerHTML = "";
    var loading = document.createElement("tr");
    var tdLoad = document.createElement("td");
    tdLoad.colSpan = 3; tdLoad.className = "muted"; tdLoad.textContent = "…";
    loading.appendChild(tdLoad);
    el.msRows.appendChild(loading);
    el.msAlerts.textContent = "";
    [el.msKpiSales, el.msKpiCollections, el.msKpiAr, el.msKpiOverstock].forEach(function (node) {
      node.textContent = "—";
    });
    [el.msKpiSalesSub, el.msKpiCollectionsSub, el.msKpiArSub, el.msKpiOverstockSub]
      .forEach(function (node) { node.textContent = ""; });
    return api("/reports/management-summary" + qs).then(function (data) {
      if (state.token !== requestToken || seq !== mgmtSeq) return; // a newer refresh owns the table
      el.msAsof.textContent = t("mgmtsummary_asof") + " " + fmtDate(data.as_of);
      el.msKpiSales.textContent = fmt(data.sales.grand_total_mtd);
      el.msKpiSalesSub.textContent =
        data.sales.invoices_mtd + " " + t("ms_kpi_invoices_sub");
      el.msKpiCollections.textContent = fmt(data.collections.amount_mtd);
      el.msKpiCollectionsSub.textContent =
        data.collections.receipts_mtd + " " + t("ms_kpi_receipts_sub");
      el.msKpiAr.textContent = fmt(data.receivables.outstanding_total);
      el.msKpiArSub.textContent =
        data.receivables.customers_with_balance + " " + t("ms_customers");
      el.msKpiOverstock.textContent = fmtQty(data.inventory_alerts.overstock_count);
      el.msKpiOverstockSub.textContent =
        data.inventory_alerts.no_sales_history_count + " " + t("ms_kpi_nohistory_sub");
      var rows = [
        ["ms_invoices", String(data.sales.invoices_today), String(data.sales.invoices_mtd)],
        ["ms_sales_total", fmt(data.sales.grand_total_today), fmt(data.sales.grand_total_mtd)],
        ["ms_net", fmt(data.sales.net_today), fmt(data.sales.net_mtd)],
        ["ms_vat", fmt(data.sales.vat_today), fmt(data.sales.vat_mtd)],
        ["ms_receipts", String(data.collections.receipts_today), String(data.collections.receipts_mtd)],
        ["ms_collections", fmt(data.collections.amount_today), fmt(data.collections.amount_mtd)],
      ];
      el.msRows.innerHTML = "";
      renderRows(el.msRows, rows, function (row) {
        var tr = document.createElement("tr");
        tr.appendChild(cell(t("ms_indicator"), t(row[0]), false, true));
        tr.appendChild(cell(t("ms_today"), row[1], true));
        tr.appendChild(cell(t("ms_mtd"), row[2], true));
        return tr;
      });
      el.msAlerts.textContent =
        t("ms_outstanding") + " " + fmt(data.receivables.outstanding_total) +
        " (" + t("ms_customers") + " " + data.receivables.customers_with_balance + ") · " +
        t("ms_overstock") + " " + data.inventory_alerts.overstock_count + " · " +
        t("ms_nohistory") + " " + data.inventory_alerts.no_sales_history_count +
        " (" + t("invalerts_policy_window") + " " + data.inventory_alerts.window_days +
        " · " + t("invalerts_policy_threshold") + " " + data.inventory_alerts.threshold_days + ")";
    }).catch(function (error) {
      if (state.token !== requestToken || seq !== mgmtSeq) return;
      el.msRows.innerHTML = "";
      el.msAlerts.textContent = "";
      [el.msKpiSales, el.msKpiCollections, el.msKpiAr, el.msKpiOverstock].forEach(function (node) {
        node.textContent = "—";
      });
      [el.msKpiSalesSub, el.msKpiCollectionsSub, el.msKpiArSub, el.msKpiOverstockSub]
        .forEach(function (node) { node.textContent = ""; });
      showError(el.msError, messageFor(error));
    });
  }

  function loadAudit() {
    clearError(el.auditError);
    el.auditRows.innerHTML = "";
    var loading = document.createElement("tr");
    var tdLoad = document.createElement("td");
    tdLoad.colSpan = 4; tdLoad.className = "muted"; tdLoad.textContent = "…";
    loading.appendChild(tdLoad);
    el.auditRows.appendChild(loading);
    return api("/audit?limit=50").then(function (rows) {
      if (!rows.length) { emptyRow(el.auditRows, 4, "empty_rows"); return; }
      renderRows(el.auditRows, rows, function (row) {
        var tr = document.createElement("tr");
        tr.appendChild(cell("date", fmtDate(row.created_at)));
        tr.appendChild(cell("actor", row.actor_user_id || "—"));
        tr.appendChild(cell("action", row.action));
        tr.appendChild(cell("entity", row.entity_type));
        return tr;
      });
    }).catch(function (error) { showError(el.auditError, messageFor(error)); });
  }

  function loadTransfers() {
    clearError(el.transfersError);
    el.transferRows.innerHTML = "";
    var loading = document.createElement("tr");
    var tdLoad = document.createElement("td");
    tdLoad.colSpan = 4; tdLoad.className = "muted"; tdLoad.textContent = "…";
    loading.appendChild(tdLoad);
    el.transferRows.appendChild(loading);
    return api("/transfers").then(function (rows) {
      if (!rows.length) { emptyRow(el.transferRows, 4, "empty_rows"); return; }
      renderRows(el.transferRows, rows, function (row) {
        var tr = document.createElement("tr");
        tr.appendChild(cell("date", fmtDate(row.created_at)));
        tr.appendChild(cell("src", warehouseLabel(row.source_warehouse_id)));
        tr.appendChild(cell("product", productLineLabel(row.product_id)));
        tr.appendChild(cell("qty", fmtQty(row.quantity), true));
        return tr;
      });
    }).catch(function (error) { showError(el.transfersError, messageFor(error)); });
  }

  function loadReturns() {
    clearError(el.returnsError);
    el.returnRows.innerHTML = "";
    var loading = document.createElement("tr");
    var tdLoad = document.createElement("td");
    tdLoad.colSpan = 5; tdLoad.className = "muted"; tdLoad.textContent = "…";
    loading.appendChild(tdLoad);
    el.returnRows.appendChild(loading);
    return api("/returns").then(function (rows) {
      if (!rows.length) { emptyRow(el.returnRows, 5, "empty_rows"); return; }
      renderRows(el.returnRows, rows, function (row) {
        var tr = document.createElement("tr");
        tr.appendChild(cell("date", fmtDate(row.return_date)));
        tr.appendChild(cell("customer", customerName(row.customer_id)));
        tr.appendChild(cell("product", productLineLabel(row.product_id)));
        tr.appendChild(cell("qty", fmtQty(row.quantity), true));
        tr.appendChild(cell("reason", row.reason || "—"));
        return tr;
      });
    }).catch(function (error) { showError(el.returnsError, messageFor(error)); });
  }

  function loadMarketing() {
    clearError(el.marketingError);
    el.marketingRows.innerHTML = "";
    var loading = document.createElement("tr");
    var tdLoad = document.createElement("td");
    tdLoad.colSpan = 6; tdLoad.className = "muted"; tdLoad.textContent = "…";
    loading.appendChild(tdLoad);
    el.marketingRows.appendChild(loading);
    return api("/marketing/spend").then(function (rows) {
      if (!rows.length) { emptyRow(el.marketingRows, 6, "empty_rows"); return; }
      renderRows(el.marketingRows, rows, function (row) {
        var tr = document.createElement("tr");
        tr.appendChild(cell("date", fmtDate(row.spend_date)));
        tr.appendChild(cell("activity", row.activity_type));
        tr.appendChild(cell("amount", fmt(row.amount), true));
        tr.appendChild(cell("notes", row.notes || "—"));
        tr.appendChild(cell("products", (row.product_ids || []).map(function (p) { return productLineLabel(p); }).join(", ") || "—"));
        tr.appendChild(cell("kol", row.kol_id ? row.kol_id : "—"));
        return tr;
      });
    }).catch(function (error) { showError(el.marketingError, messageFor(error)); });
  }

  function exportBalancesCsv() {
    var rows = (state.balancesCache || []).slice().sort(function (a, b) { return Number(b.balance) - Number(a.balance); });
    if (!rows.length) { showError(el.balancesError, t("empty_rows")); return; }
    var lines = [["customer", "branch", "balance"].join(",")];
    rows.forEach(function (r) {
      lines.push([JSON.stringify(customerName(r.customer_id)), JSON.stringify(r.branch_id), r.balance].join(","));
    });
    var blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url; a.download = "ar-balances.csv"; a.style.display = "none";
    document.body.appendChild(a); a.click();
    document.body.removeChild(a); URL.revokeObjectURL(url);
  }

  async function loadBalances() {
    clearError(el.balancesError);
    try {
      var balances = await api("/ar/balances");
      state.balancesCache = balances;
      if (el.exportBalances) el.exportBalances.onclick = function () { exportBalancesCsv(); };
      var labels = { c: t("customer"), b: t("branch"), bal: t("balance") };
      el.balanceRows.innerHTML = "";
      var sorted = balances.slice().sort(function (a, b) { return Number(b.balance) - Number(a.balance); });
      if (!sorted.length) emptyRow(el.balanceRows, 4, "empty_rows");
      sorted.forEach(function (row) {
        var tr = document.createElement("tr");
        var nameCell = cell(labels.c, customerName(row.customer_id));
        if (Number(row.balance) <= 0.004) {
          nameCell.appendChild(badgeNode(t("badge_settled", "settled"), "badge posted"));
        }
        tr.appendChild(nameCell);
        tr.appendChild(cell(labels.b, branchLabel((customerById(row.customer_id) || {}).branch_id)));
        tr.appendChild(cell(labels.bal, fmt(row.balance), true));
        var td = document.createElement("td");
        td.setAttribute("data-label", t("ledger_card_title"));
        var button = document.createElement("button");
        button.type = "button";
        button.className = "default";
        button.textContent = t("ledger_card_title");
        button.addEventListener("click", function () {
          $("ledger-customer").value = row.customer_id;
          renderCustomerLedger(row.customer_id);
        });
        td.appendChild(button);
        tr.appendChild(td);
        el.balanceRows.appendChild(tr);
      });
      fillSelect($("ledger-customer"), sorted.map(function (row) {
        return { id: row.customer_id, name_ar: customerName(row.customer_id) };
      }), customerLabel, "select_customer_ledger");
      var prefill = sorted.length ? sorted[0].customer_id : "";
      $("ledger-customer").value = prefill;
      renderCustomerLedger(prefill);
    } catch (error) {
      showError(el.balancesError, messageFor(error));
    }
  }

  async function renderCustomerLedger(customerId) {
    var tbody = el.entryRows;
    var summary = el.ledgerSummary;
    summary.innerHTML = "";
    tbody.innerHTML = "";
    if (!customerId) { emptyRow(tbody, 7, "empty_rows"); return; }
    try {
      var entries = await loadEntriesIfAllowed();
      var mine = entries.filter(function (e) { return e.customer_id === customerId; })
        .sort(function (a, b) { return a.entry_date.localeCompare(b.entry_date) || String(a.created_at).localeCompare(String(b.created_at)); });
      // Resolve voucher numbers first so the ledger shows real references.
      await Promise.all(mine.map(function (e) {
        if (e.entry_type === "invoice" && e.invoice_id && !state.invoiceNos[e.invoice_id]) {
          return resolveInvoiceNo(e.invoice_id);
        }
        return null;
      }));
      var balance = 0;
      var labels = { d: t("mv_date"), ty: t("entry_type"), v: t("voucher"), n: t("notes"), dr: t("debit"), cr: t("credit"), run: t("running") };
      mine.forEach(function (e) {
        var debit = Number(e.debit), credit = Number(e.credit);
        balance = round2(balance + debit - credit);
        var tr = document.createElement("tr");
        tr.appendChild(cell(labels.d, fmtDate(e.entry_date), true));
        tr.appendChild(cell(labels.ty, entryTypeLabel(e.entry_type)));
        var voucher = "—";
        if (e.entry_type === "invoice" && e.invoice_id) voucher = state.invoiceNos[e.invoice_id] || "…";
        else if (e.entry_type === "payment" && e.receipt_id) voucher = state.receiptNos[e.receipt_id] || "…";
        var voucherTd = cell(labels.v, voucher, false, true);
        tr.appendChild(voucherTd);
        tr.appendChild(cell(labels.n, e.note || "—"));
        tr.appendChild(cell(labels.dr, debit > 0 ? fmt(debit) : "—", true));
        tr.appendChild(cell(labels.cr, credit > 0 ? fmt(credit) : "—", true));
        tr.appendChild(cell(labels.run, fmt(balance), true));
        tbody.appendChild(tr);
      });
      if (!mine.length) emptyRow(tbody, 7, "empty_rows");
      var ag = computeAgingFor(mine, balance);
      var b = document.createElement("span");
      b.className = "badge info";
      b.textContent = t("balance") + ": " + fmt(balance);
      summary.appendChild(b);
      [["a_0_30", 0], ["a_31_60", 1], ["a_61_90", 2], ["a_90p", 3]].forEach(function (def) {
        var chip = document.createElement("span");
        chip.className = "badge " + (def[1] >= 2 ? "draft" : "info");
        chip.textContent = t(def[0]) + ": " + fmt(ag.buckets[def[1]]);
        summary.appendChild(chip);
      });
    } catch (error) {
      showError(el.balancesError, messageFor(error));
    }
  }

  async function loadCollections() {
    clearError(el.collectionsError);
    var labels = {
      no: t("receipt_no"), date: t("receipt_date"), invoice: t("invoice_no"),
      customer: t("customer"), method: t("method"), amount: t("amount"), status: t("status"),
    };
    try {
      var rows = await api("/collections");
      state.receiptNos = {};
      rows.forEach(function (r) { state.receiptNos[r.id] = r.receipt_no; });
      rows = rows.slice().sort(function (a, b) {
        return String(b.receipt_date).localeCompare(String(a.receipt_date));
      });
      var ids = [];
      var seen = {};
      rows.forEach(function (row) {
        if (!seen[row.invoice_id]) { seen[row.invoice_id] = true; ids.push(row.invoice_id); }
      });
      await Promise.all(ids.map(function (id) {
        return state.invoiceNos[id] ? null : resolveInvoiceNo(id);
      }));
      renderRows(el.receiptRows, rows, receiptRow(true, labels));
      if (!rows.length) emptyRow(el.receiptRows, 7, "empty_rows");
    } catch (error) {
      showError(el.collectionsError, messageFor(error));
    }
  }

  // D40 private accounts: owner-only ledger in the isolated `private` schema.
  // Totals are factual sums; no opening-balance or sign convention is assumed.
  async function loadPrivate() {
    clearError(el.privateError);
    var rows;
    try {
      rows = await api("/private-accounts?limit=200");
    } catch (error) {
      showError(el.privateError, messageFor(error));
      return;
    }
    var debit = 0;
    var credit = 0;
    var labels = {
      date: t("date"), account: t("private_account"),
      debit: t("private_debit"), credit: t("private_credit"), note: t("notes"),
    };
    rows.forEach(function (r) {
      debit += Number(r.debit || 0);
      credit += Number(r.credit || 0);
    });
    renderRows(el.privateRows, rows, function (row) {
      var tr = document.createElement("tr");
      tr.appendChild(cell(labels.date, String(row.entry_date), false, true));
      tr.appendChild(cell(labels.account, row.account_label));
      tr.appendChild(cell(labels.debit, fmt(row.debit), true));
      tr.appendChild(cell(labels.credit, fmt(row.credit), true));
      tr.appendChild(cell(labels.note, row.note || "—"));
      return tr;
    });
    if (!rows.length) emptyRow(el.privateRows, 5, "empty_rows");
    el.privateDebitTotal.textContent = fmt(debit);
    el.privateCreditTotal.textContent = fmt(credit);
    var seen = {};
    el.privateAccountList.innerHTML = "";
    rows.forEach(function (r) {
      if (seen[r.account_label]) return;
      seen[r.account_label] = true;
      var option = document.createElement("option");
      option.value = r.account_label;
      el.privateAccountList.appendChild(option);
    });
  }

  async function savePrivateEntry(event) {
    event.preventDefault();
    clearError(el.privateError);
    clearError(el.privateNotice);
    var body = {
      account_label: el.privateLabel.value.trim(),
      entry_date: el.privateDate.value,
      debit: el.privateDebit.value || "0",
      credit: el.privateCredit.value || "0",
      note: el.privateNote.value.trim() || null,
    };
    try {
      await api("/private-accounts", { method: "POST", body: body });
    } catch (error) {
      showError(el.privateError, messageFor(error));
      return;
    }
    el.privateForm.reset();
    showNotice(el.privateNotice, t("private_saved"), "success");
    await loadPrivate();
  }

  var customerTerritories = [];
  var customerDirectoryRows = [];
  var customerPageIndex = 0;

  function renderCustomerDirectory() {
    var owner = isOwnerUser(state.user);
    var total = customerDirectoryRows.length;
    customerPageIndex = Math.max(0, Math.min(customerPageIndex, Math.max(0, Math.ceil(total / 50) - 1)));
      renderRows(el.customerRows, customerDirectoryRows.slice(customerPageIndex * 50, (customerPageIndex + 1) * 50), function (row) {
        var tr = document.createElement("tr");
        tr.setAttribute("data-customer-id", row.id);
        tr.appendChild(cell(t("code"), row.code, false, true));
        tr.appendChild(cell(t("customer"), row.name_ar || row.name_en || row.code));
        var phone = cell(t("phone"), row.contact_phone || "—");
        phone.dir = "ltr";
        tr.appendChild(phone);
        tr.appendChild(cell(t("address"), row.address || "—"));
        tr.appendChild(cell(t("branch"), branchLabel(row.branch_id)));
        var territory = customerTerritories.find(function (item) { return item.id === row.territory_id; });
        tr.appendChild(cell(t("territory"), territory ? referenceName(territory) : shortId(row.territory_id)));
        tr.appendChild(cell(t("status"), t(row.is_active ? "active" : "customer_inactive")));
        if (owner) {
          var actions = document.createElement("td");
          actions.setAttribute("data-label", t("customer_actions"));
          var group = node("div", "supplier-actions");
          var edit = node("button", "default", t("customer_edit"));
          edit.type = "button";
          edit.setAttribute("data-customer-edit", row.id);
          edit.addEventListener("click", function () { openCustomerDialog(row); });
          var activity = node("button", "default", t(row.is_active ? "customer_deactivate" : "customer_reactivate"));
          activity.type = "button";
          activity.setAttribute(row.is_active ? "data-customer-deactivate" : "data-customer-reactivate", row.id);
          activity.addEventListener("click", function () { changeCustomerActivity(row, activity); });
          group.appendChild(edit); group.appendChild(activity); actions.appendChild(group);
          tr.appendChild(actions);
        }
        return tr;
      });
      if (!customerDirectoryRows.length) emptyRow(el.customerRows, owner ? 8 : 7, "empty_rows");
    el.customerPrev.disabled = customerPageIndex === 0;
    el.customerNext.disabled = (customerPageIndex + 1) * 50 >= total;
    el.customerPageStatus.textContent = total ? (customerPageIndex * 50 + 1) + "–" + Math.min((customerPageIndex + 1) * 50, total) + " / " + total : "0";
    $("customer-pagination").classList.toggle("hidden", total <= 50);
    try { sessionStorage.setItem("medsys.customers.page." + state.user.id, String(customerPageIndex)); } catch (_e) { /* Page recall is optional. */ }
  }

  async function loadCustomers(focusId) {
    var requestToken = state.token;
    customerDirectoryRows = [];
    el.customerRows.replaceChildren();
    el.customerPrev.disabled = true;
    el.customerNext.disabled = true;
    $("customer-pagination").classList.add("hidden");
    clearError(el.customersError);
    var owner = isOwnerUser(state.user);
    el.customerAdd.classList.toggle("hidden", !owner);
    el.customerActionsHead.classList.toggle("hidden", !owner);
    try {
      var results = await Promise.all([
        api(owner ? "/master/customers?include_inactive=true" : "/master/customers"),
        api("/master/territories"),
      ]);
      if (!state.user || state.token !== requestToken) return;
      customerTerritories = results[1];
      customerDirectoryRows = results[0];
      state.customers = results[0].filter(function (row) { return row.is_active; });
      refreshCustomerSelects();
      var savedPage = 0;
      try { savedPage = Number(sessionStorage.getItem("medsys.customers.page." + state.user.id)); } catch (_e) { /* Page recall is optional. */ }
      customerPageIndex = Number.isInteger(savedPage) ? savedPage : 0;
      var index = customerDirectoryRows.findIndex(function (row) { return row.id === focusId; });
      if (index >= 0) customerPageIndex = Math.floor(index / 50);
      renderCustomerDirectory();
    } catch (error) {
      if (state.token !== requestToken) return;
      showError(el.customersError, messageFor(error));
    }
  }

  var productEditing = null;
  var productSaving = false;
  var productLoadGeneration = 0;

  function resetProductMaintenance() {
    ++productLoadGeneration;
    productEditing = null;
    productSaving = false;
    $("product-form").reset();
    $("product-form").classList.add("hidden");
    $("product-fields").disabled = false;
    $("product-search").value = "";
    $("product-maintenance").classList.add("hidden");
    $("product-status-head").classList.add("hidden");
    $("product-actions-head").classList.add("hidden");
    el.productRows.replaceChildren();
    clearError(el.productsError);
    clearError($("products-notice"));
  }

  function openProductForm(row) {
    if (!isOwnerUser(state.user) || productSaving) return;
    productEditing = row || null;
    $("product-form").reset();
    $("product-sku").disabled = !!row;
    $("product-sku").value = row ? row.sku : "";
    $("product-name-ar").value = row ? row.name_ar : "";
    $("product-name-en").value = row ? row.name_en || "" : "";
    $("product-base-price").value = row ? String(row.base_price) : "";
    $("product-vat-rate").value = row ? String(row.vat_rate) : "";
    $("product-base-price").disabled = !!row;
    $("product-vat-rate").disabled = !!row;
    $("product-form").classList.remove("hidden");
    clearError(el.productsError);
    clearError($("products-notice"));
    $(row ? "product-name-ar" : "product-sku").focus();
  }

  async function refreshProductData(saved) {
    // A confirmed mutation must update choices even if the directory readback fails.
    state.products = state.products.filter(function (row) { return row.id !== saved.id; });
    if (saved.is_active) state.products.push(saved);
    refreshProductSelects();
    var visitSelection = el.visitProduct.value;
    fillSelect(el.visitProduct, state.products, productLabel, "select_product");
    el.visitProduct.value = visitSelection;
    await loadProducts();
  }

  async function changeProductActivity(row, button) {
    if (button.disabled || productSaving || !isOwnerUser(state.user)) return;
    if (!window.confirm(t(row.is_active ? "product_confirm_deactivate" : "product_confirm_activate"))) return;
    var requestToken = state.token;
    productSaving = true;
    button.disabled = true;
    $("product-fields").disabled = true;
    clearError(el.productsError);
    try {
      var saved = await api("/master/products/" + encodeURIComponent(row.id) + (row.is_active ? "" : "/activate"),
        { method: row.is_active ? "DELETE" : "PATCH" });
      if (state.token !== requestToken) return;
      productEditing = null;
      $("product-form").classList.add("hidden");
      showNotice($("products-notice"), t("product_saved"), "success");
      await refreshProductData(saved || Object.assign({}, row, { is_active: false }));
    } catch (error) {
      if (state.token === requestToken) showError(el.productsError, messageFor(error));
    } finally {
      if (state.token === requestToken) {
        productSaving = false;
        button.disabled = false;
        $("product-fields").disabled = false;
      }
    }
  }

  async function loadProducts() {
    var requestToken = state.token;
    var generation = ++productLoadGeneration;
    var owner = isOwnerUser(state.user);
    $("product-maintenance").classList.toggle("hidden", !owner);
    $("product-status-head").classList.toggle("hidden", !owner);
    $("product-actions-head").classList.toggle("hidden", !owner);
    clearError(el.productsError);
    el.productRows.replaceChildren();
    try {
      var path = owner ? "/master/products-maintenance?limit=500&q=" + encodeURIComponent($("product-search").value) : "/master/products";
      var rows = await api(path);
      if (state.token !== requestToken || generation !== productLoadGeneration) return;
      renderRows(el.productRows, rows, function (row) {
        var tr = document.createElement("tr");
        tr.setAttribute("data-product-id", row.id);
        tr.appendChild(cell(t("code"), row.sku, false, true));
        tr.appendChild(cell(t("product"), row.name_ar || row.name_en || row.sku));
        tr.appendChild(cell(t("base_price"), String(row.base_price), true));
        tr.appendChild(cell(t("vat_pct"), String(row.vat_rate) + " %", true));
        if (owner) {
          tr.appendChild(cell(t("status"), t(row.is_active ? "active" : "customer_inactive")));
          var actions = document.createElement("td");
          actions.setAttribute("data-label", t("customer_actions"));
          var edit = node("button", "default", t("product_edit"));
          edit.type = "button";
          edit.addEventListener("click", function () { openProductForm(row); });
          var activity = node("button", "default", t(row.is_active ? "product_deactivate" : "product_activate"));
          activity.type = "button";
          activity.addEventListener("click", function () { changeProductActivity(row, activity); });
          actions.appendChild(edit); actions.appendChild(activity); tr.appendChild(actions);
        }
        return tr;
      });
      if (!rows.length) emptyRow(el.productRows, owner ? 6 : 4, "empty_rows");
    } catch (error) {
      if (state.token !== requestToken || generation !== productLoadGeneration) return;
      showError(el.productsError, messageFor(error));
    }
  }

  function wireProducts() {
    var clearExistingSession = clearSession;
    clearSession = function () {
      resetProductMaintenance();
      return clearExistingSession.apply(this, arguments);
    };
    $("product-add").addEventListener("click", function () { openProductForm(null); });
    $("product-cancel").addEventListener("click", function () {
      if (!productSaving) {
        productEditing = null;
        $("product-form").reset();
        $("product-form").classList.add("hidden");
        $("product-add").focus();
      }
    });
    $("product-search-button").addEventListener("click", function () { if (!productSaving) loadProducts(); });
    $("product-search").addEventListener("keydown", function (event) {
      if (event.key === "Enter") { event.preventDefault(); if (!productSaving) loadProducts(); }
    });
    $("product-form").addEventListener("submit", async function (event) {
      event.preventDefault();
      if (productSaving || !isOwnerUser(state.user)) return;
      var editing = productEditing;
      var payload = { name_ar: $("product-name-ar").value.trim(), name_en: $("product-name-en").value.trim() || null };
      if (!payload.name_ar || (!editing && !$("product-sku").value.trim())) {
        showError(el.productsError, t("product_required")); return;
      }
      if (!editing) {
        payload.sku = $("product-sku").value.trim();
        payload.base_price = $("product-base-price").value.trim();
        payload.vat_rate = $("product-vat-rate").value.trim();
        if (!/^[0-9]{1,10}(\.[0-9]{1,2})?$/.test(payload.base_price) ||
            !/^[0-9]{1,3}(\.[0-9]{1,2})?$/.test(payload.vat_rate) ||
            Number(payload.vat_rate) > 100) {
          showError(el.productsError, t("product_decimal_hint")); return;
        }
      }
      var requestToken = state.token;
      var path = "/master/products" + (editing ? "/" + encodeURIComponent(editing.id) : "");
      productSaving = true;
      ++productLoadGeneration;
      $("product-fields").disabled = true;
      clearError(el.productsError);
      try {
        var saved = await api(path, { method: editing ? "PATCH" : "POST", body: payload });
        if (state.token !== requestToken) return;
        productEditing = null;
        $("product-form").reset();
        $("product-form").classList.add("hidden");
        showNotice($("products-notice"), t("product_saved"), "success");
        await refreshProductData(saved);
        if (state.token === requestToken) $("product-add").focus();
      } catch (error) {
        if (state.token === requestToken) showError(el.productsError,
          error.data && error.data.detail === "Product SKU already exists" ? t("product_duplicate") : messageFor(error));
      } finally {
        if (state.token === requestToken) {
          productSaving = false;
          $("product-fields").disabled = false;
        }
      }
    });
  }

  async function loadWarehousesView() {
    clearError(el.warehousesError);
    var labels = { c: t("code"), n: t("warehouse"), b: t("branch"), a: t("active") };
    try {
      var branches = await api("/master/branches");
      state.branches = branches;
      var warehouses = await api("/master/warehouses");
      state.warehouses = warehouses;
      refreshWarehouseSelects();
      renderRows(el.warehouseRows, warehouses, function (row) {
        var tr = document.createElement("tr");
        tr.appendChild(cell(labels.c, row.code, false, true));
        tr.appendChild(cell(labels.n, row.name_ar || row.name_en || row.code));
        tr.appendChild(cell(labels.b, branchLabel(row.branch_id)));
        tr.appendChild(cell(labels.a, row.is_active ? "✓" : "—", true));
        return tr;
      });
      if (!warehouses.length) emptyRow(el.warehouseRows, 4, "empty_rows");
      // Org-hierarchy section is an explicitly labelled prototype preview.
      var target = $("org-preview");
      target.innerHTML = "";
      var box = node("div", "chip-row");
      box.appendChild(node("span", "badge proto", t("badge_proto")));
      target.appendChild(box);
      var pc = PROTON.routing[state.lang];
      var h = node("h3", "", t("nav_warehouses") + " — " + t("p_org_title"));
      target.appendChild(h);
      var ul = node("ul");
      pc.orgBullets.forEach(function (line) { ul.appendChild(node("li", "muted", line)); });
      target.appendChild(ul);
      target.appendChild(node("div", "note", t("p_org_note")));
    } catch (error) {
      showError(el.warehousesError, messageFor(error));
    }
  }

  function isOwnerUser(user) { return !!(user && user.role === "owner" && user.is_owner === true); }

  function loadSuppliers() {
    clearError(el.suppliersError);
    if (el.supplierAdd) el.supplierAdd.classList.toggle("hidden", !isOwnerUser(state.user));
    el.supplierActionsHead.classList.toggle("hidden", !isOwnerUser(state.user));
    var labels = { c: t("code"), n: t("supplier"), p: t("phone"), a: t("address") };
    var url = isOwnerUser(state.user) ? "/master/suppliers?include_inactive=true" : "/master/suppliers";
    return api(url).then(function (rows) {
      renderRows(el.supplierRows, rows, function (row) {
        var tr = document.createElement("tr");
        tr.setAttribute("data-supplier-id", row.id);
        tr.appendChild(cell(labels.c, row.code, false, true));
        tr.appendChild(cell(labels.n, row.name_ar || row.name_en || row.code));
        tr.appendChild(cell(labels.p, row.contact_phone || "—", true));
        tr.appendChild(cell(labels.a, row.address || "—"));
        tr.appendChild(cell(t("status"), t(row.is_active ? "active" : "supplier_inactive")));
        if (isOwnerUser(state.user)) {
          var actions = document.createElement("td");
          actions.setAttribute("data-label", t("supplier_actions"));
          var group = document.createElement("div");
          group.className = "supplier-actions";
          var edit = document.createElement("button");
          edit.type = "button";
          edit.className = "default";
          edit.setAttribute("data-supplier-edit", row.id);
          edit.setAttribute("aria-label", t("supplier_edit") + " " + row.code);
          edit.textContent = t("supplier_edit");
          edit.addEventListener("click", function () { editSupplier(row.id); });
          group.appendChild(edit);
          var toggle = document.createElement("button");
          var action = row.is_active ? "supplier_deactivate" : "supplier_reactivate";
          toggle.type = "button";
          toggle.className = "default";
          toggle.setAttribute(row.is_active ? "data-supplier-deactivate" : "data-supplier-reactivate", row.id);
          toggle.setAttribute("aria-label", t(action) + " " + row.code);
          toggle.textContent = t(action);
          toggle.addEventListener("click", function () { changeSupplierActivity(row, toggle); });
          group.appendChild(toggle);
          actions.appendChild(group);
          tr.appendChild(actions);
        }
        return tr;
      });
      if (!rows.length) emptyRow(el.supplierRows, isOwnerUser(state.user) ? 6 : 5, "empty_rows");
    }).catch(function (error) {
      renderRows(el.supplierRows, [], function () { return null; });
      emptyRow(el.supplierRows, isOwnerUser(state.user) ? 6 : 5, "empty_rows");
      showError(el.suppliersError, messageFor(error));
    });
  }

  var supplierSaving = false;
  var supplierEditingId = null;
  async function changeSupplierActivity(row, button) {
    if (button.disabled || !isOwnerUser(state.user)) return;
    if (row.is_active && !window.confirm(t("supplier_confirm_deactivate"))) return;
    button.disabled = true;
    clearError(el.suppliersError);
    try {
      var options = row.is_active ? { method: "DELETE" } : { method: "PATCH", body: { is_active: true } };
      await api("/master/suppliers/" + encodeURIComponent(row.id), options);
      await loadSuppliers();
    } catch (error) {
      showError(el.suppliersError, messageFor(error));
    } finally {
      button.disabled = false;
    }
  }
  async function editSupplier(id) {
    if (supplierSaving || el.supplierDialog.open) return;
    clearError(el.suppliersError);
    try {
      var row = await api("/master/suppliers/" + encodeURIComponent(id));
      if (!el.supplierDialog.open) openSupplierDialog(row);
    } catch (error) {
      showError(el.suppliersError, messageFor(error));
    }
  }
  function openSupplierDialog(row) {
    if (!el.supplierDialog || !isOwnerUser(state.user)) return;
    clearError(el.supplierDialogError);
    if (el.supplierForm) el.supplierForm.reset();
    supplierEditingId = row ? row.id : null;
    var title = $("supplier-dialog-title");
    title.setAttribute("data-i18n", row ? "supplier_edit" : "supplier_add");
    title.textContent = t(row ? "supplier_edit" : "supplier_add");
    if (row) {
      el.supplierCode.value = row.code;
      el.supplierNameAr.value = row.name_ar;
      el.supplierNameEn.value = row.name_en || "";
      el.supplierPhone.value = row.contact_phone || "";
      el.supplierAddress.value = row.address || "";
    }
    supplierSaving = false;
    if (el.supplierSave) el.supplierSave.disabled = false;
    if (el.supplierCancel) el.supplierCancel.disabled = false;
    el.supplierDialog.showModal();
    setTimeout(function () { if (el.supplierCode) el.supplierCode.focus(); }, 0);
  }
  function closeSupplierDialog() {
    if (supplierSaving) return;
    if (el.supplierDialog && el.supplierDialog.open) el.supplierDialog.close();
  }

  var customerSaving = false;
  var customerEditingRow = null;
  var customerDialogGeneration = 0;

  function referenceName(row) {
    return (state.lang === "en" ? row.name_en || row.name_ar : row.name_ar || row.name_en) || row.code;
  }

  async function refreshCustomerData(customer) {
    // A confirmed mutation must update invoice choices even if the readback fails.
    state.customers = state.customers.filter(function (row) { return row.id !== customer.id; });
    if (customer.is_active) state.customers.push(customer);
    refreshCustomerSelects();
    await loadCustomers(customer.id);
  }

  async function changeCustomerActivity(row, button) {
    if (button.disabled || !isOwnerUser(state.user)) return;
    if (!window.confirm(t(row.is_active ? "customer_confirm_deactivate" : "customer_confirm_reactivate"))) return;
    button.disabled = true;
    clearError(el.customersError);
    try {
      var path = "/master/customers/" + encodeURIComponent(row.id) + (row.is_active ? "" : "/activate");
      var requestToken = state.token;
      var saved = await api(path, { method: row.is_active ? "DELETE" : "PATCH" });
      if (state.token !== requestToken) return;
      showNotice(el.customersNotice, t("customer_saved"), "success");
      await refreshCustomerData(saved || Object.assign({}, row, { is_active: false }));
    } catch (error) {
      if (state.token !== requestToken) return;
      showError(el.customersError, messageFor(error));
    } finally {
      button.disabled = false;
    }
  }

  async function openCustomerDialog(row) {
    if (!isOwnerUser(state.user) || el.customerDialog.open) return;
    var generation = ++customerDialogGeneration;
    customerEditingRow = row || null;
    customerSaving = false;
    el.customerForm.reset();
    clearError(el.customerDialogError);
    el.customerCode.disabled = !!row;
    el.customerBranch.disabled = !!row;
    el.customerTerritory.disabled = !!row;
    el.customerCode.value = row ? row.code : "";
    el.customerNameAr.value = row ? row.name_ar : "";
    el.customerNameEn.value = row ? row.name_en || "" : "";
    el.customerPhone.value = row ? row.contact_phone || "" : "";
    el.customerAddress.value = row ? row.address || "" : "";
    var title = $("customer-dialog-title");
    title.dataset.i18n = row ? "customer_edit" : "customer_add";
    title.textContent = t(title.dataset.i18n);
    fillSelect(el.customerBranch, [], referenceName, "customer_select_branch");
    fillSelect(el.customerTerritory, [], referenceName, "customer_select_territory");
    el.customerSave.disabled = true;
    el.customerCancel.disabled = false;
    el.customerDialog.showModal();
    (row ? el.customerNameAr : el.customerCode).focus();
    try {
      var results = await Promise.all([api("/master/branches"), api("/master/territories")]);
      if (generation !== customerDialogGeneration || !el.customerDialog.open) return;
      fillSelect(el.customerBranch, results[0], referenceName, "customer_select_branch");
      fillSelect(el.customerTerritory, results[1], referenceName, "customer_select_territory");
      if (row) {
        el.customerBranch.value = row.branch_id;
        el.customerTerritory.value = row.territory_id;
      }
      if (!results[0].length || !results[1].length) {
        showError(el.customerDialogError, t("customer_references_required"));
      } else {
        el.customerSave.disabled = false;
      }
    } catch (error) {
      if (generation === customerDialogGeneration && el.customerDialog.open) showError(el.customerDialogError, messageFor(error));
    }
  }

  function closeCustomerDialog() {
    if (customerSaving) return;
    ++customerDialogGeneration;
    el.customerDialog.close();
  }

  async function saveCustomer(event) {
    event.preventDefault();
    if (customerSaving || el.customerSave.disabled || !isOwnerUser(state.user)) return;
    clearError(el.customerDialogError);
    var names = { name_ar: el.customerNameAr.value.trim(), name_en: el.customerNameEn.value.trim() || null,
      contact_phone: el.customerPhone.value.trim() || null, address: el.customerAddress.value.trim() || null };
    if (!names.name_ar || (!customerEditingRow && !el.customerCode.value.trim())) {
      showError(el.customerDialogError, t("customer_required"));
      return;
    }
    var payload;
    if (customerEditingRow) {
      payload = {};
      Object.keys(names).forEach(function (key) {
        var original = customerEditingRow[key];
        var displayed = typeof original === "string" ? original.trim() || null : original;
        if (names[key] !== displayed) payload[key] = names[key];
      });
      if (!Object.keys(payload).length) { closeCustomerDialog(); return; }
    } else {
      payload = Object.assign({ code: el.customerCode.value.trim(), branch_id: el.customerBranch.value, territory_id: el.customerTerritory.value }, names);
    }
    customerSaving = true;
    el.customerSave.disabled = true;
    el.customerCancel.disabled = true;
    try {
      var path = "/master/customers" + (customerEditingRow ? "/" + encodeURIComponent(customerEditingRow.id) : "");
      var requestToken = state.token;
      var saved = await api(path, { method: customerEditingRow ? "PATCH" : "POST", body: payload });
      if (state.token !== requestToken) return;
      el.customerDialog.close();
      showNotice(el.customersNotice, t("customer_saved"), "success");
      await refreshCustomerData(saved);
    } catch (error) {
      if (state.token !== requestToken) return;
      var detail = error.data && error.data.detail;
      var message = detail === "Customer code already exists" ? t("customer_duplicate") :
        detail === "Customer branch or territory does not exist" ? t("customer_reference_invalid") : messageFor(error);
      showError(el.customerDialog.open ? el.customerDialogError : el.customersError, message);
    } finally {
      if (state.token === requestToken) {
        customerSaving = false;
        el.customerSave.disabled = false;
        el.customerCancel.disabled = false;
      }
    }
  }

  async function saveSupplier(event) {
    event.preventDefault();
    if (supplierSaving || !el.supplierSave || el.supplierSave.disabled) return;
    clearError(el.supplierDialogError);
    supplierSaving = true;
    el.supplierSave.disabled = true;
    if (el.supplierCancel) el.supplierCancel.disabled = true;
    try {
      var payload = {
        code: el.supplierCode.value.trim(),
        name_ar: el.supplierNameAr.value.trim(),
        name_en: el.supplierNameEn.value.trim() || null,
        contact_phone: el.supplierPhone.value.trim() || null,
        address: el.supplierAddress.value.trim() || null,
      };
      var path = "/master/suppliers" + (supplierEditingId ? "/" + encodeURIComponent(supplierEditingId) : "");
      await api(path, { method: supplierEditingId ? "PATCH" : "POST", body: payload });
      await loadSuppliers();
      if (el.supplierDialog.open) el.supplierDialog.close();
    } catch (error) {
      showError(el.supplierDialogError, messageFor(error));
    } finally {
      supplierSaving = false;
      if (el.supplierSave) el.supplierSave.disabled = false;
      if (el.supplierCancel) el.supplierCancel.disabled = false;
    }
  }

  function loadAccounts() {
    clearError(el.accountsError);
    var labels = { c: t("code"), n: t("account_name"), ty: t("account_type") };
    return api("/master/accounts").then(function (rows) {
      renderRows(el.accountRows, rows, function (row) {
        var tr = document.createElement("tr");
        tr.appendChild(cell(labels.c, row.code, false, true));
        tr.appendChild(cell(labels.n, row.name_ar || row.name_en || row.code));
        tr.appendChild(cell(labels.ty, accountTypeLabel(row.account_type)));
        return tr;
      });
      if (!rows.length) emptyRow(el.accountRows, 3, "empty_rows");
    }).catch(function (error) {
      renderRows(el.accountRows, [], function () { return null; });
      emptyRow(el.accountRows, 3, "empty_rows");
      showError(el.accountsError, messageFor(error));
    });
  }

  async function loadDoctors() {
    clearError(el.doctorsError);
    var labels = { c: t("code"), n: t("doctor"), s: t("specialty"), b: t("branch"), p: t("phone") };
    try {
      var rows = await api("/master/doctors");
      renderRows(el.doctorRows, rows, function (row) {
        var tr = document.createElement("tr");
        tr.appendChild(cell(labels.c, row.code, false, true));
        tr.appendChild(cell(labels.n, row.name_ar || row.name_en || row.code));
        tr.appendChild(cell(labels.s, row.specialty || "—"));
        tr.appendChild(cell(labels.b, branchLabel(row.branch_id)));
        tr.appendChild(cell(labels.p, row.contact_phone || "—", true));
        return tr;
      });
      if (!rows.length) emptyRow(el.doctorRows, 5, "empty_rows");
      var target = $("kolspend-preview");
      target.innerHTML = "";
      target.appendChild(node("div", "chip-row")).appendChild(node("span", "badge proto", t("badge_proto")));
      buildPreview(target, "kolspend");
    } catch (error) {
      showError(el.doctorsError, messageFor(error));
    }
  }

  // ----------------------------------------------------------- stock visits
  // Legacy medsys.visits.v1 stays untouched; device prototypes are not server records.
  var visitsData = [];
  var visitsTotal = 0;
  var visitsOffset = 0;
  var visitsSeq = 0;
  var visitStockSeq = 0;
  var visitSaving = false;
  var visitsLoading = false;
  var visitsLoadFailed = false;
  var visitStockLoading = false;
  var VISITS_PAGE_SIZE = 20;

  function canWriteVisit() {
    return state.user && (state.user.role === "medical_rep" ||
      (state.user.role === "owner" && state.user.is_owner));
  }
  function syncVisitControls() {
    el.visitFields.disabled = !canWriteVisit() || visitSaving;
    el.visitPrev.disabled = !canWriteVisit() || visitSaving || visitStockLoading;
    el.visitSave.disabled = !canWriteVisit() || visitSaving || visitStockLoading;
    el.visitReadOnly.classList.toggle("hidden", !!canWriteVisit());
    el.visitRefresh.disabled = visitsLoading || visitSaving;
    el.visitsPrev.disabled = visitsLoading || visitSaving || visitsOffset === 0;
    el.visitsNext.disabled = visitsLoading || visitSaving || visitsOffset + VISITS_PAGE_SIZE >= visitsTotal;
    el.visitsView.setAttribute("aria-busy", visitsLoading || visitSaving ? "true" : "false");
  }
  async function visitRequest(path, opts) {
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, 15000);
    try {
      return await api(path, Object.assign({}, opts || {}, { signal: controller.signal }));
    } finally { clearTimeout(timer); }
  }
  function visitCalc() {
    var prev = Number(el.visitPrev.value || 0);
    var del = Number(el.visitDel.value || 0);
    var ret = Number(el.visitRet.value || 0);
    var cur = Number(el.visitCur.value || 0);
    return { st: (Math.round(prev * 1000) + Math.round(del * 1000) -
      Math.round(ret * 1000) - Math.round(cur * 1000)) / 1000 };
  }
  function updateVisitCalc() {
    var st = visitCalc().st;
    var complete = [el.visitPrev, el.visitDel, el.visitRet, el.visitCur]
      .every(function (input) { return input.value !== ""; });
    el.visitSt.textContent = complete && Number.isFinite(st) ? fmtQty(st) : "—";
    el.visitCur.setCustomValidity(complete && st < 0 ? t("visit_warn_st") : "");
    if (complete && st < 0) showNotice(el.visitWarn, t("visit_warn_st"), "warn");
    else clearError(el.visitWarn);
  }
  function resetVisits() {
    ++visitsSeq; ++visitStockSeq;
    visitsData = []; visitsTotal = 0; visitsOffset = 0;
    visitSaving = false; visitsLoading = false; visitsLoadFailed = false; visitStockLoading = false;
    el.visitRows.replaceChildren();
    el.visitForm.reset();
    el.visitCur.setCustomValidity("");
    el.visitDate.value = ""; el.visitRep.value = ""; el.visitSt.textContent = "—";
    el.visitPage.textContent = "";
    [el.visitsError, el.visitWarn, el.visitStockHint].forEach(clearError);
    syncVisitControls();
  }
  function renderVisits() {
    el.visitRows.replaceChildren();
    if (!visitsData.length) emptyRow(el.visitRows, 6, visitsLoading ? "visit_loading" : visitsLoadFailed ? "visit_failed" : "visit_empty");
    visitsData.forEach(function (visit) {
      visit.lines.forEach(function (line, index) {
        var row = document.createElement("tr");
        row.dataset.visitId = visit.id;
        row.appendChild(cell(t("visit_at"), fmtDate(visit.visit_date), true));
        row.appendChild(cell(t("customer"), customerName(visit.customer_id)));
        var productCell = cell(t("product"), productLineLabel(line.product_id));
        if (line.batch_id) {
          var batch = node("small", "muted", t("visit_batch_id") + " " + line.batch_id);
          batch.dir = "ltr";
          productCell.appendChild(batch);
        }
        row.appendChild(productCell);
        row.appendChild(cell(t("visit_sellthrough"), fmtQty(line.sell_through), true));
        row.appendChild(cell(t("visit_amount"), fmt(line.amount), true));
        var action = document.createElement("td");
        action.setAttribute("data-label", t("visit_delete"));
        if (index === 0 && canWriteVisit() &&
            (state.user.role === "owner" || visit.rep_id === state.user.id)) {
          var button = node("button", "ghost danger", t("visit_delete"));
          button.type = "button";
          button.disabled = visitSaving;
          button.addEventListener("click", function () { deleteVisit(visit.id); });
          action.appendChild(button);
        }
        row.appendChild(action);
        el.visitRows.appendChild(row);
      });
    });
    el.visitPage.textContent = visitsLoadFailed ? "—" : visitsLoading ? "…" : visitsTotal ? (visitsOffset + 1) + "–" +
      Math.min(visitsOffset + VISITS_PAGE_SIZE, visitsTotal) + " / " + visitsTotal : "0 / 0";
    syncVisitControls();
  }
  async function loadVisits() {
    var token = state.token;
    if (!token || !roleAllowed("visits")) return;
    var seq = ++visitsSeq;
    visitsLoading = true; visitsLoadFailed = false; visitsData = [];
    clearError(el.visitsError);
    if (!el.visitDate.value) el.visitDate.value = todayLocal();
    el.visitRep.value = state.user.username;
    renderVisits();
    try {
      var data = await visitRequest("/visits?limit=" + VISITS_PAGE_SIZE + "&offset=" + visitsOffset);
      if (state.token !== token || seq !== visitsSeq) return;
      visitsData = data.items; visitsTotal = data.total;
      if (!visitsData.length && visitsOffset > 0) {
        visitsOffset = Math.max(0, visitsOffset - VISITS_PAGE_SIZE);
        return loadVisits();
      }
    } catch (error) {
      if (state.token !== token || seq !== visitsSeq) return;
      visitsTotal = 0; visitsLoadFailed = true;
      showError(el.visitsError, messageFor(error));
    } finally {
      if (state.token === token && seq === visitsSeq) {
        visitsLoading = false; renderVisits();
      }
    }
  }
  async function loadVisitStock() {
    var token = state.token, seq = ++visitStockSeq;
    var customer = el.visitCustomer.value, product = el.visitProduct.value;
    visitStockLoading = false;
    clearError(el.visitStockHint);
    el.visitPrev.value = "";
    updateVisitCalc();
    if (!token || !customer || !product || !canWriteVisit()) { syncVisitControls(); return; }
    visitStockLoading = true; syncVisitControls();
    try {
      var path = "/visits/held-stock?customer_id=" + encodeURIComponent(customer) +
        "&product_id=" + encodeURIComponent(product) + "&limit=1";
      var data = await visitRequest(path);
      if (state.token !== token || seq !== visitStockSeq) return;
      // The form records no batch. NULLS LAST lets us fetch its exact tuple, never sum batches.
      if (data.total > 1 && data.items[0].batch_id !== null) {
        data = await visitRequest(path + "&offset=" + (data.total - 1));
        if (state.token !== token || seq !== visitStockSeq) return;
      }
      var held = data.items.find(function (item) {
        return item.batch_id === null && item.customer_id === customer && item.product_id === product;
      });
      el.visitPrev.value = held ? held.quantity_on_hand : "0";
      showNotice(el.visitStockHint, t(held ? "visit_previous_loaded" : "visit_no_previous"), "info");
      updateVisitCalc();
    } catch (error) {
      if (state.token !== token || seq !== visitStockSeq) return;
      showError(el.visitStockHint, t("visit_previous_error") + " " + messageFor(error));
    } finally {
      if (state.token === token && seq === visitStockSeq) {
        visitStockLoading = false; syncVisitControls();
      }
    }
  }
  async function saveVisit(event) {
    event.preventDefault();
    if (visitSaving || visitStockLoading || !canWriteVisit()) return;
    updateVisitCalc();
    if (!el.visitForm.reportValidity()) return;
    if (!el.visitCustomer.value || !el.visitProduct.value) {
      showError(el.visitWarn, t("visit_err_pick")); return;
    }
    var token = state.token;
    var payload = {
      customer_id: el.visitCustomer.value, visit_date: el.visitDate.value,
      lines: [{ product_id: el.visitProduct.value,
        quantity_prev: el.visitPrev.value, quantity_delivered: el.visitDel.value,
        quantity_returned: el.visitRet.value, quantity_current: el.visitCur.value,
        amount: el.visitAmount.value || "0", payment_method: el.visitMethod.value,
        notes: el.visitNotes.value.trim() || null }],
    };
    visitSaving = true; clearError(el.visitWarn); syncVisitControls();
    try {
      await visitRequest("/visits", { method: "POST", body: payload });
      if (state.token !== token) return;
      visitsOffset = 0;
      await loadVisits();
      if (state.token !== token) return;
      el.visitDel.value = "0"; el.visitRet.value = "0"; el.visitCur.value = "";
      el.visitAmount.value = "0"; el.visitNotes.value = "";
      await loadVisitStock();
      if (state.token !== token) return;
      showNotice(el.visitWarn, t("visit_saved_server"), "success");
    } catch (error) {
      if (state.token !== token) return;
      showError(el.visitWarn, error.status ? messageFor(error) : t("visit_save_uncertain"));
    } finally {
      if (state.token === token) { visitSaving = false; syncVisitControls(); renderVisits(); }
    }
  }
  async function deleteVisit(id) {
    if (visitSaving || !canWriteVisit() || !window.confirm(t("visit_delete_confirm"))) return;
    var token = state.token;
    visitSaving = true; syncVisitControls(); renderVisits();
    try {
      await visitRequest("/visits/" + encodeURIComponent(id), { method: "DELETE" });
      if (state.token !== token) return;
      await loadVisits();
      if (state.token !== token) return;
      showNotice(el.visitWarn, t("visit_deleted"), "success");
    } catch (error) {
      if (state.token !== token) return;
      showError(el.visitsError, messageFor(error));
    } finally {
      if (state.token === token) { visitSaving = false; syncVisitControls(); renderVisits(); }
    }
  }

  // =========================================================================
  // COMMAND PALETTE (Ctrl+K) — searches nav + real customers/products.
  // =========================================================================
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && el.palette && el.palette.open) {
      el.palette.close();
    }
  });
  var paletteItems = [];
  var paletteRemote = null;   // server-side matches for the current query
  var paletteSeq = 0;
  function paletteNavigate(target) {
    el.palette.close();
    showView(target.view);
  }
  // P2.10: query the server so matches are not limited to the rows already
  // loaded into state (the palette used to search only the current page).
  function paletteSearch(q) {
    var seq = ++paletteSeq;
    if (!q) { paletteRemote = null; renderPalette(""); return; }
    api("/search?q=" + encodeURIComponent(q)).then(function (data) {
      if (seq !== paletteSeq) return;
      paletteRemote = { query: q, customers: data.customers || [], products: data.products || [] };
      renderPalette(q);
    }).catch(function () {
      if (seq !== paletteSeq) return;
      paletteRemote = null;
      renderPalette(q);
    });
  }
  function renderPalette(query) {
    var list = $("palette-list");
    list.innerHTML = "";
    paletteItems = [];
    var q = query.trim().toLowerCase();
    if (state.user) {
      document.querySelectorAll(".sidebar .nav-item").forEach(function (btn) {
        if (btn.classList.contains("hidden")) return;
        var labelSpan = btn.querySelector("[data-i18n]");
        var label = labelSpan ? labelSpan.textContent : btn.textContent.trim();
        paletteItems.push({
          kind: t("pal_nav"), label: label, view: btn.dataset.view,
          hay: (label + " " + (labelSpan ? dict[labelSpan.dataset.i18n] : "")).toLowerCase(),
        });
      });
      var remoteFresh = paletteRemote && paletteRemote.query === query.trim();
      if (!remoteFresh) {
        state.customers.forEach(function (c) {
          paletteItems.push({
            kind: t("customer"), label: c.name_ar || c.name_en || c.code, sub: c.code,
            view: "customers", hay: ((c.name_ar || "") + (c.name_en || "") + c.code).toLowerCase(),
          });
        });
        state.products.forEach(function (p) {
          paletteItems.push({
            kind: t("product"), label: p.name_ar || p.name_en || p.sku, sub: p.sku,
            view: "products", hay: ((p.name_ar || "") + (p.name_en || "") + p.sku).toLowerCase(),
          });
        });
      }
      if (remoteFresh) {
        paletteRemote.customers.forEach(function (c) {
          paletteItems.push({
            kind: t("customer"), label: c.name_ar || c.name_en || c.code, sub: c.code,
            view: "customers", hay: ((c.name_ar || "") + (c.name_en || "") + c.code).toLowerCase(),
          });
        });
        paletteRemote.products.forEach(function (p) {
          paletteItems.push({
            kind: t("product"), label: p.name_ar || p.name_en || p.sku, sub: p.sku,
            view: "products", hay: ((p.name_ar || "") + (p.name_en || "") + p.sku).toLowerCase(),
          });
        });
      }
    }
    var results = paletteItems.filter(function (item) { return !q || item.hay.indexOf(q) >= 0; }).slice(0, 12);
    results.forEach(function (item, index) {
      var li = document.createElement("li");
      if (index === 0) li.className = "sel";
      var spanKind = node("span", "badge info small", item.kind);
      li.appendChild(spanKind);
      var spanLabel = node("span", "", item.label);
      li.appendChild(spanLabel);
      if (item.sub) li.appendChild(node("span", "k num", item.sub));
      li.addEventListener("click", function () { paletteNavigate(item); });
      list.appendChild(li);
    });
    if (!results.length) list.appendChild(node("li", "muted", t("pal_none")));
  }
  function openPalette() {
    if (!state.user) return;
    el.paletteInput.value = "";
    paletteRemote = null;
    renderPalette("");
    el.palette.showModal();
    el.paletteInput.focus();
  }

  // =========================================================================
  // AUTH + BOOT
  // =========================================================================
  async function boot() {
    var requestToken = state.token;
    var me = await api("/auth/me");
    if (state.token !== requestToken) return;
    state.user = me;
    el.whoName.textContent = me.username;
    el.whoRole.textContent = me.role;
    el.who.classList.remove("hidden");
    el.logout.classList.remove("hidden");
    el.sidebar.classList.remove("hidden");
    el.bottomnav.classList.remove("hidden");
    el.bell.classList.remove("hidden");
    el.demoBanner.classList.remove("hidden");
    applyRoleGating();
    el.invoiceDate.value = todayLocal();
    el.invoiceNo.value = "INV-" + Date.now().toString().slice(-8);
    await loadMaster();
    if (state.token !== requestToken) return;
        try { await loadWarehouses(null); } catch (_e) {
          // Non-global roles scope warehouses per branch; labels fall back to ids.
        }
        if (state.token !== requestToken) return;
        // Preserve an explicit user selection made during async boot; only land on
        // Home when the user has not already navigated away from the login screen.
        if (currentSection === "login-view") showView("home");
        if (me.role === "read_only_auditor") {
          el.saveDraft.disabled = true;
          el.addLine.disabled = true;
          showNotice(el.formError, t("read_only_role"), "warn");
        }
        // Finance/owner: prime the entries cache for ledger/aging widgets.
        if (me.role !== "medical_rep") loadEntriesIfAllowed();
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
      if (out && state.token !== out.access_token) return;
      showError(el.loginError, messageFor(error));
    } finally {
      el.loginSubmit.disabled = false;
    }
  }

  async function logout() {
    var pending = api("/auth/logout", { method: "POST" });
    clearSession();
    try { await pending; } catch (_e) { /* Local teardown must not wait for the network. */ }
  }

  function clearSession() {
    state.token = null;
    state.user = null;
    state.entries = null;
    resetVisits();
    state.balancesCache = [];
    ++salesReportSeq;
    ++invalertsSeq;
    ++mgmtSeq;
    invalertsData = [];
    invalertsPolicyData = null;
    [el.srTotalsRows, el.srTerritoryRows, el.srRepRows, el.srProductRows,
      el.invalertsRows, el.msRows].forEach(function (body) { body.replaceChildren(); });
    [el.srError, el.invalertsError, el.msError].forEach(clearError);
    el.invalertsPolicy.textContent = "";
    el.invalertsPolicy.classList.add("hidden");
    el.msAsof.textContent = "";
    el.msAlerts.textContent = "";
    [el.msKpiSales, el.msKpiCollections, el.msKpiAr, el.msKpiOverstock]
      .forEach(function (item) { item.textContent = "—"; });
    [el.msKpiSalesSub, el.msKpiCollectionsSub, el.msKpiArSub, el.msKpiOverstockSub]
      .forEach(function (item) { item.textContent = ""; });
    state.customers = [];
    state.branches = [];
    state.products = [];
    state.warehouses = [];
    warehouseLabels = {};
    refreshProductSelects();
    refreshWarehouseSelects();
    customerDirectoryRows = [];
    customerTerritories = [];
    customerEditingRow = null;
    customerSaving = false;
    ++customerDialogGeneration;
    el.customerRows.replaceChildren();
    el.customerForm.reset();
    if (el.customerDialog.open) el.customerDialog.close();
    refreshCustomerSelects();
    localStorage.removeItem("token");
    el.who.classList.add("hidden");
    el.logout.classList.add("hidden");
    el.sidebar.classList.add("hidden");
    el.bottomnav.classList.add("hidden");
    el.bell.classList.add("hidden");
    el.demoBanner.classList.add("hidden");
    showView("login");
  }

  function badgeNode(text, className) {
    var span = document.createElement("span");
    span.className = className;
    span.textContent = text;
    return span;
  }

  function cacheElements() {
    el.demoBanner = $("demo-banner");
    el.menuToggle = $("menu-toggle");
    el.sidebar = $("sidebar");
    el.scrim = $("scrim");
    el.bottomnav = $("bottomnav");
    el.bell = $("bell");
    el.offlineChip = $("offline-chip");
    el.palette = $("palette");
    el.paletteInput = $("palette-input");

    el.loginView = $("login-view");
    el.invoiceView = $("invoice-view");
    el.invoiceView = $("invoice-view");
    el.draftView = $("draft-view");
    el.homeView = $("home-view");
    el.inventoryView = $("inventory-view");
    el.ledgerView = $("ledger-view");
    el.balancesView = $("balances-view");
    el.collectionsView = $("collections-view");
    el.customersView = $("customers-view");
    el.productsView = $("products-view");
    el.warehousesView = $("warehouses-view");
    el.suppliersView = $("suppliers-view");
    el.accountsView = $("accounts-view");
    el.doctorsView = $("doctors-view");
    el.visitsView = $("visits-view");
    el.targetsView = $("targets-view");
    el.batchesView = $("batches-view");
    el.coverView = $("cover-view");
    el.auditView = $("audit-view");
    el.transfersView = $("transfers-view");
    el.returnsView = $("returns-view");
    el.marketingView = $("marketing-view");
    el.moduleView = $("module-view");
    el.targetsError = $("targets-error");
    el.targetRows = $("target-rows");
    el.batchesError = $("batches-error");
    el.batchRows = $("batch-rows");
    el.coverError = $("cover-error");
    el.coverRows = $("cover-rows");
    el.invalertsError = $("invalerts-error");
    el.invalertsPolicy = $("invalerts-policy");
    el.invalertsStatus = $("invalerts-status");
    el.invalertsSort = $("invalerts-sort");
    el.invalertsSearch = $("invalerts-search");
    el.invalertsRows = $("invalerts-rows");
    el.msError = $("mgmtsummary-error");
    el.msDate = $("ms-date");
    el.msAsof = $("mgmtsummary-asof");
    el.msRows = $("mgmtsummary-rows");
    el.msAlerts = $("ms-alerts");
    el.msKpiSales = $("ms-kpi-sales");
    el.msKpiSalesSub = $("ms-kpi-sales-sub");
    el.msKpiCollections = $("ms-kpi-collections");
    el.msKpiCollectionsSub = $("ms-kpi-collections-sub");
    el.msKpiAr = $("ms-kpi-ar");
    el.msKpiArSub = $("ms-kpi-ar-sub");
    el.msKpiOverstock = $("ms-kpi-overstock");
    el.msKpiOverstockSub = $("ms-kpi-overstock-sub");
    el.auditError = $("audit-error");
    el.auditRows = $("audit-rows");
    el.transfersError = $("transfers-error");
    el.transferRows = $("transfer-rows");
    el.returnsError = $("returns-error");
    el.returnRows = $("return-rows");
    el.marketingError = $("marketing-error");
    el.marketingRows = $("marketing-rows");
    el.moduleDesc = $("module-desc");
    el.moduleContent = $("module-content");

    el.ledgerError = $("ledger-error");
    el.invoicelistError = $("invoicelist-error");
    el.ilStatus = $("il-status");
    el.ilFrom = $("il-from");
    el.ilTo = $("il-to");
    el.invoiceRows = $("invoice-rows");
    el.srError = $("salesreport-error");
    el.srFrom = $("sr-from");
    el.srTo = $("sr-to");
    el.srTotalsRows = $("sr-totals-rows");
    el.srTerritoryRows = $("sr-territory-rows");
    el.srRepRows = $("sr-rep-rows");
    el.srProductRows = $("sr-product-rows");
    el.customersError = $("customers-error");
    el.productsError = $("products-error");
    el.warehousesError = $("warehouses-error");
    el.suppliersError = $("suppliers-error");
    el.accountsError = $("accounts-error");
    el.doctorsError = $("doctors-error");
    el.movementRows = $("movement-rows");
    el.customerRows = $("customer-rows");
    el.customerPrev = $("customer-prev");
    el.customerNext = $("customer-next");
    el.customerPageStatus = $("customer-page-status");
    el.customerPrev.addEventListener("click", function () { --customerPageIndex; renderCustomerDirectory(); });
    el.customerNext.addEventListener("click", function () { ++customerPageIndex; renderCustomerDirectory(); });
    el.customerAdd = $("customer-add");
    el.customerActionsHead = $("customer-actions-head");
    el.customerDialog = $("customer-dialog");
    el.customerForm = $("customer-form");
    el.customerCode = $("customer-code");
    el.customerNameAr = $("customer-name-ar");
    el.customerNameEn = $("customer-name-en");
    el.customerPhone = $("customer-phone");
    el.customerAddress = $("customer-address");
    el.customerBranch = $("customer-branch");
    el.customerTerritory = $("customer-territory");
    el.customerSave = $("customer-save");
    el.customerCancel = $("customer-cancel");
    el.customersNotice = $("customers-notice");
    el.customerDialogError = $("customer-dialog-error");
    el.productRows = $("product-rows");
    el.warehouseRows = $("warehouse-rows");
    el.supplierRows = $("supplier-rows");
    el.supplierActionsHead = $("supplier-actions-head");
    el.supplierAdd = $("supplier-add");
    el.supplierDialog = $("supplier-dialog");
    el.supplierForm = $("supplier-form");
    el.supplierCode = $("supplier-code");
    el.supplierNameAr = $("supplier-name-ar");
    el.supplierNameEn = $("supplier-name-en");
    el.supplierPhone = $("supplier-phone");
    el.supplierAddress = $("supplier-address");
    el.supplierSave = $("supplier-save");
    el.supplierCancel = $("supplier-cancel");
    el.supplierDialogError = $("supplier-dialog-error");
    el.accountRows = $("account-rows");
    el.doctorRows = $("doctor-rows");
    el.entryRows = $("entry-rows");
    el.ledgerSummary = $("ledger-summary");

    el.homeError = $("home-error");
    el.inventoryError = $("inventory-error");
    el.balancesError = $("balances-error");
    el.collectionsError = $("collections-error");
    el.privateError = $("private-error");
    el.privateNotice = $("private-notice");
    el.privateRows = $("private-rows");
    el.privateDebitTotal = $("private-debit-total");
    el.privateCreditTotal = $("private-credit-total");
    el.privateForm = $("private-form");
    el.privateLabel = $("private-label");
    el.privateDate = $("private-date");
    el.privateDebit = $("private-debit");
    el.privateCredit = $("private-credit");
    el.privateNote = $("private-note");
    el.privateAccountList = $("private-account-list");
    el.statAr = $("stat-ar");
    el.statArSub = $("stat-ar-sub");
    el.statStock = $("stat-stock");
    el.statStockSub = $("stat-stock-sub");
    el.statReceipts = $("stat-receipts");
    el.statReceiptsSub = $("stat-receipts-sub");
    el.statSales = $("stat-sales");
    el.statSalesSub = $("stat-sales-sub");
    el.homeReceipts = $("home-receipts");
    el.homeDrafts = $("home-drafts");
    el.stockRows = $("stock-rows");
    el.exportBalances = $("export-balances");
    el.receiptRows = $("receipt-rows");

    el.loginForm = $("login-form");
    el.loginUsername = $("login-username");
    el.loginPassword = $("login-password");
    el.loginSubmit = $("login-submit");
    el.loginError = $("login-error");
    el.loginDemo = $("login-demo");
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
    el.draftDate = $("draft-date");
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
    el.printInvoice = $("print-invoice");
    el.visitCustomer = $("visit-customer");
    el.visitProduct = $("visit-product");
    el.visitPrev = $("visit-prev");
    el.visitDel = $("visit-del");
    el.visitRet = $("visit-ret");
    el.visitCur = $("visit-cur");
    el.visitSt = $("visit-st");
    el.visitWarn = $("visit-warn");
    el.visitAmount = $("visit-amount");
    el.visitMethod = $("visit-method");
    el.visitNotes = $("visit-notes");
    el.visitSave = $("visit-save");
    el.visitRows = $("visit-rows");
    el.visitForm = $("visit-form");
    el.visitFields = $("visit-fields");
    el.visitDate = $("visit-date");
    el.visitRep = $("visit-rep");
    el.visitReadOnly = $("visit-read-only");
    el.visitsError = $("visits-error");
    el.visitStockHint = $("visit-stock-hint");
    el.visitRefresh = $("visits-refresh");
    el.visitsPrev = $("visits-prev");
    el.visitsNext = $("visits-next");
    el.visitPage = $("visits-page");
    el.lang = $("lang");
  }

  function wire() {
    el.loginForm.addEventListener("submit", login);
    el.logout.addEventListener("click", logout);
    el.invoiceForm.addEventListener("submit", saveDraft);
    el.addLine.addEventListener("click", function () { addLine(); recalcPreview(); });
    el.postDraft.addEventListener("click", postDraft);
    el.printInvoice.addEventListener("click", function () { window.print(); });

    [["", "il_all"], ["Draft", "status_draft"], ["Posted", "status_posted"], ["Voided", "status_voided"]]
      .forEach(function (opt) {
        var o = document.createElement("option");
        o.value = opt[0]; o.textContent = t(opt[1]);
        el.ilStatus.appendChild(o);
      });
    [el.ilStatus, el.ilFrom, el.ilTo].forEach(function (n) {
      n.addEventListener("change", function () { loadInvoiceList(); });
    });
    [el.invalertsStatus, el.invalertsSort].forEach(function (n) {
      n.addEventListener("change", function () { renderInventoryAlerts(); });
    });
    el.invalertsSearch.addEventListener("input", function () { renderInventoryAlerts(); });
    el.msDate.addEventListener("change", function () { loadManagementSummary(); });

    el.menuToggle.addEventListener("click", function () { setDrawer(!drawerOpen); });
    el.scrim.addEventListener("click", function () { setDrawer(false); });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && drawerOpen) setDrawer(false);
      if ((event.ctrlKey || event.metaKey) && String(event.key).toLowerCase() === "k") {
        event.preventDefault(); openPalette();
      }
    });

    document.querySelectorAll(".sidebar .nav-item, .bnav-btn, #bell").forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (btn.dataset.view === "__menu") { setDrawer(true); return; }
        showView(btn.dataset.view, btn.dataset.view === "invoice" ? true : undefined);
      });
    });

    document.querySelectorAll("[data-goto], [data-view-goto]").forEach(function (btn) {
      btn.addEventListener("click", function (event) {
        event.preventDefault();
        showView(btn.dataset.goto || btn.dataset.viewGoto, true);
      });
    });
    document.querySelectorAll("[data-refresh]").forEach(function (btn) {
      btn.addEventListener("click", function () { showView(btn.dataset.refresh, true); });
    });

    el.customer.addEventListener("change", async function () {
      var customer = customerById(el.customer.value);
      el.branchDisplay.value = customer ? branchLabel(customer.branch_id) : "";
      clearError(el.formError);
      try {
        await loadWarehouses(customer ? customer.branch_id : null);
      } catch (_e) {
        // Role-scoped warehouses keep server-side defaults; ids render later.
      }
    });

    el.lang.addEventListener("click", function () {
      loadI18n(state.lang === "ar" ? "en" : "ar").then(function () {
        if (state.user) {
          rebuildLines();
          if (currentSection === "customers-view") loadCustomers();
          if (currentSection === "module-view") {
            var key = (moduleKey() || "analytics");
            openPreview(key);
          }
          // Composed labels (policy line, status badges) re-render in the
          // new language instead of keeping fetch-time text.
          if (currentSection === "inventoryalerts-view") {
            renderInvalertsPolicyText();
            renderInventoryAlerts();
          }
        }
      });
    });

    el.palette.addEventListener("keydown", function (event) {
      var items = Array.prototype.slice.call($("palette-list").querySelectorAll("li"));
      if (!items.length) return;
      var currentIndex = items.findIndex(function (n) { return n.classList.contains("sel"); });
      if (event.key === "ArrowDown") {
        event.preventDefault();
        if (currentIndex >= 0) items[currentIndex].classList.remove("sel");
        items[(currentIndex + 1) % items.length].classList.add("sel");
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        if (currentIndex >= 0) items[currentIndex].classList.remove("sel");
        items[(currentIndex - 1 + items.length) % items.length].classList.add("sel");
      } else if (event.key === "Enter") {
        event.preventDefault();
        var sel = items[currentIndex] || items[0];
        if (sel) sel.click();
      }
    });
    el.paletteInput.addEventListener("input", function () { paletteSearch(el.paletteInput.value.trim()); });
    el.privateForm.addEventListener("submit", savePrivateEntry);
    el.customerAdd.addEventListener("click", function () { openCustomerDialog(null); });
    el.customerForm.addEventListener("submit", saveCustomer);
    el.customerCancel.addEventListener("click", closeCustomerDialog);
    el.customerDialog.addEventListener("cancel", function (event) {
      if (customerSaving) event.preventDefault();
      else ++customerDialogGeneration;
    });
    if (el.supplierAdd) el.supplierAdd.addEventListener("click", function () { openSupplierDialog(null); });
    if (el.supplierForm) el.supplierForm.addEventListener("submit", saveSupplier);
    if (el.supplierCancel) el.supplierCancel.addEventListener("click", closeSupplierDialog);
    if (el.supplierDialog) el.supplierDialog.addEventListener("cancel", function (event) {
      if (supplierSaving) event.preventDefault();
    });
    $("open-palette").addEventListener("click", openPalette);

    el.visitPrev.addEventListener("input", updateVisitCalc);
    el.visitDel.addEventListener("input", updateVisitCalc);
    el.visitRet.addEventListener("input", updateVisitCalc);
    el.visitCur.addEventListener("input", updateVisitCalc);
    el.visitForm.addEventListener("submit", saveVisit);
    el.visitCustomer.addEventListener("change", loadVisitStock);
    el.visitProduct.addEventListener("change", loadVisitStock);
    el.visitRefresh.addEventListener("click", loadVisits);
    el.visitsPrev.addEventListener("click", function () { visitsOffset = Math.max(0, visitsOffset - VISITS_PAGE_SIZE); loadVisits(); });
    el.visitsNext.addEventListener("click", function () { visitsOffset += VISITS_PAGE_SIZE; loadVisits(); });

    $("ledger-customer").addEventListener("change", function () {
      renderCustomerLedger($("ledger-customer").value);
    });

    window.addEventListener("online", function () { el.offlineChip.classList.add("hidden"); });
    window.addEventListener("offline", function () { el.offlineChip.classList.remove("hidden"); });
    if (!navigator.onLine) el.offlineChip.classList.remove("hidden");
  }

  function moduleKey() {
    // The active preview key equals whichever nav button is highlighted.
    var active = document.querySelector(".nav-item.active, .bnav-btn.active");
    return active ? active.dataset.view : null;
  }

  // Public/cold deployments (e.g. a first-hop tunnel) can fail the very first
  // /meta fetch; the hint is cosmetic, so retry once and otherwise stay quiet.
  async function fetchMeta() {
    for (var attempt = 0; attempt < 2; attempt++) {
      try { return await api("/meta"); } catch (_e) {
        await new Promise(function (resolve) { setTimeout(resolve, 700); });
      }
    }
    return null;
  }

  async function init() {
    cacheElements();
    await loadI18n(localStorage.getItem("lang") || "ar");
    var meta = await fetchMeta();
    if (meta && meta.demo_mode && currentSection === "login-view") {
      el.loginDemo.classList.remove("hidden");
    }
    wire();
    wireProducts();
    addLine();
    updateVisitCalc();
    renderVisits();
    var token = localStorage.getItem("token");
    if (token) {
      state.token = token;
      try { await boot(); } catch (_e) { if (state.token === token) await logout(); }
    }
  }

  document.addEventListener("DOMContentLoaded", init);
})();
