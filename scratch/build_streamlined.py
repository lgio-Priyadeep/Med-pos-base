import sys, re

# Build streamlined version of architecture doc

sections = []

# Title and Changelog
sec0 = """# Pharmacy POS — Architecture Spec (v1.6.5)

*Changelog:*
- v1.5: Zero-stock deletion invariant, offline write-offs, and immutable audit logs.
- v1.6: Expiry hard-block, H1 completeness, offline directories, outbound sync, and Z-reports.
- v1.6.5: UOM fractional dispensing, RTV debit notes, Rule 55 challans, and LAN topology."""
sections.append(sec0)

# Section 1: Scope
sec1 = """## 1. Scope
- Small chain footprint: 2–5 physical retail stores (D01).
- Deployment topology: Hybrid offline-first architecture with asynchronous background sync when online, excluding direct master-data writes (§4) (D02).
- In-store scaling: Multi-counter LAN topology comprising 1 Primary node and 1–3 Worker terminals (D03).
- Small single-store operators: Supported via a simplified 2-role preset (§11) (D04).
- Operational scope: Front-desk billing, fractional strip/tablet dispensing, sales returns/exchanges, vendor returns (RTV), branch delivery challans, batch inventory, shift till reconciliation, and regulatory registers (Schedule H1 and Schedule X) (D05)."""
sections.append(sec1)

# Section 2: Tech Stack & Edge Infrastructure
sec2 = """## 2. Tech Stack & Edge Infrastructure
- **Backend**: Standardized on Python and FastAPI across store-side and Central nodes (D06).
- **Central DB**: Postgres cloud instance for reporting and aggregation (D07).
- **Local DB**: Dedicated Postgres 16 instance installed on Store Primary Node (Counter 1) (D08).
- **Multi-Counter LAN Topology**:
  - *Counter 1 (Primary Node)*: Single sequence authority committing all transactions to Postgres bound strictly to loopback `127.0.0.1` (D09). Store FastAPI binds to `0.0.0.0:8000` on private Gigabit/WPA3 LAN (D10) and broadcasts via mDNS as `medpos-primary.local:8000` for DHCP IP churn immunity (D11).
  - *Counters 2/3 (Worker Terminals)*: Lightweight UI/Electron shells connecting to Counter 1 over LAN via HTTP REST and WebSockets with zero local databases (D12).
  - *Counter 2 Standby Role*: Warm standby receiving automated daily `pg_dump` backups and continuous WAL streaming from Counter 1 (D13).
  - *Standby Promotion Script (`promote_to_primary.bat`)*: Enforces LAN ping fencing against Counter 1 to prevent split-brain hazards before activating local services (D14). Failover state machine deferred. `[DEFERRED → Doc 5: Standby Promotion Script & Fencing State Machine]`
  - *Emergency Failover Epoch*: Promoted standby adopts emergency sequence epoch `<STORE_CODE>-INV-YYYYMM-XXXX-F1` and jumps sequence by +100,000 to eliminate invoice number collisions on hardware loss (§8) (D15).
- **Local Authentication**: Salted Argon2id password hashes and role mappings replicate from Central to store Postgres, issuing store-scoped JWTs (8–12h shift TTL) locally (D16) to ensure 100% terminal authentication autonomy during internet outages and reboots (D17). Token claims and Argon2id parameters deferred. `[DEFERRED → Doc 9: Local Auth JWT Claim Schema & Argon2id Hash Parameters]`
- **Unattended Maintenance & Recovery**: Daily automated `pg_dump` to secondary drive with rolling 7-day retention (D18), background `VACUUM ANALYZE` and WAL pruning prevent disk starvation (D19). NSSM OS watchdog auto-restarts services with crash-loop backoff (max 3 restarts per 10 min) (D20). Script configs deferred. `[DEFERRED → Doc 10: Unattended Edge Backup, Pruning & Watchdog Service Spec]`
- **Clock-Skew Defense**: Store Postgres enforces monotonic commit validation (`current_timestamp >= MAX(created_at)`), blocking transactions on dead CMOS battery resets (D21). Sync heartbeats check local time against Central, triggering a prominent UI warning if skew exceeds $\pm 5$ minutes (D22)."""
sections.append(sec2)

# Section 3: Core Modules
sec3 = """## 3. Core Modules
The system partitions into 13 discrete domain modules: Inventory & UOM Hierarchy, Customer Returns & Exchanges, Vendor Returns (RTV), Branch Stock Transfers, Prescription & Dispensing, Billing & Cashier Operations, Hardware & Peripherals, Multi-Store & Governance, Operational Directories, Sync Engine, User Roles, Settings & Config, and Reporting (D23). Module dependencies and build order deferred. `[DEFERRED → Doc 7: Core Module Dependency Graph & Build Order]`"""
sections.append(sec3)

