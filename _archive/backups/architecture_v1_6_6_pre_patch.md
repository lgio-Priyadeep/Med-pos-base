# Pharmacy POS — Architecture Spec (v1.6.6)

*Changelog:*
- v1.5: Zero-stock deletion invariant, offline write-offs, audit logs.
- v1.6: Expiry block, H1 completeness, offline directories, sync, Z-reports.
- v1.6.5: Fractional dispensing, RTV debit notes, Rule 55 challans, LAN topology.
- v1.6.6: Foundation entities, two-tier auth, exchange atomicity, sync paging, recall block.

---

## 1. Scope
- Footprint: 2–5 physical retail stores (D-01).
- Hybrid model: Offline-first with async background sync; direct master writes excluded (§4) (D-02).
- Counter scaling: Multi-counter LAN (1 Primary + 1–3 Worker terminals) (D-03).
- Single-store mode: Supported via Simple 2-role preset (§11) (D-04).
- Operations: Billing, fractional dispensing, returns/exchanges, GRN, RTV, challans, batch inventory, shifts, training, and H1/NDPS registers (D-05).

### Non-Goals
Store-to-cloud master writes, cross-store vouchers, live B2B IRN, distributed consensus, EDI, and optical OCR are deferred to Phase 2.0 (§18).

---

## 2. Tech Stack & Edge Infrastructure
- **Backend & DB**: Python/FastAPI across store/Central (D-06). Central: cloud Postgres (D-07). Counter 1: local Postgres 16 (D-08) at `READ COMMITTED` (D-156) with ascending PK row-locks (`ORDER BY id ASC FOR UPDATE`) preventing deadlocks.
- **Multi-Counter LAN**:
  - *Counter 1 (Primary)*: Sequence authority on `127.0.0.1` (D-09). FastAPI binds `0.0.0.0:8000` via 10-yr TLS (D-10) (D-158), broadcasting mDNS as `medpos-primary.local:8000` with pinned fingerprint (D-11); cert replicates to standby.
  - *Counters 2/3 (Workers)*: UI shells connecting via LAN REST/WebSockets without local DB (D-12).
  - *Standby & Failover*: Counter 2 warm standby receives WAL (alert lag $> 1\text{h}$) (D-13) (D-157). `promote_to_primary.bat` fences Counter 1 via ping against split-brain (D-14). `[DEFERRED → Doc 5: Standby Promotion Script & Fencing State Machine]` Promoted node jumps sequence +100,000 adopting epoch `<STORE_CODE>-INV-YYYYMM-XXXX-F1` (§8) (D-15).
- **Local Auth**: Replicated Argon2id hashes issue store JWTs (8–12h TTL) (D-16) (D-17). `[DEFERRED → Doc 9: Local Auth JWT Claim Schema & Argon2id Hash Parameters]`
- **Maintenance & Recovery**: Alembic runs migrations with pre-flight edge backups (`pg_dump -Fc`) (D-163). Rolling 7-day backups (D-18), background `VACUUM ANALYZE` / WAL pruning (D-19), NSSM watchdog (D-20), and Central PITR (RPO < 1h, RTO < 4h) (D-166). `[DEFERRED → Doc 10: Unattended Edge Backup, Pruning & Watchdog Service Spec]` Shutdown drains checkouts 30s (D-167); startup routes orphaned `COMMITTED_PENDING_PRINT` to historic shifts.
- **Clock-Skew Defense**: Monotonic commit check (`current_timestamp >= MAX(created_at)`) blocks CMOS resets (D-21); skew $> \pm 5\text{ min}$ triggers sync warning (D-22).

---

## 3. Core Modules
Partitioned into 13 discrete domain modules: M-01 (Inventory, GRN & UOM), M-02 (Customer Returns & Exchanges), M-03 (Vendor Returns / RTV), M-04 (Branch Stock Transfers), M-05 (Prescription & Dispensing), M-06 (Billing & Cashier Operations), M-07 (Hardware & Peripherals), M-08 (Multi-Store Master Data), M-09 (Operational Directories), M-10 (Sync Engine), M-11 (User Roles & Auth), M-12 (Settings, Training Mode & Config), and M-13 (Reporting & Till Reconciliation) (D-23). `[DEFERRED → Doc 7: Core Module Dependency Graph & Build Order]`

