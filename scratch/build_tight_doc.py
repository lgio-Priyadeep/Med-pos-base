import sys, re

header = """# Pharmacy POS — Architecture Spec (v1.6.5)

*Changelog:*
- v1.5: Zero-stock deletion invariant, offline write-offs, and immutable audit logs.
- v1.6: Expiry hard-block, H1 completeness, offline directories, outbound sync, and Z-reports.
- v1.6.5: UOM fractional dispensing, RTV debit notes, Rule 55 challans, and LAN topology."""

sec1 = """## 1. Scope
- Chain footprint: 2–5 physical retail stores (D-01).
- Hybrid deployment: Offline-first with async background sync; direct master-data writes excluded (§4) (D-02).
- Counter scaling: Multi-counter LAN topology (1 Primary node + 1–3 Worker terminals) (D-03).
- Single-store operators: Supported via Simple 2-role preset (§11) (D-04).
- Operational scope: Billing, fractional dispensing, returns/exchanges, vendor returns (RTV), delivery challans, batch inventory, shift till reconciliation, and regulatory registers (Schedule H1 and Schedule X) (D-05).

### Non-Goals
Direct store-to-cloud master writes, cross-store voucher redemption, live B2B IRN e-invoicing, distributed multi-master consensus, automated supplier EDI, and optical prescription OCR are explicit non-goals for v1.6.5 (deferred to Phase 2.0, §18)."""

sec2 = """## 2. Tech Stack & Edge Infrastructure
- **Backend & DB**: Python/FastAPI across store and Central nodes (D-06). Central DB runs cloud Postgres (D-07); Counter 1 (Primary) runs local Postgres 16 (D-08).
- **Multi-Counter LAN**:
  - *Counter 1 (Primary)*: Single sequence authority committing to Postgres on `127.0.0.1` (D-09). Store FastAPI binds `0.0.0.0:8000` via store-scoped self-signed TLS (HTTPS) (D-10), broadcasting via mDNS as `medpos-primary.local:8000` with pinned certificate fingerprint validation on worker terminals (D-11). The store certificate (10-year validity) replicates to Counter 2 standby during setup, eliminating promotion mismatch.
  - *Counters 2/3 (Workers)*: UI shells connecting to Counter 1 over LAN via REST/WebSockets with zero local databases (D-12).
  - *Standby & Failover*: Counter 2 warm standby receives daily backups and WAL streaming from Counter 1 (D-13). Promotion script (`promote_to_primary.bat`) fences Counter 1 via LAN ping to prevent split-brain (D-14). `[DEFERRED → Doc 5: Standby Promotion Script & Fencing State Machine]` Promoted standby adopts epoch `<STORE_CODE>-INV-YYYYMM-XXXX-F1` jumping sequence +100,000 to eliminate invoice collisions on hardware loss (§8) (D-15).
- **Local Auth**: Replicated Argon2id hashes issue store-scoped JWTs (8–12h shift TTL) locally (D-16) for 100% auth autonomy during outages and reboots (D-17). `[DEFERRED → Doc 9: Local Auth JWT Claim Schema & Argon2id Hash Parameters]`
- **Maintenance**: Daily `pg_dump` with 7-day rolling retention (D-18); background `VACUUM ANALYZE` and WAL pruning prevent disk exhaustion (D-19). NSSM watchdog auto-restarts crashed services (max 3 restarts / 10 min) (D-20). `[DEFERRED → Doc 10: Unattended Edge Backup, Pruning & Watchdog Service Spec]`
- **Clock-Skew Defense**: Monotonic commit check (`current_timestamp >= MAX(created_at)`) blocks dead CMOS resets (D-21). Skew $> \\pm 5$ min triggers UI warning during sync heartbeat (D-22)."""