# Section 4: System Architecture
sec4 = """## 4. System Architecture

### Local-First Store Node & Multi-Counter LAN
Store nodes operate 100% autonomously offline for billing, dispensing, returns, challans, stock movements, shift operations, and registration without Central connectivity (D24). Counter 1 commits all transactions to Postgres inside append-only event tables (§5) (D25); worker terminals bill against Counter 1 over LAN.

### Store-Initiated Outbound Sync Protocol
All sync traffic is strictly store-initiated outbound (HTTPS POST / WebSockets) to traverse ISP CGNAT and dynamic IPs without inbound open ports (D26). Sync pushes trigger on fixed intervals (30–60s with exponential backoff and jitter), on network reconnect, or manual trigger (D27). Central delivers catalog updates and governance decisions strictly as response payloads to outbound store requests (D28). Central Postgres is strictly an aggregation and reporting database, never authoritative for per-store inventory (D29). Retry backoff state machines deferred. `[DEFERRED → Doc 5: Outbound Sync Trigger & Retry Backoff State Machine]`

### Operational Directories vs Master Data
Central master data (catalog, prices, taxes, presets, distributors) is centrally governed and requires live connectivity for direct writes (D30). Patient and Prescribing Doctor records are decoupled store-local operational entities with permanent store-prefixed IDs (`<STORE_CODE>-PAT-<UUID>`, `<STORE_CODE>-DOC-<UUID>`), 100% offline-creatable and synced upward asynchronously (D31). Central performs logical deduplication purely in read-only audit views and never overwrites store entity IDs (D32).

### Exception — Concurrency Control for Direct Master-Data Changes
Direct master-data writes (edits, creations, soft-deletions) require live Central connectivity with optimistic version locking to prevent multi-store catalog divergence (D30). Governed records carry an integer `version` incremented on each Central write; edits reject on mismatch (`reason: stale`) (D33); creates reject on unique business key collision (`reason: duplicate`) (D34). Soft-deletion additionally requires aggregate chain-wide physical stock to be zero (§6) (D35). Central Admin accesses governance queues via a central Web portal with zero direct database connection into store LANs (D36). Portal API contracts deferred `[DEFERRED → Doc 3: Central Admin Web Portal Endpoints]`; edge partition concurrency conflict scenarios deferred `[DEFERRED → Doc 6: Master-Data Concurrency Conflict & Partition Scenarios]`."""
sections.append(sec4)

# Section 5: Data Flow / Event Model
sec5 = """## 5. Data Flow / Event Model

### Event Envelope Standard
Every state mutation commits as an immutable append-only event adhering to a standardized envelope: `event_id` (UUIDv4 PK), `store_seq_no` (monotonic BIGSERIAL), `store_id`, `created_at` (monotonic UTC), `event_type`, and `payload` (JSONB) (D37).

### Central Ingestion Atomicity & Poison-Pill Quarantine
Central ingests store event batches sequentially in a single atomic database transaction (`BEGIN...COMMIT`) with sequence watermarks to ensure all-or-nothing consistency (D38) and deduplication via `ON CONFLICT (event_id) DO NOTHING` (D39). Schema-violating poison-pill events isolate into `central_sync_quarantine` with `sync-quarantine-tombstone` records in `central_events` to preserve sequence continuity without blocking store retry queues (D40). Central acknowledgment returns committed watermarks and quarantined IDs to unblock store queues while flagging issues for audit (D41). Central sync and quarantine table schemas deferred `[DEFERRED → Doc 1: Central Sync & Quarantine Table Schemas]`; batch ingestion HTTP contracts deferred `[DEFERRED → Doc 3: Central Ingestion Batch Endpoint Contract]`.

### Event Types
The system defines 17 categorical domain event types: sales (`sale`, `b2b-sale`), returns (`sale-return`), dispensing (`dispense`), inventory movements (`stock-move` for transfers, RTV, write-offs, and adjustments), shift operations (`shift-open`, `shift-close`, `shift-force-close`), operational directories (`patient-created`, `doctor-created`), master data governance (`discount-edit`, `master-data-edit`, `master-data-created`, `master-data-change-requested`, `master-data-change-approved`, `master-data-change-rejected`), and system administration (`low-stock-alert`, `settings-change`) (D42). Includes `sync-quarantine-tombstone` for malformed payloads. Complete JSONB payload schemas deferred. `[DEFERRED → Doc 2: Full Event Payload Schemas for Events 1–17 & Tombstones]`"""
sections.append(sec5)

