# Pharmacy POS — Architecture Spec (v1.6)

*Changelog from v1.5:
1. Statutory Expiry Hard-Block (§10): Expiry is now an unconditional hard-block in both Mandatory and Optional compliance modes (strict liability under Drugs & Cosmetics Act §18). Optional mode only relaxes non-statutory metadata.
2. Schedule H1 Register Completeness (§10): Expanded mandatory audit payload to include patient residential address, prescriber clinic address, State Medical Council registration number, manufacturer name, batch, and date. Added one-click Drug Inspector audit export.
3. Store-Local Operational Entities (§3, §4): Formally decoupled Patient and Prescriber records from central master data. Classified as store-local operational directories (`<STORE>-PAT-<UUID>`) that are 100% offline-creatable and synced upward asynchronously.
4. Store-Initiated Outbound Sync Architecture (§4): Formalized that all store-central sync is strictly store-initiated outbound (HTTP polling/long-polling or store-dialed WebSockets) to operate reliably behind ISP CGNAT and dynamic IPs without open inbound ports.
5. Idempotent Distributed Ingestion (§5): Standardized event envelope with client UUID (`event_id`) and monotonic per-store sequence (`store_seq_no`). Central enforces deduplication via `ON CONFLICT (event_id) DO NOTHING` and returns confirmed sequence watermarks.
6. Customer Sales Returns & GST Credit Notes (§3, §5, §8): Added `sale-return` event with linkage to original invoice and batch. Added per-store sequential gapless Credit Notes (`<STORE>-CN-YYYYMM-XXXX`). Implemented condition-based routing: sealed valid items return to active inventory; expired/damaged/cold-chain items route to quarantine write-off.
7. Batch Picking Engine (§6): Automated FEFO (First Expired, First Out) default suggestion, scan-to-select priority (scanning 2D GS1 barcode strictly overrides FEFO to prevent physical vs invoice batch mismatch), and multi-batch line-item splitting.
8. Stock Discrepancy Policy (§6): Replaced negative stock allowance with Manager-Authorized In-line Adjustment (`stock-adjustment-in`) at POS with audit flags, preserving non-negative stock invariants.
9. Partition-Era Sales Ingestion for Soft-Deleted Products (§6, §10): Central ingestion guarantees acceptance of partition-era historical sales for soft-deleted products. Added auto-resurrection (`deleted_at = null`) or manager write-off task if partition sales reveal remaining store stock.
10. Local Offline Authentication (§2, §15): Store Postgres replicates Argon2id password hashes and role mappings. Store FastAPI issues and validates store-scoped local JWTs (8–12h TTL) during WAN network partitions. Added store manager local account disable capability.
11. Shift Management & Till Reconciliation (§3, §5, §8): Added `shift-open`, `shift-close`, and manager `shift-force-close` events. Implemented Day-End Z-Report reconciling digital payments (Cash/Card/UPI) against physical drawer float with variance tracking.
12. Unattended Edge Maintenance & Watchdog (§2, §16): Added automated daily `pg_dump` with rolling 7-day retention, background WAL/VACUUM cleanup, monotonic clock-skew defense against dead CMOS batteries, and OS watchdog with crash-loop backoff (max 3 restarts / 10 min).*

---

## 1. Scope
- Small chain, 2-5 stores.
- Real business use, not portfolio-only.
- Hybrid deployment: offline-first, syncs when online — with one narrow exception, see §4.
- Small single-store operators supported via Simple role preset (see §11).
- Operational coverage: front-desk billing, dispensing, sales returns & exchanges, batch inventory tracking, shift till reconciliation, and regulatory compliance registers.

---

## 2. Tech Stack & Edge Infrastructure
- **Backend**: Python + FastAPI (store-side and central).
- **Central DB**: Postgres (cloud/central server).
- **Local DB**: Postgres, one dedicated instance per store terminal/server.
- **Local Authentication**:
  - Salted password hashes (Argon2id) and role permission mappings replicated from Central to store Postgres during sync.
  - Store FastAPI issues and validates store-scoped session JWTs (8–12 hour TTL, aligned to cashier shifts) locally.
  - POS terminals operate with 100% authentication autonomy during prolonged internet outages or system reboots.
