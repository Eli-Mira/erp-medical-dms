# HANDOVER – DAY 1 EXPORTS & RC3 DEFERRALS  
**(Bilingual – English + Arabic summary)**  

---  

## 1️⃣ Day‑1 Accountant CSV Exports (shipped in RC2)  

| # | Export | HTTP Endpoint | Purpose | Key Technical Guarantees |
|---|--------|---------------|---------|--------------------------|
| 1 | **Invoices Register** | `GET /invoices/export` | Full list of posted invoices (header + line items). | • UTF‑8 **BOM** (`\ufeff`) for Excel Arabic opening.<br>• All text fields prefixed with a single quote (`'`) to neutralize leading `=`, `@`, `+`, `-`, tab (`\t`) or carriage‑return (`\r`).<br>• Monetary columns are **exact Decimal strings** (no rounding).<br>• Server‑side filtering by **role / branch / territory** – only rows the caller is authorized to see are emitted. |
| 2 | **Sales Performance Report** | `GET /invoices/report/export` | Aggregated sales per rep, product, period. | Same BOM & formula‑neutralisation rules as above. Decimal totals are rendered with full precision. |
| 3 | **Stock Balances** | `GET /inventory/stock/export` | Current on‑hand quantity & valuation per SKU / warehouse. | BOM, quote‑prefix, exact decimals, scoped to the requester’s permitted warehouses. |
| 4 | **Collections / Receipts** | `GET /collections/export` | All cash, bank and other receipt entries linked to invoices. | BOM, quote‑prefix, exact decimals, role‑based visibility (e.g., treasury vs. sales). |
| 5 | **Customer AR Suite** (four related endpoints) | • `GET /ar/balances/export`  <br>• `GET /ar/entries/export`  <br>• `GET /ar/aging/export`  <br>• `GET /ar/statements/{customer_id}/export` | • Current AR balances per customer.<br>• Ledger‑style entry list (debits/credits).<br>• Aging buckets (0‑30, 31‑60, 61‑90, >90).<br>• Printable statement for a single customer. | All files share the same CSV conventions (UTF‑8 BOM, leading‑quote escaping, exact Decimal strings). Access is limited to the caller’s **customer‑group / territory** scope. |

### Technical notes (common to all five exports)

* **UTF‑8 BOM (`\ufeff`)** – required so that Microsoft Excel on Windows automatically detects UTF‑8 and displays Arabic characters correctly.  
* **Formula‑safe text** – any field that could be interpreted as a spreadsheet formula is prefixed with a single quote (`'`). This also covers leading tabs (`\t`) and carriage‑returns (`\r`).  
* **Decimal representation** – numbers are emitted as plain strings (e.g., `"12345.67"`), never in scientific notation, preserving the exact value stored in the database.  
* **Scoping** – the API enforces the caller’s **role**, **branch**, and **territory** filters before generating the CSV. No post‑filtering is required on the client side.  

---  

## 2️⃣ RC3 Deferrals (Buyer‑approved – not part of Day‑1 Go‑Live / RC2)  

> **Arabic concise summary** – **الدفعات المؤجلة في RC3** (موافق عليها من المشتري، غير مشمولة في الإطلاق الأولي RC2).  

| # | Feature (English) | Feature (Arabic) | Reason for deferral |
|---|-------------------|------------------|---------------------|
| 1 | Cash / Bank Treasury & Expense Vouchers | قسائم الخزينة / المصاريف البنكية | Requires complex multi‑currency workflow and audit‑trail UI not ready for RC2. |
| 2 | Full General Ledger (GL), Trial Balance, P&L, Balance Sheet | دفتر الأستاذ العام، ميزان المراجعة، بيان الأرباح والخسائر، الميزانية العمومية | Dependent on complete chart‑of‑accounts redesign and consolidation engine. |
| 3 | Purchasing / AP / Supplier Invoices | المشتريات / حسابات الدائنين / فواتير الموردين | Integration with supplier portal and tax‑validation service postponed. |
| 4 | Payroll & HR | الرواتب والموارد البشرية | Needs integration with external payroll provider and employee‑self‑service module. |
| 5 | Fixed Assets | الأصول الثابتة | Asset depreciation schedules and lifecycle management to be built in RC3. |
| 6 | Additional Price Tiers (`سعر 1..4`) | مستويات أسعار إضافية (`سعر 1..4`) | Current data model only supports a single `base_price` + line‑level discount; tiered pricing redesign scheduled for RC3. |
| 7 | Private Owner Workbook Migration (`حسابات خاصه.xlsx`) | ترحيل دفتر حسابات خاصة (`حسابات خاصه.xlsx`) | Kept manual/local; migration tooling will be delivered later. |
| 8 | Telegram Group / Multi‑Rep Bot Flows | تدفقات بوت تلغرام للمجموعات / ممثلي المبيعات المتعددين | Phase 1 limited to owner‑only read‑only bot; full multi‑rep automation deferred. |
| 9 | Offline Rep Sync / GPS / Dedicated Mobile Rep App (PWA online‑first) | مزامنة غير متصلة للمندوبين / GPS / تطبيق موبايل مخصص (PWA) | Requires offline storage engine and device‑level GPS integration; slated for RC3. |
|10| Returns Accounting (approval, saleable release, AR credit note, VAT reversal) | محاسبة المرتجعات (الموافقة، تحرير الصنف القابل للبيع، إشعار خصم AR، عكس الضريبة) | Targeted for **RC2‑12** (a post‑RC2 hot‑fix) or **RC2.1** as a non‑blocking UAT item; full flow will be stable only in RC3. |

### Summary (Arabic)

> **ملخص**: تم تأجيل عشرة مكونات رئيسية إلى الإصدار RC3 بناءً على قرارات المشتري (A5, A8, A10). تشمل هذه المكونات جميع عمليات الخزينة، دفتر الأستاذ العام، المشتريات، الرواتب، الأصول الثابتة، تسعير متعدد المستويات، ترحيل دفتر خاص، بوتات تلغرام المتقدمة، تطبيق المندوب غير المتصل، ومحاسبة المرتجعات. بعضها سيظهر كتصحيحات صغيرة في RC2‑12 أو RC2.1، لكن الدعم الكامل سيُطرح في RC3.  

---  

*Prepared by the Engineering Handover Team – 2026‑11‑21*