# Section 6: Stock, Inventory Lifecycle & Batch Mechanics
sec6 = """## 6. Stock, Inventory Lifecycle & Batch Mechanics

### Unit of Measure (UOM) Hierarchy & Fractional Billing
- **Integer Base-Unit Invariant**: Inventory is stored strictly in atomic integer Base Dispensing Units (`tablets`, `capsules`, `ml`, `vials`); decimals are prohibited in storage (D43).
- **Batch-Level Packaging Immutability**: `packaging_unit`, `base_unit`, and `pack_size` lock immutably on the Batch record at initial Goods Receipt Note (GRN) entry to prevent central catalog edits from distorting on-shelf stock counts (D44). Batch table column definitions and check constraints deferred. `[DEFERRED → Doc 1: Batch Table UOM Field Schema & Constraints]`
- **Dual-Representation Calculation**: Pack quantity and loose units derived via integer division and modulo: $	ext{Pack Qty} = 	ext{Base Qty} // 	ext{Pack Size}$, $	ext{Loose Qty} = 	ext{Base Qty} \pmod{	ext{Pack Size}}$ (D45).
- **Legal Metrology Pricing**: Base unit price computed using half-up rounding: $\operatorname{ROUND\_HALF\_UP}(	ext{Strip MRP} / 	ext{Pack Size}, 2)$ (D46). Statutory clauses deferred. `[DEFERRED → Doc 11: Legal Metrology Rule 2011 & Schedule Compliance Glossary]`
- **Statutory Price Clamping Invariant**: Loose Line Subtotal is strictly clamped to $\min(	ext{Loose Qty} 	imes 	ext{Unit Price}, 	ext{Strip MRP})$; buying a full pack size strictly bills Strip MRP, legally preventing fractional rounding accumulation overcharges (D47).
- **Barcode Scanning Context**: Scanning 1D/2D barcodes strictly bills 1 Packaging Unit ($1 	imes 	ext{pack\_size}$ base units); loose unit dispensing requires explicit input into a dedicated UI field (D48).
- **Fractional Return Restocking**: Cut blister strips with intact airtight foil cavities return to active stock ($+	ext{Loose Qty}$); punctured, cut, or torn foil cavities route to `quarantine-write-off` (D49).

### Near-Expiry Vendor Returns (RTV) & Alerts
Inventory monitors days to shelf expiry ($\Delta t = 	ext{expiry\_date} - 	ext{current\_date}$): 90 Days Amber (FEFO priority), 60 Days Orange (RTV recommendation), 30 Days Red (immediate physical shelf quarantine) (D50). Pharmacists execute `stock-move: rtv-quarantine`, moving stock to a return bin and generating an official GST Supplier Debit Note (§8) (D51).

### Inter-Store Stock Transfers & Statutory Delivery Challans
Physical branch road transit requires an official Delivery Challan under Rule 55 of CGST Rules 2017 (D52). Delivery Challans are restricted strictly to intra-state transfers within the same legal entity ($	ext{Source GSTIN} == 	ext{Dest GSTIN} \land 	ext{Source State} == 	ext{Dest State}$); inter-state movements mandate a full IGST Tax Invoice under Section 7(4) of the IGST Act (§8) (D53). Receiving stores log counts in `transfer-receive` splitting into `received_qty` (active), `transit_breakage_qty` (quarantine write-off with photo), and `transit_shortage_qty` (shrinkage audit) (D54). Dispatch decrements source stock; receive increments destination stock (D55). Transfer, inspection, and RTV state workflows deferred. `[DEFERRED → Doc 5: Batch Picking, Fractional Return Inspection & RTV State Machines]`

### Batch Picking & Stock Integrity
- **Batch Picking Mechanics**: Dispensing defaults to FEFO (earliest-expiring valid batch with stock $> 0$) (D56). Scanning a 2D GS1 DataMatrix strictly overrides FEFO suggestions to guarantee physical and invoiced batch parity (D57). POS automatically splits items into sub-lines across multiple batches when requested quantity exceeds primary batch stock (D58).
- **Non-Negative Stock Policy**: System stock must remain $\ge 0$ (D59). If physical stock exists on shelf but system stock displays 0, Manager PIN override triggers an immediate `stock-move: adjustment-in` at POS, logging to Central Shrinkage (D60).
- **Customer Sales Returns**: Returns validate against original invoice and batch ID; sealed undamaged items restock to active inventory (D61); batches expired since purchase and broken cold-chain items strictly route to `quarantine-write-off` (D62).
- **Soft-Delete Invariant & Partition Sales**: Products cannot be soft-deleted centrally while chain-wide stock $> 0$ (D35). Central accepts historical sales for soft-deleted items made offline (D63); if partition sales reveal remaining stock ($Stock_{	ext{initial}} - Qty_{	ext{sold}} > 0$), Central automatically clears soft-deletion (`deleted_at = null`) (D64). Partition ghost-stock scenarios deferred. `[DEFERRED → Doc 6: Partition Ghost-Stock Ingestion & Auto-Resurrection Scenarios]`"""
sections.append(sec6)