- **Unattended Database Maintenance**:
  - Daily automated `pg_dump` backups saved to a secondary local drive/partition, governed by an automated rolling 7-day retention script.
  - Scheduled background `VACUUM ANALYZE` and WAL archiving/pruning to prevent disk starvation on compact POS hardware.
  - Lightweight OS watchdog (Windows Service / NSSM / systemd) to auto-restart Postgres and FastAPI upon unexpected system crashes or OS updates. Watchdog incorporates crash-loop backoff (maximum 3 restarts within 10 minutes before halting and raising an alert).
- **Clock-Skew Defense**:
  - Store Postgres enforces a monotonic timestamp check on local commits: `current_timestamp >= MAX(created_at) FROM events`. If a dead CMOS battery or OS error resets system time backwards, transactions block and raise a clock-skew alert.
  - Store sync agent checks local OS time against Central server timestamp in sync heartbeats; skews exceeding $\pm 5$ minutes trigger a prominent UI warning.

---

## 3. Core Modules
- **Inventory**: Drugs, batches, expiry tracking, per-store stock, FEFO batch recommendation, scan-to-select override, multi-batch line splitting, low-stock alerts, write-offs, and manager-authorized adjustments.
- **Customer Returns & Exchanges**: Return validation, condition-based restocking vs quarantine write-off, refund method tracking, and GST Credit Notes.
- **Prescription & Dispensing**: Patient directory, prescribing doctor directory, Schedule H1 mandatory register, and statutory audit export.
- **Billing & Cashier Operations**: Checkout, GST invoice generation, discount presets, shift open/close float tracking, and Day-End Z-Reports.
- **Multi-Store**: Store master, stock transfer (dispatch/receive), central reporting, and cross-store aggregation.
- **Master-Data Governance**: Direct edit/create/delete (Admin/High-access) or request-approval (Manager), all concurrency-protected — see §4.
- **Operational Directories**: Store-local creation and async sync-up for walk-in patients and prescribers.
- **Sync Engine**: Store-initiated outbound sync, local-first queue, idempotent central ingestion, and sequence watermark acknowledgments.
- **User Roles**: Full 4-role model (Pharmacist, Cashier, Manager, Admin) or 2-role simple preset (High-access, Low-access).
- **Settings & Config**: Regulatory compliance mode, role presets, store configuration, and audit trails.
- **Hardware (Phase 1)**: Barcode scanner (1D linear & 2D GS1 DataMatrix), receipt printer (thermal 80mm/58mm), cash drawer kick-out via printer RJ11/12 port.
- **Reporting**: Sales, returns, GST Credit Notes, expiry, low-stock, shift cash variances, per-store and chain-wide.

---

## 4. System Architecture

### Local-First Store Node
- Each store runs its own FastAPI instance + local Postgres on a local counter PC or in-store mini-server.
- Store operates fully offline for sales, dispensing, billing, customer returns, stock-moves (write-offs, adjustments), shift management, and local patient/doctor creation — zero central dependency.
- All state changes are append-only events, committed locally first within a local transaction.

### Store-Initiated Outbound Sync Protocol
- Retail store broadband connections sit behind ISP Carrier-Grade NAT (CGNAT) or dynamic IP routers without static public IPs or open inbound ports. Central cannot initiate inbound TCP connections to stores.
- **All sync operations are strictly store-initiated outbound** (HTTPS POST / long-polling, or store-established persistent WebSocket/gRPC).
- Sync agent pushes queued local events to Central on any of three triggers:
  - Fixed time interval (configurable, e.g., every 30–60 seconds, with exponential backoff and jitter on failure).
  - Automatic trigger immediately upon network reconnect.
  - Manual "Sync Now" button on the manager dashboard.
- Central delivers master-data updates (catalog changes, updated pricing, revised tax rates, approved discount presets) and governance decisions (request approvals/rejections) **strictly as the downstream response payload** to the store's outbound heartbeat/sync request.
- Central Postgres is aggregation and reporting only — never authoritative for per-store inventory.

