# Medical Company System — Application Flows

## 1. Navigation Map

```
┌─────────────────────────────────────────────────────────────────┐
│  Top Bar: Logo | Global Search | Notifications | User Menu      │
├──────────┬──────────────────────────────────────────────────────┤
│ SIDEBAR  │                    MAIN CONTENT                      │
│          │                                                      │
│  🏠 Home │  Module view, list, or form                          │
│          │                                                      │
│  Platform│                                                      │
│    Auth  │                                                      │
│    Settings                                                     │
│    Org Structure                                                  │
│    Audit                                                          │
│    Alerts                                                         │
│    Import                                                          │
│    PWA                                                              │
│          │                                                      │
│  Master  │                                                      │
│    Customers                                                        │
│    Products/Catalog/Pricing                                         │
│    Reference Sets                                                   │
│    Batches & Expiry                                                 │
│    UOM                                                             │
│    Credit Mgmt                                                      │
│          │                                                      │
│  Sales   │                                                      │
│    Invoices / Sell-In                                             │
│    Warehouse Routing                                              │
│    Transfers                                                       │
│    Returns                                                         │
│    Receivables / Statements                                      │
│    Sales Targets                                                   │
│    Stock Visits                                                  │
│          │                                                      │
│  Inventory                                                     │
│    Stock Ledger                                                   │
│    Stock Balances                                                 │
│    Stock Cover                                                    │
│    Overstock Alerts                                               │
│          │                                                      │
│  Finance                                                        │
│    Cash & Bank                                                    │
│    Expenses & Revenue                                             │
│    P&L & Balance Sheet                                           │
│    Payroll                                                        │
│          │                                                      │
│  Marketing                                                        │
│    KOL / Doctor Spend                                            │
│    Product / Brand Spend                                        │
│    Objectives & KPIs                                             │
│          │                                                      │
│  Purchasing                                                       │
│    Suppliers                                                     │
│    Material Purchases                                             │
│          │                                                      │
│  Analytics                                                        │
│    Cross-Module Dashboard                                       │
│    Telegram Integration                                          │
│          │                                                      │
└──────────┴──────────────────────────────────────────────────────┘
```

**Sidebar collapse:** On mobile the sidebar collapses to a hamburger menu overlay.

---

## 2. Module A — Platform

### A1. Authentication Flow

```
[Login Page]
  ↓ Enter credentials (email + password)
  ↓ [Valid] → 2FA challenge (if configured)
  ↓ [Invalid] → Show error "Invalid credentials"
  ↓ [2FA valid] → Redirect to Home
  ↓ [2FA invalid/expired] → Show error, re-prompt
```

**Session management:**
- Token refresh on expiry (silent re-auth)
- Session idle timeout: configurable (default 30 min)
- Concurrency limit: 1 active session per user (older sessions invalidated)

**Logout flow:**
```
[User Menu → Logout]
  ↓ Clear session token
  ↓ Redirect to login page
  ↓ Invalidate server-side session
```

### A2. System Settings

**Screens:**
- Fiscal Year (start/end date, current open/closed)
- VAT configuration (rate, registration number)
- Company details (name, address, tax ID)
- Currency (EGP base, multi-currency toggle)
- Numbering sequences (invoice, credit note, transfer, purchase order)

**Validation states:**
- Fiscal year closed → read-only for transactions in that period
- Duplicate VAT registration → save rejected with message

### A3. Org Structure

**Entities:**
- Territories → Areas → Districts → Reps (hierarchical)
- Warehouses (each has a source warehouse flag)
- Branches (aggregation of warehouses)

**Flow:** Create Territory → Add Area → Add District → Assign Reps

### A4. Posting Draft / Posted / Voided

**State machine:**
```
[DRAFT] → Post → [POSTED]
 [POSTED] → Void (with reason code) → [VOIDED]
  [DRAFT] → Delete (soft delete)
  [VOIDED] → Cannot reverse; audit trail kept
```

**Approval gates:**
- Voiding a posted invoice requires Sales Manager or above role
- Voided invoices appear in audit but not in financial reports

### A5. Reason Codes

**Purpose:** Attach a structured reason to voids, returns, adjustments.

**Screens:**
- Manage Reason Codes (code, description, enabled/disabled)
- Select from dropdown when voiding/returning/adjusting

### A6. Simple Approvals

**Configurable approval workflows:**
- Discount > X% on invoice → Sales Manager approval
- Price override → Finance approval
- Expense > threshold → CEO approval
- Stock adjustment → Inventory Manager approval

