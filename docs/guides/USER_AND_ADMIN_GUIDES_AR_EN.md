# ElsebaeyPharma ERP — Bilingual Role User & Admin Guides | أدلة الاستخدام والإدارة (AR / EN)

- **Product / النظام:** ElsebaeyPharma ERP (`شركة السباعي فارما` — configurable via `platform_setting`)
- **Supported Browsers & Devices:** Chrome / Edge / Safari (Desktop `1440px+` & Mobile PWA `390px+`, Arabic RTL + English LTR toggle `#lang`)
- **Offline Behavior (RC2):** Read-only cached shell with live offline indicator (`وضع عدم الاتصال`); queued offline stock-visit sync ships in RC3 (`RC3-09`).

---

## 1. Owner & Finance Guide | دليل المالك والحسابات

### العربية
1. **تسجيل الدخول والتبديل بين اللغتين:** افتح رابط النظام، أدخل اسم المستخدم وكلمة المرور (`10` أحرف فأكثر)، واضغط زر `English / العربية` بالأعلى للتبديل الفوري بين RTL وLTR.
2. **إدارة المستخدمين والصلاحيات (المالك فقط):** افتح **المستخدمون والصلاحيات** لتعيين الدور (`owner`, `finance`, `sales_manager`, `district_manager`, `medical_rep`, `warehouse_staff`, `read_only_auditor`) وتحديد الفروع والمناطق المسموح بها. أي تعديل في الدور يُلغي جلسات المستخدم القديمة تلقائياً.
3. **الفواتير والتحصيل والطباعة:** أنشئ مسودة فاتورة، اختر التشغيلة حسب الأقدم صلاحية (**FEFO**)، احفظ المسودة ثم راجعها واطبعها (`Ctrl+P` / حفظ PDF بحجم A4 — تُخفى تلقائياً الأصناف ذات الكمية صفر). عند تفعيل الترحيل (`POSTING_ENABLED=true`) اضغط **ترحيل** لخصم المخزون وقيد الذمم ذرياً، ثم سجّل سندات القبض في **التحصيلات**.
4. **المرتجعات والاعتماد المالي (`RC2-12`):** كل مرتجع يدخل **الحجر الصحي (`quarantined`)** أولاً. المالك أو الحسابات فقط يعتمدون التسوية: **إعادة للمخزون الصالح (`approved_restock`)** أو **إعدام (`scrapped`)** مع إصدار إشعار دائن آلي متوافق مع ضريبة القيمة المضافة (`14%` أو `0%`).
5. **تصدير اليوم الأول للمحاسب (`RC2-13`):** صدّر ملفات CSV بترميز UTF-8 BOM (تفتح مباشرة بالعربية في Excel مع حماية ضد صيغ الحقن) للفواتير، تقرير المبيعات، أرصدة المخزون، أعمار الذمم، والتحصيلات.
6. **الحسابات الخاصة (`private`):** مرئية للمالك فقط ومعزولة تماماً في مخطط قاعدة بيانات مستقل.

### English
1. **Sign-In & Language Switch:** Open `/app/`, sign in (passwords >= 10 chars, 12h idle / 24h absolute session TTL), and use the top-right language toggle for instant Arabic RTL / English LTR switching.
2. **User Administration (Owner Only):** Assign roles and explicit branch/territory grants. Any role or scope revocation immediately invalidates prior sessions.
3. **Invoicing, FEFO Batch Picker & Collections:** Select customer, warehouse, product, and FEFO-ordered batch (earliest expiry first). Print / Save as PDF uses A4 layout with zero-quantity lines hidden. Posting atomically updates stock, AR ledger, and audit log (returns `409` while `POSTING_ENABLED=false`).
4. **Returns Settlement (`RC2-12`):** All returns enter `quarantined` status first. Only `owner` or `finance` can settle (`approved_restock` or `scrapped`) with automatic VAT-aware AR credit notes and double-settlement `409` protection.
5. **Day-1 Accountant Exports (`RC2-13`):** Download UTF-8 BOM formula-safe CSVs for `/invoices/export`, `/invoices/report/export`, `/inventory/stock/export`, `/ar/aging/export`, and `/collections/export`.

---

## 2. Sales Representative & Manager Guide | دليل المندوب ومدير المبيعات

