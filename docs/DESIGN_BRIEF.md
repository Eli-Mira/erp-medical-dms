# DESIGN_BRIEF.md — Medical Company System (ERP-Lite / DMS)

**Document Status:** Approved Baseline Design Specification  
**Version:** 1.0.0 (Phase 1 Planning Artifact)  
**Applicability:** Full-stack Responsive PWA (Desktop & Mobile)  
**Target Organization:** Egyptian Medical Distribution Enterprise (5 Branches: Dakahlia, Sharqia, Fayoum, 6th of October, Gharbia)  
**Cross-References:** `MEDICAL_COMPANY_SYSTEM_MASTER_SPEC_V2.md`, `DECISION_LOG.md`, `MODULE_MAP.md`, `CURRENT_WORKFLOWS.md`

---

## 1. Executive Summary & Design Mission

The Medical Company System replaces a mission-critical constellation of 7 interconnected Arabic Excel workbooks (spanning 361 sheets, hundreds of columns, and millions of Egyptian Pounds in transactional volume) with a modern, high-reliability, zero-cost, responsive Progressive Web Application (PWA).

### Design Mission
1. **Dignified Enterprise Utility:** The UI must be an ergonomic, fast, data-dense workhorse for accountants, warehouse clerks, sales reps in the field, and the CEO. It rejects decorative SaaS fluff, low-contrast pastel trends, and fragile spreadsheet mimicry.
2. **Arabic-First Bi-Directional Fluidity:** Arabic is the operational language of record. The interface is engineered RTL-first with zero awkward layout hacks, while accommodating inline Latin technical text (medical names, batch numbers, chemical formulas, international codes).
3. **Ergonomic Information Density:** Replaces wide manual spreadsheets (such as the 747-column AR ledger) with organized, high-density data tables, smart virtualized scrolling, sticky contextual headers, and keyboard-first navigation.
4. **Resilient Field Mobility:** The PWA must deliver a tactile, high-contrast mobile experience for sales representatives conducting on-site pharmacy stock audits and collections under bright Egyptian sunlight.

---

## 2. Company Branding Direction (Working Identity: Name TBD)

### 2.1 Brand Identity Profile
- **Company Status:** Established Egyptian pharmaceutical and medical supplies distributor.
- **Brand Archetype:** Precision, Clinical Trust, Operational Rigor, Reliability.
- **Working Name:** `MedDistro Egypt` / `DMS-Med` (Placeholder pending official trade name confirmation).
- **Brand Essence:** Sterile clarity balanced with approachable executive usability.

### 2.2 Visual Tone & Atmosphere
- **Surfaces:** Clean, crisp, high-contrast light surfaces (`#F8FAFC` to `#FFFFFF`) with subtle, functional slate border delineation (`#E2E8F0`). Avoid dark-mode-first complexity in MVP; field workers and warehouse operators work under ambient daylight and fluorescent warehouse lamps where high-contrast light themes excel.
- **Atmospheric Palette:** Deep clinical navy, medical sapphire, and slate gray, accented by crisp emerald (cash collections/posted vouchers) and focused amber (approvals/pending batches).
- **Imagery & Iconography:** Minimalist, functional SVG iconography (Lucide / Heroicons). Strictly zero stock photography, decorative 3D mascots, or extraneous illustration in business workflows.

---

## 3. Bilingual (Arabic / English) & Bi-directional RTL Architecture

### 3.1 Directionality & Layout Symmetry
- **RTL as Default:** The application defaults to Arabic (`dir="rtl"`, `lang="ar-EG"`). Users can switch instantly to English (`dir="ltr"`, `lang="en-US"`) via a top-bar language toggle.
- **CSS Logical Properties:** All stylesheets and utility classes strictly utilize logical box properties to guarantee zero layout corruption between RTL and LTR:
  - `margin-inline-start` / `margin-inline-end` (never hardcoded `margin-left` / `margin-right`)
  - `padding-inline-start` / `padding-inline-end`
  - `inset-inline-start` / `inset-inline-end`
  - `text-align: start` / `text-align: end`
- **Component Mirroring Rules:**
  - **Navigation & Drawers:** In RTL, sidebars anchor to the right edge; in LTR, to the left edge.
  - **Breadcrumbs & Flow Indicators:** Flow right-to-left in RTL (`الرئيسية ← المبيعات ← فاتورة جديدة`), with chevron icons rotated 180 degrees.
  - **Progress Bars & Gauges:** Fill from right to left in RTL.
  - **Table Columns:** Primary row identifier (Customer Name / Product Name) anchors to the right in RTL. Action icons (Edit/Print/Delete) sit on the far left.