### Operational Directories vs Master Data
- **Central Master Data**: Catalog drugs, pricing, tax rates, and discount presets are centrally governed. Direct changes require live connectivity and version locking (see Exception below).
- **Store-Local Operational Entities**: Patient records and Prescribing Doctor records are decoupled from central master data. They are **store-local operational entities** assigned permanent store-prefixed identifiers (`<STORE_CODE>-PAT-<UUID>` and `<STORE_CODE>-DOC-<UUID>`). They are 100% offline-creatable at the checkout counter and sync upward to Central asynchronously. Central performs logical deduplication purely in read-only reporting/audit views (matching doctor medical council registration numbers or patient phone numbers) and **never overwrites or mutates store-side entity IDs**.

### Exception — Concurrency Control for Direct Master-Data Changes
- Any direct change to shared central master data — edit, creation, or soft-deletion of drug catalog, pricing, tax, or discount presets — requires live central connectivity. This is the one write path that is not offline-capable.
- Applies uniformly to: Admin (§11 Full), High-access (§9/§11 Simple), and Manager's discount edits (§9 Full).
- Governed records carry an integer `version` field, incremented on each central write.
- **Edits and soft-deletes**: Submit expected version; Central rejects on mismatch — "changed by someone else, refresh and retry" (reason: `stale`).
- **Creation**: No prior version to compare; conflicts caught by uniqueness constraint on the record's business key (e.g. SKU/barcode) — concurrent duplicate create fails distinctly (reason: `duplicate`).
- **Deletion additionally requires zero stock chain-wide** — see §6.
- Central Admin users access multi-store governance and review queues through a centralized Web portal connected directly to Central FastAPI, with zero direct database connection into store LANs.

---

## 5. Data Flow / Event Model

### Event Envelope Standard
Every event generated across the chain adheres to a strict envelope schema:
- `event_id`: Client-generated UUIDv4 (Primary Key).
- `store_seq_no`: Monotonic BIGSERIAL sequence generated by store Postgres.
- `store_id`: Store identifier string.
- `created_at`: UTC timestamp (monotonic clock verified).
- `event_type`: Categorical event type string.
- `payload`: Structured JSONB data.

### Central Ingestion & Idempotency
- Central ingestion endpoint ingests event batches sequentially per store.
- Duplicate prevention: Central database enforces strict idempotency via:
  ```sql
  INSERT INTO central_events (event_id, store_seq_no, store_id, created_at, event_type, payload)
  VALUES (...)
  ON CONFLICT (event_id) DO NOTHING;
  ```
- Sync response returns the highest committed `store_seq_no` watermark. Store sync agent marks acknowledged events as synced and safely prunes queue entries older than the retention window.

### Event Types
1. `sale`: Line items, batches, tax breakdown, payment method, invoice number, customer reference.
2. `sale-return`: Original invoice reference, return line items (drug, batch, qty, price, tax), return reason, refund method, destination (`active-inventory` vs `quarantine-write-off`), credit note number.
3. `dispense`: Prescription linkage, patient reference, doctor reference, Schedule H1 mandatory register payload.
4. `stock-move`: Carries `reason`:
   - `transfer-dispatch`: Inter-store transit out.
   - `transfer-receive`: Inter-store transit in.
   - `write-off`: Physical stock removal (expired/damaged/discontinued/cold-chain breach/customer-return-damaged).
   - `adjustment-in`: Manager-authorized inline physical stock correction.
5. `shift-open`: Cashier ID, terminal ID, opening cash float amount, timestamp.
6. `shift-close`: Declared physical cash, calculated system cash, digital payment totals (UPI/Card), calculated variance, timestamp.
7. `shift-force-close`: Manager/Admin PIN override for abandoned shift, audit note, timestamp.
8. `patient-created`: Store-local patient registration payload (`store_id`, `patient_id`, full name, address, phone).
9. `doctor-created`: Store-local prescriber registration payload (`store_id`, `doctor_id`, full name, clinic address, council reg no).
10. `discount-edit`: Direct edits by Admin/Manager — who, what, when, version.
11. `master-data-edit`: Direct edits/soft-deletes by Admin/High-access — who, field, old/new value, version.
12. `master-data-created`: Direct creation by Admin/High-access — who, new record payload, version=1.
13. `master-data-change-requested`: Store-origin request from Manager.
14. `master-data-change-approved` / `master-data-change-rejected`: Central-origin governance decisions with reason (`manual` | `stale` | `duplicate` | `stock-remaining`).
15. `low-stock-alert`: Triggered when store stock drops to/below threshold.
16. `settings-change`: Admin-only configuration change (compliance mode, role preset).

