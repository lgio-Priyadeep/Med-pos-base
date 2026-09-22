# Pharmacy POS — Architecture Spec (v1.6.5)

*Changelog:*
- v1.5: Zero-stock deletion invariant, offline write-offs, and immutable audit logs.
- v1.6: Expiry hard-block, H1 completeness, offline directories, outbound sync, and Z-reports.
- v1.6.5: UOM fractional dispensing, RTV debit notes, Rule 55 challans, and LAN topology.

---

## 1. Scope
- Small chain footprint: 2–5 physical retail stores (D01).
- Deployment topology: Hybrid offline-first architecture with asynchronous background sync when online, excluding direct master-data writes (§4) (D02).
- In-store scaling: Multi-counter LAN topology comprising 1 Primary node and 1–3 Worker terminals (D03).
- Small single-store operators: Supported via a simplified 2-role preset (§11) (D04).
- Operational scope: Front-desk billing, fractional strip/tablet dispensing, sales returns/exchanges, vendor returns (RTV), branch delivery challans, batch inventory, shift till reconciliation, and regulatory registers (Schedule H1 and Schedule X) (D05).

---

## 2. Tech Stack & Edge Infrastructure
- **Backend**: Standardized on Python and FastAPI across store-side and Central nodes (D06).
- **Central DB**: Postgres cloud instance for reporting and aggregation (D07).
- **Local DB**: Dedicated Postgres 16 instance on Store Primary Node (Counter 1) (D08).
- **Multi-Counter LAN Topology**:
  - *Counter 1 (Primary Node)*: Single sequence authority committing all transactions to Postgres bound strictly to loopback `127.0.0.1` (D09). Store FastAPI binds to `0.0.0.0:8000` on private Gigabit/WPA3 LAN (D10) and broadcasts via mDNS as `medpos-primary.local:8000` for DHCP churn immunity (D11).
  - *Counters 2/3 (Worker Terminals)*: Lightweight UI/Electron shells connecting to Counter 1 over LAN via HTTP REST/WebSockets with zero local databases (D12).
  - *Counter 2 Standby Role*: Warm standby receiving automated daily `pg_dump` backups and continuous WAL streaming from Counter 1 (D13).
  - *Standby Promotion Script (`promote_to_primary.bat`)*: Enforces LAN ping fencing against Counter 1 to prevent split-brain hazards before service launch (D14). Failover state machine deferred. `[DEFERRED → Doc 5: Standby Promotion Script & Fencing State Machine]`
  - *Emergency Failover Epoch*: Promoted standby adopts emergency sequence epoch `<STORE_CODE>-INV-YYYYMM-XXXX-F1` and jumps sequence by +100,000 to eliminate invoice collisions on hardware loss (§8) (D15).
- **Local Authentication**: Salted Argon2id password hashes and role mappings replicate from Central to store Postgres, issuing store-scoped JWTs (8–12h shift TTL) locally (D16) to ensure 100% terminal auth autonomy during internet outages and reboots (D17). Token schemas deferred. `[DEFERRED → Doc 9: Local Auth JWT Claim Schema & Argon2id Hash Parameters]`
- **Unattended Maintenance & Recovery**: Daily automated `pg_dump` to secondary drive with rolling 7-day retention (D18), background `VACUUM ANALYZE` and WAL pruning prevent disk exhaustion (D19). NSSM watchdog auto-restarts services with crash-loop backoff (max 3 restarts per 10 min) (D20). Configs deferred. `[DEFERRED → Doc 10: Unattended Edge Backup, Pruning & Watchdog Service Spec]`
- **Clock-Skew Defense**: Store Postgres enforces monotonic commit validation (`current_timestamp >= MAX(created_at)`), blocking transactions on dead CMOS battery resets (D21). Sync heartbeats check local time against Central, triggering UI warning if skew exceeds $\pm 5$ minutes (D22).

---

## 3. Core Modules
The system partitions into 13 discrete domain modules: Inventory & UOM Hierarchy, Customer Returns & Exchanges, Vendor Returns (RTV), Branch Stock Transfers, Prescription & Dispensing, Billing & Cashier Operations, Hardware & Peripherals, Multi-Store & Governance, Operational Directories, Sync Engine, User Roles, Settings & Config, and Reporting (D23). Module dependencies and build order deferred. `[DEFERRED → Doc 7: Core Module Dependency Graph & Build Order]`