### العربية
1. **نطاق العرض:** يرى المندوب ومدير المبيعات عملاءهم وأهدافهم وفواتيرهم وزياراتهم داخل المناطق والفروع المخصصة لهم فقط (عزل كامل بين المناطق).
2. **زيارات المخزون والمسحوب الفعلي:** افتح **زيارات المخزون**، اختر العميل والصنف، وأدخل الرصيد السابق والمورّد والمرتجع والرصيد الفعلي؛ يحسب النظام تلقائياً **المسحوب الفعلي = السابق + المورّد − المرتجع − الحالي** دون تعديل مخزون الشركة.
3. **إنشاء مسودات الفواتير:** اختر التشغيلة الأقدم صلاحية (تُرفض التشغيلات المنتهية تلقائياً). حد الخصم الافتراضي للمندوب `<= 30%` (الخصومات الأعلى تتطلب اعتماد المالك أو الحسابات).
4. **متابعة الأهداف:** افتح **الأهداف** لمقارنة الهدف الشهري (بالوحدات) مع المبيعات المرحّلة الفعلية.

### English
1. **Strict Scope Isolation:** Reps and managers view only customers, visits, targets, and invoices within their assigned territories/branches.
2. **Stock Visits & Sell-Through:** Record customer shelf counts; the server computes `sell_through = prev + delivered - returned - current` separately from company warehouse stock.
3. **Draft Invoices & Discounts:** Expired batches are hard-blocked; default rep discount ceiling is `30%` (configurable via `REP_MAX_DISCOUNT_PCT`; higher discounts require `owner`/`finance`).
4. **Targets & Telegram:** View monthly target vs posted actuals in the PWA or via allowlisted private Telegram `/targets` and `/balance` commands (strictly scoped to your territory).

---

## 3. Warehouse Staff Guide | دليل أمين المخزن

### العربية
1. **القوائم المخصصة:** يعرض النظام لأمين المخزن شاشات المخزون، التحويلات، المرتجعات، والتنبيهات الخاصة بفرعه فقط (تُخفى شاشات العملاء/الأسعار غير المصرح بها منعاً للأخطاء).
2. **أرصدة التشغيلات والصلاحية:** راجع الكميات وتواريخ الصلاحية؛ تظهر تنبيهات **قرب الانتهاء (`90` يوماً)** والتنبيه **الحرج (`30` يوماً)**.
3. **التحويلات بين المخازن (`RC2-02`):** حوّل الكميات مع الحفاظ الكامل على التشغيلة وتاريخ الصلاحية دون أي أثر مالي أو ذمم.
4. **استلام المرتجعات في الحجر الصحي:** سجّل المرتجع للعملاء داخل فرعك فقط (`P3C-03`)؛ يدخل المرتجع في الحجر ولا يُضاف للرصيد الصالح للبيع إلا بعد اعتماد المالك أو الحسابات.

### English
1. **Focused Navigation:** Warehouse staff see only assigned-branch stock, movements, transfers, returns intake, and inventory alerts; out-of-scope master directories are hidden (`RC2-01`).
2. **Batches & Expiry Alerts:** Monitor FEFO lots with configurable near-expiry warning (`90d`) and critical (`30d`) thresholds.
3. **Warehouse Transfers:** Move batched or unbatched stock safely (canonical lock ordering prevents deadlocks) with zero AR/sales side effects.
4. **Quarantine Returns Intake:** Log returns for assigned-branch customers only (`P3C-03`); stock enters quarantine until `owner`/`finance` approves restock or scrap.

---

## 4. Admin & IT Operator Guide | دليل الإدارة والتشغيل التقني

- **Admin Split (`Eli T8`):** Eli operates infrastructure, Docker, Cloudflare Tunnel/Access, and backups (Technical Admin); ElsebaeyPharma Owner manages business users, roles, and approvals (Business Admin).
- **Single-Worker Rule:** Always keep `UVICORN_WORKERS=1` so the process-local auth rate limiter (`10/account`, `50/IP` per `300s`) stays consistent.
- **Reverse Proxy Trust:** Set `RATE_LIMIT_TRUSTED_PROXIES` ONLY to the exact Cloudflare/Nginx proxy CIDR; leave empty on direct LAN.
- **Passwords & Sessions:** Minimum `10` characters (PBKDF2-SHA256), `12h` idle / `24h` absolute TTL, instant session revocation on role/scope change.
- **Key Runbooks:**
  - Buyer-Site Install & Cutover: `PHASE4_BUYER_SITE_RUNBOOK_20261121.md`
  - Cloudflare Free Tunnel & Access: `docs/CLOUDFLARE_FREE_TUNNEL_RUNBOOK.md`
  - Telegram Bot Operations: `docs/TELEGRAM_BOT_RUNBOOK.md`
  - Backup, Recovery & Ops Monitoring: `docs/BACKUP_OPS_AND_ROLLBACK_RUNBOOK_AR_EN.md`