### 3.2 Mixed-Direction Bi-Text (BiDi) Handling
Medical distribution in Egypt constantly mixes Arabic administrative data with Latin pharmacological identifiers.
- **Rules for Mixed Strings:**
  - Arabic entity names (`صيدلية السلام الدولية`, `مخزن الدلتا`) render with natural Arabic shaping.
  - Latin drug names (`Augmentin 1g Tab`, `Cetal 500mg`, `Amoclan BID 1000mg`) must be isolated with HTML `<bdi>` (Bi-directional Isolation) tags or CSS `unicode-bidi: isolate` to prevent punctuation hopping or reversal.
  - Batch numbers (`BAT-2026-X09`), serial codes, and phone numbers (`+20 100 123 4567`) must maintain explicit LTR directionality (`dir="ltr"`).

### 3.3 Numeric, Currency, & Date Formatting
- **Numerals:** Standard Western Arabic numerals (`0, 1, 2, 3...`) are standard across Egyptian medical distribution invoicing and accounting to avoid confusion during rapid audits. The typography stack must render tabular, lining numerals (`font-variant-numeric: tabular-nums`).
- **Currency:** Egyptian Pound:
  - Arabic display: `ج.م 1,284,294.75` (Code symbol followed by space and formatted number).
  - English display: `EGP 1,284,294.75`.
  - Negative balances: Displayed distinctly as `-ج.م 45,000.00` or `(12,500.00 ج.م)` in distinct danger red (`#DC2626`), never ambiguous unstyled text.
- **Dates:** 
  - Standard format: `YYYY-MM-DD` (ISO standard for data stability) or `DD/MM/YYYY` (Egyptian commercial standard).
  - Relative time for operational feeds: `منذ ساعتين` / `2 hours ago`.

---

## 4. Typography & Color System

### 4.1 Typography Stack (Zero-Cost / Open-Source)
Free, high-performance web fonts loaded via self-hosted assets or Google Fonts CDN:

| Language / Role | Font Family | Fallback Stack | Weights Used | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Arabic Primary UI** | **Cairo** | `Segoe UI, Tahoma, sans-serif` | 400 (Regular), 600 (SemiBold), 700 (Bold) | High legibility in dense Arabic grids, clean baseline alignment |
| **Arabic Longform / Reports** | **IBM Plex Sans Arabic** | `Tahoma, Arial, sans-serif` | 400 (Regular), 500 (Medium), 600 (SemiBold) | Printable invoices, audit logs, detailed notes |
| **Latin / Numeric Primary** | **Inter** | `system-ui, -apple-system, sans-serif` | 400, 500, 600, 700 | Global microcopy, English UI, table headings |
| **Monospace / Codes** | **JetBrains Mono** | `Consolas, monospace` | 400, 500 | Batch codes, Invoice IDs, Serial numbers, IP addresses |

#### Type Scale Hierarchy
- **Display 1 (Dashboard Totals):** `32px` / Line Height: `40px` / Bold (Cairo / Inter)
- **Heading 1 (Page Title):** `24px` / Line Height: `32px` / SemiBold
- **Heading 2 (Section Title / Card Header):** `18px` / Line Height: `26px` / SemiBold
- **Heading 3 (Table Group / Modal Header):** `15px` / Line Height: `22px` / SemiBold
- **Body Regular (Forms, Labels):** `14px` / Line Height: `20px` / Regular
- **Body Dense / Grid Cell:** `13px` / Line Height: `18px` / Regular (Optimized for data entry)
- **Caption / Meta Data:** `11px` / Line Height: `16px` / Regular (Timestamps, Sub-labels)

### 4.2 Semantic Color Palette (WCAG AA Compliant)

All color tokens satisfy WCAG 2.1 AA contrast ratios (minimum 4.5:1 for normal text, 3:1 for large text and interactive components):