---

## 4. System Architecture

### Local-First Store Node & Multi-Counter LAN
Store nodes operate 100% offline for billing, dispensing, returns, challans, stock moves, shifts, and local registration without Central connectivity (D24). Counter 1 commits all transactions to Postgres inside append-only event tables (§5) (D25); worker terminals bill against Counter 1 over LAN.

### Store-Initiated Outbound Sync Protocol
Sync traffic is strictly store-initiated outbound (HTTPS/WebSockets) to traverse ISP CGNAT and dynamic IPs without open inbound ports (D26). Pushes trigger at 30–60s intervals (with backoff/jitter), on reconnect, or manual trigger (D27). Central delivers catalog updates and governance decisions strictly in response payloads (D28). Central Postgres is an aggregation/reporting DB, never authoritative for store inventory (D29). Retry state machines deferred. `[DEFERRED → Doc 5: Outbound Sync Trigger & Retry Backoff State Machine]`

### Operational Directories vs Master Data
Central master data (catalog, prices, taxes, presets, distributors) is centrally governed and requires live connectivity for direct writes (D30). Patient and Doctor records are decoupled store-local entities with permanent store-prefixed IDs (`<STORE_CODE>-PAT-<UUID>`, `<STORE_CODE>-DOC-<UUID>`), 100% offline-creatable and synced asynchronously (D31). Central performs deduplication in read-only audit views, never overwriting store IDs (D32).

### Concurrency Control for Direct Master-Data Changes
Direct master-data writes require live Central connectivity with optimistic version locking to prevent multi-store divergence (D30). Records carry integer version incremented per Central write; edits reject on mismatch (`reason: stale`) (D33); creates reject on business key collision (`reason: duplicate`) (D34). Soft-deletion requires chain-wide physical stock to be zero (§6) (D35). Central Admin uses a Web portal with zero direct database connection into store LANs (D36). Portal API contracts deferred `[DEFERRED → Doc 3: Central Admin Web Portal Endpoints]`; conflict scenarios deferred `[DEFERRED → Doc 6: Master-Data Concurrency Conflict & Partition Scenarios]`.

---

## 5. Data Flow / Event Model

### Event Envelope Standard
Every state mutation commits as an immutable append-only event: `event_id` (UUIDv4 PK), `store_seq_no` (monotonic BIGSERIAL), `store_id`, `created_at` (monotonic UTC), `event_type`, and `payload` (JSONB) (D37).

### Central Ingestion Atomicity & Poison-Pill Quarantine
Central ingests store event batches sequentially in a single atomic transaction (`BEGIN...COMMIT`) with sequence watermarks to ensure all-or-nothing consistency (D38) and idempotency via `ON CONFLICT (event_id) DO NOTHING` (D39). Schema-violating poison-pill events isolate into `central_sync_quarantine` with `sync-quarantine-tombstone` records in `central_events` to preserve sequence continuity without blocking store retry queues (D40). Central acknowledgment returns committed watermarks and quarantined IDs to unblock store queues while flagging issues for audit (D41). Sync tables deferred `[DEFERRED → Doc 1: Central Sync & Quarantine Table Schemas]`; batch ingestion contracts deferred `[DEFERRED → Doc 3: Central Ingestion Batch Endpoint Contract]`.

### Event Types
The system defines 17 categorical domain event types: sales (`sale`, `b2b-sale`), returns (`sale-return`), dispensing (`dispense`), inventory movements (`stock-move` for transfers, RTV, write-offs, adjustments), shift operations (`shift-open`, `shift-close`, `shift-force-close`), operational directories (`patient-created`, `doctor-created`), master data governance (`discount-edit`, `master-data-edit`, `master-data-created`, `master-data-change-requested`, `master-data-change-approved`, `master-data-change-rejected`), and administration (`low-stock-alert`, `settings-change`) (D42). Includes `sync-quarantine-tombstone` for malformed payloads. JSONB schemas deferred. `[DEFERRED → Doc 2: Full Event Payload Schemas for Events 1–17 & Tombstones]`

---

## 6. Stock, Inventory Lifecycle & Batch Mechanics