sec3 = """## 3. Core Modules
Partitioned into 13 discrete domain modules: M-01 (Inventory & UOM Hierarchy), M-02 (Customer Returns & Exchanges), M-03 (Vendor Returns / RTV), M-04 (Branch Stock Transfers), M-05 (Prescription & Dispensing), M-06 (Billing & Cashier Operations), M-07 (Hardware & Peripherals), M-08 (Multi-Store Master Data), M-09 (Operational Directories), M-10 (Sync Engine), M-11 (User Roles & Auth), M-12 (Settings & Config), and M-13 (Reporting & Till Reconciliation) (D-23). `[DEFERRED → Doc 7: Core Module Dependency Graph & Build Order]`"""

sec4 = """## 4. System Architecture

### Local-First Store Node & Multi-Counter LAN
Store nodes operate autonomously offline for billing, dispensing, returns, challans, stock moves, shifts, and local registration without Central connectivity (D-24). Counter 1 commits transactions to local append-only event tables (§5) (D-25); worker terminals bill against Counter 1 over LAN.

### Store-Initiated Outbound Sync Protocol
Sync traffic is strictly store-initiated outbound (HTTPS/WebSockets) traversing CGNAT and dynamic IPs without open inbound ports (D-26). Pushes trigger at 30–60s intervals (with backoff/jitter), on reconnect, or manually (D-27). Central delivers catalog updates and governance decisions strictly in response payloads (D-28). Central Postgres is an aggregation/reporting DB, never authoritative for store inventory (D-29). `[DEFERRED → Doc 5: Outbound Sync Trigger & Retry Backoff State Machine]`

### Operational Directories vs Master Data
Central master data (catalog, prices, taxes, presets, distributors) is centrally governed, requiring live connectivity for direct writes (D-30). Patient and Doctor records are decoupled store-local entities with permanent store-prefixed IDs (`<STORE_CODE>-PAT-<UUID>`, `<STORE_CODE>-DOC-<UUID>`), 100% offline-creatable and synced asynchronously (D-31). Central deduplicates in read-only audit views without mutating store IDs (D-32).

### Exception — Concurrency Control for Direct Master-Data Changes
Direct master-data writes require live Central connectivity with optimistic version locking to prevent multi-store divergence (per D-30). Records carry integer `version` incremented per Central write; edits reject on mismatch (`reason: stale`) (D-33); creates reject on business key collision (`reason: duplicate`) (D-34). Soft-deletion requires aggregate chain-wide physical stock to be zero (see D-35 in §6). Central Admin uses a Web portal with zero direct DB connection into store LANs (D-36). `[DEFERRED → Doc 3: Central Admin Web Portal Endpoints]` `[DEFERRED → Doc 6: Master-Data Concurrency Conflict & Partition Scenarios]`"""

sec5 = """## 5. Data Flow / Event Model

### Event Envelope Standard
Every mutation commits as an immutable append-only event: `event_id` (UUIDv4 PK), `store_seq_no` (monotonic BIGSERIAL), `store_id`, `created_at` (monotonic UTC), `event_type`, and `payload` (JSONB) (D-37).

### Central Ingestion Atomicity & Poison-Pill Quarantine
Central ingests store event batches sequentially in a single atomic transaction (`BEGIN...COMMIT`) with sequence watermarks ensuring consistency (D-38) and idempotency via `ON CONFLICT (event_id) DO NOTHING` (D-39). Poison-pill malformed events isolate into `central_sync_quarantine` with `sync-quarantine-tombstone` records in `central_events` preserving sequence continuity without blocking store retry queues (D-40). Central acknowledgment returns committed watermarks and quarantined IDs to unblock store queues while flagging audit issues (D-41). `[DEFERRED → Doc 1: Central Sync & Quarantine Table Schemas]` `[DEFERRED → Doc 3: Central Ingestion Batch Endpoint Contract]`

### Event Types
The system defines 19 domain event types: inbound inventory (`grn`), sales & credit (`sale`, `b2b-sale`, `credit-note-redemption`), returns (`sale-return`), dispensing (`dispense`), stock movements (`stock-move`), shift operations (`shift-open`, `shift-close`, `shift-force-close`), operational directories (`patient-created`, `doctor-created`), master data (`discount-edit`, `master-data-edit`, `master-data-created`, `master-data-change-requested`, `master-data-change-approved`, `master-data-change-rejected`), and administration (`low-stock-alert`, `settings-change`) (D-42). Store event processing enforces `ON CONFLICT (event_id) DO NOTHING` on local `grn` execution to prevent double-stock inflation during crash recovery. Includes `sync-quarantine-tombstone` for malformed payloads. `[DEFERRED → Doc 2: Full Event Payload Schemas for Events 1–19 & Tombstones]`"""