**Flow:**
```
[Submit for Approval]
  ↓ Assigned to approver
  ↓ Approver sees notification (in-app + optional Telegram)
  ↓ [Approve] → Transaction posted
  ↓ [Reject] → Returns to submitter with reason
  ↓ [Escalate] → Routed to next level
```

### A7. Audit Log

**All actions logged:** who, what, when, before/after values.

**Access:** Read-only for Auditor role; full for Admin/CEO.

### A8. Alerts

**Types:**
- Low stock (below configured threshold)
- Overstock (above configured threshold)
- Near-expiry (within configurable days)
- Credit limit breach
- Unpaid invoice overdue

**Delivery:** In-app notifications + optional Telegram (configurable per alert type).

### A9. Import Validation

**Flow:**
```
[Upload CSV/Excel]
  ↓ Validate headers, data types, required fields
  ↓ Show validation errors (row-level)
  ↓ [Fix & Retry] or [Abort]
  ↓ Preview → Confirm import
```

---

## 3. Module B — Master Data

### B1. Customers

**Fields:** name, contact, phone, address, territory, area, district, credit limit, VAT number, status (active/inactive).

**Flow:**
- Create → Validate required fields → Save → Active by default
- Inactive flag prevents new sales but keeps historical data

### B2. Products / Catalog / Pricing

**Fields:** SKU, name (AR/EN), brand, category, UOM (primary + secondary), cost price, list price, discount % (gated by UOM), pricing tier per customer group.

**Rules:**
- UOM gating: each product has one primary UOM; secondary UOMs must be defined with conversion factors.
- Price change history tracked (audit trail).

### B3. Reference Sets

- Product categories
- Brands
- Customer groups
- Expense categories
- Revenue accounts

### B4. Batches & Expiry

**Per product per warehouse:**
- Batch number, quantity received, purchase date, expiry date
- FEFO (first-expired-first-out) enforced on sales and transfers

**Flow:**
- Receive goods → Assign/create batch → Link to supplier PO
- View: "Stock by Expiry" sorted ascending

### B5. UOM (Unit of Measure)

**Screens:**
- Define UOMs (each, box, carton, pallet)
- Set conversion factors per product

**Validation:** Secondary UOM qty must convert cleanly to primary.

### B6. Credit Management

**Per customer:**
- Credit limit, current outstanding, available balance
- Over-limit → block new invoices (configurable: block or warn)
- Statement generation (AR aging)

---

## 4. Module C — Sales

### C1. Invoices (Sell-In)

**Fields:** date, customer, territory, area, rep, warehouse, source warehouse, batches (auto-allocated FEFO), lines (product, qty, unit price, discount %, line total excl. VAT, VAT amount, line total incl. VAT), payment terms.

**VAT rule:** Calculated per line, reproducible independently.

**Print rules:** Hide zero-qty items; show batch numbers on printed PDF if configured.

**Flow:**
```
[New Invoice]
  ↓ Select customer (validate credit limit)
  ↓ Select warehouse + source warehouse
  ↓ Add lines → system allocates batches (FEFO)
  ↓ Calculate VAT per line
  ↓ [Save Draft] or [Post]
  ↓ [Post] → Creates inventory deduction, updates AR
  ↓ [Print PDF] → Hidden zero-qty rows, per-line VAT shown
```

**Success:** Invoice posted, stock deducted, AR updated.
**Failure:** Insufficient stock → show which batches are short; allow partial post with confirmation.

### C2. Warehouse Routing

**Rules (confirmed):**
- Territory and source warehouse are separate fields.
- Routing logic: customer territory → nearest warehouse with stock → if none, fall back to main warehouse.
- Routing is automatic but overridable by Sales Manager.

### C3. Warehouse-to-Warehouse Transfers

**Not sales.** Internal inventory movements.

**Flow:**
```
[New Transfer]
  ↓ Source warehouse + destination warehouse
  ↓ Lines: product, batch (optional – auto-allocate FEFO), qty
  ↓ Status: Draft → In Transit → Received
  ↓ [Receive] → Increment dest stock, decrement source stock
```

**Audit:** Transfer recorded with operator, date, batch mapping.

### C4. Returns

**Explicit transactions:** customer, product, qty, date, warehouse, batch, reason code.