---

## 6. Stock, Inventory Lifecycle & Batch Mechanics

### Local Stock Calculation
- Each store's stock is local truth, computed strictly from its own local event stream:
  $$\text{Current Batch Stock} = \sum(\text{receives} + \text{adjustments-in} + \text{returns-to-active}) - \sum(\text{sales} + \text{dispatches} + \text{write-offs})$$
- No shared real-time stock pool across stores; no distributed locking on stock.

### Batch Selection & Dispensing Mechanics
1. **FEFO (First Expired, First Out) Default**: When an item is searched or selected by drug name, the POS system automatically suggests the earliest-expiring valid batch that has available stock $>0$.
2. **Scan-to-Select Priority Override**: If a cashier physically scans a 2D GS1 DataMatrix or barcode containing embedded batch and expiry data, **the scanned batch strictly overrides the FEFO suggestion**. This ensures the batch printed on the customer invoice always matches the physical package handed to the patient, preventing drug inspector citations.
3. **Multi-Batch Line-Item Splitting**: If a customer requests a quantity that exceeds the available stock of the primary batch (e.g. customer needs 15 tablets; Batch A has 10, Batch B has 20), the POS automatically splits the item into multiple sub-line items under the same medicine header (Line 1: 10 tablets from Batch A; Line 2: 5 tablets from Batch B). Each sub-line maintains its own batch, expiry, and MRP.

### Stock Discrepancy & Non-Negative Stock Policy
- System stock must remain $\ge 0$. Arbitrary negative stock balances are strictly prohibited as they distort weighted average cost of goods (COGS) and corrupt low-stock reorder thresholds.
- **Physical vs System Discrepancy at Checkout**: If physical medicine is present in hand but local system stock shows 0 (e.g. unrecorded purchase entry or count discrepancy), dispensing is blocked by default.
- **Manager-Authorized In-Line Adjustment**: To prevent halting urgent patient care, a Manager or Admin can enter their PIN directly on the checkout screen to trigger an immediate `stock-move: adjustment-in` event.
  - The adjustment instantly increments local batch stock by the required quantity.
  - The event records the cashier ID, authorizing manager ID, reason code (`misplaced-pack` | `unentered-grn` | `count-discrepancy`), and timestamp.
  - Generates a high-priority entry on the Central Discrepancy Audit Report for shrinkage review.

### Customer Sales Returns Stock Routing
- Customer returns are processed against the original invoice and batch ID.
- **Restock Condition Validation**:
  - Returned items inspected and confirmed sealed/undamaged are re-entered into active inventory (`destination: active-inventory`).
  - **Expiry Re-Check**: The system re-validates the batch expiry date at the moment of return. If the batch has expired since purchase, it is **strictly blocked from returning to active inventory** and forced into `quarantine-write-off`.
  - **Cold-Chain Rule**: Temperature-sensitive medications (e.g., insulin, biologics, vaccines) are legally prohibited from returning to active inventory once they leave store custody and are routed to `quarantine-write-off`.

### Deletion Requires Zero Stock & Partition-Era Sales Ingestion
- A product cannot be soft-deleted (`deleted_at` set) while aggregate stock across all stores is above zero. The check sums latest-synced store stock figures.
- **Partition-Era Sales Ingestion Guarantee**: If Central soft-deleted a product based on zero synced stock while Store A was partitioned offline with un-synced inventory, Store A will legally sell the units offline (Store A has not received `deleted_at`).
  - Upon reconnection, Central **must never reject historical sales events for soft-deleted products**. Transactions are ingested into sales and GST ledgers to ensure tax and accounting truth.
  - **Auto-Resurrection or Write-off Task**: If the ingested sale reveals that Store A still holds positive unsold inventory ($Stock_{\text{initial}} - Qty_{\text{sold}} > 0$), Central automatically clears the soft-delete flag (`deleted_at = null`), restoring the product to active catalog status, and dispatches a notification to Central Admin and the store manager for physical stock reconciliation.

---