sec6 = """## 6. Stock, Inventory Lifecycle & Batch Mechanics

### Unit of Measure (UOM) Hierarchy & Fractional Billing
- **Integer Base Units**: Stock is stored exclusively in integer Base Dispensing Units (`tablets`, `capsules`, `ml`, `vials`); decimals prohibited (D-43).
- **Packaging Immutability**: `packaging_unit`, `base_unit`, and `pack_size` lock immutably at GRN, isolating stock counts from catalog edits (D-44). `[DEFERRED → Doc 1: Batch Table UOM Field Schema & Constraints]`
- **Dual Representation**: Pack Qty is integer division ($\\\\text{Base} // \\\\text{Pack Size}$); loose units are modulo ($\\\\text{Base} \\\\pmod{\\\\text{Pack Size}}$) (D-45).
- **Pricing & Clamping**: Loose unit price is rounded half-up ($\\\\operatorname{ROUND\\\\_HALF\\\\_UP}(\\\\text{Strip MRP} / \\\\text{Pack Size}, 2)$) (D-46). Subtotal clamps to $\\\\min(\\\\text{Loose Qty} \\\\times \\\\text{Unit Price}, \\\\text{Strip MRP})$ (D-47). `[DEFERRED → Doc 11: Legal Metrology Rule 2011 & Schedule Compliance Glossary]`
- **Barcode & Returns**: Barcode scans bill 1 Packaging Unit (D-48). Sealed blister cavities restock ($+\\\\text{Loose Qty}$); damaged cavities route to `quarantine-write-off` (D-49).

### Near-Expiry Vendor Returns (RTV) & Transfers
- **RTV Alerts**: Expiry tiers: 90d Amber (FEFO), 60d Orange (RTV packing), 30d Red (quarantine) (D-50). Pharmacists execute `stock-move: rtv-quarantine`, generating sequential GST Debit Notes (§8) (D-51).
- **Transfers & Challans**: Intra-state branch moves require Rule 55 Delivery Challans (D-52); inter-state requires IGST Tax Invoices (§8) (D-53). Store `transfer-receive` splits intact (`received_qty`), breakage (quarantine write-off with photo) (D-54), and shortage (shrinkage audit). Dispatch decrements source; receive increments destination (D-55). `[DEFERRED → Doc 5: Batch Picking, Fractional Return Inspection & RTV State Machines]`

### Batch Picking & Stock Integrity
- **Picking**: Defaults to FEFO (earliest expiry, stock $> 0$) (D-56). 2D DataMatrix scans override FEFO (D-57). Multi-batch splits trigger when request exceeds selected batch stock (D-58).
- **Non-Negative Stock**: Stock must remain $\\\\ge 0$ (D-59). Discrepancies resolve via Manager-authorized `stock-move: adjustment-in` logging to Central Shrinkage (D-60).
- **Returns & Soft-Delete**: Returns require invoice/batch validation; sealed restocks (D-61); expired or broken cold-chain routes to `quarantine-write-off` (D-62). Soft-deletion requires zero chain stock (D-35); offline partition sales auto-clear deletion (`deleted_at = null`) if stock remains (D-63) (D-64). `[DEFERRED → Doc 6: Partition Ghost-Stock Ingestion & Auto-Resurrection Scenarios]`"""