```css
:root {
  /* Surface & Background Tokens */
  --bg-app: #F8FAFC;          /* Cool Slate light background */
  --bg-surface: #FFFFFF;      /* Clean card and table surface */
  --bg-surface-subtle: #F1F5F9;/* Inactive tabs, table hover, disabled fields */
  --border-subtle: #E2E8F0;   /* Structural grid borders */
  --border-strong: #CBD5E1;   /* Input borders and active dividers */

  /* Text Tokens */
  --text-primary: #0F172A;    /* Slate-900: High-contrast primary reading text */
  --text-secondary: #475569;  /* Slate-600: Field labels, table headers */
  --text-muted: #64748B;      /* Slate-500: Metadata, timestamps, placeholders */
  --text-inverse: #FFFFFF;    /* Pure white on solid colored badges */

  /* Primary Brand (Clinical Navy & Sapphire) */
  --primary-700: #0F2942;     /* Deep Executive Navy (Sidebar, Primary Headings) */
  --primary-600: #1A4B75;     /* Corporate Brand Blue */
  --primary-500: #2563EB;     /* Action Blue (Buttons, Active Links, Focus Rings) */
  --primary-50:  #EFF6FF;     /* Active Row Highlight, Selected Tab */

  /* Secondary Accent (Clinical Teal) */
  --accent-600:  #0D9488;     /* Warehouse & Stock Action Accent */
  --accent-500:  #14B8A6;     /* Indicators, Transfer confirmations */
  --accent-50:   #F0FDFA;     /* Stock Movement callouts */

  /* Semantic Status Tokens */
  --status-draft-bg: #FEF3C7; --status-draft-text: #92400E; --status-draft-border: #FCD34D; /* Amber */
  --status-posted-bg: #DCFCE7; --status-posted-text: #166534; --status-posted-border: #86EFAC; /* Emerald */
  --status-voided-bg: #FEE2E2; --status-voided-text: #991B1B; --status-voided-border: #FCA5A5; /* Rose */
  --status-info-bg: #DBEAFE;   --status-info-text: #1E40AF;   --status-info-border: #93C5FD; /* Sky */

  /* Private / CEO Protected Boundary */
  --security-boundary-border: #7C3AED; /* Deep Violet indicator for CEO Private Accounts */
  --security-boundary-bg:     #F5F3FF;
}
```

---

## 5. Component Design Rules & Patterns

### 5.1 Action Buttons & Interactive Controls
- **Primary Action (Commit / Save / Post):** Solid `--primary-500` background, white text, 6px subtle border radius. Height: `38px` (desktop), `44px` (touch mobile).
- **Secondary Action (Cancel / Back / Reset):** White surface, `--border-strong` border, `--text-primary` label.
- **Destructive Action (Void Voucher / Cancel Order):** Soft danger background with `--status-voided-text`, escalating to solid red confirmation dialogs.
- **Focus Rings:** Distinct 2px outer outline in `--primary-500` with 2px offset for keyboard navigability. Never suppress `outline: none` without replacement.

### 5.2 Form Inputs & High-Speed Data Entry
- **Combobox / Searchable Autocomplete:** Customers (over 1,000 pharmacies and warehouses) and products must feature ultra-fast asynchronous search with fuzzy Arabic matching (matching both with and without hamzas: `أ, إ, ا` and `ة / ه`).
- **Tabular Entry Navigation:** When entering multiple invoice lines, hitting `Enter` or `Tab` automatically advances the cursor to the next logical cell (Product → Batch → Qty → Discount % → Next Row) to match Excel's high-speed data-entry ergonomics.
- **Form Feedback:** Inline micro-validation. Errors display in red below the input with an explanatory message (e.g., "الكمية تتجاوز الرصيد المتاح بالمخزن" / "Quantity exceeds available warehouse stock").

### 5.3 Posting Status Indicators (Draft → Posted → Voided)
Every document that affects money, stock, or customer balances (Invoices, Receipts, Stock Transfers, Adjustments) must prominently display its posting lifecycle state in the header:
- **مسودة (Draft):** Amber badge (`--status-draft-bg`), dotted border. Editable, does not mutate inventory or ledgers.
- **مرحل (Posted):** Solid Emerald badge (`--status-posted-bg`), lock icon. Read-only. Ledgers and inventory updated. Edits locked.
- **ملغي (Voided):** Struck-through text, Muted Rose badge (`--status-voided-bg`). Explicitly displays who voided it, timestamp, and mandatory Reason Code.

### 5.4 Simple Approvals & Reason-Code Prompts
- **Approval Banners:** Invoices with discounts exceeding rep authorization, warehouse returns, or price overrides automatically spawn an amber banner at the top:
  `⚠️ يتطلب هذا المستند موافقة المدير المالي (خصم إضافي: 5%)`