## 7. Low Stock Alerts
- Reorder threshold configured per item, per store (admin/manager editable).
- Alert fires as a discrete `low-stock-alert` event when local stock drops to or below threshold.
- Cooldown: Alert does not re-fire on subsequent sales until stock is replenished above threshold.
- Surfaces on store dashboard (immediate notification) and Central replenishment reports (aggregated across stores).
- System-generated closure: On successful product deletion or inventory write-off bringing stock to zero without reorder intent, active alerts close automatically.

---

## 8. Invoicing (GST) & Credit Notes

### Sales Invoicing
- Per-store invoice numbering series, prefixed by store code: `<STORE_CODE>-INV-YYYYMM-XXXX`.
- Strictly sequential and gapless within each store.
- Computed and assigned locally; zero central connectivity required.

### Sales Returns & GST Credit Notes
- Conforms to Section 34 of the Indian Central Goods and Services Tax (CGST) Act, 2017.
- Every sales return or refund generates an official sequential **GST Credit Note**.
- Per-store Credit Note numbering series: `<STORE_CODE>-CN-YYYYMM-XXXX`.
- Gapless and sequential per store; computed locally.
- Payload links directly to the original invoice number, customer GSTIN (if B2B), original tax rate, and CGST/SGST/IGST reversal breakdown.
- **Offline Return Constraint**: Offline returns are strictly restricted to the issuing store where the original invoice exists in local Postgres. Cross-store returns require live central connectivity to fetch the remote invoice and issue an inter-store credit note.

---

## 9. Discounts
- Centrally governed discount presets reside on item or category records.
- Cashier can apply available presets; no manual discount edit rights.
- Manager (Full preset) or High-access (Simple preset) can edit discount preset values directly.
- Direct discount edits require live central connectivity and version-locking (subject to §4 concurrency exception).
- Changes logged immutably as `discount-edit` events (who, what, when, version).
- Insurance/TPA claims module excluded from Phase 1; schema reserves external reference fields.

---

## 10. Regulatory Compliance (India, Drugs & Cosmetics Act)

### 10.1 Absolute Expiry Hard-Block
- Under Section 18(a)(i) and Section 27 of the Drugs and Cosmetics Act, 1940, stocking, selling, or dispensing expired drugs is a strict liability criminal offense carrying mandatory imprisonment and pharmacy license cancellation.
- **Absolute Hard-Block Invariant**: Any batch whose expiry date is $\le \text{current\_date}$ is **unconditionally hard-blocked from billing and dispensing** across **both** `Mandatory` and `Optional` compliance modes.
- Neither cashiers, pharmacists, nor store managers can bypass an expiry block.
- The `compliance_mode` settings switch:
  - `Mandatory` (default): Schedule H1 register entry non-skippable, patient address mandatory, prescriber council registration non-skippable.
  - `Optional`: Non-statutory operational fields become soft prompts (e.g. patient phone number, doctor notes for OTC/non-scheduled drugs). Expiry **remains a hard-block**.

### 10.2 Schedule H1 Register Payload Completeness
Under Rule 65(9) of the Drugs & Cosmetics Rules, pharmacies must maintain an immutable Schedule H1 register for a minimum of 3 years. The dispensing payload schema must capture:
1. Supply Date and Time.
2. Patient Full Name and **Residential Address**.
3. Prescribing Doctor Full Name, **Clinic/Hospital Address**, and **State Medical Council Registration Number**.
4. Drug Generic Name and Brand Name.
5. **Batch/Lot Number**.
6. **Manufacturer Name**.
7. Quantity Dispensed and Pack Size.
8. Dispensing Pharmacist ID and Digital Signature / PIN.

- **Drug Inspector Export**: The system provides a one-click, tamper-evident audit export (CSV and formatted PDF) filterable by date range, drug, or doctor, strictly conforming to Drug Inspector inspection standards.
- Dispense audit logs are append-only; update and delete operations are blocked at the database level (`REVOKE UPDATE, DELETE ON dispense_events`).
- Customer PII (patient names and residential addresses) is encrypted at rest in local Postgres to comply with India's Digital Personal Data Protection (DPDP) Act, 2023.

---

## 11. Roles & Access Control