---

## 4. System Architecture

### Local-First Store Node & Multi-Counter LAN
Stores operate autonomously offline for billing, dispensing, returns, challans, stock moves, shifts, and registration (D-24). Counter 1 commits to local event tables (§5) (D-25); workers bill over LAN. Status bar displays offline duration (`Last synced: X min ago`) with reassuring messaging (D-168).

### Store-Initiated Outbound Sync Protocol
Sync is store-initiated outbound (HTTPS/WebSockets) traversing CGNAT without inbound ports (D-26). Sync uses rotatable API keys; Central Admin uses Argon2id session cookies (D-159). Pushes trigger at 30–60s intervals with 500-event ceilings and watermark continuation (D-27) (D-153). Central returns catalog updates, pricing, and CDSCO recalls (D-28). Central DB aggregates for reporting, never authoritative for store stock (D-29). `[DEFERRED → Doc 5: Outbound Sync Trigger & Retry Backoff State Machine]`

### Master Data Delivery & Concurrency Control
Master data enforces monotonic `master_data_version` watermarks, applying only payloads where `incoming_version > local_version` (D-151), with Central Admin `force_apply: true` override. Large releases use transport chunking (`batch_id`, `page X of Y`); stores stage in `master_data_staging`, activating atomically via MVCC (D-152).
Direct master writes require live Central connection with optimistic version locking (D-30). Records carry integer `version`; edits reject on mismatch (`reason: stale`) (D-33), prompting refresh-and-retry backed by a 5-minute advisory lock (`editing_by`) (D-155); duplicate keys reject (D-34). Soft-deletion requires chain-wide zero stock (see D-35 in §6). Central Admin uses a Web portal without direct DB connections into store LANs (D-36). `[DEFERRED → Doc 3: Central Admin Web Portal Endpoints]` `[DEFERRED → Doc 6: Master-Data Concurrency Conflict & Partition Scenarios]`

### Operational Directories vs Master Data
Patients and Doctors are store-local entities (`<STORE_CODE>-PAT-<UUID>`, `<STORE_CODE>-DOC-<UUID>`), offline-creatable and synced asynchronously (D-31). Central deduplicates in read-only audit views without mutating store IDs (D-32).

---

## 5. Data Flow / Event Model

### Event Envelope Standard
Mutations commit as immutable append-only events: `event_id` (UUIDv4 PK), `store_seq_no` (BIGSERIAL), `store_id`, `created_at` (monotonic UTC), `event_type`, and `payload` (JSONB) (D-37).

### Central Ingestion Atomicity & Poison-Pill Quarantine
Central ingests batches atomically (`BEGIN...COMMIT`) with watermarks (D-38) and `ON CONFLICT (event_id) DO NOTHING` (D-39). Malformed events isolate into `central_sync_quarantine` with `sync-quarantine-tombstone` records in `central_events` preserving sequence continuity (D-40). Central ack returns committed watermarks and quarantined IDs, unblocking queues and alerting Central Admin via dashboard/webhooks (D-41) (D-154). `[DEFERRED → Doc 1: Central Sync & Quarantine Table Schemas]` `[DEFERRED → Doc 3: Central Ingestion Batch Endpoint Contract]`

### Event Types
Defines 21 event types: inventory (`grn`), sales/credit (`sale`, `b2b-sale`, `credit-note-redemption`), returns (`sale-return`), dispensing (`dispense`), stock (`stock-move`), shifts (`shift-open`, `shift-close`, `shift-force-close`), directories (`patient-created`, `doctor-created`), master data (`discount-edit`, `master-data-edit`, `master-data-created`, `master-data-change-requested`, `master-data-change-approved`, `master-data-change-rejected`), and admin (`low-stock-alert`, `settings-change`, `reprint`) (D-42) (D-126) (D-137). Local `grn` uses `ON CONFLICT DO NOTHING` preventing stock inflation. `[DEFERRED → Doc 2: Full Event Payload Schemas for Events 1–21 & Tombstones]`

---

## 6. Stock, Inventory Lifecycle & Batch Mechanics