- **Mandatory Reason-Code Dialog:** When voiding any posted document, recording a customer return, or adjusting warehouse quantities, a modal forces the user to select an official reason code:
  - Dropdown options: `بضاعة تالفة (Damaged goods)`, `انتهاء الصلاحية (Expired batch)`, `خطأ في التسجيل (Data entry error)`, `مرتجع عميل (Customer return)`, `تسوية جردية (Inventory reconciliation)`.
  - Free-text explanation field (mandatory if reason is "أخرى / Other").

### 5.5 Protected Private Accounts Security Boundary
Per Decision D10 and `MODULE_MAP.md`, Owner/Private Accounts (`حسابات خاصة`) live in the same PostgreSQL database but exist within an isolated security boundary.
- **Visual Distinction:** When an authorized executive accesses this module, the top navigation displays a prominent violet security badge: `🔒 حسابات سرية - وصول مقيد للرئيس التنفيذي` (Restricted CEO Confidential).
- **Zero Accidental Leaks:** Financial rollups and charts in general screens automatically omit private ledger lines unless specifically viewed within the authenticated private context.

---

## 6. Table & Grid Behavior (Dense Medical ERP Core)

Tables represent the heart of the operational system. They replace sprawling Excel sheets while guaranteeing immediate visibility of balances, transactions, and inventory.

### 6.1 Grid Architecture & Navigation
- **Sticky Column & Header Anchoring:**
  - Table headers remain fixed at the top during vertical scrolling.
  - In RTL mode, the rightmost columns (Customer Name, Product Code) remain frozen during horizontal scrolling.
  - The leftmost column (Action menu: View, Print, Void) remains pinned.
- **Row Density Modes:**
  - **Compact (Default):** Row height `36px`, font size `13px`. Maximum visible information for accounting audits.
  - **Standard:** Row height `44px`, font size `14px`. Optimized for tablet and standard touch devices.
- **Visual Alternation:** Subtle alternating row zebra striping (`#FFFFFF` / `#F8FAFC`) with clear hover highlighting (`#EFF6FF`).

### 6.2 Numeric Alignment & Decimal Conventions
- **Alignment Rule:**
  - Text (Customer, Product, Territory, Rep) aligns to the **Start** (Right in RTL, Left in LTR).
  - Quantities, Currency, Balances, and Percentages align to the **End** (Left in RTL, Right in LTR).
  - This ensures all numbers align strictly along their decimal point for instant visual scanning.
- **Currency & Precision:**
  - Quantities formatted as integers or up to 2 decimal places if partial packaging exists.
  - Currency strictly formatted with 2 decimal places and thousands commas: `1,450.00`.
  - Zero Values: Formatted as a subtle gray dash (`—`) rather than `0.00` to prevent visual clutter in wide tables.

### 6.3 Wide Sheet Adaptations (e.g., 747-Column AR Ledger & Multi-Warehouse Views)
- **Pivot/Normalization:** The legacy 747-column wide spreadsheet layout is transformed into an interactive Ledger Card:
  - Top filter: Select Customer / Pharmacy.
  - Header: Displays Current Balance, Credit Limit, Aging Summary (0-30, 31-60, 61-90, 90+ days), Assigned Sales Rep.
  - Body: Chronological transactional ledger with columns: `Date`, `Voucher Type`, `Voucher #`, `Description`, `Debit (مدين)`, `Credit (دائن)`, `Running Balance (الرصيد)`.
- **Row Expansion (Accordion Detail):** In master sales tables, clicking an invoice row smoothly expands an inline sub-table displaying item lines, batch numbers, expiry dates, unit prices, discounts, and VAT breakdowns without leaving the page.

### 6.4 Table Action Bar
Every major data grid provides a persistent top toolbar:
- Quick Global Search (Fuzzy text filter across all visible columns).
- Branch / Governorate Selector (`الدقهلية`, `الشرقية`, `الفيوم`, `6 أكتوبر`, `الغربية`, `الكل`).
- Date Range Picker with pre-sets: `اليوم (Today)`, `هذا الأسبوع (This Week)`, `هذا الشهر (This Month)`, `الربع الحالي (Current Quarter)`, `السنة الحالية (YTD)`, `مخصص (Custom)`.
- Export dropdown: `Export to Excel (.xlsx)` and `Export to PDF`.

