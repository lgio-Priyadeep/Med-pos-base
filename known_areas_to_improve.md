# Pharmacy POS — Architecture Roadmap & Engineering Gap Registry

This document serves as the authoritative, living engineering registry tracking architectural gaps, retail edge cases, regulatory requirements, and technical enhancements for the Pharmacy POS system.

The document is organized into three distinct parts:
- **[Part I: Active Architectural Gaps & Improvement Roadmap (v1.6 &rarr; v1.7 / v2.0)](#part-i-active-architectural-gaps--improvement-roadmap-v16--v17--v20)**: High-priority enhancements identified following the v1.6 specification baseline.
- **[Part II: Active Priority vs. Complexity Roadmap Matrix](#part-ii-active-priority-vs-complexity-roadmap-matrix)**: Strategic prioritization mapping items across Phase 1.7 (Pilot Hardening) and Phase 2.0 (Chain Scale).
- **[Part III: Historical Milestone Archive (v1.5 &rarr; v1.6 Resolved Baseline)](#part-iii-historical-milestone-archive-v15--v16-resolved-baseline)**: Verified record of the 12 core improvements and 8 operational safeguards codified into [architecture_v1_6.md](file:///c:/Users/surya/OneDrive/Desktop/med_pos/architecture_v1_6.md).

---

## Part I: Active Architectural Gaps & Improvement Roadmap (v1.6 &rarr; v1.7 / v2.0)

### 1. Retail Pharmacy & Fractional Inventory Lifecycle

#### 1.1 Unit of Measure (UOM) Hierarchy & Loose Strip/Tablet Fractional Sales
- **v1.6 Baseline:** Inventory models treat medicine items as discrete, single-unit quantities without an explicit packaging unit hierarchy.
- **Retail Reality & Operational Risk:**
  In Indian retail pharmacies, customers routinely request partial strips (e.g. 4 tablets of an antibiotic course or 5 capsules from a 15-pack strip). When systems lack native UOM conversion, cashiers either force customers to purchase whole strips (causing customer friction) or maintain an off-the-books "loose drawer" while billing full packs. This corrupts physical inventory tallies, skews reorder alerts, and distorts the Cost of Goods Sold (COGS).
- **Architectural Specification for v1.7:**
  - **Integer Base-Unit Storage:** Local Postgres stores and calculates batch inventory exclusively in atomic **Base Dispensing Units** (e.g., individual `tablets`, `capsules`, `ml`, `vials`).
  - **UOM Conversion Hierarchy:**
    - `packaging_unit`: Standard commercial packaging (e.g., "Strip of 10", "Box of 100", "Bottle of 60ml").
    - `base_unit`: Minimal dispensable atomic unit (e.g., "Tablet", "Capsule", "ml").
    - `pack_size`: Integer ratio representing the number of base units per packaging unit (e.g. 10 tablets/strip).
  - **Dual-Representation Display & Math:**
    $$\text{Pack Qty} = \text{Base Qty} \mathbin{//} \text{Pack Size}, \quad \text{Loose Qty} = \text{Base Qty} \pmod{\text{Pack Size}}$$
  - **Statutory Pricing & Fractional Rounding:**
    Under the Legal Metrology (Packaged Commodities) Rules, 2011, the maximum permitted unit price for cut strips is derived as:
    $$\text{Unit Price} = \operatorname{ROUND\_HALF\_UP}\left(\frac{\text{Strip MRP}}{\text{Pack Size}}, 2\right)$$
    The POS checkout engine guarantees that the sum of fractional line items does not exceed the statutory MRP of the complete pack.
  - **Fractional Return Policy:**
    Customers can return unconsumed, intact whole strips or uncut blister portions where the foil seal over each individual tablet remains 100% airtight and undamaged. Individual cut blister cavities with broken or punctured foil seals are legally deemed contaminated/opened and are **strictly prohibited from returning to active inventory**, automatically routing to `quarantine-write-off`.

#### 1.2 Near-Expiry Vendor Return Workflow (RTV & Supplier Debit Notes)
- **v1.6 Baseline:** Enforces an absolute hard-block when expiry $\le \text{current\_date}$ (§10.1) and routes expired customer returns to `quarantine-write-off`.
- **Operational Reality & Financial Risk:**
  Retail pharmacies cannot afford to retain stock until it expires. Indian pharmaceutical distributors/stockists legally accept unsold stock for commercial credit or refund under a **Breakage & Expiry Claim** only if returned **60 to 90 days prior to expiry** (or within a strict 30-day window post-expiry depending on distributor contracts). If stock remains on retail shelves until expiry, distributors reject commercial credit, inflicting 100% financial write-off loss on the pharmacy.
- **Architectural Specification for v1.7:**
  - **Configurable Near-Expiry Alerts:**
    Automated alerts configured per store:
    - *90 Days (Amber):* Highlights batches on POS inventory search; prioritizes automated FEFO suggestions.
    - *60 Days (Orange):* Triggers automated distributor Return-to-Vendor (RTV) packing suggestions.
    - *30 Days (Red):* Flags batches for immediate physical shelf quarantine.
  - **Return-to-Vendor Event (`stock-move: rtv-quarantine`):**
    Allows pharmacists to pull batches off the active billing shelf into a dedicated vendor-return quarantine bin. The event records `distributor_id`, `batch_id`, `quantity`, `purchase_invoice_ref`, and `reason: near-expiry-claim`.
  - **Sequential Supplier Debit Notes:**
    Store generates an official GST-compliant Debit Note: `<STORE_CODE>-DN-YYYYMM-XXXX`, detailing original purchase invoice number, distributor GSTIN, reversed tax components (CGST/SGST/IGST), and agreed claim value.
  - **Distributor Master Data Sync:**
    Distributor profiles (name, GSTIN, credit terms) replicate from Central down to stores, enabling full offline generation of RTV documents during network partitions.
  - **Settlement Tracking:**
    Central sync agent tracks the claim status lifecycle: `dispatched` $\rightarrow$ `acknowledged_by_vendor` $\rightarrow$ `credit_note_received` $\rightarrow$ `settled`.

#### 1.3 Inter-Store Stock In-Transit Reconciliation & Statutory Delivery Challans
- **v1.6 Baseline:** Supports `transfer-dispatch` and `transfer-receive` under `stock-move` (§5), but assumes immediate, variance-free receipt.
- **Operational Reality & Legal Gap:**
  1. *Physical Transportation Legality:* Under Rule 55 of the Indian CGST Rules, 2017, transporting pharmaceuticals between store branches without an accompanying tax invoice is illegal unless accompanied by an official, sequential **Delivery Challan** carrying vehicle numbers, HSN, batch numbers, and declared value.
  2. *In-Transit Loss / Breakage:* Transit between stores involves physical handling, heat, or road accidents. If Store A dispatches 100 ampoules, but Store B receives only 92 intact ampoules (5 broken in transit, 3 missing), existing specs provide no mechanism to reconcile the variance without corrupting one store's books.
- **Architectural Specification for v1.7:**
  - **Virtual In-Transit State:**
    Stock dispatched from Store A leaves Store A's local ledger and enters a Central-tracked `In-Transit` virtual pool:
    $$\text{Store A Stock} \mathrel{-}= Q_{\text{dispatch}}, \quad \text{In-Transit Stock} \mathrel{+}= Q_{\text{dispatch}}$$
  - **Statutory Delivery Challan Generation:**
    Source store issues a sequential Delivery Challan: `<STORE_CODE>-DC-YYYYMM-XXXX`, containing dispatcher GSTIN, recipient GSTIN, transport mode/vehicle number, HSN codes, batch/expiry details, and legal declaration: *"Goods transferred for internal branch stock, not for immediate sale"*.
  - **Discrepancy & Variance Ingestion at Receipt:**
    Store B receives the shipment and executes `transfer-receive` specifying:
    - `received_qty`: Actual accepted intact quantity (added to Store B active stock).
    - `transit_breakage_qty`: Damaged units (routed to Store B quarantine write-off with photo audit).
    - `transit_shortage_qty`: Missing units (triggers a transit shortage investigation event on Central).
  - Central ledger automatically reconciles and clears the `In-Transit` pool:
    $$\text{In-Transit Stock} \mathrel{-}= (Q_{\text{received}} + Q_{\text{breakage}} + Q_{\text{shortage}})$$

---

### 2. Statutory & Regulatory Hardening (India)

#### 2.1 Schedule X & NDPS Dual-Prescription Custody & Bound Ledger Maintenance
- **v1.6 Baseline:** Mandates Schedule H1 register compliance (§10.2), capturing 8 statutory parameters and 3-year audit retention.
- **Statutory Reality & Extreme Liability:**
  Schedule X drugs (e.g., Ketamine, Methylphenidate, Barbiturates) and NDPS (Narcotic Drugs and Psychotropic Substances) represent the highest tier of regulatory liability in Indian retail pharmacy. Under Rule 65 of the Drugs and Cosmetics Rules:
  1. Prescriptions must be written in **duplicate**. The pharmacy must physically endorse and **retain the original prescription for 2 years**.
  2. The pharmacy must maintain a separate, **bound Schedule X register** with sequentially numbered pages.
  3. The register must record daily running balances (Opening Stock + Receipts - Dispensed = Closing Stock) for every batch, cross-checked daily.
  4. Pharmacists must submit periodic statutory returns to the State Drug Licensing Authority.
- **Architectural Specification for v1.7:**
  - **Prescription Digital Archival:** Dispensing requires mandatory physical scanning or webcam photo capture of the original prescription, retained locally in encrypted storage and synced to Central.
  - **Dual-Pharmacist Verification / High-Security PIN:** Dispensing Schedule X drugs requires authorization from a registered Pharmacist PIN and records State Pharmacy Council registration credentials.
  - **Automated Daily Running Balance Ledger:**
    The system generates an automated, immutable daily Schedule X balance report comparing opening batch counts, GRN receipts, sales, and closing balance, flagging any physical variance immediately.
  - **One-Click State Licensing Authority Statutory Return:** Export format matching Schedule X statutory reporting templates for submission to the Assistant Drugs Controller.

#### 2.2 B2B E-Invoicing (IRN) & Dynamic QR Integration
- **v1.6 Baseline:** Store generates sequential B2C invoices `<STORE_CODE>-INV-YYYYMM-XXXX` locally.
- **Statutory Reality & Architectural Balance:**
  Under Section 31 and Rule 48(4) of the CGST Rules, any registered entity supplying to other registered businesses (B2B) must generate an **Invoice Reference Number (IRN)** and digitally signed QR code via the government's Invoice Registration Portal (IRP). While retail B2C cash sales are exempt, pharmacies regularly supply to local doctor clinics, nursing homes, institutional accounts, and B2B corporate customers.
- **Architectural Specification for v1.7 (Preserving Offline-First):**
  - **B2C vs. B2B Checkout Classification:**
    - Cashier selects "Retail / Patient" (B2C) $\rightarrow$ 100% offline local invoice generation, exempt from IRN.
    - Cashier enters customer GSTIN (B2B) $\rightarrow$ Activates e-invoicing workflow.
  - **Online Flow (WAN Available):**
    Store pushes invoice payload to Central or directly calls the IRP API; receives 64-character hash IRN and signed QR code; prints standard e-invoice.
  - **Offline Flow (WAN Partitioned):**
    To avoid stopping critical patient care in clinics, the POS issues a **Provisional B2B Delivery Invoice / Challan** (`<STORE_CODE>-PROV-YYYYMM-XXXX`) carrying a prominent legal disclaimer: *"Provisional B2B supply pending IRN generation under Rule 48(4)"*.
  - **Asynchronous Reconciliation Queue:**
    The Central sync agent ingests the provisional B2B invoice, submits it to the IRP within the legally permitted reconciliation window, obtains the official IRN, and pushes the signed document back down to the store for reprint/customer dispatch.

---

### 3. Edge Architecture, In-Store Scaling & Distributed Integrity

#### 3.1 In-Store Multi-Counter LAN Topology & Counter Failover
- **v1.6 Baseline:** States that each store runs "FastAPI + local Postgres on a local counter PC or in-store mini-server" (§4).
- **Operational Reality & Concurrency Risk:**
  A busy retail pharmacy operates 2 to 4 checkout counters simultaneously. If each counter ran an independent Postgres instance and local event stream, Counter 1 and Counter 2 would maintain separate stock tallies and duplicate invoice number series, causing stock overselling and severe GST invoice sequence collisions.
- **Architectural Specification for v1.7:**
  - **In-Store LAN Primary-Worker Architecture:**
    - **Primary Store Node (In-Store Mini-Server or Counter 1 PC):** Hosts the authoritative Store Postgres database, the local event engine, and the Store FastAPI sync agent.
    - **Worker Terminals (Counter 2, Counter 3):** Run lightweight client applications (desktop web UI / Electron shell) connecting directly to the Primary Node over the store's Gigabit Ethernet / isolated WPA3 Wi-Fi LAN.
  - **Single Store Sequence Authority:**
    All transactions from all counters in the store commit against the Primary Node's Postgres database within local serializable transactions. Monotonic sequence numbering (`store_seq_no`) and invoice numbering (`<STORE_CODE>-INV-...`) remain strictly linear and gapless across all counters.
  - **Warm-Standby Counter Failover:**
    Secondary Counter 2 is configured as a warm standby. Daily `pg_dump` backups or Postgres streaming replication on LAN keep Counter 2's standby Postgres updated. If Counter 1 suffers a catastrophic hardware failure (motherboard/SSD burn), the store manager executes a single-step failover script on Counter 2:
    `promote_to_primary.bat`, which updates local network routes and resumes billing within 5 minutes.

#### 3.2 Atomic Push Batches & Delta Master-Data Replication Cursor
- **v1.6 Baseline:** Stores push batches of queued events to Central; Central dedupes via `ON CONFLICT (event_id) DO NOTHING` and returns sequence watermarks.
- **Distributed Edge Case:**
  1. *Partial Batch Network Drops:* If a store pushes 100 events, Central processes 40, and the cellular connection drops before Central sends the response, what happens? If Central didn't use an atomic transaction boundary, events 1..40 are committed on Central, but the store believes all 100 failed and will retry all 100.
  2. *Downstream Bandwidth Bloat:* If master data contains 25,000 drug SKUs, returning catalog data in heartbeat responses without cursor tracking exhausts store cellular bandwidth.
- **Architectural Specification for v1.7:**
  - **Central Batch Ingestion Atomicity:**
    Central wraps each incoming store event batch inside a single atomic database transaction:
    ```sql
    BEGIN;
      INSERT INTO central_events (...) VALUES (...) ON CONFLICT (event_id) DO NOTHING;
      UPDATE store_sync_watermarks SET last_committed_seq = :max_seq WHERE store_id = :store_id;
    COMMIT;
    ```
    If connection drops mid-batch, the entire batch rolls back on Central. If committed, the store's subsequent retry is completely absorbed by the idempotent PK constraint.
  - **Delta Master-Data Sync Cursor:**
    Store sync requests submit a `master_data_version_cursor` (e.g. `1042`). Central queries only records updated since version 1042:
    ```sql
    SELECT * FROM master_catalog WHERE version > :cursor ORDER BY version ASC LIMIT 500;
    ```
  - **Tombstone Replication for Soft-Deletes:**
    Soft-deleted catalog items (`deleted_at IS NOT NULL`) are explicitly delivered in delta payloads with `action: deactivate`, ensuring stores remove deactivated products from active search menus without losing historical reference.

#### 3.3 Cross-Store Customer Store Credit & Double-Spend Prevention
- **v1.6 Baseline:** Implements GST Credit Notes for sales returns (§8), restricted offline to the issuing store.
- **Retail Reality & Financial Risk:**
  When customers return medications, pharmacies frequently issue a "Store Credit / Wallet Voucher" instead of physical cash. If a customer receives a ₹1,000 credit voucher at Store A, they may visit Store B in the same chain to buy expensive drugs. If Store B operates offline, Store B has no way to verify whether the voucher was already redeemed at Store A or Store C.
- **Architectural Specification for v1.7:**
  - **Issuing-Store Offline Autonomy:**
    A store credit voucher can **always be redeemed offline at the issuing store** where the credit note was generated, because the local Postgres database holds authoritative ledger truth.
  - **Cross-Store Gated Redemption (Network Required):**
    If a customer presents a Store A voucher at Store B, redemption **strictly requires live Central connectivity**.
    - Store B executes a real-time Two-Phase Lock (2PL) API call against Central:
      `POST /api/v1/vouchers/redeem` (verifies balance, locks voucher ID, decrements balance).
    - If Store B is offline, the POS displays a clear, polite modal: *"Cross-Store Credit Voucher requires network connectivity to verify balance. Please pay via Cash/UPI or redeem at original store."*
    - This eliminates the distributed double-spending vulnerability while preserving 100% offline autonomy for local store operations.

---

### 4. Edge Resiliency, Peripheral Faults & Security Hardening

#### 4.1 POS Thermal Receipt Printer Jam & Transaction Rollback Resilience
- **v1.6 Baseline:** Hardware module covers barcode scanner and thermal receipt printer (§3, §57).
- **Operational Reality & Cashier Confusion:**
  In retail checkouts, thermal printers frequently run out of paper rolls, suffer cutter blade jams, or have loose USB cables. If the system commits the transaction and immediately attempts to print without hardware status checks:
  - If it fails, cashiers often assume the sale did not register and ring up the customer a second time, charging them twice and double-deducting batch inventory.
- **Architectural Specification for v1.7:**
  - **Two-Phase Checkout State Machine:**
    1. Financial & Inventory Commit (`STATUS: COMMITTED_PENDING_PRINT`). Database transaction commits, batch stock decrements, cash drawer kicks open via ESC/POS command.
    2. Spooler ACK (`STATUS: COMPLETED`). System queries printer status bytes via ESC/POS command (`DLE EOT 1` / paper-out / error sensor).
  - **Graceful Error Recovery UI:**
    If the printer reports an error or fails to respond, the checkout UI displays a prominent banner:
    *"Sale #INV-1029 Recorded Successfully. Printer Error: Paper Out / Jammed. Replace paper roll and click Reprint."*
  - **Audited Duplicate Reprint Safeguard:**
    Reprinting any invoice prints a prominent header: `*** DUPLICATE COPY ***` along with cashier ID and reprint timestamp, preventing fraudulent multiple returns of the same bill.

#### 4.2 Local Hardware-Bound Cryptographic Key Management (DPAPI / TPM 2.0)
- **v1.6 Baseline:** Patient names and residential addresses encrypted at rest using AES-256 in store Postgres under DPDP Act, 2023 (§16).
- **Security Vulnerability:**
  If the AES-256 database encryption master key is stored in a plaintext configuration file (`.env` or `config.json`) on the counter PC, an attacker or disgruntled employee stealing the physical PC / hard drive can extract both the database and the key together, defeating the entire encryption architecture.
- **Architectural Specification for v1.7:**
  - **OS-Bound Key Wrapping via Windows DPAPI / TPM:**
    The store's AES-256 database master key is never stored in plaintext on disk.
    - On Windows POS terminals, the key is encrypted using the **Windows Data Protection API (DPAPI)** with `CRYPTPROTECT_LOCAL_MACHINE` and machine-specific cryptographic entropy.
    - On modern hardware with TPM 2.0 (Trusted Platform Module), the key is sealed against the system's PCR (Platform Configuration Register) state.
  - **Drive Theft Invalidation:**
    If the hard drive is removed and plugged into another computer, the DPAPI/TPM unsealing fails, rendering the encrypted patient database unreadable.
  - **Central Recovery Key Escrow:**
    During initial store setup, an emergency recovery key is encrypted with Central's RSA-4096 public key and stored centrally, allowing disaster recovery in case of motherboard replacement.

---

## Part II: Active Priority vs. Complexity Roadmap Matrix

The following matrix organizes the active engineering areas into targeted development milestones:

| Area | Impact | Complexity | Target Milestone | Rationale / Driver |
| :--- | :---: | :---: | :---: | :--- |
| **UOM & Loose Tablet Dispensing (§1.1)** | **Critical** (Operational) | Medium | **Phase 1.7 (Pilot Hardening)** | Mandatory for real-world counter billing; prevents loose-tablet off-book drawers. |
| **In-Store Multi-Counter LAN Topology (§3.1)** | **Critical** (Integrity) | Medium | **Phase 1.7 (Pilot Hardening)** | Required for multi-counter stores to prevent stock and sequence desync. |
| **Schedule X & NDPS Bound Register (§2.1)** | **Critical** (Legal) | Medium | **Phase 1.7 (Pilot Hardening)** | Criminal liability under D&C Act Rule 65; requires 2-year prescription retention. |
| **POS Thermal Printer Resilience (§4.1)** | **High** (Operational) | Low | **Phase 1.7 (Pilot Hardening)** | Prevents cashier double-billing and inventory corruption during paper jams. |
| **Near-Expiry Vendor Return (RTV) (§1.2)** | **High** (Financial) | Medium | **Phase 1.7 (Pilot Hardening)** | Prevents 100% stock loss by returning near-expiry items to distributors 60–90d early. |
| **Inter-Store Delivery Challans (Rule 55) (§1.3)** | **High** (Legal/Accounting) | Medium | **Phase 1.7 (Pilot Hardening)** | CGST Rule 55 statutory requirement for road transit; reconciles breakage. |
| **Atomic Sync Push & Delta Cursor (§3.2)** | **High** (Reliability) | Medium | **Phase 2.0 (Chain Scale)** | Prevents cellular data exhaustion on large catalogs and ensures push atomicity. |
| **Cross-Store Voucher Double-Spend Guard (§3.3)** | **High** (Financial) | Low | **Phase 2.0 (Chain Scale)** | Eliminates voucher double-spending across chain branches during network partitions. |
| **DPAPI / TPM Hardware Key Binding (§4.2)** | **Medium** (Security) | Low | **Phase 2.0 (Chain Scale)** | Hardens DPDP Act patient privacy against physical hard drive theft. |
| **B2B E-Invoicing (IRN) Asynchronous Queue (§2.2)** | **Medium** (Compliance) | High | **Phase 2.0 (Chain Scale)** | Required for institutional/clinic B2B supplies; preserves B2C retail offline speed. |

---

## Part III: Historical Milestone Archive (v1.5 &rarr; v1.6 Resolved Baseline)

The following 12 core architectural improvements and 8 operational safeguards were reviewed, designed, and fully integrated into the authoritative [architecture_v1_6.md](file:///c:/Users/surya/OneDrive/Desktop/med_pos/architecture_v1_6.md) specification:

### 1. Statutory & Regulatory Compliance Baseline
- **1.1 Absolute Expiry Hard-Block in All Modes (§10.1):**
  - *v1.5 Baseline:* Allowed `Optional` compliance mode where expiry became a warning.
  - *Resolution in v1.6:* Made expiry an unconditional hard-block across both `Mandatory` and `Optional` modes under Section 18 of the Drugs & Cosmetics Act, 1940.
- **1.2 Schedule H1 Register Record Completeness (§10.2):**
  - *v1.5 Baseline:* Omitted patient address, doctor clinic address, council registration, and manufacturer.
  - *Resolution in v1.6:* Expanded dispensing audit payload to include all 8 statutory parameters under Rule 65(9), added encrypted customer PII under DPDP Act 2023, and implemented a one-click Drug Inspector audit export (CSV/PDF).
- **1.3 Store-Local Operational Walk-in Entities (§3, §4):**
  - *v1.5 Baseline:* Patient and doctor creation required live central master-data connectivity.
  - *Resolution in v1.6:* Decoupled Patients and Prescribers from master data, classifying them as Store-Local Operational Entities (`<STORE>-PAT-<UUID>`, `<STORE>-DOC-<UUID>`) that are 100% offline-creatable.

### 2. Retail Pharmacy & Inventory Lifecycle Baseline
- **2.1 Customer Sales Returns & GST Credit Notes (§3, §5, §8):**
  - *v1.5 Baseline:* Lacked sales returns and credit note mechanisms.
  - *Resolution in v1.6:* Added `sale-return` event, condition-based restocking vs. quarantine write-off, and sequential per-store GST Credit Notes (`<STORE>-CN-YYYYMM-XXXX`) conforming to Section 34 of the CGST Act.
- **2.2 Batch Selection Mechanics & Line-Item Splitting (§6):**
  - *v1.5 Baseline:* Lacked selection rules and line splitting.
  - *Resolution in v1.6:* Implemented automated FEFO (First Expired, First Out) suggestions, scan-to-select priority override (physical 2D barcode scan strictly overrides FEFO), and automated multi-batch line splitting.
- **2.3 Physical vs. System Discrepancy & Non-Negative Stock (§6):**
  - *v1.5 Baseline:* Prohibited adjustments at checkout, risking patient treatment halt.
  - *Resolution in v1.6:* Replaced negative stock with Manager-Authorized In-Line Adjustment (`stock-adjustment-in`) at POS with PIN authorization and central shrinkage audit flags.

### 3. Distributed Systems & Sync Engine Mechanics Baseline
- **3.1 Store-Initiated Outbound Sync Architecture (§4):**
  - *v1.5 Baseline:* Described master data as "pushed down to stores".
  - *Resolution in v1.6:* Formalized that all sync is strictly store-initiated outbound (HTTP polling/WebSockets) to operate reliably behind ISP CGNAT and dynamic IPs.
- **3.2 Idempotent Event Ingestion & Replay Protection (§5):**
  - *v1.5 Baseline:* Lacked envelope schema and deduplication keys.
  - *Resolution in v1.6:* Standardized envelope with UUID `event_id` and monotonic `store_seq_no`; Central enforces idempotency via `ON CONFLICT (event_id) DO NOTHING` and returns confirmed sequence watermarks.
- **3.3 Partition-Era Sales Ingestion for Soft-Deleted Products (§6):**
  - *v1.5 Baseline:* Risk of rejecting sales made offline for products soft-deleted centrally.
  - *Resolution in v1.6:* Central ingestion guarantees acceptance of partition-era sales, auto-clearing `deleted_at` if store stock remains or dispatching a manager write-off task.

### 4. Authentication, Cashier & Infrastructure Baseline
- **4.1 Local Authentication During Network Partitions (§2, §16):**
  - *v1.5 Baseline:* Depended on central identity connectivity for JWT token issuance.
  - *Resolution in v1.6:* Replicated Argon2id password hashes locally; Store FastAPI issues store-scoped session JWTs (8–12h shift TTL) with local manager account revocation capability.
- **4.2 Shift Management & Day-End Till Reconciliation (Z-Report) (§5, §13):**
  - *v1.5 Baseline:* Lacked shift open/close tracking and physical drawer reconciliation.
  - *Resolution in v1.6:* Added `shift-open`, `shift-close`, and manager `shift-force-close` events with automated Day-End Z-Reports calculating cashier till variance.
- **4.3 Unattended Store Postgres Maintenance (§2, §17):**
  - *v1.5 Baseline:* Lacked unattended database maintenance specs.
  - *Resolution in v1.6:* Automated daily `pg_dump` with rolling 7-day retention, background WAL/VACUUM cleanup, and watchdog crash-loop throttling.

### 5. Summary of 8 Hardened Operational Safeguards (v1.6)
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
| **Absolute Expiry Hard-Block** | Critical (Legal) | Low | **Resolved** | [architecture_v1_6.md §10.1](file:///c:/Users/surya/OneDrive/Desktop/med_pos/architecture_v1_6.md#101-absolute-expiry-hard-block) |
| **Store-Initiated Outbound Sync** | Critical (Architecture) | Low | **Resolved** | [architecture_v1_6.md §4](file:///c:/Users/surya/OneDrive/Desktop/med_pos/architecture_v1_6.md#store-initiated-outbound-sync-protocol) |
| **Schedule H1 Register Payload** | Critical (Legal) | Low | **Resolved** | [architecture_v1_6.md §10.2](file:///c:/Users/surya/OneDrive/Desktop/med_pos/architecture_v1_6.md#102-schedule-h1-register-payload-completeness) |
| **Sales Returns & GST Credit Notes** | High (Business) | Medium | **Resolved** | [architecture_v1_6.md §5, §8](file:///c:/Users/surya/OneDrive/Desktop/med_pos/architecture_v1_6.md#8-invoicing-gst--credit-notes) |
| **Batch Picking (FEFO) & Scan Priority**| High (Operations) | Medium | **Resolved** | [architecture_v1_6.md §6](file:///c:/Users/surya/OneDrive/Desktop/med_pos/architecture_v1_6.md#batch-selection--dispensing-mechanics) |
| **Offline Walk-in Patient/Doctor Creation** | High (Operations) | Low | **Resolved** | [architecture_v1_6.md §4](file:///c:/Users/surya/OneDrive/Desktop/med_pos/architecture_v1_6.md#operational-directories-vs-master-data) |
| **Event Idempotency Keys (UUIDs)** | High (Reliability) | Low | **Resolved** | [architecture_v1_6.md §5](file:///c:/Users/surya/OneDrive/Desktop/med_pos/architecture_v1_6.md#central-ingestion--idempotency) |
| **Partition-Era Soft-Delete Ingestion** | High (Integrity) | Low | **Resolved** | [architecture_v1_6.md §6](file:///c:/Users/surya/OneDrive/Desktop/med_pos/architecture_v1_6.md#deletion-requires-zero-stock--partition-era-sales-ingestion) |
| **Offline Local Auth & Credentials** | High (Availability) | Medium | **Resolved** | [architecture_v1_6.md §2, §16](file:///c:/Users/surya/OneDrive/Desktop/med_pos/architecture_v1_6.md#local-authentication) |
| **Shift / Till Reconciliation (Z-Report)**| Medium (Business) | Medium | **Resolved** | [architecture_v1_6.md §13](file:///c:/Users/surya/OneDrive/Desktop/med_pos/architecture_v1_6.md#13-shift-management--day-end-till-reconciliation-z-report) |
| **Store Postgres Auto-Backup / Watchdog** | Medium (DevOps) | Medium | **Resolved** | [architecture_v1_6.md §2, §17](file:///c:/Users/surya/OneDrive/Desktop/med_pos/architecture_v1_6.md#unattended-database-maintenance) |
| **Stock Discrepancy & In-Line Adjustment**| Medium (Operations) | Low | **Resolved** | [architecture_v1_6.md §6](file:///c:/Users/surya/OneDrive/Desktop/med_pos/architecture_v1_6.md#stock-discrepancy--non-negative-stock-policy) |