**Flow:**
```
[New Return]
  ↓ Select customer → auto-fill recent invoice
  ↓ Select product + batch (must exist in customer's received batches)
  ↓ Enter qty + reason code
  ↓ [Submit] → If > threshold, route for approval
  ↓ [Approved] → Stock returned to warehouse (new batch record)
  ↓ Credit note generated → AR adjusted
```

**Validation:** Return qty cannot exceed what customer received in that batch.

### C5. Receivables / Statements

- AR aging report (30/60/90+ days)
- Customer statement (period select)
- Collection tracking per invoice

### C6. Sales Targets

**Granularity:** Rep, Territory, Product, Period (monthly/quarterly).

**Flow:**
- Set target → Track actual vs target → Dashboard view
- Rep view: their own targets only; Manager view: their area/territory; CEO: all

### C7. Stock Visits (Mobile-First)

**This is the core mobile workflow.** Per product per visit.

**Screen fields (vertical scroll, mobile-first):**
1. Previous stock (auto-filled from last visit)
2. New order / delivery (qty received this visit)
3. Returns (qty returned this visit)
4. Current stock (visual count by rep)
5. Sell-through (auto-calculated: prev + delivered - returns - current)
6. Collection / Payment (amount collected, method, date)
7. Notes (free text)
8. Rep (auto-filled, read-only)
9. Visit date (auto-filled today, editable)

**Validation:**
- Current stock ≥ 0
- Sell-through cannot be negative (warn if calculated negative)
- Collection amount ≤ outstanding invoice total (warn if exceeded)

**Success path:** All required fields → Save → Confirmation toast → Navigate to next product

**Failure path:** Missing required field → Highlight field in red → Disable Save button

---

## 5. Module D — Inventory

### D1. Stock Ledger

**Per product per warehouse per batch:**
- In (purchases, transfers in, returns)
- Out (sales, transfers out, adjustments)
- Running balance
- Timestamp and transaction reference

**Filters:** Date range, warehouse, product, batch, transaction type.

### D2. Stock Balances

**Views:**
- Full stock list (net price E = C × (1 − D); SUMIFS cumulative)
- Under-disposal view (items nearing expiry, flagged for promotional sale)

### D3. Stock Cover

**Formula:** `current stock / recent average daily sales rate`
- Window configurable (default: last 30 days)
- Low cover flag: ratio < configured threshold (e.g., < 7 days)

### D4. Overstock Alerts

**Configurable threshold:** Days of cover above which alert fires (e.g., > 180 days).
**Action:** Alert appears in dashboard + optional Telegram notification.

### D5. Low-Stock Alerts

**Configurable:** Minimum qty per product. Alert when on-hand falls below threshold.

---

## 6. Module E — Finance

### E1. Cash & Bank

**Accounts:** Cash (multiple tills/locations), Bank accounts.

**Flow:**
```
[New Transaction]
  ↓ Type: Deposit / Withdrawal / Transfer
  ↓ Account, date, amount, reference, category
  ↓ [Save] → Updates account balance
  ↓ [Reconcile] → Match bank statement lines
```

### E2. Expenses & Revenue

**Expense categories:** From reference sets.
**Revenue accounts:** From reference sets.

**Flow:**
```
[New Expense]
  ↓ Category, amount, date, vendor, receipt attachment
  ↓ If > threshold → require approval (Configurable per category)
  ↓ [Approved/Posted] → Posts to P&L
```

### E3. P&L & Balance Sheet

**Generated from posted transactions.**
- P&L: revenue − expenses by period
- Balance Sheet: assets = liabilities + equity (auto-balanced)

**Views:** Monthly, quarterly, fiscal-year-to-date.
**Period lock:** Closed fiscal years are read-only.

### E4. Payroll (Lightweight)

**Fields per employee:** base salary, deductions (tax, insurance), allowances, net pay.

**Net pay formula:** `E = B − C − D` (base − deductions − allowances, as per workflow spec).

**Flow:**
```
[Monthly Payroll Run]
  ↓ Select period
  ↓ Auto-calculate net per employee
  ↓ Review → Approve → Generate payment list
  ↓ Export to bank format (if integrated)
```

### E5. Private / Owner Accounts

**Isolated from business accounts.** Visible only to CEO/owner.

**Cross-workbook aggregation:** External links import data from legacy Excel workbooks.

---

## 7. Module F — Marketing

### F1. KOL / Doctor Spend

**Fields:** doctor name, specialty, area, date, amount, type (consultation, event, sample), notes.

**Flow:**
```
[New KOL Spend]
  ↓ Select doctor (or create new)
  ↓ Enter amount, type, date, notes
  ↓ [Save] → Records in KOL ledger
  ↓ [View by Doctor] → Aggregate spend per doctor
```