---

## 7. Dashboard & Analytics Layout

The executive dashboard replaces the tedious process of opening multiple Excel workbooks to compute company performance. It satisfies Section 7 of the Master Spec V2.

### 7.1 Dashboard Layout Grid

```
+-------------------------------------------------------------------------------------------------------+
| TOP CONTROL BAR: [Branch: All Branches ▼]  [Date Range: Month-to-Date ▼]  [Refresh]  [Export Summary]  |
+-------------------------------------------------------------------------------------------------------+
| EXECUTIVE KPI CARDS (Row 1 - 4 Key Financial Indicators)                                              |
| +--------------------+ +--------------------+ +--------------------+ +--------------------+           |
| | مبيعات الشهر (Sales) | | التحصيلات (Collect)| | المديونيات (AR)    | | صافي الربح (Profit) |           |
| | ج.م 4,850,200      | | ج.م 3,920,000      | | ج.م 8,420,150      | | ج.م 745,800        |           |
| | ↑ 12% vs last mo   | | 80.8% of Sales     | | 14 overdue >60d    | | Margin: 15.4%      |           |
| +--------------------+ +--------------------+ +--------------------+ +--------------------+           |
+-------------------------------------------------------------------------------------------------------+
| COMPARATIVE ANALYTICS & TRENDS (Row 2 - 2 Columns)                                                    |
| +--------------------------------------------------+ +-----------------------------------------------+ |
| | Sales vs. Collections Trend (12 Months)          | | Sales by Branch / Territory (مبيعات الفروع)   | |
| | [Dual-bar / line chart: Invoiced vs Cash Inflow] | | [Interactive horizontal stacked bar chart:    | |
| |                                                  | |  Dakahlia, Sharqia, Fayoum, 6 Oct, Gharbia]   | |
| +--------------------------------------------------+ +-----------------------------------------------+ |
+-------------------------------------------------------------------------------------------------------+
| INVENTORY & PERFORMANCE (Row 3 - 3 Columns)                                                           |
| +------------------------+ +--------------------------------+ +--------------------------------------+ |
| | Inventory Health       | | Rep Performance vs Target      | | Top 5 Debtors (أعلى مديونيات عملاء) | |
| | - Stock Value: 12.4M   | | Rep A: 94% [████████░]         | | 1. مخزن الأمل: ج.م 420,000         | |
| | - Stock Cover: 42 Days | | Rep B: 88% [███████░░]         | | 2. صيدلية السلام: ج.م 310,000      | |
| | - Overstock alerts: 6  | | Rep C: 105%[█████████]         | | 3. صيدلية النور: ج.م 280,000       | |
| +------------------------+ +--------------------------------+ +--------------------------------------+ |
+-------------------------------------------------------------------------------------------------------+
| OPERATIONAL ALERTS & NEAR-EXPIRY FEED (Row 4 - Full Width)                                            |
| [⚠️ 4 Batches Near Expiry (<60 Days)]  [🔴 2 Customers Exceeded Credit Limit]  [📦 5 Stock Minimums] |
+-------------------------------------------------------------------------------------------------------+
```

### 7.2 Widget Specifications & Business Formulas
1. **Sales Metric Card:** Total invoiced net amount for selected period (`∑ Line Total`). Shows delta comparison against previous period.
2. **Collections Metric Card:** Total cash and bank receipts deposited for selected period. Displays collection ratio (`(Collections / Sales) * 100`).
3. **Receivables & Aging:** Outstanding customer balance total with flag for debts older than 60 days.
4. **Sales by Branch Widget:** Displays performance across the 5 company branches (respecting the business rule: Sales Territory vs Source Warehouse).
5. **Sales Targets vs. Actual (V2 §2B.13):** Progress bars per sales representative and territory.
6. **Stock Cover & Overstock Alerts (V2 §2B.14-15):** Computes `Current Stock / (Recent 30-day Average Daily Sales)`. Highlights products with cover exceeding 90 days (Overstock) or under 15 days (Re-order Alert).
7. **Doctor / KOL Promotional Spend (V2 §2B.16-18):** Executive overview of marketing expenses grouped by medical specialty and doctor/KOL.

---

## 8. Responsive Behavior & Mobile Field Experience