sec7 = """## 7. Low Stock Alerts
Configured per item, per store in integer base units (D-65). Triggers discrete `low-stock-alert` event when stock drops to or below threshold, suppressed until replenished above threshold (D-66). Closes automatically upon deliberate stock write-offs that zero inventory without reorder intent (D-67). `[DEFERRED → Doc 5: Low-Stock Alert State Lifecycle & Cooldown Flow]`"""

sec8 = """## 8. Invoicing (GST), Credit Notes, Debit Notes & Delivery Challans

### Numbering Series Orthogonality
Document series are store-locally computed, gapless, and mutually orthogonal across 6 series (D-68): Retail B2C Invoices (`<STORE>-INV-...`), Emergency Failover B2C Invoices (`-F1`), Registered B2B Invoices (`<STORE>-B2B-...`), Sales Return Credit Notes (`<STORE>-CN-...`), Supplier Return Debit Notes (`<STORE>-DN-...`), and Delivery Challans (`<STORE>-DC-...`). `[DEFERRED → Doc 1: Document Series Table Schemas & GST Line-Item Fields]`

### Invoicing Specifications
- **B2C Retail Checkout**: Conforms to CGST Section 31 with GSTIN, HSN, batch, expiry, tax breakdown, dynamic NPCI UPI QR (`upi://pay?...`), and audio soundbox confirmation (D-69). Optional WhatsApp share link (`wa.me`) provides paperless receipts (D-70).
- **Two-Phase Print Commit & Jam Resilience**: Checkout commits locally as `COMMITTED_PENDING_PRINT` before printer status check (D-121) (300ms ESC/POS check with OS spooler fallback) (D-122). Cash drawer kick synchronizes with print spooling (D-123). Printer jams prompt UI banner for reprint with audited `*** DUPLICATE COPY ***` watermark (D-124). Customer walkaway during jam triggers cashier void issuing offsetting Credit Note (`<STORE_CODE>-CN-...`), restoring stock and preserving numbering (D-125). `[DEFERRED → Doc 5: Two-Phase Checkout Print Commit & Abandonment Void Workflow]`
- **B2B Invoices & Credit/Debit Notes**: B2B invoices capture buyer 15-digit GSTIN, legal name, and HSN summary under Rule 46(b) for monthly GSTR-1 (D-71). Credit Notes conform to Section 34 CGST Act reversing output tax (D-72); store credit balances are non-transferable across branches, redeemable solely at issuing store (D-73). Debit Notes conform to Section 34(3) for vendor returns (D-74). Rule 55 Delivery Challans accompany intra-state transport with vehicle number and non-sale declaration (D-75). `[DEFERRED → Doc 11: GST Statutory Invoicing, Credit/Debit Note & Challan Clauses]`"""

sec9 = """## 9. Discounts
Centrally governed presets reside on item/category records (D-76). Cashiers are restricted to selecting presets; manual overrides prohibited in v1.6.5 (D-77). Managers (Full preset) or High-access users (Simple preset) edit presets directly via live Central connection with optimistic version locking (§4) (D-78), logged immutably as `discount-edit` events (D-79). `[DEFERRED → Doc 5: Live Discount Edit & Version Verification Flow]`
Manual Insurance / TPA tender metadata fields (Insurer Name, Policy Number, Pre-Authorization Code) captured at checkout as invoice metadata (D-80). `[DEFERRED → Doc 1: Discount Preset Table & TPA Metadata Schema]`"""

