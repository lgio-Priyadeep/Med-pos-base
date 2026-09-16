# Pharmacy POS — Architecture Roadmap & Engineering Gap Registry

This document serves as the authoritative, living engineering registry tracking architectural gaps, retail edge cases, regulatory requirements, and technical enhancements for the Pharmacy POS system.

The document is organized into three distinct parts:
- **[Part I: Active Architectural Gaps & Improvement Roadmap (v1.6.5 &rarr; v2.0 Enterprise Scope)](#part-i-active-architectural-gaps--improvement-roadmap-v165--v20-enterprise-scope)**: Detailed analysis of enterprise capabilities intentionally deferred for the V2 Major Iteration (Multi-Store Enterprise Chain Scale).
- **[Part II: Active Priority vs. Complexity Roadmap Matrix (Track B: Deferred for V2)](#part-ii-active-priority-vs-complexity-roadmap-matrix-track-b-deferred-for-v2)**: Strategic matrix defining the 12 enterprise capabilities targeted for Phase 2.0.
- **[Part III: Historical Milestone Archive](#part-iii-historical-milestone-archive)**:
  - **[Section A: v1.6 &rarr; v1.6.5 Resolved Baseline](#section-a-v16--v165-resolved-baseline)**: Verified record of the 8 Track A items, 4 interim bridges, and 8 defensive operational safeguards codified into [architecture_v1_6_5.md](architecture_v1_6_5.md).
  - **[Section B: v1.5 &rarr; v1.6 Resolved Baseline](#section-b-v15--v16-resolved-baseline)**: Verified record of the 12 core improvements and 8 operational safeguards codified into historical [_archive/Prev_iterations/Architecture/architecture_v1_6.md](_archive/Prev_iterations/Architecture/architecture_v1_6.md).

---

## Part I: Active Architectural Gaps & Improvement Roadmap (v1.6.5 &rarr; v2.0 Enterprise Scope)

The following 12 enterprise capabilities are formally deferred for the **V2 Major Iteration (Phase 2.0 Chain Scale)**. Each capability has an active operational bridge codified in [architecture_v1_6_5.md](architecture_v1_6_5.md) to support pilot stores (2–5 stores) without enterprise cloud overhead.

### 1. Enterprise Supply Chain & Distributor Settlement
#### 1.1 Automated Central Supplier Settlement (EDI Bridges & AP Ledger)
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Chain Scale]`
- **Scope:** Automated Electronic Data Interchange (EDI) bridges into distributor enterprise software (Marg, MediVision) and automated central Accounts Payable (AP) ledger reconciliation across multi-store chains.
- **Deferral Rationale:** High integration complexity with heterogeneous distributor software. Over-engineering for pilot deployments.
- **Codified Interim Bridge in v1.6.5 ([§6 / §8](architecture_v1_6_5.md#8-invoicing-gst-credit-notes-debit-notes--delivery-challans)):** Stores issue sequential GST Supplier Debit Notes (`<STORE>-DN-...`) locally; reconciliation is managed manually in central AP bookkeeping.

#### 1.2 Central In-Transit Virtual Pool & 3PL Carrier Integration
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Chain Scale]`
- **Scope:** Chain-wide virtual in-transit inventory pool, automated 3PL freight carrier tracking APIs, and formal insurance carrier liability claims for regional warehouse logistics.
- **Deferral Rationale:** Requires enterprise hub-and-spoke infrastructure needed only when scaling beyond 5 pilot stores.
- **Codified Interim Bridge in v1.6.5 ([§6 / §8](architecture_v1_6_5.md#inter-store-stock-transfers--statutory-delivery-challans)):** Sequential Rule 55 Delivery Challans (`<STORE>-DC-...`) for intra-state road transit, and receipt discrepancy ingestion splitting intact vs breakage vs shortage.

---

### 2. Statutory & Government Gateway Integrations
#### 2.1 B2B E-Invoicing (IRN) via Government IRP Gateway
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Chain Scale]`
- **Scope:** Real-time generation of Invoice Reference Numbers (IRN) and signed QR codes via direct NIC/GSP API handshakes and asynchronous edge queues.
- **Deferral Rationale:** Over 95% of retail pharmacy sales are B2C (exempt from IRN under Rule 48(4)). Live government gateway handshakes introduce counter stalls.
- **Codified Interim Bridge in v1.6.5 ([§8](architecture_v1_6_5.md#invoicing-specifications)):** Stores generate sequential Store-Local B2B Tax Invoices (`<STORE>-B2B-...`) with buyer GSTIN for manual monthly GSTR-1 upload.

---

### 3. Distributed Edge Clustering & Synchronization
#### 3.1 Automated Standby Failover Clustering (Streaming Replication & VIP)
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Chain Scale]`
- **Scope:** Streaming Postgres replication, virtual IP (VIP) automatic rerouting, and distributed consensus fencing on edge PC hardware.
- **Deferral Rationale:** High risk of split-brain in retail edge environments with non-technical staff.
- **Codified Interim Bridge in v1.6.5 ([§2](architecture_v1_6_5.md#2-tech-stack--edge-infrastructure)):** Daily automated `pg_dump` replication, scripted promotion (`promote_to_primary.bat`) with LAN fencing, and emergency sequence epoch (`-F1`).

#### 3.2 Delta Replication Cursor Engine & Soft-Delete Tombstones
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Chain Scale]`
- **Scope:** Central pagination cursor engine (`version > :cursor ORDER BY version ASC LIMIT 500`) and bidirectional soft-delete tombstone synchronization across 50+ stores.
- **Deferral Rationale:** Standard polling operates reliably for pilot catalogs (<10k SKUs) without complex cursor migrations.
- **Codified Interim Bridge in v1.6.5 ([§5](architecture_v1_6_5.md#central-ingestion-atomicity--poison-pill-defense)):** Central batch push transaction atomicity with poison-pill isolation tombstones (`sync-quarantine-tombstone`).

#### 3.3 Cross-Store Store Credit Voucher Double-Spend Coordinator (2PL)
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Chain Scale]`
- **Scope:** Real-time distributed two-phase locking (2PL) across stores to allow redemption of store credit vouchers at any branch in the chain.
- **Deferral Rationale:** Requires 99.99% central cloud uptime; network partitions cause customer friction.
- **Codified Interim Bridge in v1.6.5 ([§8](architecture_v1_6_5.md#invoicing-specifications)):** Store Credit Vouchers are **strictly redeemable only at the issuing branch**.

---

### 4. Enterprise Security & Hardware Integration
#### 4.1 Hardware-Bound TPM 2.0 / DPAPI Silicon Key Sealing
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Enterprise Hardening]`
- **Scope:** Hardware TPM 2.0 Platform Configuration Register (PCR) sealing and Windows DPAPI machine key wrapping for AES-256 keys.
- **Deferral Rationale:** Pilot counters use diverse PC hardware lacking uniform TPM chips; requires C/Win32 FFI bindings.
- **Codified Interim Bridge in v1.6.5 ([§16](architecture_v1_6_5.md#16-security--data-protection)):** Hardened Windows File System ACLs (`icacls`) restricting keys strictly to `NT SERVICE\MedPOS`.

---

### 5. Enterprise Cloud & Customer Experience Capabilities
#### 5.1 Central Cloud Multi-Tenant Kubernetes Cluster
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Enterprise Infrastructure]`
- **Scope:** Auto-scaling Kubernetes clusters, managed cloud databases (AWS RDS / GCP Cloud SQL), and multi-region failover for 50+ stores.
- **Deferral Rationale:** High operational cost without pilot business value.
- **Codified Interim Bridge in v1.6.5 ([§2](architecture_v1_6_5.md#2-tech-stack--edge-infrastructure)):** Single low-cost Cloud VM running containerized Postgres 16 and FastAPI with off-site backups.

#### 5.2 Customer-Facing Dynamic UPI Secondary LCD Pole Display
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 In-Store Experience]`
- **Scope:** Real-time checkout display on a pole-mounted secondary LCD rendering dynamic NPCI UPI QR codes linked to live payment gateway webhooks.
- **Deferral Rationale:** Dual-head video driver complexity and payment aggregator enterprise contracts.
- **Codified Interim Bridge in v1.6.5 ([§8](architecture_v1_6_5.md#invoicing-specifications)):** Dynamic NPCI UPI QR string (`upi://pay?...`) printed directly on thermal paper receipts, paired with static counter soundboxes.

#### 5.3 Cashless Insurance / Third-Party Administrator (TPA) Direct Claims
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Enterprise Integration]`
- **Scope:** Real-time online pre-authorization and co-pay split billing with Indian health insurance TPAs (Medi Assist, Paramount).
- **Deferral Rationale:** Lengthy corporate empaneled onboarding and complex co-pay billing engines.
- **Codified Interim Bridge in v1.6.5 ([§9](architecture_v1_6_5.md#9-discounts)):** Manual tender metadata fields capturing Insurer Name, Policy Number, and Pre-Auth Code on standard GST invoices.

#### 5.4 Prescription Optical Character Recognition (OCR) AI Parsing
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 In-Store Experience]`
- **Scope:** Edge AI computer vision models automatically scanning and parsing cursive handwritten doctor prescriptions.
- **Deferral Rationale:** High error rate on handwritten prescriptions poses extreme liability if transcribed without 100% human verification.
- **Codified Interim Bridge in v1.6.5 ([§10.3](architecture_v1_6_5.md#103-schedule-x--ndps-dual-prescription-custody--bound-ledger)):** Digital webcam/scanner photo capture attached to dispense records with manual cashier entry.

#### 5.5 Automated WhatsApp & SMS Digital Invoice Delivery
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Customer Engagement]`
- **Scope:** Automated background dispatch of digital GST invoices and Credit Notes to WhatsApp and SMS via enterprise cloud gateways.
- **Deferral Rationale:** Meta WhatsApp Business API compliance and Indian Telecom DLT registration overhead.
- **Codified Interim Bridge in v1.6.5 ([§3](architecture_v1_6_5.md#3-core-modules)):** Cashier one-click WhatsApp Web share link (`wa.me`) with pre-formatted invoice text.

---

## Part II: Active Priority vs. Complexity Roadmap Matrix (Track B: Deferred for V2)

| Area / Feature | Impact | Complexity | Target Milestone | Deferral Rationale for V2 Major Iteration | Codified Interim Bridge in v1.6.5 |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **Automated Central Supplier Settlement (§1.1)** | High (Financial) | High | **Phase 2.0 (Chain Scale)** | Requires distributor EDI software bridges and automated AP reconciliation. | Local GST Debit Notes (`<STORE>-DN-...`); manual AP reconciliation. |
| **Central In-Transit Virtual Pool (§1.2)** | High (Logistics) | High | **Phase 2.0 (Chain Scale)** | Regional warehouse hub routing, 3PL logistics carrier APIs, and freight dispute arbitration. | Rule 55 Delivery Challans (`<STORE>-DC-...`) and receipt variance breakdown. |
| **B2B E-Invoicing (IRN) via IRP Gateway (§2.1)** | Medium (Compliance) | High | **Phase 2.0 (Chain Scale)** | 95%+ retail is B2C (exempt); live NIC/GSP API integration introduces queue latency. | Sequential B2B Invoices (`<STORE>-B2B-...`) with buyer GSTIN for manual GSTR-1. |
| **Automated Standby Clustering (§3.1)** | High (Availability) | High | **Phase 2.0 (Chain Scale)** | Streaming replication, VIP failover, and split-brain fencing overhead on edge PCs. | Scripted promotion (`promote_to_primary.bat`) with LAN fencing and `-F1` epoch. |
| **Delta Replication Cursor & Tombstones (§3.2)** | High (Reliability) | High | **Phase 2.0 (Chain Scale)** | Pilot catalogs (<10k SKUs) sync fine with standard polling; cursor requires schema overhaul. | Ingestion push atomicity with poison-pill quarantine tombstones. |
| **Cross-Store Voucher Double-Spend 2PL (§3.3)** | High (Financial) | High | **Phase 2.0 (Chain Scale)** | Requires 99.99% central cloud uptime, 2PL locking, and offline rejection fallbacks. | Vouchers strictly redeemable only at the issuing branch. |
| **Hardware-Bound TPM 2.0 Key Sealing (§4.1)** | Medium (Security) | High | **Phase 2.0 (Chain Scale)** | Requires C/Win32 FFI bindings, uniform TPM 2.0 chips, and Central RSA key escrow. | Windows File System ACLs (`icacls`) restricting keys to `NT SERVICE\MedPOS`. |
| **Central Cloud Multi-Tenant Cluster (§5.1)** | High (Infrastructure) | High | **Phase 2.0 (Chain Scale)** | Over-engineering for 2–5 pilot stores; high cloud operational expenditure. | Single low-cost Cloud VM running containerized Postgres + FastAPI with backups. |
| **Dynamic UPI Customer Secondary Display (§5.2)**| Medium (Operations) | Medium | **Phase 2.0 (Chain Scale)** | Dual-head display drivers, serial pole display protocols, and payment webhook matching. | Dynamic UPI QR on thermal paper receipts, plus countertop static UPI soundbox. |
| **Cashless Insurance / TPA Processing (§5.3)** | High (Business) | High | **Phase 2.0 (Chain Scale)** | High regulatory overhead, lengthy TPA onboarding, and co-pay split billing engines. | Manual "Insurance / TPA" tender method capturing policy and claim reference numbers. |
| **Prescription Vision OCR Parsing (§5.4)** | High (Experience) | High | **Phase 2.0 (Chain Scale)** | High error rate on cursive handwriting; extreme liability if incorrect dosages transcribed. | Digital webcam/scanner photo capture attached to local dispensing record. |
| **Automated WhatsApp / SMS Gateway (§5.5)** | Medium (Marketing) | Medium | **Phase 2.0 (Chain Scale)** | Meta WhatsApp Business API compliance, Indian Telecom DLT registration, and SMS gateways. | Cashier one-click `wa.me` browser link with pre-formatted invoice text. |

---

## Part III: Historical Milestone Archive

### Section A: v1.6 &rarr; v1.6.5 Resolved Baseline

The following 8 core architectural improvements, 4 interim bridges, and 8 hardened operational safeguards were designed, verified, and codified into the authoritative [architecture_v1_6_5.md](architecture_v1_6_5.md) specification:

#### 1. Retail Pharmacy & Inventory Lifecycle Hardening
- **1.1 Unit of Measure (UOM) Hierarchy & Fractional Dispensing (§3, §6):**
  - Stored batch inventory exclusively in atomic Base Dispensing Units (`tablets`, `capsules`, `ml`).
  - Enforced batch-level immutability for `pack_size`, `packaging_unit`, and `base_unit` to protect on-shelf stock counts from central catalog mutations.
  - Implemented Legal Metrology Rule 2011 rounding ($\operatorname{ROUND\_HALF\_UP}(\text{Strip MRP} / \text{Pack Size}, 2)$) with statutory upper bound price clamping ($\text{Subtotal} \le \text{Strip MRP}$).
  - Codified barcode scan invariant defaulting to 1 Packaging Unit ($1 \times \text{pack\_size}$ base units).
  - Codified sealed blister returns to active stock vs cut/punctured blister quarantine write-off.
- **1.2 Near-Expiry Vendor Returns (RTV) & Supplier Debit Notes (§5, §6, §8):**
  - Introduced configurable shelf-expiry alert tiers: 90d (Amber FEFO) / 60d (Orange RTV packing) / 30d (Red Shelf Quarantine).
  - Added `stock-move: rtv-quarantine` event.
  - Created sequential, offline GST Supplier Debit Notes: `<STORE_CODE>-DN-YYYYMM-XXXX`.
  - Replicated distributor profiles to stores for partition autonomy.
- **1.3 Rule 55 Statutory Delivery Challans & In-Transit Variance (§5, §6, §8):**
  - Implemented sequential offline Delivery Challans: `<STORE_CODE>-DC-YYYYMM-XXXX` for intra-state road transit.
  - Enforced statutory guard blocking Challans and mandating IGST Tax Invoices for inter-state branch movements under Section 7(4) of the IGST Act.
  - Ingested receipt discrepancies in `transfer-receive` splitting intact stock, quarantine breakage with photo audit, and shrinkage shortage flags.

#### 2. Regulatory Compliance Hardening (India)
- **2.1 Schedule X & NDPS Dual-Prescription Custody & Bound Ledger (§3, §5, §10):**
  - Mandated digital scanning/photo capture of duplicate prescriptions compressed to <250 KB WebP, encrypted with AES-256, and governed by a 90-day edge retention with 2-year cloud archive.
  - Captured registered Pharmacist PIN and State Pharmacy Council registration credentials.
  - Codified automated, immutable Daily Running Balance Ledger ($\text{Opening} + \text{Receipts} - \text{Dispensed} = \text{Closing}$).
  - Provided one-click State Drug Licensing Authority statutory return export.

#### 3. Edge Architecture & Distributed Reliability
- **3.1 In-Store Multi-Counter LAN Topology & Concurrency (§2, §4):**
  - Established Primary-Worker LAN architecture: Counter 1 (Primary Node) runs Postgres on `127.0.0.1` and FastAPI on LAN (`0.0.0.0:8000`); Counter 2/3 (Worker Terminals) run lightweight UI connecting over LAN via mDNS (`medpos-primary.local:8000`).
  - Preserved single sequence authority: monotonic `store_seq_no` and gapless `<STORE>-INV-...` series across all counters.
  - Scripted promotion (`promote_to_primary.bat`) with LAN reachability fencing and emergency failover sequence epoch (`<STORE>-INV-YYYYMM-XXXX-F1`).
- **3.2 Central Ingestion Push Atomicity & Poison-Pill Quarantine (§5):**
  - Wrapped Central batch ingestion and sequence watermarks in a single atomic database transaction (`BEGIN...COMMIT`).
  - Isolated malformed events into `central_sync_quarantine` while writing `sync-quarantine-tombstone` records to `central_events` to preserve sequence continuity without wedging the store retry queue.
- **3.3 POS Thermal Receipt Printer Jam Resilience (§3, §4, §8, Hardware):**
  - Implemented two-phase checkout commit (`COMMITTED_PENDING_PRINT` $\rightarrow$ `COMPLETED`).
  - Added non-blocking 300ms ESC/POS status polling with automatic OS print spooler fallback for write-only USB printers.
  - Synchronized cash drawer kick with print spool dispatch.
  - Handled customer abandonment during printer jams via automated void issuing an offsetting GST Credit Note (`<STORE>-CN-...`), preserving gapless invoice sequences.
- **3.4 Windows Edge File Security Hardening (§16):**
  - Locked down AES-256 database keys and environment files via Windows File System ACLs (`icacls`) strictly to `NT SERVICE\MedPOS`.

#### 4. Summary of 8 Hardened Operational Safeguards (v1.6.5)
1. **Legal Metrology Clamping Invariant (§6):** Strict upper bound on loose unit pricing ($\text{Subtotal} \le \text{Strip MRP}$), clamping full pack counts to prevent fractional rounding accumulation violations.
2. **Batch-Level Packaging Immutability (§6):** `pack_size` and UOM attributes locked immutably per batch at GRN, protecting historical counts against central catalog mutations.
3. **Standby Failover Fencing & Epochs (§2):** `promote_to_primary.bat` checks Counter 1 reachability to eliminate split-brain; applies emergency sequence epoch (`-F1`) on hardware loss.
4. **Poison-Pill Quarantine Tombstones (§5):** Malformed events route to `central_sync_quarantine` with `sync-quarantine-tombstone` in `central_events` to preserve sequence continuity without wedging the store retry queue.
5. **Printer Jam Abandonment Accounting (§8):** Formal GST Credit Note issuance on customer walkaway, preserving gapless invoice sequences.
6. **Statutory Road Transit Boundary Guard (§6, §8):** Rule 55 Delivery Challans restricted to intra-state moves; mandates IGST Tax Invoice across state borders.
7. **Storage & PII Protection (§10, §16):** Prescription photos compressed to <250 KB WebP, encrypted with AES-256, and pruned locally after 90 days following central cloud sync.
8. **In-Store Zero-Conf Networking (§2, §17):** Counter 1 mDNS broadcast (`medpos-primary.local:8000`) immunizes worker terminals against router DHCP IP reassignments.

---

### Resolved Baseline Matrix (v1.6 &rarr; v1.6.5)

| Area / Feature | Impact | Complexity | Status in v1.6.5 | Spec Reference |
| :--- | :---: | :---: | :---: | :---: |
| **UOM & Fractional Strip/Tablet Dispensing** | Critical (Operational) | Medium | **Resolved** | [architecture_v1_6_5.md §3, §6](architecture_v1_6_5.md#unit-of-measure-uom-hierarchy--fractional-billing) |
| **Schedule X & NDPS Dual Custody & Ledger** | Critical (Legal) | Medium | **Resolved** | [architecture_v1_6_5.md §10.3](architecture_v1_6_5.md#103-schedule-x--ndps-dual-prescription-custody--bound-ledger) |
| **In-Store Multi-Counter LAN Billing** | Critical (Integrity) | Medium | **Resolved** | [architecture_v1_6_5.md §2, §4](architecture_v1_6_5.md#local-first-store-node--multi-counter-lan) |
| **Near-Expiry Vendor Return (RTV) & Debit Notes**| High (Financial) | Medium | **Resolved** | [architecture_v1_6_5.md §5, §6, §8](architecture_v1_6_5.md#near-expiry-vendor-returns-rtv--alerts) |
| **Rule 55 Statutory Delivery Challans** | High (Legal/Accounting)| Medium | **Resolved** | [architecture_v1_6_5.md §5, §6, §8](architecture_v1_6_5.md#inter-store-stock-transfers--statutory-delivery-challans) |
| **Central Ingestion Push Atomicity & Quarantine**| High (Reliability) | Low | **Resolved** | [architecture_v1_6_5.md §5](architecture_v1_6_5.md#central-ingestion-atomicity--poison-pill-defense) |
| **POS Thermal Printer Resilience & 2-Phase** | High (Operational) | Low | **Resolved** | [architecture_v1_6_5.md §3, §4, §8](architecture_v1_6_5.md#8-invoicing-gst-credit-notes-debit-notes--delivery-challans) |
| **Windows OS File Security Hardening (`icacls`)** | Medium (Security) | Low | **Resolved** | [architecture_v1_6_5.md §16](architecture_v1_6_5.md#16-security--data-protection) |
| **Store-Local Sequential B2B Invoices** | Medium (Compliance) | Low | **Resolved** | [architecture_v1_6_5.md §8](architecture_v1_6_5.md#numbering-series-orthogonality) |
| **Dynamic NPCI UPI QR on Thermal Bill** | Medium (Operations) | Low | **Resolved** | [architecture_v1_6_5.md §8](architecture_v1_6_5.md#invoicing-specifications) |
| **Cashier One-Click WhatsApp Web Share** | Medium (Marketing) | Low | **Resolved** | [architecture_v1_6_5.md §3](architecture_v1_6_5.md#3-core-modules) |
| **Manual Insurance / TPA Tender Metadata** | High (Business) | Low | **Resolved** | [architecture_v1_6_5.md §9](architecture_v1_6_5.md#9-discounts) |

---

### Section B: v1.5 &rarr; v1.6 Resolved Baseline

The following 12 core architectural improvements and 8 operational safeguards were reviewed, designed, and fully integrated into the historical [architecture_v1_6.md](_archive/Prev_iterations/Architecture/architecture_v1_6.md) specification:

#### 1. Statutory & Regulatory Compliance Baseline
- **1.1 Absolute Expiry Hard-Block in All Modes:** Expiry made an unconditional hard-block across both Mandatory and Optional modes under Section 18 of the Drugs & Cosmetics Act, 1940.
- **1.2 Schedule H1 Register Record Completeness:** Expanded dispensing audit payload to include all 8 statutory parameters under Rule 65(9), encrypted customer PII under DPDP Act 2023, and implemented a one-click Drug Inspector audit export (CSV/PDF).
- **1.3 Store-Local Operational Walk-in Entities:** Decoupled Patients and Prescribers from central master data, classifying them as Store-Local Operational Entities (`<STORE>-PAT-<UUID>`, `<STORE>-DOC-<UUID>`) that are 100% offline-creatable.

#### 2. Retail Pharmacy & Inventory Lifecycle Baseline
- **2.1 Customer Sales Returns & GST Credit Notes:** Added `sale-return` event, condition-based restocking vs quarantine write-off, and sequential per-store GST Credit Notes (`<STORE>-CN-YYYYMM-XXXX`) conforming to Section 34 of the CGST Act.
- **2.2 Batch Selection Mechanics & Line-Item Splitting:** Implemented automated FEFO suggestions, scan-to-select priority override (physical 2D barcode scan strictly overrides FEFO), and automated multi-batch line splitting.
- **2.3 Physical vs. System Discrepancy & Non-Negative Stock:** Replaced negative stock with Manager-Authorized In-Line Adjustment (`stock-adjustment-in`) at POS with PIN authorization and central shrinkage audit flags.

#### 3. Distributed Systems & Sync Engine Mechanics Baseline
- **3.1 Store-Initiated Outbound Sync Architecture:** Formalized that all sync is strictly store-initiated outbound (HTTP polling/WebSockets) to operate reliably behind ISP CGNAT and dynamic IPs.
- **3.2 Idempotent Event Ingestion & Replay Protection:** Standardized envelope with UUID `event_id` and monotonic `store_seq_no`; Central enforces idempotency via `ON CONFLICT (event_id) DO NOTHING` and returns confirmed sequence watermarks.
- **3.3 Partition-Era Sales Ingestion for Soft-Deleted Products:** Central ingestion guarantees acceptance of partition-era sales, auto-clearing `deleted_at` if store stock remains or dispatching a manager write-off task.

#### 4. Authentication, Cashier & Infrastructure Baseline
- **4.1 Local Authentication During Network Partitions:** Replicated Argon2id password hashes locally; Store FastAPI issues store-scoped session JWTs (8–12h shift TTL) with local manager account revocation capability.
- **4.2 Shift Management & Day-End Till Reconciliation (Z-Report):** Added `shift-open`, `shift-close`, and manager `shift-force-close` events with automated Day-End Z-Reports calculating cashier till variance.
- **4.3 Unattended Store Postgres Maintenance:** Automated daily `pg_dump` with rolling 7-day retention, background WAL/VACUUM cleanup, and watchdog crash-loop throttling.

#### 5. Summary of 8 Hardened Operational Safeguards (v1.6)
1. **Clock-Skew Defense (§2):** Monotonic event time verification (`current_timestamp >= MAX(created_at)`) prevents dead CMOS batteries from corrupting sales.
2. **Scan-to-Select Priority (§6):** Physical 2D barcode scan strictly overrides automated FEFO suggestions.
3. **Restock Expiry & Cold-Chain Safeguard (§6):** Returned drugs re-check expiry; expired drugs and broken cold-chain items route to quarantine write-off.
4. **Partition Ghost Stock Auto-Resurrection (§6):** Central automatically restores soft-deleted products if partition sales reveal remaining store inventory.
5. **Shift Lockout Prevention (§13):** Manager `shift-force-close` override enables register handover if a cashier leaves without closing.
6. **Store Entity Namespaces (§4):** Store-prefixed permanent IDs (`<STORE>-PAT-<UUID>`) prevent cross-store ID collisions.
7. **Local Staff Revocation (§11):** Store Managers can disable compromised staff accounts locally during WAN network partitions.
8. **Automated Storage Retention (§2):** Rolling 7-day backup retention and watchdog backoff prevent disk full errors and high CPU crash loops.

---

### Resolved Baseline Matrix (v1.5 &rarr; v1.6)

| Area | Impact | Complexity | Status in v1.6 | Spec Reference |
| :--- | :---: | :---: | :---: | :---: |
| **Absolute Expiry Hard-Block** | Critical (Legal) | Low | **Resolved** | [_archive/Prev_iterations/Architecture/architecture_v1_6.md §10.1](_archive/Prev_iterations/Architecture/architecture_v1_6.md#101-absolute-expiry-hard-block) |
| **Store-Initiated Outbound Sync** | Critical (Architecture) | Low | **Resolved** | [_archive/Prev_iterations/Architecture/architecture_v1_6.md §4](_archive/Prev_iterations/Architecture/architecture_v1_6.md#store-initiated-outbound-sync-protocol) |
| **Schedule H1 Register Payload** | Critical (Legal) | Low | **Resolved** | [_archive/Prev_iterations/Architecture/architecture_v1_6.md §10.2](_archive/Prev_iterations/Architecture/architecture_v1_6.md#102-schedule-h1-register-payload-completeness) |
| **Sales Returns & GST Credit Notes** | High (Business) | Medium | **Resolved** | [_archive/Prev_iterations/Architecture/architecture_v1_6.md §5, §8](_archive/Prev_iterations/Architecture/architecture_v1_6.md#8-invoicing-gst--credit-notes) |
| **Batch Picking (FEFO) & Scan Priority**| High (Operations) | Medium | **Resolved** | [_archive/Prev_iterations/Architecture/architecture_v1_6.md §6](_archive/Prev_iterations/Architecture/architecture_v1_6.md#batch-selection--dispensing-mechanics) |
| **Offline Walk-in Patient/Doctor Creation** | High (Operations) | Low | **Resolved** | [_archive/Prev_iterations/Architecture/architecture_v1_6.md §4](_archive/Prev_iterations/Architecture/architecture_v1_6.md#operational-directories-vs-master-data) |
| **Event Idempotency Keys (UUIDs)** | High (Reliability) | Low | **Resolved** | [_archive/Prev_iterations/Architecture/architecture_v1_6.md §5](_archive/Prev_iterations/Architecture/architecture_v1_6.md#central-ingestion--idempotency) |
| **Partition-Era Soft-Delete Ingestion** | High (Integrity) | Low | **Resolved** | [_archive/Prev_iterations/Architecture/architecture_v1_6.md §6](_archive/Prev_iterations/Architecture/architecture_v1_6.md#deletion-requires-zero-stock--partition-era-sales-ingestion) |
| **Offline Local Auth & Credentials** | High (Availability) | Medium | **Resolved** | [_archive/Prev_iterations/Architecture/architecture_v1_6.md §2, §16](_archive/Prev_iterations/Architecture/architecture_v1_6.md#2-tech-stack--edge-infrastructure) |
| **Shift / Till Reconciliation (Z-Report)**| Medium (Business) | Medium | **Resolved** | [_archive/Prev_iterations/Architecture/architecture_v1_6.md §13](_archive/Prev_iterations/Architecture/architecture_v1_6.md#13-shift-management--day-end-till-reconciliation-z-report) |
| **Store Postgres Auto-Backup / Watchdog** | Medium (DevOps) | Medium | **Resolved** | [_archive/Prev_iterations/Architecture/architecture_v1_6.md §2, §17](_archive/Prev_iterations/Architecture/architecture_v1_6.md#2-tech-stack--edge-infrastructure) |
| **Stock Discrepancy & In-Line Adjustment**| Medium (Operations) | Low | **Resolved** | [_archive/Prev_iterations/Architecture/architecture_v1_6.md §6](_archive/Prev_iterations/Architecture/architecture_v1_6.md#stock-discrepancy--non-negative-stock-policy) |