# Section 7: Low Stock Alerts
sec7 = """## 7. Low Stock Alerts
Configured per item, per store in integer base dispensing units (D65). Triggers discrete `low-stock-alert` event when local stock drops to or below threshold, suppressed until inventory is replenished above threshold (D66). Closes automatically upon deliberate stock write-offs that zero inventory without reorder intent (D67). State lifecycle transitions deferred. `[DEFERRED → Doc 5: Low-Stock Alert State Lifecycle & Cooldown Flow]`"""
sections.append(sec7)

# Section 8: Invoicing (GST), Credit Notes, Debit Notes & Delivery Challans
sec8 = """## 8. Invoicing (GST), Credit Notes, Debit Notes & Delivery Challans

### Numbering Series Orthogonality
All document series are computed store-locally, gapless, and mutually orthogonal across 6 discrete series (D68): Retail B2C Invoices (`<STORE_CODE>-INV-YYYYMM-XXXX`), Emergency Failover B2C Invoices (`<STORE_CODE>-INV-YYYYMM-XXXX-F1`), Registered B2B Invoices (`<STORE_CODE>-B2B-YYYYMM-XXXX`), Sales Return Credit Notes (`<STORE_CODE>-CN-YYYYMM-XXXX`), Supplier Return Debit Notes (`<STORE_CODE>-DN-YYYYMM-XXXX`), and Rule 55 Delivery Challans (`<STORE_CODE>-DC-YYYYMM-XXXX`). Document series tables and line-item schemas deferred. `[DEFERRED → Doc 1: Document Series Table Schemas & GST Line-Item Fields]`

### Invoicing Specifications
- **B2C Retail Checkout**: Conforms to CGST Section 31 with GSTIN, HSN, batch, expiry, CGST/SGST breakdown, dynamic NPCI UPI QR string (`upi://pay?...`), and countertop audio soundbox confirmation (D69). Cashiers have an optional one-click WhatsApp Web share link (`wa.me`) with pre-formatted invoice text (D70).
- **Two-Phase Print Commit & Jam Resilience**: Checkout commits locally as `COMMITTED_PENDING_PRINT` before testing printer status (D121) (300ms ESC/POS check with OS spooler fallback) (D122). Cash drawer kick synchronizes with print spooling (D123). Printer jams trigger a UI error banner with one-click reprint generating audited watermark `*** DUPLICATE COPY ***` (D124). If customer leaves during a jam, cashier triggers an automated void issuing an offsetting GST Credit Note (`<STORE_CODE>-CN-...`), restoring stock and preserving gapless numbering (D125). Print commit and void state machines deferred. `[DEFERRED → Doc 5: Two-Phase Checkout Print Commit & Abandonment Void Workflow]`
- **B2B Invoices & Credit/Debit Notes**: B2B invoices capture buyer 15-digit GSTIN, legal name, and HSN summary under Rule 46(b) for manual monthly GSTR-1 filing (D71). Credit Notes conform to Section 34 CGST Act, reversing tax liability (D72); store credit balances are strictly non-transferable across branches and redeemable solely at issuing store node (D73). Debit Notes conform to Section 34(3) for vendor returns (D74). Delivery Challans accompany intra-state transport with vehicle number and statutory non-sale clause under Rule 55 (D75). Statutory clauses deferred. `[DEFERRED → Doc 11: GST Statutory Invoicing, Credit/Debit Note & Challan Clauses]`"""
sections.append(sec8)

# Section 9: Discounts
sec9 = """## 9. Discounts
Centrally governed discount presets reside on item or category records (D76). Cashiers are restricted to selecting pre-configured presets; manual discount overrides are prohibited (D77). Managers (Full preset) or High-access users (Simple preset) edit discount presets directly via live Central connection with optimistic version locking (§4) (D78). Edits log immutably as `discount-edit` events (D79). Live discount edit flows deferred. `[DEFERRED → Doc 5: Live Discount Edit & Version Verification Flow]`
Manual Insurance / TPA tender metadata fields (Insurer Name, Policy Number, Pre-Authorization Approval Code) captured at checkout as text metadata on standard GST invoices (D80). Discount preset and TPA table schemas deferred. `[DEFERRED → Doc 1: Discount Preset Table & TPA Metadata Schema]`"""
sections.append(sec9)