### Unit of Measure (UOM) Hierarchy & Fractional Billing
- **Integer Base-Unit Invariant**: Inventory stored strictly in atomic integer Base Dispensing Units (`tablets`, `capsules`, `ml`, `vials`); decimals prohibited in storage (D43).
- **Batch-Level Packaging Immutability**: `packaging_unit`, `base_unit`, and `pack_size` lock immutably on Batch at GRN to prevent catalog edits distorting shelf stock (D44). `[DEFERRED → Doc 1: Batch Table UOM Field Schema & Constraints]`
- **Dual-Representation**: Pack and loose quantities derived via integer division and modulo: $\text{Pack Qty} = \text{Base Qty} // \text{Pack Size}$, $\text{Loose Qty} = \text{Base Qty} \pmod{\text{Pack Size}}$ (D45).
- **Legal Metrology Pricing**: Base unit price rounded half-up: $\operatorname{ROUND\_HALF\_UP}(\text{Strip MRP} / \text{Pack Size}, 2)$ (D46). Statutory rules deferred. `[DEFERRED → Doc 11: Legal Metrology Rule 2011 & Schedule Compliance Glossary]`
- **Statutory Price Clamping**: Loose Subtotal clamped to $\min(\text{Loose Qty} \times \text{Unit Price}, \text{Strip MRP})$; full pack bills Strip MRP to prevent rounding overcharges (D47).
- **Barcode Scanning**: 1D/2D barcodes bill 1 Packaging Unit ($1 \times \text{pack\_size}$ base units); loose units require explicit input in dedicated UI field (D48).
- **Fractional Return Restocking**: Blisters with intact airtight foil return to active stock ($+\text{Loose Qty}$); punctured/cut cavities route to `quarantine-write-off` (D49).

### Near-Expiry Vendor Returns (RTV) & Alerts
Days to shelf expiry ($\Delta t = \text{expiry\_date} - \text{current\_date}$) monitored: 90d Amber (FEFO priority), 60d Orange (RTV recommendation), 30d Red (immediate shelf quarantine) (D50). Pharmacists execute `stock-move: rtv-quarantine` to return bin, generating sequential GST Debit Note (§8) (D51).

### Inter-Store Stock Transfers & Statutory Delivery Challans
Branch road transit requires Rule 55 Delivery Challan (D52), restricted to intra-state moves with identical GSTIN; inter-state moves require IGST Tax Invoice (§8) (D53). Receiving store logs `transfer-receive` splitting into `received_qty` (active), `transit_breakage_qty` (quarantine write-off with photo), and `transit_shortage_qty` (shrinkage audit) (D54). Dispatch decrements source stock; receive increments destination stock (D55). State workflows deferred. `[DEFERRED → Doc 5: Batch Picking, Fractional Return Inspection & RTV State Machines]`

### Batch Picking & Stock Integrity
- **Batch Picking**: Dispensing defaults to FEFO for earliest-expiring valid batch with stock $> 0$ (D56). 2D GS1 DataMatrix scan overrides FEFO to guarantee physical/invoiced parity (D57). Multi-batch line split triggered when requested qty exceeds primary batch stock (D58).
- **Non-Negative Stock**: System stock must remain $\ge 0$ (D59). If physical stock exists but system displays 0, Manager PIN triggers `stock-move: adjustment-in`, logging to Central Shrinkage (D60).
- **Sales Returns**: Validated against original invoice/batch; sealed items restock to active inventory (D61); expired batches or broken cold-chain route to `quarantine-write-off` (D62).
- **Soft-Delete & Partitions**: Products cannot be soft-deleted while chain stock $> 0$ (D35). Central accepts offline sales of soft-deleted items (D63), auto-resurrecting items (`deleted_at = null`) if partition sales reveal remaining stock (D64). `[DEFERRED → Doc 6: Partition Ghost-Stock Ingestion & Auto-Resurrection Scenarios]`

---

## 7. Low Stock Alerts
Configured per item, per store in integer base dispensing units (D65). Triggers discrete `low-stock-alert` event when stock drops to or below threshold, suppressed until replenished above threshold (D66). Closes automatically upon deliberate stock write-offs that zero inventory without reorder intent (D67). State lifecycle transitions deferred. `[DEFERRED → Doc 5: Low-Stock Alert State Lifecycle & Cooldown Flow]`

---

## 8. Invoicing (GST), Credit Notes, Debit Notes & Delivery Challans