sec10 = """## 10. Regulatory Compliance (India, Drugs & Cosmetics Act)

### 10.1 Absolute Expiry Hard-Block
Under Drugs & Cosmetics Act 1940 (Sections 18(a)(i), 27), stocking or selling expired drugs is a strict liability criminal offense. Batches with $\\\\text{expiry\\\\_date} < (\\\\text{CURRENT\\\\_TIMESTAMP AT TIME ZONE 'Asia/Kolkata'})::\\\\text{DATE}$ are unconditionally blocked from billing and dispensing across both Mandatory and Optional compliance modes (D-81), with zero bypass allowance for cashiers, pharmacists, or managers (D-82). Batches remain valid through the final day of their declared expiry month; at 00:00:00 IST on the subsequent day, hard-block unconditionally triggers. Optional mode relaxes only non-statutory metadata.

### 10.2 Schedule H1 Register Completeness
Rule 65(9) mandates an immutable 3-year register capturing 7 mandatory parameters: supply date/time, patient name/address, doctor name/address/registration, drug brand/generic, batch/manufacturer, quantity/pack size, and dispensing pharmacist PIN (D-83). Supports one-click Drug Inspector export (CSV/PDF) (D-84). Postgres enforces `REVOKE UPDATE, DELETE ON dispense_events` (§16) (D-85). `[DEFERRED → Doc 1: Schedule H1 Register & Schedule X Ledger Table Schemas]` `[DEFERRED → Doc 2: Dispense Event Schedule H1/X Audit Payload Schema]`

### 10.3 Schedule X & NDPS Dual-Prescription Custody & Bound Ledger
Rule 65(4) mandates digital scan or photo capture of duplicate prescriptions (D-86). Images compressed to 150–200 DPI WebP (<250 KB), AES-256 encrypted, with 90-day edge retention and 2-year Central cloud archival (D-87). `[DEFERRED → Doc 9: Prescription Image AES-256 Storage & Retention Specification]` Dispensing strictly binds registered Pharmacist credentials via Tier B Full Argon2id Password verification and State Council credentials (D-88), establishing statutory non-repudiation. Enforces automated immutable Daily Running Balance Ledger ($\\\\text{Opening} + \\\\text{Receipts} - \\\\text{Dispensed} = \\\\text{Closing}$) (D-89) with one-click export for Assistant Drugs Controller (D-90)."""

sec11 = """## 11. Roles & Access Control

### Selectable Role Presets
System supports Full (4-Role) and Simple (2-Role) presets (D-91):
- **Full Preset (4-Role)** (D-92): Pharmacist (dispensing, H1/X registers, prescription capture, batch selection), Cashier (billing, checkout, presets, shifts; blocked from H1/X dispense without pharmacist sign-off (D-93)), Manager (cashier/pharmacist rights + return authorization, RTV debit notes, challans, `adjustment-in` PIN, shift force-close, local user account disable during outages, stock write-offs, master-data change requests, direct discount edits), Admin (manager rights + direct master-data edit/create/delete, approving §12 requests, chain reporting, store setup, compliance mode).
- **Simple Preset (2-Role)**: High-Access (merges Pharmacist + Manager + Admin) and Low-Access (billing/shifts only = Cashier) (D-94).
`[DEFERRED → Doc 4: Comprehensive Role Permission Matrix (4-Role & 2-Role)]`

### Local User Revocation
Store Managers can locally disable compromised user accounts directly on Store FastAPI during network partitions, immediately invalidating local login without waiting for Central sync (D-95)."""

sec12 = """## 12. Master-Data Change Request Flow (Full Preset Only)
Direct edit/create/delete authority is restricted strictly to Admin via live connection (§4) (D-96). Managers submit change requests for catalog, pricing, and tax (excluding discounts, which managers edit directly under §9) (D-97). Requests are scoped to single-field, single-record diffs (`field_name`, `current_value`, `expected_version`, `proposed_value`) (D-98). `[DEFERRED → Doc 2: Master-Data Change Request Payload Schema]`
Deletion requests reuse the edit mechanism (`field_name: deleted_at`), gated by chain-wide zero-stock verification (D-99). Request workflow states: `pending` $\\\\rightarrow$ `approved` / `rejected` (reasons: `manual`, `stale`, `duplicate`, `stock-remaining`) (D-100). Central auto-rejects stale edits on version mismatch and duplicate creates on unique business key collision (D-101). `[DEFERRED → Doc 5: Master-Data Change Request State Machine]`"""