The application is deployed as a single responsive codebase using Tailwind CSS breakpoints:
- **Mobile (`< 640px`):** Single column, bottom navigation, full-screen touch forms.
- **Tablet (`640px - 1024px`):** Collapsible navigation rail, responsive two-column dashboards.
- **Desktop (`> 1024px`):** Full persistent multi-tier sidebar, multi-column grids, fixed split-panes.

### 8.1 Sales Representative Mobile Workflow (V2 §2B.10 Customer Stock-Visit Form)
Sales reps visit pharmacies and regional warehouses in person. The mobile UI is specifically tailored for this high-frequency, one-handed operational workflow:

```
+------------------------------------------+
| ≡  تسجيل زيارة عميل (Customer Visit)  👤 |
+------------------------------------------+
| العميل: صيدلية الأمل الحديثة             |
| المندوب: أحمد محمود      التاريخ: اليوم  |
+------------------------------------------+
| [ اختيار الصنف / Drug Selector      🔍 ] |
+------------------------------------------+
| الصنف: أوجمنتين 1 جم أقراص               |
| ---------------------------------------- |
| رصيد سابق بالصيدلية (Prev Stock) :   25  |
| طلبية/توريد جديد (Delivered)    : [+ 10] |
| مرتجعات الزيارة (Returns)        : [-  0] |
| رصيد الصيدلية الحالي (Actual):      12  |
| ======================================== |
| المسحوب الفعلي المحسوب:                  |
| Sell-Through = 25 + 10 - 0 - 12 = 23 علبة |
+------------------------------------------+
| تحصيل نقدي مسدد (Collection) : [ 1,500 ] |
| ملاحظات الزيارة: [ تم الاتفاق على توريد ] |
+------------------------------------------+
| [   💾 حفظ الزيارة واعتماد المسحوب     ] |
+------------------------------------------+
| 🏠 الرئيسية   📋 الزيارات   📦 المخزن   ⚙️ |
+------------------------------------------+
```

### 8.2 Mobile UI Specifics
- **Touch Ergonomics:** All primary interactive elements have a minimum hit target of `44px × 44px`. Key action buttons anchor to the bottom thumb-zone.
- **Form Keypads:** Numeric fields automatically invoke the numeric keyboard on smartphones (`inputmode="decimal"`).
- **Responsive Table Fallbacks:** On viewports `< 768px`, wide transactional tables automatically transform into stacked informational cards showing Key, Amount, Date, and Status, with a tap-to-expand drawer for full line-item details.
- **Network Resilience:** Visual PWA banner appears if connectivity drops during a field visit (`وضع عدم الاتصال - سيتم الحفظ محلياً` / Offline Mode - Changes queued locally).

---

## 9. Accessibility, Usability & Field Ergonomics

1. **High Contrast for Sunlight Legibility:** Contrast ratios exceed WCAG AA standards. Field reps frequently check stock and invoices outside pharmacies or in dimly lit backroom storage; washed-out grays and tiny text are strictly banned.
2. **Keyboard Accessibility (Full Power-User Operation):**
   - Every input and action reachable via standard `Tab` and `Shift+Tab`.
   - `Esc` immediately dismisses modals, slide-overs, and popups.
   - `Ctrl + K` (or `Cmd + K`) invokes the Global Instant Search from anywhere in the app.
3. **Screen Readers & Semantic HTML:**
   - Interactive icons include explicit `aria-label` tags in both Arabic and English (e.g., `aria-label="طباعة الفاتورة"` / `Print Invoice`).
   - Dynamic balance updates utilize `aria-live="polite"` regions so assistive technology announces recalculated totals without page reloads.
4. **Touch Safety:** Destructive actions (Void, Delete, Cancel Approval) require a two-step confirmation or explicit slide-to-confirm action to prevent accidental taps on mobile touchscreens.

---

## 10. Anti-Patterns — Examples of What the UI Must NOT Look Like

To protect the integrity of the system and prevent regressions into bad UX habits, developers and UI contributors must adhere to these negative constraints:

### 1. ❌ The Raw Spreadsheet Clone
*What it looks like:* A browser page that literally looks like an embedded Excel sheet with endless unvalidated green/gray grid lines, formula errors (`#REF!`, `#VALUE!`), unformatted numbers (`14294.73333333`), and horizontal scrollbars spanning 5,000 pixels.  
*Why it fails:* Replicating Excel in HTML inherits all of Excel's fragility without adding relational integrity, validation, or mobile responsiveness.