### Numbering Series Orthogonality
Document series are computed store-locally, gapless, and mutually orthogonal across 6 series (D68): Retail B2C Invoices (`<STORE_CODE>-INV-YYYYMM-XXXX`), Emergency Failover B2C Invoices (`<STORE_CODE>-INV-YYYYMM-XXXX-F1`), Registered B2B Invoices (`<STORE_CODE>-B2B-YYYYMM-XXXX`), Sales Return Credit Notes (`<STORE_CODE>-CN-YYYYMM-XXXX`), Supplier Return Debit Notes (`<STORE_CODE>-DN-YYYYMM-XXXX`), and Delivery Challans (`<STORE_CODE>-DC-YYYYMM-XXXX`). Series schemas deferred. `[DEFERRED → Doc 1: Document Series Table Schemas & GST Line-Item Fields]`

### Invoicing Specifications
- **B2C Retail Checkout**: Conforms to CGST Section 31 with GSTIN, HSN, batch, expiry, tax breakdown, dynamic NPCI UPI QR (`upi://pay?...`), and audio soundbox confirmation (D69). Optional one-click WhatsApp share link (`wa.me`) provides paperless receipts (D70).
- **Two-Phase Print Commit & Jam Resilience**: Checkout commits locally as `COMMITTED_PENDING_PRINT` before printer check (D121) (300ms ESC/POS check with OS spooler fallback) (D122). Cash drawer kick synchronizes with print spooling (D123). Printer jams prompt UI banner with one-click reprint adding audited `*** DUPLICATE COPY ***` watermark (D124). Customer walkaway during jam triggers cashier void issuing offsetting Credit Note (`<STORE_CODE>-CN-...`), restoring stock and preserving gapless numbering (D125). Workflows deferred. `[DEFERRED → Doc 5: Two-Phase Checkout Print Commit & Abandonment Void Workflow]`
- **B2B Invoices & Credit/Debit Notes**: B2B invoices capture buyer 15-digit GSTIN, legal name, and HSN summary under Rule 46(b) for monthly GSTR-1 (D71). Credit Notes conform to Section 34 CGST Act, reversing tax liability (D72); store credit balances are non-transferable across branches, redeemable solely at issuing store (D73). Debit Notes conform to Section 34(3) for vendor returns (D74). Rule 55 Delivery Challans accompany intra-state transport with vehicle number and non-sale declaration (D75). Clauses deferred. `[DEFERRED → Doc 11: GST Statutory Invoicing, Credit/Debit Note & Challan Clauses]`

---

## 9. Discounts
Centrally governed discount presets reside on item or category records (D76). Cashiers are restricted to selecting pre-configured presets; manual discount overrides are prohibited (D77). Managers (Full preset) or High-access users (Simple preset) edit discount presets directly via live Central connection with optimistic version locking (§4) (D78). Edits log immutably as `discount-edit` events (D79). Live discount edit flows deferred. `[DEFERRED → Doc 5: Live Discount Edit & Version Verification Flow]`
Manual Insurance / TPA tender metadata fields (Insurer Name, Policy Number, Pre-Authorization Approval Code) captured at checkout as text metadata on standard GST invoices (D80). Preset and TPA schemas deferred. `[DEFERRED → Doc 1: Discount Preset Table & TPA Metadata Schema]`

---

## 10. Regulatory Compliance (India, Drugs & Cosmetics Act)

### 10.1 Absolute Expiry Hard-Block
Under Section 18(a)(i) and Section 27 of Drugs & Cosmetics Act 1940, stocking or selling expired drugs is a strict liability criminal offense. Batches with $\text{expiry\_date} \le \text{current\_date}$ are unconditionally blocked from billing and dispensing across both Mandatory and Optional compliance modes (D81). Zero bypass allowance for cashiers, pharmacists, or managers (D82). Optional mode relaxes only non-statutory metadata.

### 10.2 Schedule H1 Register Completeness
Rule 65(9) mandates an immutable 3-year register capturing 7 mandatory parameters: supply date/time, patient name/address, doctor name/address/registration, drug brand/generic, batch/manufacturer, quantity/pack size, and dispensing pharmacist PIN (D83). Supports one-click Drug Inspector audit export (CSV and PDF) (D84). Postgres enforces `REVOKE UPDATE, DELETE ON dispense_events` (§16) (D85). Tables deferred `[DEFERRED → Doc 1: Schedule H1 Register & Schedule X Ledger Table Schemas]`; payload schemas deferred `[DEFERRED → Doc 2: Dispense Event Schedule H1/X Audit Payload Schema]`.