### Selectable Role Presets
Set per store at setup by Central Admin:
- **Full Preset (4-Role)**:
  - **Pharmacist**: Dispensing, prescription verification, H1 register entry, batch selection, physical inventory view.
  - **Cashier**: Billing, checkout, applying pre-configured discounts, opening/closing own shift, shift cash declaration. Cannot dispense H1 drugs without pharmacist sign-off; cannot edit master data or discounts.
  - **Manager**: All Pharmacist and Cashier rights, plus: customer return authorization, `stock-adjustment-in` PIN authorization, shift force-close override, local user account disabling during outages, stock write-offs, submitting §12 master-data change requests, direct discount preset edits (§9).
  - **Admin**: All Manager rights, plus: direct master-data edit/create/delete (§4), approving/rejecting §12 requests, chain-wide reporting, store setup, compliance mode configuration.
- **Simple Preset (2-Role)** (for single-operator / small pharmacy counters):
  - **High-Access**: Merges Pharmacist + Manager + Admin rights (dispense, direct discount edit, direct master-data edit/create/delete, write-offs, adjustments, returns, reports, shift overrides).
  - **Low-Access**: Billing only, apply discounts, open/close own shift. No dispense, no edits, no adjustments, no write-offs (= Cashier).

### Local User Revocation
If an employee is terminated while a store is offline, the Store Manager is empowered to locally disable the user's account directly on the store FastAPI terminal, immediately invalidating local login without waiting for Central sync.

---

## 12. Master-Data Change Request Flow (Full Preset Only)
- Direct edit/create/delete: Admin (subject to §4 live-connectivity exception).
- Request only: Manager (catalog, pricing, tax — not discounts, see §9).
- No access: Cashier, Pharmacist.
- Scope: Single-field, single-record diff for edits (`field_name`, `current_value`, `expected_version`, `proposed_value`).
- Deletion requests reuse the edit mechanism (`field_name: deleted_at`, `proposed_value: <timestamp>`), gated by the zero-stock check across all stores.
- Create requests carry the full new-record payload (`action: create`).
- Request States: `pending` $\rightarrow$ `approved` / `rejected` (`manual` | `stale` | `duplicate` | `stock-remaining`).
- Central auto-rejects stale edits on version mismatch and duplicate creates on unique business key collision.
- Table: `master_data_change_requests` (store-authoritative request fields, central-authoritative review fields).

---

## 13. Shift Management & Day-End Till Reconciliation (Z-Report)
- Multiple cashiers share counters across morning and evening shifts.
- **Shift Lifecycle**:
  1. `shift-open`: Cashier logs in, counts and enters physical cash float in drawer. Terminal unlocks for billing.
  2. Operating Period: System tracks cumulative Cash, Card, UPI, and Credit Note disbursements.
  3. `shift-close`: Cashier counts physical cash drawer and enters blind cash declaration.
  4. System computes **Till Variance**:
     $$\text{Variance} = \text{Declared Physical Cash} - (\text{Opening Float} + \text{Cash Sales} - \text{Cash Refunds})$$
- **Day-End Z-Report**: Generated at store closing. Summarizes gross sales, net sales, GST collections (CGST/SGST), payment breakdown (Cash vs UPI vs Card), customer return disbursements, and individual cashier till variances.
- **Manager Force-Close**: If Cashier A leaves the counter or falls ill without closing their shift, a Manager can issue a `shift-force-close` event with an audit note, unlocking the register for Cashier B without disrupting counter flow.

---

## 14. Testing & Verification Suite