### 2. ❌ The Low-Contrast "Dribbble SaaS Slop"
*What it looks like:* Light gray text (`#94A3B8`) on slightly lighter gray backgrounds (`#F1F5F9`), tiny 10px fonts, pastel-washed status badges where text is unreadable, and giant empty whitespace borders that force the user to scroll endlessly to see 5 rows of data.  
*Why it fails:* Warehouse staff and financial accountants processing 200 orders a day experience extreme eye strain and miss critical discrepancies.

### 3. ❌ The Broken "Mirror-Hack" RTL
*What it looks like:* Applying a naïve CSS `transform: scaleX(-1)` or unguided `direction: rtl` that mirrors numbers (`123-` instead of `-123`), reverses Latin drug brand names (`orpA`), places question marks on the wrong side, or breaks phone numbers into jumbled digits.  
*Why it fails:* Destroys trust with Egyptian pharmaceutical staff. Arabic UI requires deliberate semantic layout, proper text isolation (`<bdi>`), and standard tabular digits.

### 4. ❌ Modal Hell & Deep Nesting
*What it looks like:* Clicking an invoice opens a popup modal; clicking a line item opens a second modal on top of it; clicking the batch opens a third popup.  
*Why it fails:* Completely unusable on mobile devices and disorients users on desktop. Complex workflows must use dedicated pages, inline accordions, or clean split-pane slide-over panels.

### 5. ❌ The Desktop Grid Squeezed into Mobile
*What it looks like:* Shrinking a 12-column invoice table onto an iPhone screen so that columns become 20 pixels wide, text is clipped, and buttons are microscopic.  
*Why it fails:* Field reps cannot enter pharmacy stock counts or collect payments on the road. Mobile screens must use optimized vertical card layouts with touch-friendly controls.

### 6. ❌ Cluttered "Pilot Cockpit" Dashboard
*What it looks like:* 25 animated circular gauges, 3D pie charts, and rainbow-colored graphs jammed onto the home screen without hierarchy, competing for visual attention.  
*Why it fails:* The CEO and managers need clear, actionable operational answers in 5 seconds: *What were sales today? How much did we collect? Who owes us money? Which products are expiring?*

---

## 11. Printable & PDF Document Design Rules

Per confirmed workflow §2B.4 and §2B.5:
1. **Zero-Quantity Suppression:** Printed and exported PDF invoices must strictly suppress catalog items with 0 quantity. Only actual billed lines render.
2. **Official Invoice Layout:**
   - Top Header: Company bilingual logo/trade name, Tax Card number (البطاقة الضريبية), Commercial Registration (السجل التجاري), Branch Office, Document Date, Sequential Serial Invoice Number.
   - Customer Information Block: Pharmacy/Warehouse name, License/Tax number, Address, Sales Territory, Assigned Sales Rep.
   - Itemized Grid: Serial (`م`), Product Name (`اسم الصنف`), Batch No (`التشغيلة`), Expiry Date (`الصلاحية`), Quantity (`الكمية`), Public Price (`سعر الجمهور`), Wholesale Unit Price (`سعر الوحدة`), Discount % (`الخصم`), Net Price (`الصافي`), Total Line (`الإجمالي`).
   - Summary Footer: Subtotal before VAT, VAT amount (14% or medical exemption rate), Net Total in numbers and written Arabic letters (تفقيط: `فقط وقدره...`), Signature lines (المستلم / أمين المخزن / الحسابات).
3. **Print Stylesheet:** Built-in `@media print` CSS ensures clean black-and-white page breaks, no browser headers/footers, and crisp tabular borders.

---

## 12. Verification & Design Review Checklist

Before any frontend view or component is approved into production, verify against this checklist:
- [ ] Rendered correctly in both Arabic (`dir="rtl"`) and English (`dir="ltr"`).
- [ ] Latin drug names and batch codes do not corrupt surrounding Arabic text.
- [ ] Table numbers align to the end with tabular font figures and two decimal places.
- [ ] Posting status (Draft / Posted / Voided) is instantly recognizable.
- [ ] Minimum touch targets (44px) satisfied on mobile viewports.
- [ ] Contrast ratio meets WCAG AA (≥ 4.5:1).
- [ ] Tested and verified on standard desktop Chrome/Edge and mobile Safari/Chrome.
- [ ] Zero decorative pastel slop; high visual clarity for enterprise medical distribution.