sec13 = """## 13. Shift Management & Day-End Till Reconciliation (Z-Report)
Cashiers share counters; shift unlocks upon login and opening float entry (`shift-open`) (D-102), tracking Cash, Card, UPI, and Note tenders.
At shift close, cashier enters blind cash declaration; system calculates Till Variance: $\\\\text{Variance} = \\\\text{Declared Cash} - (\\\\text{Opening Float} + \\\\text{Cash Sales} - \\\\text{Cash Refunds})$ (D-103). To eliminate false shortage alerts upon return redemptions, `Cash Sales` strictly isolates physical cash tenders (`sum(tender_split.cash)`), excluding store credit voucher redemptions and digital tenders; `Cash Refunds` strictly isolates physical cash returns. Day-End Z-Report generated at closing summarizes sales, tax, tenders, returns, debit notes, and variances (D-104). `[DEFERRED → Doc 1: Shift Session & Z-Report Table Schemas]`
Managers can force-close abandoned shifts with an audit note (`shift-force-close`) to unblock counters (D-105). `[DEFERRED → Doc 5: Shift Lifecycle & Till Reconciliation State Machine]`"""

sec14 = """## 14. Testing & Verification Suite
The system enforces an automated unit and integration testing suite covering legal hard-blocks, Legal Metrology fractional rounding math, barcode priority overrides, Schedule H1/X audit logging, LAN multi-counter concurrency, standby failover fencing, Central push atomicity, printer jam recovery, Rule 55 transport guards, and offline auth autonomy (D-106). All 20 executable test case scenario implementations are deferred to eliminate scenario tables from the specification. `[DEFERRED → Doc 8: Automated Unit & Integration Test Suite Specifications (Tests 1–20)]`"""

sec15 = """## 15. Observability & Telemetry
Structured JSON logging with correlation IDs tracks store events, sync attempts, printer status, and manager overrides (D-107). `[DEFERRED → Doc 9: Structured Log Schema & Audit Correlation ID Spec]`
Continuous telemetry tracks queue depth/lag, poison-pill rate, LAN latency, printer jams, and till variances (D-108). Automated alerts fire on sync offline $> 30$ min, poison pills, till shortage $> \\\\text{₹}500$, and disk storage $> 80\\\\%$ (D-109). `[DEFERRED → Doc 10: Operational Telemetry Metrics & Alerting Thresholds]`"""

sec16 = """## 16. Security & Data Protection
Credentials use Argon2id hashes with store-level salting (D-110). Store Postgres binds strictly to `127.0.0.1` (§2). Store LAN traffic is encrypted in-transit via self-signed TLS (HTTPS); terminal API calls pass store-scoped JWTs (D-111). Windows file permissions locked via `icacls` restricting database keys and config files strictly to `NT SERVICE\\\\MedPOS` with zero access for standard accounts (D-112). `[DEFERRED → Doc 9: Edge Security Hardening, Windows File ACLs & Encryption Spec]`
DPDP Act 2023 compliance: Patient PII and prescription scans encrypted at rest via AES-256 (D-113) with 90-day rolling edge retention (§10.3) (D-114). Audit immutability: Dispense logs, invoices, credit/debit notes, challans, and stock adjustments enforce append-only storage via `REVOKE UPDATE, DELETE` (D-115)."""

sec17 = """## 17. Deployment Safety & Edge Rollout
Canary deployment mandates a single store live for 7 days before chain-wide rollout (D-116). Every database migration must include a backwards-compatible rollback script (D-117). POS terminals configure NSSM watchdog auto-recovery, disk write-cache protection, and UPS graceful shutdown (D-118). Worker terminals discover Counter 1 via mDNS broadcast (`medpos-primary.local:8000`) (D-119). `[DEFERRED → Doc 10: Canary Rollout Protocol, Rollback Procedures & Edge Checklist]`"""