### 10.3 Schedule X & NDPS Dual-Prescription Custody & Bound Ledger
Rule 65(4) mandates digital physical scan or webcam photo capture of duplicate prescriptions (D86). Images compressed locally to 150–200 DPI WebP (<250 KB), AES-256 encrypted, with 90-day rolling edge retention and 2-year Central cloud archival (D87). Image encryption specs deferred. `[DEFERRED → Doc 9: Prescription Image AES-256 Storage & Retention Specification]` Dispensing binds registered Pharmacist PIN and State Pharmacy Council credentials (D88). Enforces automated immutable Daily Running Balance Ledger ($\text{Opening} + \text{Receipts} - \text{Dispensed} = \text{Closing}$) (D89) with one-click statutory export for Assistant Drugs Controller (D90).

---

## 11. Roles & Access Control

### Selectable Role Presets
System supports Full (4-Role) and Simple (2-Role) presets (D91):
- **Full Preset (4-Role)**: Pharmacist (dispensing, H1/X registers, prescription capture, batch selection), Cashier (billing, checkout, presets, shifts; blocked from H1/X dispense without pharmacist sign-off (D93)), Manager (all cashier/pharmacist rights + return authorization, RTV debit notes, challans, `adjustment-in` PIN, shift force-close, local user account disable during outages, stock write-offs, master-data change requests, direct discount edits), Admin (all manager rights + direct master-data edit/create/delete, approving §12 requests, chain reporting, store setup, compliance mode) (D92).
- **Simple Preset (2-Role)**: High-Access (merges Pharmacist + Manager + Admin) and Low-Access (billing/shifts only = Cashier) (D94).
Action-by-role permission matrix deferred. `[DEFERRED → Doc 4: Comprehensive Role Permission Matrix (4-Role & 2-Role)]`

### Local User Revocation
Store Managers can locally disable compromised user accounts directly on Store FastAPI during network partitions, immediately invalidating local login without waiting for Central sync (D95).

---

## 12. Master-Data Change Request Flow (Full Preset Only)
Direct edit/create/delete authority restricted strictly to Admin via live connection (§4) (D96). Managers submit change requests for catalog, pricing, and tax (excluding discounts, which managers edit directly under §9) (D97). Change requests are scoped to single-field, single-record diffs (`field_name`, `current_value`, `expected_version`, `proposed_value`) (D98). Payload diff schema deferred. `[DEFERRED → Doc 2: Master-Data Change Request Payload Schema]`
Deletion requests reuse edit mechanism (`field_name: deleted_at`), gated by chain-wide zero-stock verification (D99). Request workflow states: `pending` $\rightarrow$ `approved` / `rejected` (`manual` | `stale` | `duplicate` | `stock-remaining`) (D100). Central auto-rejects stale edits on version mismatch and duplicate creates on unique business key collision (D101). Request state machine deferred. `[DEFERRED → Doc 5: Master-Data Change Request State Machine]`

---

## 13. Shift Management & Day-End Till Reconciliation (Z-Report)
Cashiers share counters across shifts; shift unlocks upon cashier login and opening float entry (`shift-open`) (D102). Operating period records Cash, Card, UPI, and Credit/Debit Note transactions.
At shift close, cashier enters blind physical cash declaration; system calculates Till Variance: $\text{Variance} = \text{Declared Physical Cash} - (\text{Opening Float} + \text{Cash Sales} - \text{Cash Refunds})$ (D103). Day-End Z-Report generated at closing summarizes gross/net sales, tax, tenders, returns, debit notes, and cashier variances (D104). Shift and Z-Report table schemas deferred. `[DEFERRED → Doc 1: Shift Session & Z-Report Table Schemas]`
Managers can force-close abandoned shifts with an audit note (`shift-force-close`) to unblock counters (D105). Shift state transitions deferred. `[DEFERRED → Doc 5: Shift Lifecycle & Till Reconciliation State Machine]`

---

## 14. Testing & Verification Suite
The system enforces an automated unit and integration testing suite covering legal hard-blocks, Legal Metrology fractional rounding math, barcode priority overrides, Schedule H1/X audit logging, LAN multi-counter concurrency, standby failover fencing, Central push atomicity, printer jam recovery, Rule 55 transport guards, and offline auth autonomy (D106). All 20 executable test case scenario implementations are deferred to the test specification to eliminate scenario tables from the architecture specification. `[DEFERRED → Doc 8: Automated Unit & Integration Test Suite Specifications (Tests 1–20)]`