# Section 10: Regulatory Compliance
sec10 = """## 10. Regulatory Compliance (India, Drugs & Cosmetics Act)

### 10.1 Absolute Expiry Hard-Block
Under Section 18(a)(i) and Section 27 of the Drugs & Cosmetics Act 1940, stocking, selling, or dispensing expired drugs is a strict liability criminal offense. Batches with $	ext{expiry\_date} \le 	ext{current\_date}$ are unconditionally blocked from billing and dispensing across both `Mandatory` and `Optional` compliance modes (D81). Zero bypass allowance for cashiers, pharmacists, or managers (D82). Optional mode only relaxes non-statutory metadata.

### 10.2 Schedule H1 Register Completeness
Rule 65(9) mandates an immutable 3-year register capturing 7 mandatory parameters: supply date/time, patient name/address, doctor name/address/registration, drug brand/generic, batch/manufacturer, quantity/pack size, and dispensing pharmacist PIN (D83). Supports one-click Drug Inspector audit export (CSV and PDF) (D84). Immutability enforced in Postgres via `REVOKE UPDATE, DELETE ON dispense_events` (§16) (D85). Database tables deferred `[DEFERRED → Doc 1: Schedule H1 Register & Schedule X Ledger Table Schemas]`; dispense audit payloads deferred `[DEFERRED → Doc 2: Dispense Event Schedule H1/X Audit Payload Schema]`.

### 10.3 Schedule X & NDPS Dual-Prescription Custody & Bound Ledger
Rule 65(4) mandates digital physical scan or webcam photo capture of duplicate prescriptions (D86). Images compressed locally to 150–200 DPI WebP (<250 KB), AES-256 encrypted, held under 90-day rolling edge retention with 2-year Central cloud archival (D87). Image encryption specs deferred. `[DEFERRED → Doc 9: Prescription Image AES-256 Storage & Retention Specification]` Dispensing binds registered Pharmacist PIN and State Pharmacy Council credentials (D88). Enforces automated immutable Daily Running Balance Ledger ($	ext{Opening} + 	ext{Receipts} - 	ext{Dispensed} = 	ext{Closing}$) (D89) and one-click statutory export for Assistant Drugs Controller (D90)."""
sections.append(sec10)

# Section 11: Roles & Access Control
sec11 = """## 11. Roles & Access Control

### Selectable Role Presets
System supports Full (4-Role) and Simple (2-Role) presets (D91):
- **Full Preset (4-Role)**: Pharmacist (dispensing, H1/X registers, prescription capture, batch selection), Cashier (billing, checkout, presets, shifts; blocked from H1/X dispense without pharmacist sign-off (D93)), Manager (all cashier/pharmacist rights + return authorization, RTV debit notes, challans, `adjustment-in` PIN, shift force-close, local user account disable during outages, stock write-offs, master-data change requests, direct discount edits), Admin (all manager rights + direct master-data edit/create/delete, approving §12 requests, chain reporting, store setup, compliance mode) (D92).
- **Simple Preset (2-Role)**: High-Access (merges Pharmacist + Manager + Admin) and Low-Access (billing/shifts only = Cashier) (D94).
Action-by-role permission matrix deferred. `[DEFERRED → Doc 4: Comprehensive Role Permission Matrix (4-Role & 2-Role)]`

### Local User Revocation
Store Managers can locally disable compromised user accounts directly on Store FastAPI during network partitions, immediately invalidating local login without waiting for Central sync (D95)."""
sections.append(sec11)

# Section 12: Master-Data Change Request Flow
sec12 = """## 12. Master-Data Change Request Flow (Full Preset Only)
Direct edit/create/delete authority restricted strictly to Admin via live connection (§4) (D96). Managers submit change requests for catalog, pricing, and tax (excluding discounts, which managers edit directly under §9) (D97). Change requests are scoped to single-field, single-record diffs (`field_name`, `current_value`, `expected_version`, `proposed_value`) (D98). Request payload diff schema deferred. `[DEFERRED → Doc 2: Master-Data Change Request Payload Schema]`
Deletion requests reuse edit mechanism (`field_name: deleted_at`), gated by chain-wide zero-stock verification (D99). Request workflow states: `pending` $	ext{	o}$ `approved` / `rejected` (`manual` | `stale` | `duplicate` | `stock-remaining`) (D100). Central auto-rejects stale edits on version mismatch and duplicate creates on unique business key collision (D101). Request state machine deferred. `[DEFERRED → Doc 5: Master-Data Change Request State Machine]`"""
sections.append(sec12)