sec18 = """## 18. Open Items (Phase 2 Roadmap — V2 Chain Scale)
Enterprise capabilities deferred to Phase 2.0 with interim bridges codified in v1.6.5 (D-120): EDI supplier settlement, in-transit virtual pool, B2B IRN e-invoicing, streaming standby clustering, replication cursors, cross-store voucher 2PL, TPM 2.0 sealing, cloud K8s cluster, customer pole display, cashless TPA co-pay, prescription OCR AI, and WhatsApp gateway. `[DEFERRED → Doc 6: V2 Enterprise Distributed Edge Cases & Scenarios]` `[DEFERRED → Doc 7: V2 Enterprise Module Dependencies & Architectural Roadmap]`

### Open Architecture Questions
1. **Q1: In-Line Adjustment Qty Scope**: When physical stock exists at POS but system displays 0, does `stock-adjustment-in` adjust immediate transaction qty or full shelf count? (Owner: Core POS Lead; Target: v1.6.6 Sprint 1)
2. **Q2: Shift Handover Float Policy**: In multi-shift counters, do cashiers swap cash drawer cassettes or perform in-place float count handoffs? (Owner: Retail Operations Lead; Target: v1.6.6 Sprint 1)
3. **Q3: Credit Note Validity & Partial Redemption**: Do `<STORE_CODE>-CN-...` credit balances expire after statutory periods and allow partial multi-visit redemption? (Owner: Finance & GST Lead; Target: v1.6.6 Sprint 2)"""

sec19 = """## 19. Deferred Items Register

### Doc 1: Data Schema
1. `[DEFERRED → Doc 1: Central Sync & Quarantine Table Schemas]`
2. `[DEFERRED → Doc 1: Batch Table UOM Field Schema & Constraints]`
3. `[DEFERRED → Doc 1: Document Series Table Schemas & GST Line-Item Fields]`
4. `[DEFERRED → Doc 1: Discount Preset Table & TPA Metadata Schema]`
5. `[DEFERRED → Doc 1: Schedule H1 Register & Schedule X Ledger Table Schemas]`
6. `[DEFERRED → Doc 1: Shift Session & Z-Report Table Schemas]`

### Doc 2: Event Schema
7. `[DEFERRED → Doc 2: Full Event Payload Schemas for Events 1–19 & Tombstones]`
8. `[DEFERRED → Doc 2: Dispense Event Schedule H1/X Audit Payload Schema]`
9. `[DEFERRED → Doc 2: Master-Data Change Request Payload Schema]`

### Doc 3: API Contracts
10. `[DEFERRED → Doc 3: Central Admin Web Portal Endpoints]`
11. `[DEFERRED → Doc 3: Central Ingestion Batch Endpoint Contract]`

### Doc 4: RBAC Permissions
12. `[DEFERRED → Doc 4: Comprehensive Role Permission Matrix (4-Role & 2-Role)]`

### Doc 5: State Machines
13. `[DEFERRED → Doc 5: Standby Promotion Script & Fencing State Machine]`
14. `[DEFERRED → Doc 5: Outbound Sync Trigger & Retry Backoff State Machine]`
15. `[DEFERRED → Doc 5: Batch Picking, Fractional Return Inspection & RTV State Machines]`
16. `[DEFERRED → Doc 5: Low-Stock Alert State Lifecycle & Cooldown Flow]`
17. `[DEFERRED → Doc 5: Two-Phase Checkout Print Commit & Abandonment Void Workflow]`
18. `[DEFERRED → Doc 5: Live Discount Edit & Version Verification Flow]`
19. `[DEFERRED → Doc 5: Master-Data Change Request State Machine]`
20. `[DEFERRED → Doc 5: Shift Lifecycle & Till Reconciliation State Machine]`

### Doc 6: Conflicts & Edge Cases
21. `[DEFERRED → Doc 6: Master-Data Concurrency Conflict & Partition Scenarios]`
22. `[DEFERRED → Doc 6: Partition Ghost-Stock Ingestion & Auto-Resurrection Scenarios]`
23. `[DEFERRED → Doc 6: V2 Enterprise Distributed Edge Cases & Scenarios]`

### Doc 7: Dependency Map
24. `[DEFERRED → Doc 7: Core Module Dependency Graph & Build Order]`
25. `[DEFERRED → Doc 7: V2 Enterprise Module Dependencies & Architectural Roadmap]`

### Doc 8: Test Plan
26. `[DEFERRED → Doc 8: Automated Unit & Integration Test Suite Specifications (Tests 1–20)]`

### Doc 9: Security & Audit Spec
27. `[DEFERRED → Doc 9: Local Auth JWT Claim Schema & Argon2id Hash Parameters]`
28. `[DEFERRED → Doc 9: Prescription Image AES-256 Storage & Retention Specification]`
29. `[DEFERRED → Doc 9: Structured Log Schema & Audit Correlation ID Spec]`
30. `[DEFERRED → Doc 9: Edge Security Hardening, Windows File ACLs & Encryption Spec]`

### Doc 10: Deployment Plan
31. `[DEFERRED → Doc 10: Unattended Edge Backup, Pruning & Watchdog Service Spec]`
32. `[DEFERRED → Doc 10: Operational Telemetry Metrics & Alerting Thresholds]`
33. `[DEFERRED → Doc 10: Canary Rollout Protocol, Rollback Procedures & Edge Checklist]`

### Doc 11: Glossary
34. `[DEFERRED → Doc 11: Legal Metrology Rule 2011 & Schedule Compliance Glossary]`
35. `[DEFERRED → Doc 11: GST Statutory Invoicing, Credit/Debit Note & Challan Clauses]`

---
*Status: Active (v1.6.5). Supersedes architecture_v1_6.md and architecture_v1_5.md.*"""

