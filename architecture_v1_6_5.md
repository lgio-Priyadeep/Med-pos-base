# Pharmacy POS — Architecture Spec (v1.6.5)

*Changelog from v1.6:
1. Fractional Inventory & Unit of Measure (UOM) Hierarchy (§3, §6): Stores and calculates batch inventory exclusively in atomic integer Base Dispensing Units (tablets, capsules, ml). Batch-level immutability for pack_size, packaging_unit, and base_unit prevents central catalog edits from distorting on-shelf stock counts. Legal Metrology Rule 2011 fractional rounding with statutory MRP price clamping. Scanning 1D/2D barcodes strictly defaults to 1 Packaging Unit (pack_size base units). Sealed blister cavities return to active inventory; cut/punctured cavities route to quarantine-write-off.
2. Near-Expiry Vendor Returns (RTV) & Local Supplier Debit Notes (§5, §6, §8): Configurable shelf-expiry alert tiers (90d Amber FEFO / 60d Orange RTV packing / 30d Red shelf quarantine). Added stock-move: rtv-quarantine event. Introduced sequential, offline GST Debit Notes (<STORE_CODE>-DN-YYYYMM-XXXX) with CGST/SGST/IGST tax reversal breakdowns. Replicated distributor profiles for offline document generation.
3. Rule 55 Inter-Store Statutory Delivery Challans (§5, §6, §8): Offline sequential Delivery Challans (<STORE_CODE>-DC-YYYYMM-XXXX) for physical branch road transport. Statutory guard mandates identical GSTIN and state codes; automatically blocks Challan and requires an IGST Stock Transfer Invoice for inter-state movements. Receipt discrepancy ingestion in transfer-receive splits into received_qty (intact), transit_breakage_qty (quarantine write-off with photo audit), and transit_shortage_qty (shrinkage investigation flag).
4. Schedule X & NDPS Dual-Prescription Custody & Bound Ledger (§3, §5, §10): Mandatory digital scanning/photo capture of duplicate prescriptions (compressed to <250 KB WebP, AES-256 encrypted, 90-day edge retention with 2-year cloud archive). Dispense events capture registered Pharmacist PIN and State Pharmacy Council credentials. Automated, immutable Daily Running Balance Ledger (Opening + Receipts - Dispensed = Closing). One-click State Drug Licensing Authority statutory export.
5. In-Store Multi-Counter LAN Topology & Failover Fencing (§2, §4): Counter 1 (Primary Node) runs authoritative Postgres on 127.0.0.1 and Store FastAPI on LAN (0.0.0.0:8000). Counter 2/3 (Worker Terminals) run lightweight UI connecting over LAN via mDNS (medpos-primary.local:8000) for dynamic DHCP router immunity. Single sequence authority maintains monotonic store_seq_no and gapless invoice series. Standby failover script (promote_to_primary.bat) enforces LAN reachability fencing and applies emergency sequence epoch (<STORE>-INV-YYYYMM-XXXX-F1) on total hardware loss.
6. Central Batch Ingestion Push Atomicity & Poison-Pill Quarantine (§5): Wraps Central event batch ingestion and sequence watermark updates in a single atomic database transaction (BEGIN...COMMIT). Malformed/schema-violating events route to central_sync_quarantine with sync-quarantine-tombstone records in central_events to preserve sequence continuity without wedging the store retry queue.
7. Thermal Receipt Printer Jam Resilience & Abandonment Accounting (§3, §4, §8, Hardware): Two-phase checkout commit (COMMITTED_PENDING_PRINT -> COMPLETED). Non-blocking 300ms ESC/POS status check with automatic OS print spooler fallback for write-only USB printers. Cash drawer kick synchronized with print spooling. Prominent UI error banner with one-click reprint and audited *** DUPLICATE COPY *** watermark. If customer leaves during a jam, cashier triggers an automated void issuing an offsetting GST Credit Note (<STORE>-CN-...), preserving gapless numbering.
8. Windows OS Edge Security Hardening (§16): OS file permissions locked via icacls restricting AES-256 database keys and environment files strictly to NT SERVICE\MedPOS.
9. Pragmatic Interim Enterprise Bridges (§3, §8, §9, §18): Sequential Store-Local B2B Invoices (<STORE>-B2B-YYYYMM-XXXX) under Rule 46(b) for manual monthly GSTR-1 upload; dynamic NPCI UPI QR string on 80mm thermal receipts (upi://pay?...); cashier one-click WhatsApp Web share link (wa.me); manual Insurance/TPA tender metadata fields.*

---

## 1. Scope
- Small chain, 2-5 stores.
- Real business use, not portfolio-only.
- Hybrid deployment: offline-first, syncs when online — with one narrow exception, see §4.
- In-store scaling: Multi-counter LAN topology (1 Primary node + 1-3 Worker terminals).
- Small single-store operators supported via Simple role preset (see §11).
- Operational coverage: front-desk billing, fractional strip/tablet dispensing, sales returns & exchanges, vendor returns (RTV), branch delivery challans, batch inventory tracking, shift till reconciliation, and regulatory compliance registers (Schedule H1 and Schedule X).

---

## 2. Tech Stack & Edge Infrastructure
- **Backend**: Python + FastAPI (store-side and central).
- **Central DB**: Postgres (cloud/central virtual machine or managed instance).
- **Local DB**: Postgres 16, dedicated instance on Store Primary Node (Counter 1 PC or in-store mini-server).
- **In-Store Multi-Counter LAN Architecture**:
  - **Primary Store Node (Counter 1)**: Runs Store Postgres and Store FastAPI sync service.
    - Postgres is strictly bound to `127.0.0.1` on Counter 1 (no external database network listener).
    - Store FastAPI binds to `0.0.0.0:8000` on the store's private Gigabit Ethernet / WPA3 LAN.
    - Service broadcasts on the local LAN via mDNS / Zero-Configuration Networking as `medpos-primary.local:8000`, immunizing worker terminals against router DHCP IP reassignments.
  - **Worker Terminals (Counter 2, Counter 3)**:
    - Run lightweight desktop web UI / Electron shells connecting to `http://medpos-primary.local:8000` via LAN HTTP REST and WebSockets.
    - Worker terminals maintain zero local database instances; all transactions commit directly against Counter 1 within store-scoped session JWTs.
- **Standby Counter & Failover Epoch Protection**:
  - Counter 2 serves as a warm standby node receiving automated daily `pg_dump` backups and continuous WAL archives from Counter 1.
  - **Scripted Promotion (`promote_to_primary.bat`)**:
    1. *LAN Fencing Check*: Script attempts to ping and query Counter 1's health endpoint over LAN. If Counter 1 responds, promotion is blocked to eliminate split-brain hazards.
    2. *Service Activation*: Starts local Postgres service on Counter 2 and launches Store FastAPI.
    3. *Sequence Protection*: If Counter 1 suffered catastrophic unrecoverable drive loss, Counter 2 adopts an emergency failover sequence epoch: `<STORE_CODE>-INV-YYYYMM-XXXX-F1` and jumps `store_seq_no` forward by a safe margin ($+100,000$), guaranteeing zero collision with morning invoices.
- **Local Authentication**:
  - Salted password hashes (Argon2id) and role permission mappings replicated from Central to store Postgres during sync.
  - Store FastAPI issues and validates store-scoped session JWTs (8–12 hour TTL, aligned to cashier shifts) locally.
  - POS terminals operate with 100% authentication autonomy during prolonged internet outages or system reboots.
- **Unattended Database Maintenance**:
  - Daily automated `pg_dump` backups saved to a secondary local drive/partition, governed by an automated rolling 7-day retention script.
  - Scheduled background `VACUUM ANALYZE` and WAL archiving/pruning to prevent disk starvation on compact POS hardware.
  - Lightweight OS watchdog (Windows Service / NSSM) to auto-restart Postgres and FastAPI upon unexpected system crashes or OS updates. Watchdog incorporates crash-loop backoff (maximum 3 restarts within 10 minutes before halting and raising an alert).
- **Clock-Skew Defense**:
  - Store Postgres enforces a monotonic timestamp check on local commits: `current_timestamp >= MAX(created_at) FROM events`. If a dead CMOS battery or OS error resets system time backwards, transactions block and raise a clock-skew alert.
  - Store sync agent checks local OS time against Central server timestamp in sync heartbeats; skews exceeding $\pm 5$ minutes trigger a prominent UI warning.

---

## 3. Core Modules
- **Inventory & UOM Hierarchy**: Fractional strip/tablet tracking, integer base units (`tablets`, `capsules`, `ml`), packaging unit hierarchy, batch-level pack size immutability, FEFO recommendations, scan-to-select priority, multi-batch line splitting, low-stock alerts, write-offs, and manager adjustments.
- **Customer Returns & Exchanges**: Return validation, condition-based restocking (sealed intact blister cavities) vs quarantine write-off (cut/punctured blister foil, cold-chain breach), refund method tracking, and GST Credit Notes.
- **Vendor Returns (RTV)**: Near-expiry alerts (90d/60d/30d), `rtv-quarantine` bin routing, distributor profile sync, and sequential GST Supplier Debit Notes.
- **Branch Stock Transfers**: Rule 55 intra-state Delivery Challans, inter-state IGST tax invoice enforcement, and receipt variance ingestion (intact vs breakage vs shortage).
- **Prescription & Dispensing**: Patient directory, prescribing doctor directory, Schedule H1 mandatory register, and Schedule X & NDPS dual-prescription custody with daily running balance ledger.
- **Billing & Cashier Operations**: Multi-counter LAN checkout, B2C invoices, B2B tax invoices, dynamic UPI QR on thermal bill, optional cashier one-click WhatsApp Web share link (`wa.me`) for paperless receipts, discount presets, shift open/close float tracking, and Day-End Z-Reports.
- **Hardware & Peripherals**: Barcode scanner (1D linear & 2D GS1 DataMatrix), thermal receipt printer (80mm/58mm) with two-phase jam resilience and spooler fallback, cash drawer kick-out via printer RJ11/12 port, and webcam/scanner prescription photo capture.
- **Multi-Store & Governance**: Store master, stock transfer, central reporting, cross-store aggregation, and master-data change requests.
- **Operational Directories**: Store-local creation and async sync-up for walk-in patients and prescribers.
- **Sync Engine**: Store-initiated outbound sync, local-first queue, atomic central batch ingestion with poison-pill quarantine tombstones, and sequence watermark acknowledgments.
- **User Roles**: Full 4-role model (Pharmacist, Cashier, Manager, Admin) or 2-role simple preset (High-access, Low-access).
- **Settings & Config**: Regulatory compliance mode, role presets, store configuration, and audit trails.
- **Reporting**: Sales, returns, GST Credit Notes, Supplier Debit Notes, Delivery Challans, Schedule H1/X registers, expiry, low-stock, shift cash variances, per-store and chain-wide.

---

## 4. System Architecture

### Local-First Store Node & Multi-Counter LAN
- Each store operates a Local-First Store Node: Counter 1 acts as Primary Server; Counter 2/3 act as Worker Terminals over LAN.
- Store operates fully offline for sales, fractional dispensing, customer returns, vendor returns (RTV), delivery challans, stock-moves, shift management, and local patient/doctor registration — zero central dependency.
- All state changes are append-only events, committed to Counter 1 Postgres within a local transaction.

### Store-Initiated Outbound Sync Protocol
- Store broadband connections sit behind ISP Carrier-Grade NAT (CGNAT) or dynamic IP routers without static public IPs or open inbound ports. Central cannot initiate inbound TCP connections to stores.
- **All sync operations are strictly store-initiated outbound** (HTTPS POST / long-polling, or store-established persistent WebSocket/gRPC).
- Sync agent running on Counter 1 pushes queued local events to Central on three triggers:
  - Fixed time interval (configurable, e.g., every 30–60 seconds, with exponential backoff and jitter on failure).
  - Automatic trigger immediately upon network reconnect.
  - Manual "Sync Now" button on the manager dashboard.
- Central delivers master-data updates (catalog changes, updated pricing, revised tax rates, approved discount presets, distributor profiles) and governance decisions (request approvals/rejections) **strictly as the downstream response payload** to the store's outbound heartbeat/sync request.
- Central Postgres is aggregation and reporting only — never authoritative for per-store inventory.

### Operational Directories vs Master Data
- **Central Master Data**: Catalog drugs, pricing, tax rates, discount presets, and distributor profiles are centrally governed. Direct changes require live connectivity and version locking (see Exception below).
- **Store-Local Operational Entities**: Patient records and Prescribing Doctor records are decoupled from central master data. They are **store-local operational entities** assigned permanent store-prefixed identifiers (`<STORE_CODE>-PAT-<UUID>` and `<STORE_CODE>-DOC-<UUID>`). They are 100% offline-creatable at any counter and sync upward to Central asynchronously. Central performs logical deduplication purely in read-only reporting/audit views and **never overwrites or mutates store-side entity IDs**.

### Exception — Concurrency Control for Direct Master-Data Changes
- Any direct change to shared central master data — edit, creation, or soft-deletion of drug catalog, pricing, tax, or discount presets — requires live central connectivity. This is the one write path that is not offline-capable.
- Applies uniformly to: Admin (§11 Full), High-access (§9/§11 Simple), and Manager's discount edits (§9 Full).
- Governed records carry an integer `version` field, incremented on each central write.
- **Edits and soft-deletes**: Submit expected version; Central rejects on mismatch (reason: `stale`).
- **Creation**: Uniqueness constraint on record business key (SKU/barcode); concurrent duplicate create fails distinctly (reason: `duplicate`).
- **Deletion additionally requires zero stock chain-wide** — see §6.
- Central Admin users access multi-store governance and review queues through a centralized Web portal connected directly to Central FastAPI, with zero direct database connection into store LANs.

---

## 5. Data Flow / Event Model

### Event Envelope Standard
Every event generated across the chain adheres to a strict envelope schema:
- `event_id`: Client-generated UUIDv4 (Primary Key).
- `store_seq_no`: Monotonic BIGSERIAL sequence generated by store Postgres on Counter 1.
- `store_id`: Store identifier string.
- `created_at`: UTC timestamp (monotonic clock verified).
- `event_type`: Categorical event type string.
- `payload`: Structured JSONB data.

### Central Ingestion Atomicity & Poison-Pill Defense
- Central ingestion endpoint ingests event batches sequentially per store inside a single atomic database transaction:
  ```sql
  BEGIN;
    -- Ingest valid events with deduplication
    INSERT INTO central_events (event_id, store_seq_no, store_id, created_at, event_type, payload)
    VALUES (...)
    ON CONFLICT (event_id) DO NOTHING;

    -- Update store sequence watermark
    UPDATE store_sync_watermarks SET last_committed_seq = :max_seq WHERE store_id = :store_id;
  COMMIT;
  ```
- **Poison-Pill Quarantine & Tombstones**: If an individual event in the batch suffers schema corruption or violates database check constraints, Central isolates the event into `central_sync_quarantine` and writes a lightweight tombstone to `central_events`:
  ```sql
  INSERT INTO central_events (event_id, store_seq_no, store_id, created_at, event_type, payload)
  VALUES (:event_id, :store_seq_no, :store_id, :created_at, 'sync-quarantine-tombstone', :quarantine_meta);
  ```
- The transaction commits, preserving sequence continuity on Central. The sync acknowledgment returns:
  ```json
  {
    "status": "success",
    "acknowledged_seq": 1042,
    "quarantined_events": ["550e8400-e29b-41d4-a716-446655440000"]
  }
  ```
- The store marks events as synced up to `acknowledged_seq`, while flagging the quarantined event on the Manager Dashboard for investigation.

### Event Types
1. `sale`: Line items (with base units, pack conversion, and fractional pricing), batches, tax breakdown, payment method, invoice number (`<STORE>-INV-...`), customer reference.
2. `b2b-sale`: Registered business sale, buyer GSTIN, line items, HSN tax summary, sequential B2B invoice number (`<STORE>-B2B-...`).
3. `sale-return`: Original invoice reference, return line items (drug, batch, qty, price, tax), condition validation (`active-inventory` vs `quarantine-write-off`), Credit Note number (`<STORE>-CN-...`).
4. `dispense`: Prescription linkage, patient reference, doctor reference, Schedule H1 mandatory register payload, and Schedule X registered Pharmacist PIN / prescription image hash.
5. `stock-move`: Carries `reason`:
   - `transfer-dispatch`: Inter-store transit out accompanied by Delivery Challan (`<STORE>-DC-...`).
   - `transfer-receive`: Inter-store transit in with receipt variance breakdown (`received_qty`, `transit_breakage_qty`, `transit_shortage_qty`).
   - `rtv-quarantine`: Near-expiry stock pulled to return bin, linked to Supplier Debit Note (`<STORE>-DN-...`).
   - `write-off`: Physical stock removal (expired, damaged, broken cold-chain, cut blister cavities).
   - `adjustment-in`: Manager PIN authorized inline physical stock correction at POS.
6. `shift-open`: Cashier ID, terminal ID, opening cash float, timestamp.
7. `shift-close`: Declared physical cash, calculated system cash, digital payment totals (UPI/Card), variance, timestamp.
8. `shift-force-close`: Manager/Admin PIN override for abandoned shift, audit note, timestamp.
9. `patient-created`: Store-local patient registration (`store_id`, `patient_id`, full name, address, phone).
10. `doctor-created`: Store-local prescriber registration (`store_id`, `doctor_id`, full name, clinic address, council reg no).
11. `discount-edit`: Direct edits by Admin/Manager — who, what, when, version.
12. `master-data-edit`: Direct edits/soft-deletes by Admin/High-access — who, field, old/new value, version.
13. `master-data-created`: Direct creation by Admin/High-access — who, new record payload, version=1.
14. `master-data-change-requested`: Store-origin request from Manager.
15. `master-data-change-approved` / `master-data-change-rejected`: Central governance decisions.
16. `low-stock-alert`: Triggered when local stock drops to/below threshold.
17. `settings-change`: Admin configuration change (compliance mode, role preset).

---

## 6. Stock, Inventory Lifecycle & Batch Mechanics

### Unit of Measure (UOM) Hierarchy & Fractional Billing
- **Integer Base-Unit Storage**: Inventory is tracked strictly in integer **Base Dispensing Units** (`tablets`, `capsules`, `ml`, `vials`). Decimal quantities are prohibited in database storage.
- **Batch-Level Packaging Immutability**:
  - `packaging_unit`: Standard commercial packaging (e.g., "Strip of 10", "Box of 100", "Bottle of 60ml").
  - `base_unit`: Minimal dispensable atomic unit (e.g., "Tablet", "Capsule", "ml").
  - `pack_size`: Integer ratio representing the number of base units per packaging unit ($P \in \mathbb{Z}^+$).
  - *Immutability Invariant*: These fields are locked immutably on the **Batch** table at GRN / initial entry. Upstream changes to the master product catalog cannot alter existing batch packaging definitions.
- **Dual-Representation Calculation**:
  $$\text{Pack Qty} = \text{Base Qty} \mathbin{//} \text{Pack Size}, \quad \text{Loose Qty} = \text{Base Qty} \pmod{\text{Pack Size}}$$
- **Legal Metrology (Packaged Commodities) Rules 2011 Statutory Pricing**:
  - Base unit price is computed using half-up rounding:
    $$\text{Unit Price} = \operatorname{ROUND\_HALF\_UP}\left(\frac{\text{Strip MRP}}{\text{Pack Size}}, 2\right)$$
  - **Statutory Upper Bound & Clamping Invariant**:
    $$\text{Loose Line Subtotal} = \min\left(\text{Loose Qty} \times \text{Unit Price}, \ \text{Strip MRP}\right)$$
    If the loose quantity equals the full pack size ($\text{Loose Qty} = \text{Pack Size}$), the line total is strictly clamped to the full Strip MRP, legally preventing fractional rounding accumulation overcharges.
- **Barcode Scanning Context Invariant**:
  - Scanning a manufacturer 1D (EAN-13) or 2D (GS1 DataMatrix) barcode strictly bills **1 Packaging Unit ($1 \times \text{pack\_size}$ base units)**.
  - Loose unit dispensing requires the cashier to explicitly input quantities into a dedicated `[Packs] + [Loose]` segmented interface.
- **Fractional Return Policy**:
  - Cut blister strips with intact, airtight, undamaged foil over each individual tablet legally return to active stock ($+\text{Loose Qty}$ base units).
  - Blister cavities with punctured, torn, or broken foil seals are legally deemed contaminated and are **strictly routed to `quarantine-write-off`**.

### Near-Expiry Vendor Returns (RTV) & Alerts
- Store stock monitors days to expiry ($\Delta t = \text{expiry\_date} - \text{current\_date}$):
  - **90 Days (Amber)**: Highlights batch on search; prioritizes automated FEFO suggestions.
  - **60 Days (Orange)**: Triggers automated Return-to-Vendor (RTV) packing recommendation.
  - **30 Days (Red)**: Flags batch for immediate physical shelf quarantine.
- Pharmacists execute `stock-move: rtv-quarantine`, moving stock out of billing inventory into a return bin, generating an official GST Debit Note (see §8).

### Inter-Store Stock Transfers & Statutory Delivery Challans
- Internal branch stock movement requires an official Delivery Challan under Rule 55 of the CGST Rules, 2017.
- **Intra-State Restriction Guard**: Delivery Challans are valid strictly when $\text{Source GSTIN} == \text{Dest GSTIN} \land \text{Source State} == \text{Dest State}$. If stock moves across state lines, the system mandates a full GST Tax Invoice with IGST under Section 7(4) of the IGST Act.
- **Receipt Discrepancy Ingestion**: Receiving store enters actual physical counts in `transfer-receive`:
  - `received_qty`: Intact units added to receiving store active stock.
  - `transit_breakage_qty`: Damaged units routed to receiving store quarantine write-off with photo attachment.
  - `transit_shortage_qty`: Missing units logged as shrinkage investigation flag.
- Store inventory remains strictly sovereign: dispatch decrements source store; receive increments destination store.

### Batch Selection & Dispensing Mechanics
1. **FEFO (First Expired, First Out) Default**: System automatically suggests the earliest-expiring valid batch with available stock $>0$.
2. **Scan-to-Select Priority Override**: Physically scanning a 2D GS1 DataMatrix containing batch/expiry data strictly overrides the FEFO suggestion, ensuring physical and invoiced batch parity.
3. **Multi-Batch Line-Item Splitting**: If requested quantity exceeds primary batch stock, the POS automatically splits the item into sub-lines with individual batch, expiry, and MRP details.

### Stock Discrepancy & Non-Negative Stock Policy
- System stock must remain $\ge 0$.
- **Manager-Authorized In-Line Adjustment**: If physical stock exists but system stock displays 0, a Manager or Admin PIN override triggers an immediate `stock-move: adjustment-in` event recording cashier ID, authorizing manager ID, reason code, and timestamp, logging to the Central Shrinkage Report.

### Customer Sales Returns Stock Routing
- Returns are validated against the original invoice and batch ID.
- **Restock Condition Validation**:
  - Sealed, unexpired, undamaged items return to active inventory (`destination: active-inventory`).
  - **Expiry Re-Check**: Batches expired since purchase are strictly blocked from active restock and routed to `quarantine-write-off`.
  - **Cold-Chain Rule**: Temperature-sensitive medications (insulin, vaccines) are legally prohibited from returning to active stock and route to `quarantine-write-off`.

### Deletion Requires Zero Stock & Partition-Era Sales Ingestion
- Products cannot be soft-deleted centrally while aggregate chain-wide stock $>0$.
- Central never rejects historical sales events for soft-deleted products made offline.
- If an ingested sale reveals unsold inventory ($Stock_{\text{initial}} - Qty_{\text{sold}} > 0$), Central automatically clears the soft-delete flag (`deleted_at = null`) and notifies Central Admin and the store manager.

---

## 7. Low Stock Alerts
- Configured per item, per store in base dispensing units.
- Triggers discrete `low-stock-alert` event when local stock drops to or below threshold.
- Cooldown: Suppressed until stock is replenished above threshold.
- Surfaces on store dashboard and Central replenishment reports.
- Closes automatically upon stock write-off bringing inventory to zero without reorder intent.

---

## 8. Invoicing (GST), Credit Notes, Debit Notes & Delivery Challans

### Numbering Series Orthogonality
All document series are computed store-locally, gapless, and mutually orthogonal:
- **Retail B2C Invoices**: `<STORE_CODE>-INV-YYYYMM-XXXX`
- **Emergency Failover B2C Invoices**: `<STORE_CODE>-INV-YYYYMM-XXXX-F1`
- **Registered B2B Invoices**: `<STORE_CODE>-B2B-YYYYMM-XXXX`
- **Sales Return Credit Notes**: `<STORE_CODE>-CN-YYYYMM-XXXX`
- **Supplier Return Debit Notes**: `<STORE_CODE>-DN-YYYYMM-XXXX`
- **Rule 55 Delivery Challans**: `<STORE_CODE>-DC-YYYYMM-XXXX`

### Invoicing Specifications
- **B2C Retail Checkout**: Conforms to CGST Section 31. Printed thermal bills display store GSTIN, HSN, batch numbers, expiry, CGST/SGST breakdown, dynamic NPCI UPI QR string (`upi://pay?pa=...&am=...&pn=...&tr=...`), complemented by a standalone countertop static UPI audio soundbox for cashier audio payment confirmation. Cashiers have an optional one-click WhatsApp Web share link (`wa.me`) with pre-formatted invoice text for paperless delivery.
- **B2B Tax Invoicing (Rule 46(b))**: Captures buyer 15-digit GSTIN, legal business name, and HSN summary. Carries statutory note: *"Standard B2B Tax Invoice — Offline Pilot Mode"*, supporting manual monthly GSTR-1 portal filing.
- **Sales Returns & GST Credit Notes**: Conforms to Section 34 of the CGST Act. Links directly to the original invoice, reversing tax components. Offline returns are restricted to the issuing store where the original invoice exists locally; associated store credit balances tracked under Credit Notes (`<STORE_CODE>-CN-...`) are strictly non-transferable across branches and redeemable solely at the issuing store node.
- **Supplier Debit Notes**: Conforms to Section 34(3) of the CGST Act. Issued to distributors for returned near-expiry or damaged goods, recording distributor GSTIN, original purchase invoice reference, reversed input tax credit, and claim amount.
- **Rule 55 Delivery Challans**: Accompanies internal intra-state vehicle transit. Carries vehicle registration number, HSN codes, batch details, declared internal transfer value, and legal declaration: *"Goods transferred for internal branch stock, not for immediate sale"*.

---

## 9. Discounts
- Centrally governed discount presets reside on item or category records.
- Cashier can apply available presets; no manual discount edit rights.
- Manager (Full preset) or High-access (Simple preset) can edit discount preset values directly.
- Direct discount edits require live central connectivity and version-locking (subject to §4 concurrency exception).
- Changes logged immutably as `discount-edit` events.
- Manual Insurance/TPA tender metadata fields captured at checkout (Insurer Name, Policy Number, Pre-Authorization Approval Code) as text metadata on standard GST invoices.

---

## 10. Regulatory Compliance (India, Drugs & Cosmetics Act)

### 10.1 Absolute Expiry Hard-Block
- Under Section 18(a)(i) and Section 27 of the Drugs and Cosmetics Act, 1940, stocking, selling, or dispensing expired drugs is a strict liability criminal offense.
- **Absolute Hard-Block Invariant**: Any batch where $\text{expiry\_date} \le \text{current\_date}$ is **unconditionally hard-blocked from billing and dispensing** across both `Mandatory` and `Optional` compliance modes.
- Neither cashiers, pharmacists, nor store managers can bypass an expiry block.

### 10.2 Schedule H1 Register Payload Completeness
Under Rule 65(9) of the Drugs & Cosmetics Rules, pharmacies must maintain an immutable Schedule H1 register for 3 years capturing:
1. Supply Date and Time.
2. Patient Full Name and Residential Address.
3. Prescribing Doctor Full Name, Clinic Address, and State Medical Council Registration Number.
4. Drug Generic Name and Brand Name.
5. Batch Number and Manufacturer Name.
6. Quantity Dispensed and Pack Size.
7. Dispensing Pharmacist ID and Digital PIN.
- One-click Drug Inspector audit export (CSV and formatted PDF).
- `REVOKE UPDATE, DELETE ON dispense_events` enforced in store Postgres.

### 10.3 Schedule X & NDPS Dual-Prescription Custody & Bound Ledger
Under Rule 65(4) of the Drugs and Cosmetics Rules:
1. **Prescription Digital Archival**: Dispensing Schedule X drugs requires mandatory physical scanning or webcam photo capture of the original prescription.
   - Images compressed locally to 150–200 DPI WebP (<250 KB) and encrypted using AES-256 in `C:\medpos\prescriptions\`.
   - 90-day rolling edge retention with automated cloud sync (Central retains full 2-year statutory archive).
2. **Pharmacist Credential Binding**: Dispensing requires authorization with a registered Pharmacist PIN and records State Pharmacy Council registration credentials.
3. **Automated Immutable Daily Running Balance Ledger**:
   $$\text{Opening Batch Balance} + \text{Receipts (GRN)} - \text{Dispensed} = \text{Closing Batch Balance}$$
   Discrepancies highlight immediately for physical stock audit.
4. **State Licensing Authority Statutory Return**: One-click statutory reporting export formatted for submission to the Assistant Drugs Controller.

---

## 11. Roles & Access Control

### Selectable Role Presets
- **Full Preset (4-Role)**:
  - **Pharmacist**: Dispensing, Schedule H1/X register entry, prescription image capture, batch selection, physical inventory view.
  - **Cashier**: Billing, checkout, applying pre-configured discounts, opening/closing own shift, shift cash declaration. Cannot dispense H1/X drugs without pharmacist sign-off.
  - **Manager**: All Pharmacist and Cashier rights, plus: customer return authorization, vendor RTV debit note approval, delivery challan dispatch/receive, `stock-adjustment-in` PIN authorization, shift force-close override, local user account disabling during outages, stock write-offs, submitting §12 master-data change requests, direct discount preset edits (§9).
  - **Admin**: All Manager rights, plus: direct master-data edit/create/delete (§4), approving/rejecting §12 requests, chain-wide reporting, store setup, compliance mode configuration.
- **Simple Preset (2-Role)** (for single-operator / small pharmacy counters):
  - **High-Access**: Merges Pharmacist + Manager + Admin rights.
  - **Low-Access**: Billing only, apply discounts, open/close own shift (= Cashier).

### Local User Revocation
Store Managers can locally disable compromised user accounts directly on the store FastAPI terminal during network partitions, immediately invalidating local login without waiting for Central sync.

---

## 12. Master-Data Change Request Flow (Full Preset Only)
- Direct edit/create/delete: Admin (subject to §4 live-connectivity exception).
- Request only: Manager (catalog, pricing, tax — not discounts, see §9).
- No access: Cashier, Pharmacist.
- Scope: Single-field, single-record diff for edits (`field_name`, `current_value`, `expected_version`, `proposed_value`).
- Deletion requests reuse the edit mechanism (`field_name: deleted_at`), gated by the chain-wide zero-stock check.
- Request States: `pending` $\rightarrow$ `approved` / `rejected` (`manual` | `stale` | `duplicate` | `stock-remaining`).
- Central auto-rejects stale edits on version mismatch and duplicate creates on unique business key collision.

---

## 13. Shift Management & Day-End Till Reconciliation (Z-Report)
- Cashiers share counters across morning and evening shifts.
- **Shift Lifecycle**:
  1. `shift-open`: Cashier logs in, enters opening cash float. Terminal unlocks for billing.
  2. Operating Period: System tracks Cash, Card, UPI, and Credit/Debit Note transactions.
  3. `shift-close`: Cashier enters blind physical cash declaration.
  4. System computes **Till Variance**:
     $$\text{Variance} = \text{Declared Physical Cash} - (\text{Opening Float} + \text{Cash Sales} - \text{Cash Refunds})$$
- **Day-End Z-Report**: Generated at store closing, summarizing gross sales, net sales, tax breakdown, tender split, customer returns, vendor debit notes, and cashier till variances.
- **Manager Force-Close**: Allows Managers to close an abandoned shift with an audit note, unblocking the counter.

---

## 14. Testing & Verification Suite

### Automated Unit & Integration Tests
1. **Absolute Expiry Hard-Block**: Bill batch with $\text{expiry} \le \text{today}$ in `Optional` compliance mode. Assert: Hard-block, transaction rejected.
2. **UOM Integer Division & Rounding**: Test packaging with MRP ₹10.00 and pack size 7. Assert: Base unit price ₹1.43; buying 7 loose units clamped to ₹10.00 (not ₹10.01).
3. **UOM Barcode Scan Default**: Scan 2D DataMatrix for strip of 10. Assert: POS defaults to 10 base units on invoice line.
4. **Schedule H1 Completeness**: Dispense Schedule H1 drug without patient address or prescriber registration. Assert: Validation error, dispense blocked.
5. **Schedule X Prescription & Ledger**: Dispense Schedule X drug without prescription image or pharmacist PIN. Assert: Blocked. Ingest valid dispense; assert daily balance equation reconciles.
6. **Multi-Counter LAN Concurrency**: Counters 1 and 2 concurrently commit sales over LAN. Assert: Gapless `store_seq_no` sequence, zero duplicate invoice numbers.
7. **Standby Failover Fencing**: Execute `promote_to_primary.bat` while Counter 1 is reachable. Assert: Promotion blocked. Isolate Counter 1; assert Counter 2 promotes with `-F1` invoice epoch.
8. **Central Push Atomicity & Quarantine**: Push batch with 1 valid and 1 schema-corrupt event. Assert: Valid event commits, corrupt event routes to `central_sync_quarantine` with tombstone, store queue unblocked.
9. **Printer Jam 2-Phase State Machine**: Simulate printer offline at checkout. Assert: Sale commits as `COMMITTED_PENDING_PRINT`; UI displays error banner; reprint prints duplicate watermark.
10. **Printer Jam Customer Abandonment**: Customer walks away during printer jam. Cashier triggers void. Assert: System issues GST Credit Note, increments stock, gapless invoice series preserved.
11. **Rule 55 Challan Inter-State Guard**: Attempt Delivery Challan between Karnataka and Tamil Nadu stores. Assert: Blocked with statutory notice requiring IGST Tax Invoice.
12. **Transfer Discrepancy Breakdown**: Dispatch 100 units; receive 90 intact, 5 broken, 5 missing. Assert: 90 added to active stock, 5 routed to quarantine write-off, 5 logged to shortage audit.
13. **Near-Expiry Vendor Return Debit Note**: Pull batch with 45 days to expiry via `rtv-quarantine`. Assert: Stock removed from shelf; sequential GST Debit Note generated.
14. **Customer Return Condition Routing**: Return unexpired intact blister strip $\rightarrow$ restocked to active stock. Return unexpired punctured blister strip $\rightarrow$ routed to quarantine write-off.
15. **Offline Local Auth**: Disconnect WAN cable, restart store PC. User logs in. Assert: Local FastAPI validates against Argon2id hash and issues local JWT.
16. **Monotonic Clock Defense**: Set system clock back by 1 year. Attempt sale. Assert: Monotonic check fails with clock-skew error.
17. **Shift Reconciliation Math**: Open shift with 1000 float, 500 cash sale, declare 1400 cash. Assert: Z-Report shows -100 cash shortage variance.
18. **Windows File ACL Enforcement**: Verify non-privileged OS user cannot read `C:\medpos\config\db_key.env`.
19. **Prescription Image Edge Prune**: Ingest prescription image older than 90 days with confirmed Central sync. Assert: Edge file purged.
20. **Backup Retention**: Simulate 10 days of automated `pg_dump`. Assert: Only 7 rolling archives retained.

---

## 15. Observability & Telemetry
- **Structured JSON Logging**: Every store event, sync attempt, printer status failure, and manager override logged with correlation IDs.
- **Operational Metrics**:
  - Sync queue depth and lag (seconds since last acknowledged watermark).
  - Quarantined poison-pill event rate.
  - Multi-counter LAN latency and connection drop frequency.
  - Printer jam frequency and reprint count.
  - Cashier till variance and shrinkage tracking.
  - Frequency of manager `stock-adjustment-in` overrides.
  - Frequency of barcode scan overrides over FEFO.
  - Clock-skew alerts ($\Delta t > 5\text{ min}$).
  - Local database and prescription image disk storage utilization.
- **Alerting Thresholds**:
  - Store sync offline $> 30$ minutes during operating hours.
  - Quarantined poison-pill event recorded on Central.
  - Till cash shortage $> \text{₹}500$ on shift close.
  - Local disk storage $> 80\%$ full.

---

## 16. Security & Data Protection
- **Local Credential Storage**: Password hashes stored using Argon2id with store-level salting. Store Postgres bound strictly to `127.0.0.1`.
- **In-Store Network Security**: Store FastAPI listens on store LAN (`0.0.0.0:8000`) protected by WPA3-Enterprise or wired Gigabit switches. All counter API calls pass store-scoped session JWTs.
- **Windows File System ACL Hardening**: AES-256 database encryption keys and configuration files locked down via `icacls "C:\medpos\config" /inheritance:r /grant:r "NT SERVICE\MedPOS":(R)`. Standard Windows user accounts have no read permissions.
- **Prescription & Patient Data Privacy (DPDP Act 2023)**:
  - Patient PII (names, phone numbers, addresses) encrypted at rest in Postgres using AES-256.
  - Prescription scan images encrypted at rest in `C:\medpos\prescriptions\` using AES-256 before disk write.
  - Rolling 90-day edge image retention policy to minimize localized data breach liability.
- **Audit Immutability**: Dispense logs, GST invoices, GST Credit/Debit Notes, Delivery Challans, shift events, and stock adjustments are strictly append-only (`REVOKE UPDATE, DELETE`).

---

## 17. Deployment Safety & Edge Rollout
- **Staged Rollout**: Single canary store live for 7 days before rolling updates to remaining chain stores.
- **Rollback Safety**: Every database migration accompanied by a backwards-compatible rollback script.
- **Windows Edge Hardening**: POS terminals configured with unattended service recovery (NSSM), disk write-cache protection, and automatic UPS graceful shutdown integration.
- **Zero-Conf In-Store Discovery**: Worker terminals discover Counter 1 via mDNS (`medpos-primary.local:8000`), eliminating router static IP configuration hurdles.

---

## 18. Open Items (Phase 2 Roadmap — V2 Chain Scale)
The following enterprise capabilities are formally deferred to Phase 2.0, with interim operational bridges established in v1.6.5:
1. **Automated Central Supplier Settlement**: Stores generate local GST Debit Notes (§8); downstream distributor EDI bridges and automated AP ledger reconciliation deferred to V2.
2. **Central In-Transit Virtual Pool**: Rule 55 Challans and store receipt discrepancy logging codified in v1.6.5; chain-wide 3PL freight carrier APIs and logistics claims deferred to V2.
3. **B2B E-Invoicing (IRN) via Government IRP**: Store-local B2B Tax Invoices `<STORE>-B2B-...` generated locally for manual GSTR-1 upload; live NIC/GSP API handshakes and async IRN queues deferred to V2.
4. **Automated Standby Clustering**: Scripted failover (`promote_to_primary.bat`) with LAN fencing and epoch suffixes codified in v1.6.5; automated virtual IP (VIP) database streaming clusters deferred to V2.
5. **Delta Replication Cursor & Soft-Delete Tombstones**: Central push transaction atomicity with poison-pill quarantine tombstones codified in v1.6.5; central cursor pagination engines deferred to V2.
6. **Cross-Store Voucher Double-Spend 2PL**: Store credit vouchers strictly redeemable only at the issuing branch (v1.6 rule preserved); real-time distributed wallet redemptions deferred to V2.
7. **Hardware-Bound TPM 2.0 Key Sealing**: Windows File ACL (`icacls`) lockdown codified in v1.6.5; native C/Win32 TPM PCR silicon sealing deferred to V2.
8. **Central Cloud Multi-Tenant Kubernetes Cluster**: Single containerized Cloud VM with nightly backups sufficient for 2-5 pilot stores; auto-scaling Kubernetes clusters deferred to V2.
9. **Customer Dynamic UPI Secondary LCD Pole Display**: Dynamic UPI QR string printed on thermal receipt + countertop static UPI soundbox codified in v1.6.5; dual-head pole display drivers deferred to V2.
10. **Cashless Insurance / TPA Direct Processing**: Manual tender metadata fields codified in v1.6.5; live IRDAI TPA gateway integrations deferred to V2.
11. **Prescription Optical Character Recognition (OCR) AI Parsing**: Digital webcam/scanner photo capture attached to dispense records codified in v1.6.5; edge AI cursive handwriting transcription deferred to V2.
12. **Automated WhatsApp / SMS Enterprise Gateway**: Cashier one-click `wa.me` web link codified in v1.6.5; Meta WhatsApp Business API and Indian Telecom DLT gateway integrations deferred to V2.

---
*Status: Active (v1.6.5). Supersedes [architecture_v1_6.md](_archive/Prev_iterations/Architecture/architecture_v1_6.md) and [architecture_v1_5.md](_archive/Prev_iterations/Architecture/architecture_v1_5.md).*