### F2. Product / Brand Spend

**Linked to specific product or brand.**

**Fields:** product/brand, amount, date, campaign name, type.

### F3. Objectives & KPIs

**Per campaign:**
- Objective (description)
- Expected KPI (target value, e.g., "100 prescriptions")
- Actual result (entered post-campaign)
- ROI calculation: `(actual − expected) / expected` or custom formula
- Notes

**Flow:**
```
[New Campaign]
  ↓ Set objective + expected KPI
  ↓ Record spends (linked)
  ↓ Post-campaign: enter actual result
  ↓ System calculates KPI variance
```

---

## 8. Module G — Purchasing

### G1. Suppliers

**Fields:** name, contact, VAT number, address, payment terms, preferred status.

### G2. Material Purchases

**Depth-gated:** Basic purchasing visible to all; advanced (PO approval, GRN) gated by role.

**Flow:**
```
[New Purchase Order]
  ↓ Select supplier
  ↓ Lines: product, qty, unit cost, expected delivery date
  ↓ [Send to Supplier] (email/export) or [Save Draft]
  ↓ [Receive Goods] → Creates batch records in inventory
  ↓ [Match Invoice] → Links supplier invoice to PO + GRN
```

---

## 9. Module H — Analytics

### H1. Cross-Module Dashboard

**KPIs displayed:**
- Sales revenue (monthly, YTD)
- Sell-in vs sell-through ratio
- Stock cover summary
- Overstock / low-stock counts
- AR aging buckets
- Marketing spend vs KPI achievement
- Cash position

**Drill-down:** Click any KPI → navigates to module with filtered view.

### H2. Telegram Integration

**Configurable alerts sent to Telegram channel:**
- Daily sales summary (per warehouse)
- Overstock alerts
- Low-stock alerts
- Near-expiry warnings
- Credit limit breaches

**Format:** Compact text summary with links to relevant screens.

### H3. WhatsApp (Future)

**Planned:** Same alerts via WhatsApp Business API. Not yet implemented.

---

## 10. Role-Specific Flows

### CEO / Owner
- Full access to all modules
- Private accounts view
- Analytics dashboard (all data)
- Approval authority for all overrides
- Can close fiscal periods

### System Administrator
- Full platform access
- Cannot view private accounts
- Can manage users, roles, settings
- Can view audit logs

### Finance / Accounting
- Modules: A (settings), B (master), C (receivables), D (ledger), E (full), H (analytics)
- Cannot create/edit products or customers
- Can post expenses, run payroll, view P&L and balance sheet
- Cannot void invoices (requires Sales Manager+ or CEO)

### Sales Manager
- Modules: A, B (read), C (full), D (read), H (analytics for sales)
- Can approve discounts > threshold, void invoices, override warehouse routing
- Can view all reps' stock visit data
- Can set sales targets

### Sales Representative
- Modules: A (partial), B (customers read), C (stock visits, own invoices), H (own targets)
- Can only see their own territory's data
- Can conduct stock visits (mobile-first)
- Cannot view pricing or cost data
- Cannot void invoices

### Warehouse / Inventory
- Modules: A, B (batches), C (transfers), D (full), H (inventory analytics)
- Can process transfers, receive goods, adjust stock (with approval if > threshold)
- Cannot create customers or set prices

### Branch / Area Manager
- Modules: A, B (read), C (area-level), D (area-level), H (area analytics)
- Can view all reps in their area
- Can approve returns within area
- Cannot access finance module

### Read-Only / Auditor
- All modules: view-only
- Full audit log access
- No create/edit/delete permissions
- Can export reports

---

## 11. Approval / Override Paths

| Action | Threshold | Approver |
|--------|-----------|----------|
| Invoice discount | > configured % | Sales Manager |
| Price override | Any | Finance |
| Return | > configured qty or value | Sales Manager |
| Expense | > configured amount | CEO / Finance (configurable) |
| Stock adjustment | > configured qty | Inventory Manager |
| Warehouse transfer | Any | Warehouse Manager (self-approve if same role) |
| Void invoice | Any | Sales Manager or CEO |
| Credit limit increase | Any | Finance + CEO (dual) |
| Fiscal year close | Any | CEO only |

**Override flow:**
```
[Submit with override]
  ↓ System routes to appropriate approver
  ↓ Approver notified (in-app + Telegram if configured)
  ↓ [Approve] → Transaction posts with override flag in audit
  ↓ [Reject] → Returns to originator with reason; can resubmit
  ↓ [Escalate] → Next level in hierarchy
```