### Unit of Measure (UOM) Hierarchy & Fractional Billing
Stock is stored in integer base units without decimals (D-43). Packaging locks at GRN, isolating counts from catalog edits (D-44). `[DEFERRED → Doc 1: Batch Table UOM Field Schema & Constraints]` Pack Qty is integer division ($\text{Base} // \text{Pack Size}$); loose units are modulo ($\text{Base} \pmod{\text{Pack Size}}$) (D-45). Loose unit price rounds half-up ($\operatorname{ROUND\_HALF\_UP}(\text{Strip MRP} / \text{Pack Size}, 2)$) (D-46); subtotal clamps to $\min(\text{Loose Qty} \times \text{Unit Price}, \text{Strip MRP})$ (D-47). `[DEFERRED → Doc 11: Legal Metrology Rule 2011 & Schedule Compliance Glossary]` Barcode scans bill 1 Packaging Unit (D-48). Sealed blister cavities restock; damaged route to quarantine (D-49).

### Inbound Goods Receipt (GRN) & Classifications
Inbound stock commits via `grn` events capturing supplier, invoice ref, batch, and `purchase_price_per_unit` (D-127) (Manager/Admin only). Short receipts log ordered vs received quantities in GRN events (D-128). Zero-MRP entry enforces `CHECK ((is_free_supply = TRUE AND mrp = 0) OR (is_free_supply = FALSE AND mrp > 0))` (D-129), barring commercial sales. Drug records capture `drug_schedule ENUM` and `is_ndps BOOLEAN` (D-130); NDPS enforces dual-custody and blocks repeats under Rule 65(11A). Chapter 30 HSN validates on invoice creation: soft-warn B2C, hard-block B2B (D-131).

### Near-Expiry Vendor Returns (RTV) & Transfers
Shelf expiry tiers (90d Amber FEFO / 60d Orange RTV / 30d Red quarantine) trigger `stock-move: rtv-quarantine` issuing sequential Debit Notes (§8) (D-50) (D-51). Branch transfers require Rule 55 Challans (intra-state) or IGST invoices (inter-state) (D-52) (D-53). Receiving splits intact (`received_qty`), breakage (quarantine write-off with photo), and shortage (shrinkage audit) (D-54) (D-55). `[DEFERRED → Doc 5: Batch Picking, Fractional Return Inspection & RTV State Machines]`

### Batch Picking, Stock-Take & Integrity
Picking defaults to FEFO (D-56); 2D scans override (D-57); multi-batch splits auto-trigger (D-58). Stock remains $\ge 0$ (D-59); discrepancies resolve via Manager `adjustment-in` (D-60); damaged write-offs require photo, reason, and Quick-PIN (D-170). Stock-take uses 5–10 min rack micro-freezes bound to store-local `rack_location` (D-171). Returns pick invoice batch sub-lines (D-169); sealed restocks (D-61); expired or broken cold-chain routes to quarantine write-off (D-62). Soft-deletion requires zero chain stock (D-35); partition sales clear deletion (`deleted_at = null`) if stock remains (D-63) (D-64). `[DEFERRED → Doc 6: Partition Ghost-Stock Ingestion & Auto-Resurrection Scenarios]`

---

## 7. Low Stock Alerts
Configured per item, per store in integer base units (D-65). Triggers discrete `low-stock-alert` event when stock drops to or below threshold, suppressed until replenished above threshold (D-66). Closes automatically upon deliberate stock write-offs that zero inventory without reorder intent (D-67). `[DEFERRED → Doc 5: Low-Stock Alert State Lifecycle & Cooldown Flow]`

---

## 8. Invoicing (GST), Credit Notes, Debit Notes, Challans & Exchanges

### Numbering Series Orthogonality
Series are store-computed, gapless, and orthogonal across 6 series (D-68): Retail B2C (`-INV-`), Failover B2C (`-F1`), B2B (`-B2B-`), Credit Notes (`-CN-`), Debit Notes (`-DN-`), and Challans (`-DC-`). `[DEFERRED → Doc 1: Document Series Table Schemas & GST Line-Item Fields]`

### Checkout Workflow & Peripheral Resilience
B2C checkout complies with CGST Section 31 (GSTIN, HSN, batch, expiry, tax breakdown, dynamic UPI QR, soundbox confirmation) (D-69). WhatsApp share (`wa.me`) provides paperless receipts (D-70). Cashiers may toggle bill previews (D-134). Unrecognized barcodes prompt manual search and log gap events (D-135). Phone search supports family disambiguation while masking medical history (D-136).
Checkout commits locally as `COMMITTED_PENDING_PRINT` before printer check (D-121) (300ms ESC/POS check with spooler fallback) (D-122). Cash drawer kicks with spooling (D-123). Jams prompt UI reprint with audited `*** DUPLICATE COPY ***` watermark, logging a `reprint` event (D-124) (D-137). Walkaways during jams trigger cashier void issuing offsetting Credit Notes (`<STORE_CODE>-CN-...`), restoring stock and preserving numbering (D-125). `[DEFERRED → Doc 5: Two-Phase Checkout Print Commit & Abandonment Void Workflow]`

### Returns, Cash Refund Limits & Atomic Exchanges
Customer returns issue store-bound GST Credit Notes (`<STORE>-CN-...`) (D-72) (D-73). Cash refunds enforce a daily counter ceiling; split settlements issue cash up to limit and credit notes for remainder (D-133). Exchanges execute as atomic 3-event groups (`sale-return`, `credit-note-redemption`, `sale`) bound by `exchange_group_id` in a single transaction (D-132); client session staging ensures zero dangling credit; down-sells leave active balances on the Credit Note.
B2B invoices capture buyer GSTIN, legal name, and HSN summary under Rule 46(b) for GSTR-1 (D-71). Debit Notes conform to Section 34(3) for vendor returns (D-74). Rule 55 Challans accompany intra-state transport with vehicle numbers and non-sale declarations (D-75). `[DEFERRED → Doc 11: GST Statutory Invoicing, Credit/Debit Note & Challan Clauses]`

---

## 9. Discounts & Price Governance
Presets reside on item/category records (D-76). Cashiers may apply ad-hoc discounts $\le 15.0\%$ net effective discount off Strip MRP (D-77) (D-138):
$$\text{Effective Discount \%} = \frac{\text{Line MRP} - \text{Billed Unit Price}}{\text{Line MRP}} \times 100 \le 15.0\%$$
Discounts are barred on zero-MRP free supplies and DPCO drugs; billed prices cannot drop below `purchase_price_per_unit` without Manager override (D-139).
Manager Quick-PIN overrides permit discounts up to 100% locally, subject to a monthly ceiling (₹5,000) (D-140). Offline pool exhaustion mandates dual credentials (Full) or High-Access Argon2id Password override (Simple: max ₹1,500/sale, non-controlled, $\ge 20$ char remark, `emergency_offline_override: true`). Direct preset edits require live Central connection with optimistic locking (D-78), logged as `discount-edit` events (D-79). `[DEFERRED → Doc 5: Live Discount Edit & Version Verification Flow]` Insurance/TPA tender metadata captures on invoice (D-80). `[DEFERRED → Doc 1: Discount Preset Table & TPA Metadata Schema]`

---

## 10. Regulatory Compliance (India, Drugs & Cosmetics Act)

### 10.1 Absolute Expiry Hard-Block & Drug Recalls
Batches with $\text{expiry\_date} < (\text{CURRENT\_TIMESTAMP AT TIME ZONE 'Asia/Kolkata'})::\text{DATE}$ are unconditionally blocked across Mandatory and Optional modes (D-81) with zero bypass (D-82). Batches remain billable through declared MM/YYYY month-end; lockout occurs at 00:00:00 IST next day. CDSCO drug recalls in sync payloads (`batch-recall`) auto-quarantine batches (D-143); carts with recalled batches hard-block at checkout commit (`COMMITTED_PENDING_PRINT`, HTTP 409 `DRUG_RECALL_BLOCK`), allowing non-destructive line removal.

### 10.2 Schedule H1 Register & Prescription Reuse Limits
Rule 65(9) mandates an immutable 3-year H1 register capturing 7 statutory parameters (D-83) with one-click export (D-84) and `REVOKE UPDATE, DELETE` (D-85). `[DEFERRED → Doc 1: Schedule H1 Register & Schedule X Ledger Table Schemas]` `[DEFERRED → Doc 2: Dispense Event Schedule H1/X Audit Payload Schema]` Rule 65(11) prohibits repeat dispensing of Schedule H/H1 drugs unless prescribers explicitly author repeat instructions (`is_repeatable = true`) (D-141). Prescriptions track cumulative balances (`prescribed_base_units`, `cum_dispensed_base_units`, `unfulfilled_base_units`) locked `FOR UPDATE` (D-142), expiring after statutory windows (7d antimicrobials, 30d chronic H, 72h X/NDPS). DPDP Act 2023 patient consent is soft-required (D-145).

### 10.3 Schedule X & NDPS Dual-Prescription Custody & Bound Ledger
Rule 65(4) mandates digital scans of duplicate prescriptions (<250 KB WebP, AES-256 encrypted, 90d edge retention, 2yr cloud archive) (D-86) (D-87). `[DEFERRED → Doc 9: Prescription Image AES-256 Storage & Retention Specification]` Dispensing binds registered Pharmacist credentials via Tier B Full Argon2id Password verification and State Council credentials (D-88). Daily Running Balance Ledger ($\text{Opening} + \text{Receipts} - \text{Dispensed} = \text{Closing}$) (D-89) updates via scheduled midnight opening balance materialization (D-144) with one-click export (D-90). Image retrieval verifies stored SHA-256 hashes against decrypted image bytes (D-146).

---

## 11. Roles & Access Control

### Selectable Role Presets & Authentication Hierarchy
System supports Full (4-Role: Pharmacist, Cashier, Manager, Admin) and Simple (2-Role: High-Access, Low-Access) presets (D-91) (D-92) (D-94). Cashiers cannot dispense H1/X without pharmacist sign-off (D-93). `[DEFERRED → Doc 4: Comprehensive Role Permission Matrix (4-Role & 2-Role)]`
Two-tier auth (D-147): Tier A Session Quick-PIN (4–6 digits, set at shift-open, auto-expires at close/12h) authorizes supervisor overrides (adjustments, cashier discounts, returns, H1 sign-off); Tier B Full Argon2id Password is required for high-liability governance (account disable, Schedule X/NDPS dispense, master change approval, training reset).
Terminals block concurrent logins while another shift is active (D-149). Failed logins trigger throttling: 5 failed attempts locks `(terminal_id + username)` for 15 minutes (D-148). Managers can disable compromised accounts locally, invalidating active JWTs via incremented user `token_generation` counters cached with 30s TTL (D-95) (D-150).

---

## 12. Master-Data Change Request Flow (Full Preset Only)
Admin holds exclusive direct edit/create/delete authority via live connection (§4) (D-96). Managers submit change requests for catalog, pricing, and tax (excluding discounts under §9) (D-97) as single-field diffs (`field_name`, `current_value`, `expected_version`, `proposed_value`) (D-98). `[DEFERRED → Doc 2: Master-Data Change Request Payload Schema]`
Deletion requests set `field_name: deleted_at`, gated by chain-wide zero-stock (D-99). Workflow: `pending` $\rightarrow$ `approved` / `rejected` (`manual`, `stale`, `duplicate`, `stock-remaining`) (D-100). Central auto-rejects stale edits and duplicate creates (D-101). `[DEFERRED → Doc 5: Master-Data Change Request State Machine]`

---

## 13. Shift Management & Day-End Till Reconciliation (Z-Report)
Registers unlock on login and opening float entry (`shift-open`) (D-102), tracking Cash, Card, UPI, and Note tenders. Terminals isolate peer shifts, blocking Cashier B from viewing/closing Cashier A's shift (D-173).
At shift close, cashier enters blind cash declaration; system calculates Till Variance:
$$\text{Variance} = \text{Declared Cash} - (\text{Opening Float} + \text{Cash Sales} - \text{Cash Refunds})$$
`Cash Sales` isolates physical cash (`sum(tender_split.cash)`), excluding credit notes and digital tenders; `Cash Refunds` isolates physical cash returns (D-103). Recovered crash transactions bind to historic shifts, preventing float distortion (D-174). Day-End Z-Report aggregates shifts, sales, tax, tenders, returns, debit notes, and variances (D-104). `[DEFERRED → Doc 1: Shift Session & Z-Report Table Schemas]` Managers can force-close abandoned shifts with audit notes (`shift-force-close`) (D-105). `[DEFERRED → Doc 5: Shift Lifecycle & Till Reconciliation State Machine]`

---

## 14. Testing & Verification Suite
Automated tests cover legal hard-blocks, Legal Metrology, barcode overrides, Schedule H1/X, LAN concurrency, standby failover, Central push atomicity, printer jams, Rule 55 transport, offline auth, B2B tax, tax reversals, shift isolation, version conflicts, clock-skew, discount caps, and stress limits (D-106) (D-175). All 28 test specifications are deferred. `[DEFERRED → Doc 8: Automated Unit & Integration Test Suite Specifications (Tests 1–28)]`

---

## 15. Observability & Telemetry
Structured JSON logging with correlation IDs tracks events, sync, printers, and overrides (D-107). `[DEFERRED → Doc 9: Structured Log Schema & Audit Correlation ID Spec]`
Continuous telemetry tracks queue depth/lag, poison pills, LAN latency, jams, and till variances (D-108). Scheduled background jobs compute rolling 7/30-day SKU velocity, return anomalies, sync payload sizes, scan-to-commit duration via `checkout_started_at`, and failed logins (D-172). Alerts fire on sync offline $> 30\text{ min}$, poison pills, till shortage $> \text{₹}500$, and disk $> 80\%$ (D-109). `[DEFERRED → Doc 10: Operational Telemetry Metrics & Alerting Thresholds]`

---

## 16. Security & Data Protection
Credentials use Argon2id hashes with store salting (D-110). Store Postgres binds to `127.0.0.1` (§2). LAN traffic uses TLS; terminal API calls pass store-scoped JWTs (D-111). Windows permissions locked via `icacls` restrict DB keys and configs strictly to `NT SERVICE\MedPOS` (D-112). `[DEFERRED → Doc 9: Edge Security Hardening, Windows File ACLs & Encryption Spec]`
DPDP Act 2023: Patient PII and prescription scans are encrypted at rest via AES-256 (D-113) with 90-day edge retention (§10.3) (D-114) and annual key rotation with `key_id` tagging and background re-encryption (D-161). Dispense logs, invoices, notes, challans, and adjustments enforce append-only storage via `REVOKE UPDATE, DELETE` (D-115). Scheduled 4-hour jobs compute Merkle root hashes of committed events for tamper detection (D-160). Training sessions run in isolated Postgres schema (`training.*`), recreated on start with separate `TRAINING-` series (D-162).

---

## 17. Deployment Safety & Edge Rollout
Canary deployment mandates a single store live for 7 days before chain rollout (D-116). Database migrations include backwards-compatible rollback scripts via Alembic (D-117) (D-163). Windows updates enforce WSUS deferral to a 2–3 AM maintenance window on Windows 10/11 LTSC (D-164). Terminals configure NSSM watchdog recovery, disk write-cache protection, and UPS graceful shutdown (D-118). Workers discover Counter 1 via mDNS broadcast (`medpos-primary.local:8000`) (D-119). Tiered disk responses: 85% log pruning and standard `VACUUM ANALYZE` (forbidding `VACUUM FULL`); 90% degraded write mode preserving heartbeats and statutory images; 98% emergency read-only mode (D-165). `[DEFERRED → Doc 10: Canary Rollout Protocol, Rollback Procedures & Edge Checklist]`

---

## 18. Open Items (Phase 2 Roadmap — V2 Chain Scale)
Enterprise capabilities deferred to Phase 2.0 with interim bridges codified in v1.6.6 (D-120): EDI settlement, in-transit virtual pool, B2B IRN, streaming standby clustering, replication cursors, cross-store voucher 2PL, TPM 2.0 sealing, cloud K8s, customer pole display, cashless TPA co-pay, prescription OCR AI, and WhatsApp gateway. `[DEFERRED → Doc 6: V2 Enterprise Distributed Edge Cases & Scenarios]` `[DEFERRED → Doc 7: V2 Enterprise Module Dependencies & Architectural Roadmap]`

### Open Architecture Questions
1. **Q1: UPI Timeout & Soundbox Reconcile**: Dynamic UPI QR scanned but webhook stalls: max cashier wait before cash fallback? (Owner: Payments Lead; Target: v1.7 Sprint 1)
2. **Q2: Automated Shelf-Quarantine Bins**: Should RTV shelf-quarantine group expired batches into distributor physical tote bins? (Owner: Operations Lead; Target: v1.7 Sprint 1)

---

## 19. Deferred Items Register

### Doc 1: Data Schema
- `[DEFERRED → Doc 1: Central Sync & Quarantine Table Schemas]`
- `[DEFERRED → Doc 1: Batch Table UOM Field Schema & Constraints]`
- `[DEFERRED → Doc 1: Document Series Table Schemas & GST Line-Item Fields]`
- `[DEFERRED → Doc 1: Discount Preset Table & TPA Metadata Schema]`
- `[DEFERRED → Doc 1: Schedule H1 Register & Schedule X Ledger Table Schemas]`
- `[DEFERRED → Doc 1: Shift Session & Z-Report Table Schemas]`

### Doc 2: Event Schema
- `[DEFERRED → Doc 2: Full Event Payload Schemas for Events 1–21 & Tombstones]`
- `[DEFERRED → Doc 2: Dispense Event Schedule H1/X Audit Payload Schema]`
- `[DEFERRED → Doc 2: Master-Data Change Request Payload Schema]`

### Doc 3: API Contracts
- `[DEFERRED → Doc 3: Central Admin Web Portal Endpoints]`
- `[DEFERRED → Doc 3: Central Ingestion Batch Endpoint Contract]`

### Doc 4: RBAC Permissions
- `[DEFERRED → Doc 4: Comprehensive Role Permission Matrix (4-Role & 2-Role)]`

### Doc 5: State Machines
- `[DEFERRED → Doc 5: Standby Promotion Script & Fencing State Machine]`
- `[DEFERRED → Doc 5: Outbound Sync Trigger & Retry Backoff State Machine]`
- `[DEFERRED → Doc 5: Batch Picking, Fractional Return Inspection & RTV State Machines]`
- `[DEFERRED → Doc 5: Low-Stock Alert State Lifecycle & Cooldown Flow]`
- `[DEFERRED → Doc 5: Two-Phase Checkout Print Commit & Abandonment Void Workflow]`
- `[DEFERRED → Doc 5: Live Discount Edit & Version Verification Flow]`
- `[DEFERRED → Doc 5: Master-Data Change Request State Machine]`
- `[DEFERRED → Doc 5: Shift Lifecycle & Till Reconciliation State Machine]`

### Doc 6: Conflicts & Edge Cases
- `[DEFERRED → Doc 6: Master-Data Concurrency Conflict & Partition Scenarios]`
- `[DEFERRED → Doc 6: Partition Ghost-Stock Ingestion & Auto-Resurrection Scenarios]`
- `[DEFERRED → Doc 6: V2 Enterprise Distributed Edge Cases & Scenarios]`

### Doc 7: Dependency Map
- `[DEFERRED → Doc 7: Core Module Dependency Graph & Build Order]`
- `[DEFERRED → Doc 7: V2 Enterprise Module Dependencies & Architectural Roadmap]`

### Doc 8: Test Plan
- `[DEFERRED → Doc 8: Automated Unit & Integration Test Suite Specifications (Tests 1–28)]`

### Doc 9: Security & Audit Spec
- `[DEFERRED → Doc 9: Local Auth JWT Claim Schema & Argon2id Hash Parameters]`
- `[DEFERRED → Doc 9: Prescription Image AES-256 Storage & Retention Specification]`
- `[DEFERRED → Doc 9: Structured Log Schema & Audit Correlation ID Spec]`
- `[DEFERRED → Doc 9: Edge Security Hardening, Windows File ACLs & Encryption Spec]`

### Doc 10: Deployment Plan
- `[DEFERRED → Doc 10: Unattended Edge Backup, Pruning & Watchdog Service Spec]`
- `[DEFERRED → Doc 10: Operational Telemetry Metrics & Alerting Thresholds]`
- `[DEFERRED → Doc 10: Canary Rollout Protocol, Rollback Procedures & Edge Checklist]`

### Doc 11: Glossary
- `[DEFERRED → Doc 11: Legal Metrology Rule 2011 & Schedule Compliance Glossary]`
- `[DEFERRED → Doc 11: GST Statutory Invoicing, Credit/Debit Note & Challan Clauses]`

---
*Status: Active (v1.6.6). Supersedes architecture_v1_6_5.md, architecture_v1_6.md, and architecture_v1_5.md.*