all_secs = [header, sec1, sec2, sec3, sec4, sec5, sec6, sec7, sec8, sec9, sec10, sec11, sec12, sec13, sec14, sec15, sec16, sec17, sec18, sec19]
full_doc = "\n\n---\n\n".join(all_secs[:1] + all_secs[1:2]) + "\n\n---\n\n" + "\n\n---\n\n".join(all_secs[2:])

words = full_doc.split()
print("Total words:", len(words))
print("Below 3500:", len(words) < 3500)

# Validate markers
sec19_str = full_doc[full_doc.find("## 19. Deferred Items Register") :]
body_str = full_doc[: full_doc.find("## 19. Deferred Items Register")]

body_markers = re.findall(r"\[DEFERRED → Doc \d+:[^\]]+\]", body_str)
reg_markers = re.findall(r"\[DEFERRED → Doc \d+:[^\]]+\]", sec19_str)

print(f"Body markers: {len(body_markers)}, Reg markers: {len(reg_markers)}")
print("Body - Reg:", set(body_markers) - set(reg_markers))
print("Reg - Body:", set(reg_markers) - set(body_markers))

# Validate D-IDs
d_tags = re.findall(r"\(D-\d+\)", full_doc)
print(f"Total D-tags: {len(d_tags)}")
d_nums = [int(re.search(r"\d+", d).group()) for d in d_tags]
from collections import Counter
counts = Counter(d_nums)
dups = [k for k, v in counts.items() if v > 1]
print("Duplicates:", dups)
missing = [i for i in range(1, 126) if i not in counts]
print("Missing in 1..125:", missing)

with open("scratch/arch_tight.md", "w", encoding="utf-8") as f:
    f.write(full_doc)
print("Saved to scratch/arch_tight.md")