---

## 12. Validation States

### Form-Level Validation
- **Required fields:** Highlighted in red on submit if empty
- **Data type:** Numeric fields reject text; date fields reject invalid dates
- **Referential integrity:** Dropdowns disable options that would break foreign keys

### Business Rule Validation
- **Credit limit:** Block or warn on invoice submit if exceeded
- **Stock availability:** Block if qty > on-hand (allow partial with confirmation)
- **Batch expiry:** Block sale of expired batch; warn if within near-expiry window
- **UOM conversion:** Reject if secondary qty doesn't convert cleanly
- **Fiscal period:** Block posting to closed period

### Real-Time Validation
- **Live stock check:** As qty entered, available qty shown
- **Live credit check:** Available credit shown as user fills invoice
- **Duplicate detection:** Customer/product with same VAT/TIN warns on save

---

## 13. Mobile-Specific Flows

### General Mobile UX
- Sidebar → hamburger overlay
- Tables → card-based layout
- Forms → single-column, large touch targets
- Date pickers → native mobile date picker
- Camera → capture receipts directly

### Stock Visit (Primary Mobile Workflow)
```
[Open App → Stock Visits Tab]
  ↓ Shows list of customers assigned to my territory
  ↓ [Tap Customer] → Shows product list with previous stock
  ↓ [Tap Product] → Opens stock-visit screen (see C7)
  ↓ Swipe left → Quick notes
  ↓ Swipe right → Mark as done
  ↓ [Done] → Auto-advance to next product
  ↓ [Finish Customer] → Summary screen → Next customer
```

**Offline support:**
- Stock visits cached locally if no connectivity
- Sync on reconnection (conflict resolution: last-write-wins with audit trail)
- Visual indicator: cloud icon (synced) vs offline icon (pending sync)

---

## 14. Sales Rollup (from CURRENT_WORKFLOWS)

**Primary rollup:** Per warehouse → branch monthly.
**Period:** Months Jan–Dec, mapped from columns N17–Y17 in legacy Excel.

**Flow:**
```
[Analytics → Sales Rollup]
  ↓ Select warehouse + month
  ↓ System aggregates all posted invoices for that warehouse in that month
  ↓ Shows: total qty, total value, top products, top customers
  ↓ Rollup by branch: sum all warehouses in branch
  ↓ Export to PDF/Excel
```

---

## 15. Sold Balances (from CURRENT_WORKFLOWS)

**Workbook: رصيد الارصدة المباعة**

**Logic:**
- Net price: `E = C × (1 − D)` where C = unit cost, D = discount %
- Cumulative sold balance per customer per product via SUMIFS

**Screen:**
- Select period (date range)
- Select customer (optional, filter)
- Select product (optional, filter)
- Grid: customer, product, qty sold, avg price, total value, remaining balance

---

## 16. Stock Lists (from CURRENT_WORKFLOWS)

**View 1: Full Stock (كامل الكمية)**
- Net price calculation applied
- Cumulative quantities via SUMIFS
- Filters: warehouse, product category, expiry status

**View 2: Under Disposal (تحت التصريف)**
- Items with expiry within configured threshold
- Flagged for promotional sale or return to supplier
- Quick action: create transfer to clearance warehouse

---

## 17. Error Handling & Edge Cases

| Scenario | System Response |
|----------|----------------|
| Network loss during save | Local cache; retry on reconnect; show pending badge |
| Concurrent edit (two users same invoice) | Last-write-wins with conflict notification to both |
| Invoice post fails mid-flight | Transaction rolled back; draft preserved |
| Batch runs out of stock during allocation | Show shortfall; allow partial invoice or cancel |
| Fiscal year already closed | Block new postings; show "Period Closed" message |
| Duplicate customer VAT | Warn on save; allow override with reason |
| Negative sell-through | Flag as anomaly; require rep note explaining discrepancy |

---

## 18. Logout & Session Security

**Auto-logout:**
- Idle timeout: configurable (default 30 minutes)
- Session expiry: hard limit 12 hours

**Manual logout:**
- User menu → Logout → Confirm dialog → Clear session → Redirect to login

**Security:**
- Password hash: bcrypt or equivalent
- 2FA: TOTP (optional, configurable per user)
- Session token: HTTP-only cookie + CSRF token
- Audit: login success/failure logged with IP and device