### Automated Unit & Integration Tests
1. **Absolute Expiry Hard-Block**: Attempt to bill batch with $\text{expiry} \le \text{today}$ in `Optional` compliance mode. Assert: Hard-block, transaction rejected.
2. **Schedule H1 Completeness**: Dispense Schedule H1 drug without patient address or doctor council registration. Assert: Validation error, dispense blocked.
3. **Outbound Sync over NAT**: Simulate CGNAT environment (store blocked from inbound traffic). Assert: Store initiates outbound polling; successfully pushes events and pulls master-data updates.
4. **Ingestion Idempotency**: Re-send identical event batch with identical `event_id` UUIDs. Assert: Central returns HTTP 200, zero duplicate rows in `central_events`.
5. **FEFO & Scan Override**: Store has Batch A (expiring in 10 days) and Batch B (expiring in 90 days). Item selected by name $\rightarrow$ Batch A suggested. 2D barcode for Batch B scanned $\rightarrow$ Batch B billed on invoice.
6. **Multi-Batch Split**: Request 15 units; Batch A has 10 units, Batch B has 20 units. Assert: Two sub-line items generated on single invoice, stock deducted correctly.
7. **Customer Return to Active Stock**: Process return of sealed unexpired strip. Assert: Local batch stock increments, gapless Credit Note generated.
8. **Customer Return Expiry Block**: Process return of strip whose batch expired after sale. Assert: System blocks restock to active inventory and forces routing to `quarantine-write-off`.
9. **Partition-Era Soft-Delete Ingestion**: Central soft-deletes drug while Store A is offline. Store A sells remaining stock offline. Store A reconnects. Assert: Central ingests sale event, updates GST ledger, and auto-resurrects drug or alerts Admin.
10. **Offline Local Auth**: Disconnect store network cable, restart store PC. Attempt user login. Assert: Local FastAPI authenticates against local Argon2id hash and issues valid store session JWT.
11. **Monotonic Clock Defense**: Set system clock backwards by 1 year. Attempt transaction. Assert: Local transaction fails with clock-skew error.
12. **Shift Reconciliation Math**: Open shift with 1000 float, execute 500 cash sale, declare 1400 cash. Assert: Z-Report shows -100 cash shortage variance.
13. **Backup Retention**: Run backup script for 10 simulated days. Assert: Only 7 most recent `pg_dump` archives retained on disk.

---

## 15. Observability & Telemetry
- **Structured JSON Logging**: Every store event, sync attempt, and manager override logged with correlation IDs.
- **Operational Metrics**:
  - Sync queue depth and sync lag (seconds since last acknowledged watermark).
  - Deduplicated event replay rate.
  - Cashier till variance and cash shrinkage tracking.
  - Frequency of manager-authorized `stock-adjustment-in` events.
  - Frequency of scan-to-select overrides over FEFO.
  - Clock-skew alerts ($\Delta t > 5\text{ min}$).
  - Local database disk storage utilization percentage.
- **Alerting Thresholds**:
  - Store sync offline $> 30$ minutes during operating hours.
  - Till cash shortage $> \text{₹}500$ on shift close.
  - Multiple `stock-adjustment-in` overrides within a single shift.
  - Local disk storage $> 85\%$ full.

---

## 16. Security & Data Protection
- **Local Credential Storage**: Password hashes stored using Argon2id with store-level salting. Store Postgres bound strictly to `127.0.0.1`.
- **JWT Key Architecture**: Store FastAPI uses an asymmetric public key or store-local secret for local JWT signing, eliminating central identity provider dependency during WAN disconnects.
- **Patient Data Privacy (DPDP Act 2023)**: Patient names, phone numbers, and addresses encrypted at rest using AES-256 in store Postgres.
- **Network Isolation**: Central Web Administration portal communicates strictly with Central FastAPI over HTTPS/TLS 1.3. No incoming firewall ports opened on store LAN routers.
- **Audit Immutability**: Dispense logs, GST invoices, GST Credit Notes, shift reconciliation events, and stock adjustments are strictly append-only. Database users assigned `NO UPDATE, NO DELETE` grants on historical audit tables.

---

## 17. Deployment Safety & Edge Rollout
- **Staged Rollout**: Single canary store live for 7 days before rolling updates to remaining chain stores.
- **Rollback Safety**: Every database migration accompanied by a backwards-compatible rollback script.
- **Windows Edge Hardening**: POS terminals configured with unattended service recovery (NSSM / Windows Service Manager), disk write-cache protection, and automatic UPS graceful shutdown integration.

---

## 18. Open Items (Phase 2 Roadmap)
- Central hosting infrastructure sizing: Self-hosted VM vs managed cloud (RDS/Cloud SQL).
- Integrated UPI dynamic QR code generator displayed on customer-facing secondary LCD screen.
- Insurance / Third-Party Administrator (TPA) direct cashless claim processing.
- Optical Character Recognition (OCR) for doctor prescription scanning at dispensing counter.
- Automated WhatsApp/SMS delivery of GST invoices and credit notes to patients.

---
*Status: Active (v1.6). Supersedes [architecture_v1_5.md](file:///c:/Users/surya/OneDrive/Desktop/med_pos/architecture_v1_5.md).*