# Section 13: Shift Management & Till Reconciliation
sec13 = """## 13. Shift Management & Day-End Till Reconciliation (Z-Report)
Cashiers share counters across shifts; shift unlocks upon cashier login and opening float entry (`shift-open`) (D102). Operating period records Cash, Card, UPI, and Credit/Debit Note transactions.
At shift close, cashier enters blind physical cash declaration; system calculates Till Variance: $	ext{Variance} = 	ext{Declared Physical Cash} - (	ext{Opening Float} + 	ext{Cash Sales} - 	ext{Cash Refunds})$ (D103). Day-End Z-Report generated at closing summarizes gross/net sales, tax, tenders, returns, debit notes, and cashier variances (D104). Shift and Z-Report table schemas deferred. `[DEFERRED → Doc 1: Shift Session & Z-Report Table Schemas]`
Managers can force-close abandoned shifts with an audit note (`shift-force-close`) to unblock counters (D105). Shift state transitions deferred. `[DEFERRED → Doc 5: Shift Lifecycle & Till Reconciliation State Machine]`"""
sections.append(sec13)

# Section 14: Testing & Verification Suite
sec14 = """## 14. Testing & Verification Suite
The system enforces an automated unit and integration testing suite covering legal hard-blocks, Legal Metrology fractional rounding math, barcode priority overrides, Schedule H1/X audit logging, LAN multi-counter concurrency, standby failover fencing, Central push atomicity, printer jam recovery, Rule 55 transport guards, and offline auth autonomy (D106). All 20 executable test case scenario implementations are deferred to the test specification to eliminate scenario tables from the architecture specification. `[DEFERRED → Doc 8: Automated Unit & Integration Test Suite Specifications (Tests 1–20)]`"""
sections.append(sec14)

# Section 15: Observability & Telemetry
sec15 = """## 15. Observability & Telemetry
Structured JSON logging with correlation IDs implemented across all store events, sync attempts, printer status checks, and manager overrides (D107). Log schema deferred. `[DEFERRED → Doc 9: Structured Log Schema & Audit Correlation ID Spec]`
Continuous telemetry tracks sync queue depth/lag, poison-pill rate, LAN latency, printer jams, and cashier till variances (D108). Automated alerts fire on sync offline $> 30$ minutes, poison-pill quarantines, till cash shortage $> 	ext{₹}500$, and disk storage $> 80\%$ (D109). Operational metrics and threshold configs deferred. `[DEFERRED → Doc 10: Operational Telemetry Metrics & Alerting Thresholds]`"""
sections.append(sec15)

# Section 16: Security & Data Protection
sec16 = """## 16. Security & Data Protection
Local credentials stored using Argon2id password hashes with store-level salting (D110). Store Postgres binds strictly to `127.0.0.1` (§2). Store LAN protected via WPA3-Enterprise / Gigabit Ethernet; all terminal API calls pass store-scoped session JWTs (D111). Windows file permissions locked via `icacls` restricting database keys and configuration files strictly to `NT SERVICE\MedPOS` with zero read access for standard accounts (D112). Security hardening scripts deferred. `[DEFERRED → Doc 9: Edge Security Hardening, Windows File ACLs & Encryption Spec]`
DPDP Act 2023 compliance: Patient PII and prescription scans encrypted at rest using AES-256 (D113) with 90-day rolling edge retention (§10.3) (D114). Audit immutability: Dispense logs, invoices, credit/debit notes, challans, and stock adjustments enforce append-only storage via `REVOKE UPDATE, DELETE` (D115)."""
sections.append(sec16)

# Section 17: Deployment Safety & Edge Rollout
sec17 = """## 17. Deployment Safety & Edge Rollout
Staged deployment mandates a single canary store live for 7 days before chain-wide rollout (D116). Every database migration must include a backwards-compatible rollback script (D117). POS terminals configured with NSSM watchdog auto-recovery, disk write-cache protection, and UPS graceful shutdown (D118). Worker terminals discover Counter 1 via mDNS broadcast (`medpos-primary.local:8000`) (D119). Deployment checklists deferred. `[DEFERRED → Doc 10: Canary Rollout Protocol, Rollback Procedures & Edge Checklist]`"""
sections.append(sec17)