---

## 15. Observability & Telemetry
Structured JSON logging with correlation IDs implemented across all store events, sync attempts, printer status checks, and manager overrides (D107). Log schema deferred. `[DEFERRED → Doc 9: Structured Log Schema & Audit Correlation ID Spec]`
Continuous telemetry tracks sync queue depth/lag, poison-pill rate, LAN latency, printer jams, and cashier till variances (D108). Automated alerts fire on sync offline $> 30$ minutes, poison-pill quarantines, till cash shortage $> \text{₹}500$, and disk storage $> 80\%$ (D109). Operational metrics and threshold configs deferred. `[DEFERRED → Doc 10: Operational Telemetry Metrics & Alerting Thresholds]`

---

## 16. Security & Data Protection
Local credentials stored using Argon2id password hashes with store-level salting (D110). Store Postgres binds strictly to `127.0.0.1` (§2). Store LAN protected via WPA3-Enterprise / Gigabit Ethernet; all terminal API calls pass store-scoped session JWTs (D111). Windows file permissions locked via `icacls` restricting database keys and configuration files strictly to `NT SERVICE\MedPOS` with zero read access for standard accounts (D112). Security hardening scripts deferred. `[DEFERRED → Doc 9: Edge Security Hardening, Windows File ACLs & Encryption Spec]`
DPDP Act 2023 compliance: Patient PII and prescription scans encrypted at rest using AES-256 (D113) with 90-day rolling edge retention (§10.3) (D114). Audit immutability: Dispense logs, invoices, credit/debit notes, challans, and stock adjustments enforce append-only storage via `REVOKE UPDATE, DELETE` (D115).

---

## 17. Deployment Safety & Edge Rollout
Staged deployment mandates a single canary store live for 7 days before chain-wide rollout (D116). Every database migration must include a backwards-compatible rollback script (D117). POS terminals configured with NSSM watchdog auto-recovery, disk write-cache protection, and UPS graceful shutdown (D118). Worker terminals discover Counter 1 via mDNS broadcast (`medpos-primary.local:8000`) (D119). Deployment checklists deferred. `[DEFERRED → Doc 10: Canary Rollout Protocol, Rollback Procedures & Edge Checklist]`

---

## 18. Open Items (Phase 2 Roadmap — V2 Chain Scale)
Enterprise capabilities deferred to Phase 2.0 with interim operational bridges (D120): (1) Automated Central Supplier Settlement (store-local GST Debit Notes §8); (2) Central In-Transit Virtual Pool (Rule 55 Challans §8); (3) B2B E-Invoicing (store-local B2B Invoices §8); (4) Automated Standby Clustering (LAN ping fencing & -F1 epoch §2); (5) Delta Replication Cursors (push atomicity & tombstones §5); (6) Cross-Store Voucher Double-Spend 2PL (issuing-store redemption only §8); (7) Hardware-Bound TPM 2.0 (Windows ACL lockdown §16); (8) Central Cloud K8s (Cloud VM §2); (9) Dynamic UPI Secondary Display (bill QR + audio §8); (10) Cashless Insurance/TPA (invoice tender metadata §9); (11) Prescription OCR AI (photo capture §10); (12) Automated WhatsApp/SMS (cashier wa.me link §8). Enterprise edge cases `[DEFERRED → Doc 6: V2 Enterprise Distributed Edge Cases & Scenarios]`; roadmap dependencies `[DEFERRED → Doc 7: V2 Enterprise Module Dependencies & Architectural Roadmap]`.

### Open Architecture Questions
1. **Q1: In-Line Adjustment Qty Scope**: When physical stock exists at POS but system displays 0, does `stock-adjustment-in` adjust immediate transaction qty or full shelf count? (Owner: Core POS Lead; Target: v1.6.6 Sprint 1)
2. **Q2: Shift Handover Float Policy**: In multi-shift counters, do cashiers swap cash drawer cassettes or perform in-place float count handoffs? (Owner: Retail Operations Lead; Target: v1.6.6 Sprint 1)
3. **Q3: Credit Note Validity & Partial Redemption**: Do `<STORE_CODE>-CN-...` credit balances expire after statutory periods and allow partial multi-visit redemption? (Owner: Finance & GST Lead; Target: v1.6.6 Sprint 2)

