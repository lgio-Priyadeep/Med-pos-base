import sys, re
sys.stdout.reconfigure(encoding='utf-8')

clean_draft = '''# Pharmacy POS — Architecture Spec (v1.6.5)

*Changelog:*
- v1.5: Zero-stock deletion invariant, offline write-offs, and immutable audit logs.
- v1.6: Expiry hard-block, H1 completeness, offline directories, outbound sync, and Z-reports.
- v1.6.5: UOM fractional dispensing, RTV debit notes, Rule 55 challans, and LAN topology.

---

## 1. Scope
- Small chain target: 2–5 physical retail stores.
- Hybrid offline-first architecture with asynchronous background sync when online, excluding direct master-data writes (§4).
- In-store counter scaling: Multi-counter LAN topology (1 Primary node + 1–3 Worker terminals).
- Simple 2-role preset supported for single-operator counters (§11).
- Operational coverage: front-desk billing, fractional strip/tablet dispensing, sales returns/exchanges, vendor returns (RTV), branch delivery challans, batch inventory, shift till reconciliation, and regulatory compliance registers (Schedule H1 and Schedule X).

---

## 2. Tech Stack & Edge Infrastructure
- **Backend**: Standardized on Python and FastAPI across store nodes and Central services.
- **Central Database**: Postgres cloud instance for reporting and aggregation.
- **Local Database**: Dedicated Postgres 16 instance on Store Primary Node (Counter 1).
- **In-Store Multi-Counter LAN Topology**:
  - *Counter 1 (Primary Node)*: Authors all local commits; Postgres binds strictly to loopback `127.0.0.1` (no external database listener); Store FastAPI binds to `0.0.0.0:8000` on private Gigabit/WPA3 LAN, broadcasting via mDNS as `medpos-primary.local:8000` to immunize worker terminals against router DHCP IP reassignments.
  - *Counters 2/3 (Worker Terminals)*: Lightweight UI/Electron shells connecting over LAN to `medpos-primary.local:8000` via HTTP REST/WebSockets with zero local databases.
  - *Counter 2 Standby Role*: Warm standby receiving automated daily `pg_dump` backups and continuous WAL streaming from Counter 1.
  - *Standby Promotion Script (`promote_to_primary.bat`)*: Enforces LAN ping fencing against Counter 1 to prevent split-brain hazards before activating local services. `[DEFERRED → Doc 5: Standby Promotion Script & Fencing State Machine]`
  - *Emergency Failover Epoch*: Hardware loss causes promoted standby to adopt emergency epoch `<STORE_CODE>-INV-YYYYMM-XXXX-F1` and jump sequence by +100,000 to eliminate invoice collisions (§8).
- **Local Authentication**: Salted Argon2id password hashes and role mappings replicate from Central, issuing store-scoped JWTs (8–12h shift TTL) for 100% offline terminal authentication autonomy during WAN outages and reboots. Detailed token claim schemas and hash parameters deferred. `[DEFERRED → Doc 9: Local Auth JWT Claim Schema & Argon2id Hash Parameters]`
- **Unattended Edge Maintenance**: Daily automated `pg_dump` to secondary drive with rolling 7-day retention, background `VACUUM ANALYZE`, WAL pruning, and NSSM OS watchdog recovery (max 3 restarts per 10 min) prevent disk exhaustion and crash loops. Script configs deferred. `[DEFERRED → Doc 10: Unattended Edge Backup, Pruning & Watchdog Service Spec]`
- **Clock-Skew Defense**: Store Postgres enforces monotonic commit validation (`current_timestamp >= MAX(created_at)`), blocking commits on backward time drift. Sync heartbeats check local time against Central, triggering a prominent UI warning if skew exceeds $\pm 5$ minutes.

---

## 3. Core Modules
The system is partitioned into 13 discrete domain modules:
1. **Inventory & UOM Hierarchy**: Integer base units, pack immutability, FEFO picking, scan override, and write-offs.
2. **Customer Returns & Exchanges**: Invoice validation, blister foil condition routing, and GST Credit Notes.
3. **Vendor Returns (RTV)**: Expiry alert tiers (90d/60d/30d), return binning, and supplier GST Debit Notes.
4. **Branch Stock Transfers**: Rule 55 Delivery Challans, boundary tax guards, and receipt variance logging.
5. **Prescription & Dispensing**: Patient/doctor directories, Schedule H1 registers, Schedule X duplicate prescription archives, and bound ledgers.
6. **Billing & Cashier Operations**: Multi-counter LAN checkout, B2C/B2B invoices, dynamic UPI QR, WhatsApp share, and shift float reconciliation.
7. **Hardware & Peripherals**: Barcode scanners (1D/2D GS1), thermal printers with two-phase commit, RJ11 drawer kicks, and webcam photo capture.
8. **Multi-Store & Governance**: Master catalog sync, inter-store transfers, Central reporting, and change request reviews.
9. **Operational Directories**: Store-local offline walk-in patient and prescriber records with store-prefixed permanent IDs.
10. **Sync Engine**: Outbound store push over CGNAT, batch atomicity, poison-pill quarantine, and watermark acknowledgments.
11. **User Roles**: Selectable Full (4-role) and Simple (2-role) presets, and local staff account revocation.
12. **Settings & Config**: Compliance mode configuration, role presets, and append-only audit enforcement.
13. **Reporting**: Statutory registers, gross/net sales, GST tax summaries, till variances, and shrinkage analytics.

Module-to-module dependencies and build order are deferred to separate architectural specifications from implementation sequencing. `[DEFERRED → Doc 7: Core Module Dependency Graph & Build Order]`

---

## 4. System Architecture

### Local-First Store Node & Multi-Counter LAN
- Store operates 100% autonomously offline for billing, dispensing, returns, challans, stock movements, shift operations, and registration without Central dependency.
- Counter 1 commits all transactions to Postgres inside append-only event tables (§5); worker terminals bill against Counter 1 over LAN.

### Store-Initiated Outbound Sync Protocol
- All sync traffic is strictly store-initiated outbound (HTTPS POST / WebSockets) to operate reliably behind ISP CGNAT and dynamic IPs without inbound open ports.
- Sync triggers on fixed intervals (30–60s with exponential backoff and jitter), on network reconnect, or manual trigger. Central delivers catalog updates and governance decisions strictly as response payloads to outbound store requests.
- Central Postgres is strictly an aggregation and reporting database, never authoritative for per-store inventory. Retry backoff algorithms and network connection state machines deferred. `[DEFERRED → Doc 5: Outbound Sync Trigger & Retry Backoff State Machine]`

### Operational Directories vs Master Data
- **Central Master Data**: Drug catalog, prices, taxes, presets, and distributor profiles are centrally governed and require live connectivity for direct writes (see Exception below).
- **Store-Local Operational Entities**: Patient and Prescribing Doctor records are decoupled store-local operational entities with permanent store-prefixed IDs (`<STORE_CODE>-PAT-<UUID>`, `<STORE_CODE>-DOC-<UUID>`), 100% offline-creatable and synced upward asynchronously. Central performs logical deduplication purely in read-only audit views and never overwrites store entity IDs.

### Exception — Concurrency Control for Direct Master-Data Changes
- Direct master-data writes (edits, creations, soft-deletions) require live Central connectivity with optimistic version locking to prevent multi-store divergence. Governed records carry an integer `version` incremented on each Central write; edits reject on mismatch (`reason: stale`); creates reject on unique business key collision (`reason: duplicate`).
- Soft-deletion additionally requires aggregate chain-wide physical stock to be zero (§6).
- Central Admin accesses governance queues via a central Web portal with zero direct database connection into store LANs. Portal API contracts deferred. `[DEFERRED → Doc 3: Central Admin Web Portal Endpoints]`
- Multi-store write conflicts, simultaneous store/central edits, and network partition concurrency scenarios deferred. `[DEFERRED → Doc 6: Master-Data Concurrency Conflict & Partition Scenarios]`

---

## 5. Data Flow / Event Model

### Event Envelope Standard
Every state mutation commits as an immutable append-only event adhering to a standardized envelope: `event_id` (UUIDv4 PK), `store_seq_no` (monotonic BIGSERIAL), `store_id`, `created_at` (monotonic UTC), `event_type`, and `payload` (JSONB).

### Central Ingestion Atomicity & Poison-Pill Quarantine
- Central ingests store event batches sequentially in a single atomic database transaction (`BEGIN...COMMIT`), updating `central_events` and store watermarks simultaneously to ensure all-or-nothing consistency. Central enforces deduplication via `ON CONFLICT (event_id) DO NOTHING`.
- Schema-violating poison-pill events isolate into `central_sync_quarantine` with a `sync-quarantine-tombstone` recorded in `central_events` to preserve sequence continuity without blocking store retry queues. Central acknowledgment returns committed watermarks and quarantined IDs to unblock the store queue.
- Central sync and quarantine table schemas deferred. `[DEFERRED → Doc 1: Central Sync & Quarantine Table Schemas]`
- Ingestion endpoint HTTP contracts and batch payload schemas deferred. `[DEFERRED → Doc 3: Central Ingestion Batch Endpoint Contract]`

### Event Types
The system defines 17 categorical business event types and 1 quarantine event:
1. `sale`: Line items, base units, pack conversions, fractional pricing, taxes, invoice number (`<STORE_CODE>-INV-...`).
2. `b2b-sale`: Registered B2B sale, buyer GSTIN, line items, HSN tax summary (`<STORE_CODE>-B2B-...`).
3. `sale-return`: Original invoice reference, batch, return condition validation, Credit Note number (`<STORE_CODE>-CN-...`).
4. `dispense`: Prescription linkage, patient/doctor IDs, Schedule H1 mandatory register data, and Schedule X PIN/image metadata.
5. `stock-move`: Inventory adjustments carrying specific reasons: `transfer-dispatch` (accompanied by Challan `<STORE_CODE>-DC-...`), `transfer-receive` (logs variance breakdown: `received_qty`, `transit_breakage_qty`, `transit_shortage_qty`), `rtv-quarantine` (near-expiry stock pulled to return bin, generating Debit Note `<STORE_CODE>-DN-...`), `write-off` (physical removal of expired/damaged stock), and `adjustment-in` (Manager PIN authorized in-line physical correction at POS).
6. `shift-open`: Cashier ID, terminal ID, opening cash float, timestamp.
7. `shift-close`: Declared physical cash, calculated system cash, digital payment totals, variance, timestamp.
8. `shift-force-close`: Manager PIN override for abandoned shifts with audit reason.
9. `patient-created`: Store-local walk-in patient registration (`<STORE_CODE>-PAT-<UUID>`).
10. `doctor-created`: Store-local prescriber registration (`<STORE_CODE>-DOC-<UUID>`).
11. `discount-edit`: Direct preset edits by Manager/Admin with live version locking.
12. `master-data-edit`: Direct edits/soft-deletes by Admin with version check.
13. `master-data-created`: Direct catalog creation by Admin with business key check.
14. `master-data-change-requested`: Store-origin catalog/pricing change request from Manager (§12).
15. `master-data-change-approved` / `rejected`: Central governance review decisions.
16. `low-stock-alert`: Triggered when local stock drops to or below configured threshold.
17. `settings-change`: Admin configuration updates (compliance mode, role preset).
- `sync-quarantine-tombstone`: Synthetic marker preserving monotonic watermark progression for malformed payloads.

Complete JSONB payload schemas deferred. `[DEFERRED → Doc 2: Full Event Payload Schemas for Events 1–17 & Tombstones]`

---

## 6. Stock, Inventory Lifecycle & Batch Mechanics

### Unit of Measure (UOM) Hierarchy & Fractional Billing
- **Integer Base-Unit Invariant**: Inventory is tracked and stored strictly in atomic integer Base Dispensing Units (`tablets`, `capsules`, `ml`, `vials`); decimals are prohibited in storage.
- **Batch-Level Packaging Immutability**: `packaging_unit` (e.g. Strip of 10), `base_unit` (e.g. Tablet), and `pack_size` (integer ratio $P \in \mathbb{Z}^+$) are locked immutably on the Batch record at initial Goods Receipt Note (GRN) entry to prevent central catalog edits from distorting on-shelf stock counts. Batch table column definitions and check constraints deferred. `[DEFERRED → Doc 1: Batch Table UOM Field Schema & Constraints]`
- **Dual-Representation Calculation**: Pack quantity and loose units derived via integer division and modulo ($\text{Pack Qty} = \text{Base Qty} // \text{Pack Size}$, $\text{Loose Qty} = \text{Base Qty} \pmod{\text{Pack Size}}$).
- **Legal Metrology Rules 2011 Pricing**: Base unit price computed using half-up rounding: $\operatorname{ROUND\_HALF\_UP}(\text{Strip MRP} / \text{Pack Size}, 2)$. Statutory clauses deferred. `[DEFERRED → Doc 11: Legal Metrology Rule 2011 & Schedule Compliance Glossary]`
- **Statutory Price Clamping Invariant**: Loose Line Subtotal is strictly clamped to $\min(\text{Loose Qty} \times \text{Unit Price}, \text{Strip MRP})$; buying a full pack size strictly bills Strip MRP, legally preventing fractional rounding accumulation overcharges.
- **Barcode Scanning Context**: Scanning 1D/2D barcodes strictly bills 1 Packaging Unit ($1 \times \text{pack\_size}$ base units); loose unit dispensing requires explicit input into a dedicated UI field.
- **Fractional Return Restocking**: Cut blister strips with intact, airtight, undamaged foil over each individual tablet return to active stock ($+\text{Loose Qty}$); punctured, cut, or torn foil cavities route to `quarantine-write-off`.

### Near-Expiry Vendor Returns (RTV) & Alerts
- Inventory monitors days to shelf expiry ($\Delta t = \text{expiry\_date} - \text{current\_date}$): 90 Days Amber (FEFO priority), 60 Days Orange (RTV recommendation), 30 Days Red (immediate physical shelf quarantine).
- Pharmacists execute `stock-move: rtv-quarantine`, moving stock out of billing inventory into a return bin, generating an official GST Supplier Debit Note (§8).

### Inter-Store Stock Transfers & Statutory Delivery Challans
- Physical branch road transit requires an official Delivery Challan under Rule 55 of CGST Rules 2017. Delivery Challans are restricted strictly to intra-state transfers within the same legal entity ($\text{Source GSTIN} == \text{Dest GSTIN} \land \text{Source State} == \text{Dest State}$). Inter-state movements mandate a full IGST Tax Invoice under Section 7(4) of the IGST Act (§8).
- Receiving stores log counts in `transfer-receive` splitting into `received_qty` (active), `transit_breakage_qty` (quarantine write-off with photo), and `transit_shortage_qty` (shrinkage audit). Dispatch decrements source stock; receive increments destination stock. Transfer, inspection, and RTV state machines deferred. `[DEFERRED → Doc 5: Batch Picking, Fractional Return Inspection & RTV State Machines]`

### Batch Picking Mechanics
- Dispensing defaults to FEFO (earliest-expiring valid batch with stock $> 0$). Scanning a 2D GS1 DataMatrix strictly overrides FEFO suggestions to guarantee physical and invoiced batch parity. POS automatically splits items into sub-lines across multiple batches when requested quantity exceeds available primary batch stock.

### Stock Discrepancy & Non-Negative Stock Policy
- System stock must remain $\ge 0$. Negative stock billing is strictly prohibited. If physical stock exists on shelf but system stock displays 0, Manager PIN override triggers an immediate `stock-move: adjustment-in` at POS, logging cashier ID, authorizing manager ID, and reason code to Central Shrinkage Report.

### Customer Sales Returns Stock Routing
- Returns validate against original invoice and batch ID. Sealed undamaged items restock to active inventory; batches expired since purchase and broken cold-chain items (insulin, vaccines) strictly route to `quarantine-write-off`.

### Deletion Invariant & Partition-Era Sales Acceptance
- Products cannot be soft-deleted centrally while aggregate chain-wide stock $> 0$.
- Central never rejects historical sales events for soft-deleted products made offline. If an ingested sale reveals remaining unsold stock ($Stock_{\text{initial}} - Qty_{\text{sold}} > 0$), Central automatically clears soft-deletion (`deleted_at = null`) and notifies Central Admin and store manager. Detailed partition edge cases deferred. `[DEFERRED → Doc 6: Partition Ghost-Stock Ingestion & Auto-Resurrection Scenarios]`

---

## 7. Low Stock Alerts
- Configured per item, per store in integer base dispensing units.
- Triggers discrete `low-stock-alert` event when local stock drops to or below threshold.
- Cooldown: Alert is suppressed until inventory is replenished above threshold. Closes automatically upon deliberate stock write-offs that zero inventory without reorder intent. State lifecycle transitions deferred. `[DEFERRED → Doc 5: Low-Stock Alert State Lifecycle & Cooldown Flow]`

---

## 8. Invoicing (GST), Credit Notes, Debit Notes & Delivery Challans

### Numbering Series Orthogonality
All document series are computed store-locally, gapless, and mutually orthogonal across 6 discrete series: Retail B2C Invoices (`<STORE_CODE>-INV-YYYYMM-XXXX`), Emergency Failover B2C Invoices (`<STORE_CODE>-INV-YYYYMM-XXXX-F1`), Registered B2B Invoices (`<STORE_CODE>-B2B-YYYYMM-XXXX`), Sales Return Credit Notes (`<STORE_CODE>-CN-YYYYMM-XXXX`), Supplier Return Debit Notes (`<STORE_CODE>-DN-YYYYMM-XXXX`), and Rule 55 Delivery Challans (`<STORE_CODE>-DC-YYYYMM-XXXX`). Table structures and line-item schemas deferred. `[DEFERRED → Doc 1: Document Series Table Schemas & GST Line-Item Fields]`

### Invoicing Specifications
- **B2C Retail Checkout**: Conforms to CGST Section 31. Printed thermal bills display store GSTIN, HSN, batch, expiry, CGST/SGST breakdown, dynamic NPCI UPI QR string (`upi://pay?...`), and countertop audio soundbox confirmation. Cashiers have an optional one-click WhatsApp Web share link (`wa.me`) with pre-formatted invoice text for paperless delivery.
- **Two-Phase Print Commit & Jam Resilience**: Checkout commits locally as `COMMITTED_PENDING_PRINT` before testing printer status (300ms ESC/POS check with OS spooler fallback). Cash drawer kick synchronizes with print spooling. Printer jams trigger a UI error banner with one-click reprint generating audited watermark `*** DUPLICATE COPY ***`. If customer leaves during a jam, cashier triggers an automated void issuing an offsetting GST Credit Note (`<STORE_CODE>-CN-...`), restoring stock and preserving gapless invoice numbering. Print state transitions and void flow deferred. `[DEFERRED → Doc 5: Two-Phase Checkout Print Commit & Abandonment Void Workflow]`
- **B2B Tax Invoicing (Rule 46(b))**: Captures buyer 15-digit GSTIN, legal name, and HSN summary with statutory text *"Standard B2B Tax Invoice — Offline Pilot Mode"* for manual monthly GSTR-1 filing.
- **Sales Returns & GST Credit Notes**: Conforms to CGST Section 34, reversing tax liability. Offline returns and store credit balances are strictly non-transferable across branches and redeemable solely at issuing store node.
- **Supplier Debit Notes**: Conforms to CGST Section 34(3), issued to distributors for returned near-expiry or damaged goods, recording distributor GSTIN, purchase invoice ref, reversed ITC, and claim amount.
- **Rule 55 Delivery Challans**: Accompanies internal branch road transport with vehicle number, HSN, batch, declared internal transfer value, and statutory non-sale declaration. Statutory clauses and GST legal text deferred. `[DEFERRED → Doc 11: GST Statutory Invoicing, Credit/Debit Note & Challan Clauses]`

---

## 9. Discounts
- Centrally governed discount presets reside on item or category records. Cashiers are restricted to selecting pre-configured presets; manual discount percentage/amount editing is prohibited.
- Managers (Full preset) or High-access users (Simple preset) edit discount presets directly via live Central connection with optimistic version locking (§4). Edits log immutably as `discount-edit` events. Live discount edit flows deferred. `[DEFERRED → Doc 5: Live Discount Edit & Version Verification Flow]`
- Manual Insurance / TPA tender metadata fields (Insurer Name, Policy Number, Pre-Authorization Approval Code) captured at checkout as text metadata on standard GST invoices. Discount and TPA table schemas deferred. `[DEFERRED → Doc 1: Discount Preset Table & TPA Metadata Schema]`

---

## 10. Regulatory Compliance (India, Drugs & Cosmetics Act)

### 10.1 Absolute Expiry Hard-Block
- Under Section 18(a)(i) and Section 27 of the Drugs and Cosmetics Act 1940, stocking, selling, or dispensing expired drugs is a strict liability criminal offense.
- **Absolute Hard-Block Invariant**: Batches with $\text{expiry\_date} \le \text{current\_date}$ are unconditionally blocked from billing and dispensing across both `Mandatory` and `Optional` compliance modes. Zero bypass allowance for cashiers, pharmacists, or managers. Optional mode only relaxes non-statutory metadata.

### 10.2 Schedule H1 Register Payload Completeness
- Under Rule 65(9), pharmacies must maintain an immutable Schedule H1 register for 3 years capturing 7 mandatory parameters: supply date/time, patient name/address, doctor name/address/registration, drug brand/generic, batch/manufacturer, quantity/pack size, and dispensing pharmacist PIN.
- One-click Drug Inspector audit export supported (CSV and formatted PDF). Immutability enforced in Postgres via `REVOKE UPDATE, DELETE ON dispense_events` (§16). Database tables deferred. `[DEFERRED → Doc 1: Schedule H1 Register & Schedule X Ledger Table Schemas]` Dispense audit payloads deferred. `[DEFERRED → Doc 2: Dispense Event Schedule H1/X Audit Payload Schema]`

### 10.3 Schedule X & NDPS Dual-Prescription Custody & Bound Ledger
- Under Rule 65(4), Schedule X dispensing requires mandatory digital scanning or webcam photo capture of duplicate prescriptions. Images compressed locally to 150–200 DPI WebP (<250 KB), AES-256 encrypted, held under 90-day rolling edge retention with 2-year Central cloud archival. Image encryption specs deferred. `[DEFERRED → Doc 9: Prescription Image AES-256 Storage & Retention Specification]`
- Dispensing binds registered Pharmacist PIN and State Pharmacy Council registration credentials. Enforces automated immutable Daily Running Balance Ledger ($\text{Opening} + \text{Receipts} - \text{Dispensed} = \text{Closing}$) and one-click statutory export formatted for Assistant Drugs Controller.

---

## 11. Roles & Access Control

### Selectable Role Presets
- **Full Preset (4-Role)**:
  - **Pharmacist**: Dispensing, Schedule H1/X registers, prescription capture, batch selection, physical inventory view.
  - **Cashier**: Billing, checkout, applying presets, shift open/close float. Cannot dispense H1/X drugs without pharmacist sign-off.
  - **Manager**: All Pharmacist and Cashier rights, plus: return authorization, RTV debit notes, delivery challans, `adjustment-in` PIN, shift force-close, local user account disabling during outages, stock write-offs, master-data change requests (§12), direct discount preset edits (§9).
  - **Admin**: All Manager rights, plus: direct master-data edit/create/delete (§4), approving/rejecting §12 requests, chain reporting, store setup, compliance mode configuration.
- **Simple Preset (2-Role)** (single-operator / small pharmacy counters):
  - **High-Access**: Merges Pharmacist + Manager + Admin rights.
  - **Low-Access**: Billing only, apply discounts, open/close own shift (= Cashier).
- Comprehensive action-by-role permission matrix deferred. `[DEFERRED → Doc 4: Comprehensive Role Permission Matrix (4-Role & 2-Role)]`

### Local User Revocation
Store Managers can locally disable compromised user accounts directly on Store FastAPI during network partitions, immediately invalidating local login without waiting for Central sync.

---

## 12. Master-Data Change Request Flow (Full Preset Only)
- Direct edit/create/delete authority restricted strictly to Admin via live connection (§4). Managers submit single-field, single-record change requests for catalog, pricing, and tax (excluding discounts, which managers edit directly under §9). Request payload diff schema deferred. `[DEFERRED → Doc 2: Master-Data Change Request Payload Schema]`
- Deletion requests reuse edit mechanism (`field_name: deleted_at`), gated by chain-wide zero-stock verification. Request workflow states: `pending` $\rightarrow$ `approved` / `rejected` (`manual` | `stale` | `duplicate` | `stock-remaining`). Central auto-rejects stale edits on version mismatch and duplicate creates on unique business key collision. Request state machine deferred. `[DEFERRED → Doc 5: Master-Data Change Request State Machine]`

---

## 13. Shift Management & Day-End Till Reconciliation (Z-Report)
- Cashiers share counters across shifts; shift unlocks upon cashier login and opening float entry (`shift-open`). Operating period records Cash, Card, UPI, and Credit/Debit Note transactions.
- At shift close, cashier enters blind physical cash declaration; system calculates Till Variance:
  $$\text{Variance} = \text{Declared Physical Cash} - (\text{Opening Float} + \text{Cash Sales} - \text{Cash Refunds})$$
- Day-End Z-Report generated at closing summarizes gross/net sales, tax, tenders, returns, debit notes, and cashier variances. Shift and Z-Report table schemas deferred. `[DEFERRED → Doc 1: Shift Session & Z-Report Table Schemas]`
- Managers can force-close abandoned shifts with an audit note (`shift-force-close`) to unblock counters. Shift state transitions deferred. `[DEFERRED → Doc 5: Shift Lifecycle & Till Reconciliation State Machine]`

---

## 14. Testing & Verification Suite
The system enforces an automated unit and integration testing suite covering legal hard-blocks, Legal Metrology fractional rounding math, barcode priority overrides, Schedule H1/X audit logging, LAN multi-counter concurrency, standby failover fencing, Central push atomicity, printer jam recovery, Rule 55 transport guards, and offline auth autonomy. All 20 executable test case scenario implementations are deferred to the test specification to eliminate scenario tables from the architecture specification. `[DEFERRED → Doc 8: Automated Unit & Integration Test Suite Specifications (Tests 1–20)]`

---

## 15. Observability & Telemetry
- Structured JSON logging with correlation IDs implemented across all store events, sync attempts, printer status checks, and manager overrides. Log schema deferred. `[DEFERRED → Doc 9: Structured Log Schema & Audit Correlation ID Spec]`
- Continuous telemetry tracks sync queue depth/lag, poison-pill rate, LAN latency, printer jams, and cashier till variances. Automated alerts fire on sync offline $> 30$ minutes, poison-pill quarantines, till cash shortage $> \text{₹}500$, and disk storage $> 80\%$. Operational metrics and threshold configs deferred. `[DEFERRED → Doc 10: Operational Telemetry Metrics & Alerting Thresholds]`

---

## 16. Security & Data Protection
- Local credentials stored using Argon2id password hashes with store-level salting. Store Postgres binds strictly to `127.0.0.1` (§2).
- Store LAN protected via WPA3-Enterprise / Gigabit Ethernet; all terminal API calls pass store-scoped session JWTs.
- Windows file permissions locked via `icacls` restricting database keys and configuration files strictly to `NT SERVICE\MedPOS` with zero read access for standard accounts. Security hardening scripts deferred. `[DEFERRED → Doc 9: Edge Security Hardening, Windows File ACLs & Encryption Spec]`
- DPDP Act 2023 compliance: Patient PII and prescription scans encrypted at rest using AES-256 with 90-day rolling edge retention (§10.3).
- Audit immutability: Dispense logs, invoices, credit/debit notes, challans, and stock adjustments enforce append-only storage via `REVOKE UPDATE, DELETE`.

---

## 17. Deployment Safety & Edge Rollout
- Staged deployment mandates a single canary store live for 7 days before chain-wide rollout.
- Every database migration must include a backwards-compatible rollback script.
- POS terminals configured with NSSM watchdog auto-recovery, disk write-cache protection, and UPS graceful shutdown. Worker terminals discover Counter 1 via mDNS broadcast (`medpos-primary.local:8000`). Deployment checklists deferred. `[DEFERRED → Doc 10: Canary Rollout Protocol, Rollback Procedures & Edge Checklist]`

---

## 18. Open Items (Phase 2 Roadmap — V2 Chain Scale)
The following enterprise capabilities are formally deferred to Phase 2.0, with interim operational bridges established in v1.6.5:
1. **Central Supplier Settlement**: Store-local GST Debit Notes (§8); distributor EDI deferred to V2.
2. **Central In-Transit Virtual Pool**: Rule 55 Challans & receipt discrepancy logging codified; 3PL freight APIs deferred to V2.
3. **B2B E-Invoicing (IRN) via Government IRP**: Store-local B2B Invoices `<STORE_CODE>-B2B-...` for manual GSTR-1 upload; live IRP APIs deferred to V2.
4. **Standby Clustering**: Scripted failover (`promote_to_primary.bat`) with LAN fencing & `-F1` epoch codified; automated VIP database clustering deferred to V2.
5. **Delta Replication Cursors**: Push atomicity with poison-pill quarantine tombstones codified; cursor pagination deferred to V2.
6. **Cross-Store Voucher Double-Spend 2PL**: Credit vouchers strictly non-transferable across branches; real-time distributed wallets deferred to V2.
7. **Hardware TPM 2.0 Key Sealing**: Windows `icacls` lockdown codified; native TPM PCR silicon sealing deferred to V2.
8. **Cloud Multi-Tenant Kubernetes**: Single Cloud VM with nightly backups sufficient for 2-5 pilot stores; auto-scaling Kubernetes deferred to V2.
9. **Dynamic Secondary LCD Pole Display**: Dynamic UPI QR on thermal bill + audio soundbox codified; dual-head pole displays deferred to V2.
10. **Cashless Insurance / TPA Processing**: Manual tender metadata fields codified; live IRDAI TPA gateway deferred to V2.
11. **Prescription OCR AI Parsing**: Digital photo capture attached to dispense records codified; cursive handwriting OCR deferred to V2.
12. **Automated WhatsApp / SMS Gateway**: Cashier one-click `wa.me` web link codified; Meta WhatsApp Business API deferred to V2.

Enterprise distributed edge cases deferred. `[DEFERRED → Doc 6: V2 Enterprise Distributed Edge Cases & Scenarios]`
Enterprise roadmap dependency tree deferred. `[DEFERRED → Doc 7: V2 Enterprise Module Dependencies & Architectural Roadmap]`

### Open Architecture Questions
1. **Q1: In-Line Adjustment Qty Scope**: When physical stock exists at POS but system stock displays 0, does `stock-adjustment-in` adjust only the quantity required for the current transaction or the full physical shelf count?
   - *Owner*: Core POS Lead
   - *Target*: v1.6.6 Sprint 1
2. **Q2: Shift Handover Float Policy**: In multi-shift counters, do cashiers swap physical cash drawer cassettes or perform an in-place handoff and count of shared float?
   - *Owner*: Retail Operations Lead
   - *Target*: v1.6.6 Sprint 1
3. **Q3: Credit Note Validity & Partial Redemption**: Do `<STORE_CODE>-CN-...` credit balances expire after a statutory period (e.g. 180 days) and can they be partially redeemed across multiple retail visits?
   - *Owner*: Finance & GST Lead
   - *Target*: v1.6.6 Sprint 2

---

## 19. Deferred Items Register

### Doc 1: Data Schema Doc
1. `[DEFERRED → Doc 1: Central Sync & Quarantine Table Schemas]` — DDL for central_events, store_sync_watermarks, and central_sync_quarantine.
2. `[DEFERRED → Doc 1: Batch Table UOM Field Schema & Constraints]` — Column definitions and constraints for packaging_unit, base_unit, pack_size, and integer quantity checks.
3. `[DEFERRED → Doc 1: Document Series Table Schemas & GST Line-Item Fields]` — DDL for document sequence counters, invoice tables, and GST line-item tax calculation fields.
4. `[DEFERRED → Doc 1: Discount Preset Table & TPA Metadata Schema]` — Schema for discount preset rules and invoice-attached Insurance/TPA claim metadata.
5. `[DEFERRED → Doc 1: Schedule H1 Register & Schedule X Ledger Table Schemas]` — Database tables for 3-year Schedule H1 audit logs and Schedule X daily running balance ledgers.
6. `[DEFERRED → Doc 1: Shift Session & Z-Report Table Schemas]` — Table schemas for cashier shift float tracking, blind cash declarations, till variances, and Day-End Z-Reports.

### Doc 2: Event Schema Doc
7. `[DEFERRED → Doc 2: Full Event Payload Schemas for Events 1–17 & Tombstones]` — Complete JSONB payload specifications and schemas for all 17 domain event types and quarantine tombstones.
8. `[DEFERRED → Doc 2: Dispense Event Schedule H1/X Audit Payload Schema]` — Detailed payload structures capturing 7 statutory H1 parameters, pharmacist credentials, and Schedule X prescription image hashes.
9. `[DEFERRED → Doc 2: Master-Data Change Request Payload Schema]` — JSON schema for single-field, single-record change request diffs.

### Doc 3: API Contract Doc
10. `[DEFERRED → Doc 3: Central Admin Web Portal Endpoints]` — REST API contracts for Central Admin governance dashboards, change request review queues, and multi-store shrinkage reports.
11. `[DEFERRED → Doc 3: Central Ingestion Batch Endpoint Contract]` — Request/response contracts, headers, batch sizing rules, and error codes for POST /api/v1/sync/events/batch.

### Doc 4: RBAC Permission Matrix
12. `[DEFERRED → Doc 4: Comprehensive Role Permission Matrix (4-Role & 2-Role)]` — Complete action-by-role permission grid mapping Pharmacist, Cashier, Manager, Admin, High-Access, and Low-Access against every system operation.

### Doc 5: Critical Flow State Machines
13. `[DEFERRED → Doc 5: Standby Promotion Script & Fencing State Machine]` — Step-by-step failover state machine, LAN health ping check, service launch, and emergency -F1 epoch sequence jump.
14. `[DEFERRED → Doc 5: Outbound Sync Trigger & Retry Backoff State Machine]` — Sync trigger state machine with exponential backoff, jitter, and automatic reconnection retry loops.
15. `[DEFERRED → Doc 5: Batch Picking, Fractional Return Inspection & RTV State Machines]` — State workflows for barcode scan priority over FEFO, multi-batch line splitting, blister condition inspection, and 90d/60d/30d RTV quarantine routing.
16. `[DEFERRED → Doc 5: Low-Stock Alert State Lifecycle & Cooldown Flow]` — State transitions for alert triggering, replenishment cooldown suppression, and auto-close on deliberate zero stock write-offs.
17. `[DEFERRED → Doc 5: Two-Phase Checkout Print Commit & Abandonment Void Workflow]` — Checkout state machine, ESC/POS status probe, OS spooler fallback, reprint watermarking, and customer abandonment Credit Note void.
18. `[DEFERRED → Doc 5: Live Discount Edit & Version Verification Flow]` — State machine for live Central discount preset verification, version incrementing, and stale write conflict rejection.
19. `[DEFERRED → Doc 5: Master-Data Change Request State Machine]` — Lifecycle transitions and automated Central rejection rules.
20. `[DEFERRED → Doc 5: Shift Lifecycle & Till Reconciliation State Machine]` — Step-by-step cashier shift transitions and manager force-close override workflow.

### Doc 6: Conflict & Edge Case Matrix
21. `[DEFERRED → Doc 6: Master-Data Concurrency Conflict & Partition Scenarios]` — Matrix resolving simultaneous store/central edits, optimistic version mismatch handling, and duplicate key creation conflicts.
22. `[DEFERRED → Doc 6: Partition Ghost-Stock Ingestion & Auto-Resurrection Scenarios]` — Protocol for ingesting historical partition sales of soft-deleted items and automated un-deletion on remaining stock.
23. `[DEFERRED → Doc 6: V2 Enterprise Distributed Edge Cases & Scenarios]` — Enterprise edge cases covering multi-store voucher redemptions, virtual in-transit inventory pools, and carrier freight claims.

### Doc 7: Dependency Map
24. `[DEFERRED → Doc 7: Core Module Dependency Graph & Build Order]` — Module-to-module dependency hierarchy and implementation sequence across the 13 core modules.
25. `[DEFERRED → Doc 7: V2 Enterprise Module Dependencies & Architectural Roadmap]` — Enterprise capability dependency tree and Phase 2.0 scaling roadmap.

### Doc 8: Test Plan Doc
26. `[DEFERRED → Doc 8: Automated Unit & Integration Test Suite Specifications (Tests 1–20)]` — Verbatim test specifications, assertions, and mock scenarios for all 20 automated system tests.

### Doc 9: Security & Audit Log Spec
27. `[DEFERRED → Doc 9: Local Auth JWT Claim Schema & Argon2id Hash Parameters]` — Argon2id cryptographic parameters and store-scoped JWT claim payload structures.
28. `[DEFERRED → Doc 9: Prescription Image AES-256 Storage & Retention Specification]` — Technical specification for WebP compression, local AES-256 disk encryption, and 90-day pruning automation.
29. `[DEFERRED → Doc 9: Structured Log Schema & Audit Correlation ID Spec]` — Standardized JSON log schema, event correlation IDs, and transaction tracing specs across store terminals and sync agents.
30. `[DEFERRED → Doc 9: Edge Security Hardening, Windows File ACLs & Encryption Spec]` — Windows icacls command configurations locking database keys to NT SERVICE\\MedPOS and DPDP Act 2023 AES-256 database encryption at rest.

### Doc 10: Deployment & Rollout Plan
31. `[DEFERRED → Doc 10: Unattended Edge Backup, Pruning & Watchdog Service Spec]` — Nightly automated pg_dump schedules, 7-day rolling archive pruning scripts, and NSSM service watchdog restart configs.
32. `[DEFERRED → Doc 10: Operational Telemetry Metrics & Alerting Thresholds]` — Prometheus metric definitions, monitoring queries, and alerting rules for sync lag, poison pills, and till shortages.
33. `[DEFERRED → Doc 10: Canary Rollout Protocol, Rollback Procedures & Edge Checklist]` — 7-day single canary store evaluation criteria, migration rollback procedures, and edge POS hardware protection checklists.

### Doc 11: Glossary
34. `[DEFERRED → Doc 11: Legal Metrology Rule 2011 & Schedule Compliance Glossary]` — Statutory definitions for Legal Metrology Packaged Commodities Rule 2011 fractional pricing, Schedule H1, and Schedule X/NDPS regulations.
35. `[DEFERRED → Doc 11: GST Statutory Invoicing, Credit/Debit Note & Challan Clauses]` — Legal definitions and statutory text clauses under CGST Section 31, Section 34, Rule 46(b), and Rule 55 Delivery Challans.

---
*Status: Active (v1.6.5). Supersedes architecture_v1_6.md and architecture_v1_5.md.*
'''

with open('scratch/draft_content.md', 'w', encoding='utf-8') as f:
    f.write(clean_draft)

words = len(clean_draft.split())
print(f'CLEAN DRAFT WORD COUNT: {words}')