# Section 18: Open Items
sec18 = """## 18. Open Items (Phase 2 Roadmap — V2 Chain Scale)
The following 12 enterprise capabilities are formally deferred to Phase 2.0 with interim operational bridges established:
1. Automated Central Supplier Settlement (interim: store-local GST Debit Notes §8).
2. Central In-Transit Virtual Pool (interim: Rule 55 Challans & receipt discrepancy logging §8).
3. B2B E-Invoicing via Govt IRP (interim: store-local B2B Invoices `<STORE_CODE>-B2B-...` for manual GSTR-1 §8).
4. Automated Standby Clustering (interim: scripted failover with LAN fencing & `-F1` epoch §2).
5. Delta Replication Cursors (interim: push atomicity with poison-pill quarantine tombstones §5).
6. Cross-Store Voucher Double-Spend 2PL (interim: credit notes non-transferable, redeemable only at issuing store §8).
7. Hardware-Bound TPM 2.0 Key Sealing (interim: Windows File ACL `icacls` lockdown §16).
8. Central Cloud Multi-Tenant Kubernetes (interim: single Cloud VM with nightly backups §2).
9. Customer Dynamic UPI Secondary LCD Pole Display (interim: dynamic UPI QR on bill + audio soundbox §8).
10. Cashless Insurance / TPA Direct Processing (interim: manual tender metadata fields on invoices §9).
11. Prescription OCR AI Parsing (interim: digital webcam/scanner photo capture attached to dispense records §10).
12. Automated WhatsApp / SMS Gateway (interim: cashier one-click `wa.me` web link §8) (D120).
Enterprise distributed edge cases `[DEFERRED → Doc 6: V2 Enterprise Distributed Edge Cases & Scenarios]`; enterprise roadmap dependencies `[DEFERRED → Doc 7: V2 Enterprise Module Dependencies & Architectural Roadmap]`.

### Open Architecture Questions
1. **Q1: In-Line Adjustment Qty Scope**: When physical stock exists at POS but system stock displays 0, does `stock-adjustment-in` adjust only the quantity required for the immediate transaction or the full physical shelf count?
   - *Owner*: Core POS Lead
   - *Target*: v1.6.6 Sprint 1
2. **Q2: Shift Handover Float Policy**: In multi-shift counters, do cashiers swap physical cash drawer cassettes or perform an in-place handoff and count of shared float?
   - *Owner*: Retail Operations Lead
   - *Target*: v1.6.6 Sprint 1
3. **Q3: Credit Note Validity & Partial Redemption**: Do `<STORE_CODE>-CN-...` credit balances expire after a statutory period (e.g. 180 days) and can they be partially redeemed across multiple retail visits?
   - *Owner*: Finance & GST Lead
   - *Target*: v1.6.6 Sprint 2"""
sections.append(sec18)