---

## 19. Deferred Items Register

### Doc 1: Data Schema Doc
1. `[DEFERRED → Doc 1: Central Sync & Quarantine Table Schemas]`
2. `[DEFERRED → Doc 1: Batch Table UOM Field Schema & Constraints]`
3. `[DEFERRED → Doc 1: Document Series Table Schemas & GST Line-Item Fields]`
4. `[DEFERRED → Doc 1: Discount Preset Table & TPA Metadata Schema]`
5. `[DEFERRED → Doc 1: Schedule H1 Register & Schedule X Ledger Table Schemas]`
6. `[DEFERRED → Doc 1: Shift Session & Z-Report Table Schemas]`

### Doc 2: Event Schema Doc
7. `[DEFERRED → Doc 2: Full Event Payload Schemas for Events 1–17 & Tombstones]`
8. `[DEFERRED → Doc 2: Dispense Event Schedule H1/X Audit Payload Schema]`
9. `[DEFERRED → Doc 2: Master-Data Change Request Payload Schema]`

### Doc 3: API Contract Doc
10. `[DEFERRED → Doc 3: Central Admin Web Portal Endpoints]`
11. `[DEFERRED → Doc 3: Central Ingestion Batch Endpoint Contract]`

### Doc 4: RBAC Permission Matrix
12. `[DEFERRED → Doc 4: Comprehensive Role Permission Matrix (4-Role & 2-Role)]`

### Doc 5: Critical Flow State Machines
13. `[DEFERRED → Doc 5: Standby Promotion Script & Fencing State Machine]`
14. `[DEFERRED → Doc 5: Outbound Sync Trigger & Retry Backoff State Machine]`
15. `[DEFERRED → Doc 5: Batch Picking, Fractional Return Inspection & RTV State Machines]`
16. `[DEFERRED → Doc 5: Low-Stock Alert State Lifecycle & Cooldown Flow]`
17. `[DEFERRED → Doc 5: Two-Phase Checkout Print Commit & Abandonment Void Workflow]`
18. `[DEFERRED → Doc 5: Live Discount Edit & Version Verification Flow]`
19. `[DEFERRED → Doc 5: Master-Data Change Request State Machine]`
20. `[DEFERRED → Doc 5: Shift Lifecycle & Till Reconciliation State Machine]`

### Doc 6: Conflict & Edge Case Matrix
21. `[DEFERRED → Doc 6: Master-Data Concurrency Conflict & Partition Scenarios]`
22. `[DEFERRED → Doc 6: Partition Ghost-Stock Ingestion & Auto-Resurrection Scenarios]`
23. `[DEFERRED → Doc 6: V2 Enterprise Distributed Edge Cases & Scenarios]`

### Doc 7: Dependency Map
24. `[DEFERRED → Doc 7: Core Module Dependency Graph & Build Order]`
25. `[DEFERRED → Doc 7: V2 Enterprise Module Dependencies & Architectural Roadmap]`

### Doc 8: Test Plan Doc
26. `[DEFERRED → Doc 8: Automated Unit & Integration Test Suite Specifications (Tests 1–20)]`

### Doc 9: Security & Audit Log Spec
27. `[DEFERRED → Doc 9: Local Auth JWT Claim Schema & Argon2id Hash Parameters]`
28. `[DEFERRED → Doc 9: Prescription Image AES-256 Storage & Retention Specification]`
29. `[DEFERRED → Doc 9: Structured Log Schema & Audit Correlation ID Spec]`
30. `[DEFERRED → Doc 9: Edge Security Hardening, Windows File ACLs & Encryption Spec]`

### Doc 10: Deployment & Rollout Plan
31. `[DEFERRED → Doc 10: Unattended Edge Backup, Pruning & Watchdog Service Spec]`
32. `[DEFERRED → Doc 10: Operational Telemetry Metrics & Alerting Thresholds]`
33. `[DEFERRED → Doc 10: Canary Rollout Protocol, Rollback Procedures & Edge Checklist]`

### Doc 11: Glossary
34. `[DEFERRED → Doc 11: Legal Metrology Rule 2011 & Schedule Compliance Glossary]`
35. `[DEFERRED → Doc 11: GST Statutory Invoicing, Credit/Debit Note & Challan Clauses]`
---
*Status: Active (v1.6.5). Supersedes architecture_v1_6.md and architecture_v1_5.md.*