# Section 19: Deferred Items Register (Concise 1 line per marker <= 15 words)
sec19 = """## 19. Deferred Items Register

### Doc 1: Data Schema Doc
1. `[DEFERRED → Doc 1: Central Sync & Quarantine Table Schemas]` — DDL for central_events, sync watermarks, and quarantine tables.
2. `[DEFERRED → Doc 1: Batch Table UOM Field Schema & Constraints]` — Column schemas and check constraints for packaging units and pack size.
3. `[DEFERRED → Doc 1: Document Series Table Schemas & GST Line-Item Fields]` — DDL for document counters, invoice tables, and GST line-item tax calculations.
4. `[DEFERRED → Doc 1: Discount Preset Table & TPA Metadata Schema]` — Schemas for discount preset configuration and invoice Insurance/TPA metadata.
5. `[DEFERRED → Doc 1: Schedule H1 Register & Schedule X Ledger Table Schemas]` — Tables for 3-year H1 audit logs and Schedule X daily running balance ledgers.
6. `[DEFERRED → Doc 1: Shift Session & Z-Report Table Schemas]` — Schemas for cashier shifts, blind declarations, till variances, and Z-Reports.

### Doc 2: Event Schema Doc
7. `[DEFERRED → Doc 2: Full Event Payload Schemas for Events 1–17 & Tombstones]` — JSONB payload schemas for all 17 domain event types and quarantine tombstones.
8. `[DEFERRED → Doc 2: Dispense Event Schedule H1/X Audit Payload Schema]` — Detailed payload schemas capturing statutory H1 parameters and Schedule X prescription hashes.
9. `[DEFERRED → Doc 2: Master-Data Change Request Payload Schema]` — JSON schema for single-field, single-record change request diff payloads.

### Doc 3: API Contract Doc
10. `[DEFERRED → Doc 3: Central Admin Web Portal Endpoints]` — REST contracts for Central governance dashboard, review queues, and shrinkage reports.
11. `[DEFERRED → Doc 3: Central Ingestion Batch Endpoint Contract]` — Request/response contract and error codes for POST /api/v1/sync/events/batch.

### Doc 4: RBAC Permission Matrix
12. `[DEFERRED → Doc 4: Comprehensive Role Permission Matrix (4-Role & 2-Role)]` — Complete action-by-role permission grid mapping Pharmacist, Cashier, Manager, Admin, High/Low-Access.

### Doc 5: Critical Flow State Machines
13. `[DEFERRED → Doc 5: Standby Promotion Script & Fencing State Machine]` — Failover state machine, ping fencing check, and emergency -F1 epoch jump.
14. `[DEFERRED → Doc 5: Outbound Sync Trigger & Retry Backoff State Machine]` — Sync trigger state machine with exponential backoff and jitter retry loops.
15. `[DEFERRED → Doc 5: Batch Picking, Fractional Return Inspection & RTV State Machines]` — State workflows for 2D barcode override, blister return inspection, and RTV tiers.
16. `[DEFERRED → Doc 5: Low-Stock Alert State Lifecycle & Cooldown Flow]` — State transitions for alert triggering, replenishment cooldown, and write-off suppression.
17. `[DEFERRED → Doc 5: Two-Phase Checkout Print Commit & Abandonment Void Workflow]` — Two-phase print commit, spooler fallback, duplicate watermark, and walkaway void flow.
18. `[DEFERRED → Doc 5: Live Discount Edit & Version Verification Flow]` — State machine for live Central discount editing, version verification, and conflict rejection.
19. `[DEFERRED → Doc 5: Master-Data Change Request State Machine]` — Lifecycle transitions and automated Central rejection rules for change requests.
20. `[DEFERRED → Doc 5: Shift Lifecycle & Till Reconciliation State Machine]` — Step-by-step cashier shift transitions, blind cash declaration, and manager force-close.

### Doc 6: Conflict & Edge Case Matrix
21. `[DEFERRED → Doc 6: Master-Data Concurrency Conflict & Partition Scenarios]` — Matrix resolving simultaneous store/central edits, optimistic version mismatch, and duplicate keys.
22. `[DEFERRED → Doc 6: Partition Ghost-Stock Ingestion & Auto-Resurrection Scenarios]` — Protocol for ingesting partition sales of soft-deleted items and automated un-deletion.
23. `[DEFERRED → Doc 6: V2 Enterprise Distributed Edge Cases & Scenarios]` — Enterprise edge cases for multi-store voucher redemptions and virtual in-transit pools.

### Doc 7: Dependency Map
24. `[DEFERRED → Doc 7: Core Module Dependency Graph & Build Order]` — Module-to-module dependency hierarchy and implementation sequence across 13 core modules.
25. `[DEFERRED → Doc 7: V2 Enterprise Module Dependencies & Architectural Roadmap]` — Enterprise capability dependency tree and Phase 2.0 scaling roadmap.

### Doc 8: Test Plan Doc
26. `[DEFERRED → Doc 8: Automated Unit & Integration Test Suite Specifications (Tests 1–20)]` — Verbatim test specifications, assertions, and mock scenarios for all 20 automated tests.

### Doc 9: Security & Audit Log Spec
27. `[DEFERRED → Doc 9: Local Auth JWT Claim Schema & Argon2id Hash Parameters]` — Argon2id cryptographic parameters and store-scoped JWT claim payload structures.
28. `[DEFERRED → Doc 9: Prescription Image AES-256 Storage & Retention Specification]` — WebP compression, local AES-256 encryption, and 90-day pruning automation specification.
29. `[DEFERRED → Doc 9: Structured Log Schema & Audit Correlation ID Spec]` — Standardized JSON log schema, correlation IDs, and transaction tracing specifications.
30. `[DEFERRED → Doc 9: Edge Security Hardening, Windows File ACLs & Encryption Spec]` — Windows icacls lockdown configurations and DPDP Act 2023 AES-256 encryption specs.

### Doc 10: Deployment & Rollout Plan
31. `[DEFERRED → Doc 10: Unattended Edge Backup, Pruning & Watchdog Service Spec]` — Nightly automated pg_dump schedules, 7-day rolling archive pruning, and NSSM configs.
32. `[DEFERRED → Doc 10: Operational Telemetry Metrics & Alerting Thresholds]` — Metric definitions, monitoring queries, and alerting thresholds for sync lag and shortages.
33. `[DEFERRED → Doc 10: Canary Rollout Protocol, Rollback Procedures & Edge Checklist]` — 7-day single canary store protocol, migration rollback procedures, and edge checklists.

### Doc 11: Glossary
34. `[DEFERRED → Doc 11: Legal Metrology Rule 2011 & Schedule Compliance Glossary]` — Statutory definitions for Legal Metrology Packaged Commodities Rule 2011, Schedule H1, and Schedule X.
35. `[DEFERRED → Doc 11: GST Statutory Invoicing, Credit/Debit Note & Challan Clauses]` — Statutory definitions and clauses under CGST Section 31, Section 34, Rule 46(b), and Rule 55."""
sections.append(sec19)

footer = """
---
*Status: Active (v1.6.5). Supersedes architecture_v1_6.md and architecture_v1_5.md.*
"""

full_content = "\n\n---\n\n".join(sections) + footer

with open("scratch/streamlined_draft.md", "w", encoding="utf-8") as f:
    f.write(full_content)

words = len(full_content.split())
print(f"STREAMLINED DRAFT WORD COUNT: {words}")
