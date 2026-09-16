# Pharmacy POS — Architecture Roadmap & Engineering Gap Registry

This document serves as the authoritative, living engineering registry tracking architectural gaps, retail edge cases, regulatory requirements, and technical enhancements for the Pharmacy POS system.

The document is organized into three distinct parts:
- **[Part I: Active Architectural Gaps & Improvement Roadmap (v1.6 &rarr; v1.7 / v2.0)](#part-i-active-architectural-gaps--improvement-roadmap-v16--v17--v20)**: Detailed architectural analysis of active gaps, categorized by delivery feasibility (Incremental Iterations vs. Deferred V2 Major Iteration).
- **[Part II: Active Priority vs. Complexity Roadmap Matrix](#part-ii-active-priority-vs-complexity-roadmap-matrix)**: Strategic prioritization separating **Track A (Feasible for Smaller Incremental Iterations)** from **Track B (Intentionally Deferred for V2 Major Iteration)**.
- **[Part III: Historical Milestone Archive (v1.5 &rarr; v1.6 Resolved Baseline)](#part-iii-historical-milestone-archive-v15--v16-resolved-baseline)**: Verified record of the 12 core improvements and 8 operational safeguards codified into [architecture_v1_6.md](file:///c:/Users/surya/OneDrive/Desktop/med_pos/architecture_v1_6.md).

---

## Part I: Active Architectural Gaps & Improvement Roadmap (v1.6 &rarr; v1.7 / v2.0)

### 1. Retail Pharmacy & Fractional Inventory Lifecycle

#### 1.1 Unit of Measure (UOM) Hierarchy & Loose Strip/Tablet Fractional Sales
`[Feasible for Incremental Iteration — Phase 1.7 / Pilot Hardening]`
- **v1.6 Baseline:** Inventory models treat medicine items as discrete, single-unit quantities without an explicit packaging unit hierarchy.
- **Retail Reality & Operational Risk:**
  In Indian retail pharmacies, customers routinely request partial strips (e.g. 4 tablets of an antibiotic course or 5 capsules from a 15-pack strip). When systems lack native UOM conversion, cashiers either force customers to purchase whole strips (causing customer friction) or maintain an off-the-books "loose drawer" while billing full packs. This corrupts physical inventory tallies, skews reorder alerts, and distorts the Cost of Goods Sold (COGS).
- **Incremental Delivery Scope (Phase 1.7):**
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
- **Architectural Invariant:** 100% local database logic; zero WAN or central cloud dependencies.

#### 1.2 Near-Expiry Vendor Return Workflow (RTV & Supplier Debit Notes)
`[Hybrid Delivery: Store-Side RTV Feasible in Phase 1.7 | Central Settlement Deferred for V2]`
- **v1.6 Baseline:** Enforces an absolute hard-block when expiry $\le \text{current\_date}$ (§10.1) and routes expired customer returns to `quarantine-write-off`.
- **Operational Reality & Financial Risk:**
  Retail pharmacies cannot afford to retain stock until it expires. Indian pharmaceutical distributors/stockists legally accept unsold stock for commercial credit or refund under a **Breakage & Expiry Claim** only if returned **60 to 90 days prior to expiry** (or within a strict 30-day window post-expiry depending on distributor contracts). If stock remains on retail shelves until expiry, distributors reject commercial credit, inflicting 100% financial write-off loss on the pharmacy.
- **Feasible Incremental Delivery Scope (Phase 1.7 / Pilot Hardening):**
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
- **Deferral Rationale for V2 Major Iteration (Central Settlement):**
  - Automating the downstream distributor claim lifecycle (`dispatched` $\rightarrow$ `acknowledged_by_vendor` $\rightarrow$ `credit_note_received` $\rightarrow$ `settled`) requires Electronic Data Interchange (EDI) bridges into distributor enterprise software (e.g. Marg, MediVision) and central Accounts Payable (AP) ledger reconciliation across multi-store chains.
- **Feasible Incremental Interim Slice (Phase 1.7 / 1.8):**
  Stores generate and print the legal GST Debit Note locally; the physical return package and printed debit note are handed to the distributor sales representative, while financial settlement is reconciled manually in central bookkeeping until V2.

#### 1.3 Inter-Store Stock In-Transit Reconciliation & Statutory Delivery Challans
`[Hybrid Delivery: Store-Side Challans Feasible in Phase 1.7 | Central In-Transit Pool Deferred for V2]`
- **v1.6 Baseline:** Supports `transfer-dispatch` and `transfer-receive` under `stock-move` (§5), but assumes immediate, variance-free receipt.
- **Operational Reality & Legal Gap:**
  1. *Physical Transportation Legality:* Under Rule 55 of the Indian CGST Rules, 2017, transporting pharmaceuticals between store branches without an accompanying tax invoice is illegal unless accompanied by an official, sequential **Delivery Challan** carrying vehicle numbers, HSN, batch numbers, and declared value.
  2. *In-Transit Loss / Breakage:* Transit between stores involves physical handling, heat, or road accidents. If Store A dispatches 100 ampoules, but Store B receives only 92 intact ampoules (5 broken in transit, 3 missing), existing specs provide no mechanism to reconcile the variance without corrupting one store's books.
- **Feasible Incremental Delivery Scope (Phase 1.7 / Pilot Hardening):**
  - **Statutory Delivery Challan Generation:**
    Source store issues a sequential Delivery Challan: `<STORE_CODE>-DC-YYYYMM-XXXX`, containing dispatcher GSTIN, recipient GSTIN, transport mode/vehicle number, HSN codes, batch/expiry details, and legal declaration: *"Goods transferred for internal branch stock, not for immediate sale"*.
  - **Store Discrepancy & Variance Ingestion at Receipt:**
    Store B receives the shipment and executes `transfer-receive` specifying:
    - `received_qty`: Actual accepted intact quantity (added to Store B active stock).
    - `transit_breakage_qty`: Damaged units (routed to Store B quarantine write-off with photo audit).
    - `transit_shortage_qty`: Missing units (logged as shrinkage investigation flag).
- **Deferral Rationale for V2 Major Iteration (Virtual In-Transit Pool & Logistics Claims):**
  - Centrally managing a dynamic, chain-wide virtual `In-Transit` pool, automated third-party logistics (3PL) freight carrier tracking APIs, and formal insurance carrier liability claims requires enterprise hub-and-spoke infrastructure needed only when scaling beyond 5 pilot stores to regional warehouse distribution.
- **Feasible Incremental Interim Slice (Phase 1.7 / 1.8):**
  Both Store A and Store B maintain strict local stock sovereignty (Store A decrements on dispatch, Store B increments on receipt). Central aggregates transfer discrepancies purely as an audit shrinkage report without mutating store stock.

---

### 2. Statutory & Regulatory Hardening (India)

#### 2.1 Schedule X & NDPS Dual-Prescription Custody & Bound Ledger Maintenance
`[Feasible for Incremental Iteration — Phase 1.7 / Pilot Hardening]`
- **v1.6 Baseline:** Mandates Schedule H1 register compliance (§10.2), capturing 8 statutory parameters and 3-year audit retention.
- **Statutory Reality & Extreme Liability:**
  Schedule X drugs (e.g., Ketamine, Methylphenidate, Barbiturates) and NDPS (Narcotic Drugs and Psychotropic Substances) represent the highest tier of regulatory liability in Indian retail pharmacy. Under Rule 65 of the Drugs and Cosmetics Rules:
  1. Prescriptions must be written in **duplicate**. The pharmacy must physically endorse and **retain the original prescription for 2 years**.
  2. The pharmacy must maintain a separate, **bound Schedule X register** with sequentially numbered pages.
  3. The register must record daily running balances (Opening Stock + Receipts - Dispensed = Closing Stock) for every batch, cross-checked daily.
  4. Pharmacists must submit periodic statutory returns to the State Drug Licensing Authority.
- **Incremental Delivery Scope (Phase 1.7):**
  - **Prescription Digital Archival:** Dispensing requires mandatory physical scanning or webcam photo capture of the original prescription, retained locally in encrypted storage and synced to Central.
  - **Dual-Pharmacist Verification / High-Security PIN:** Dispensing Schedule X drugs requires authorization from a registered Pharmacist PIN and records State Pharmacy Council registration credentials.
  - **Automated Daily Running Balance Ledger:**
    The system generates an automated, immutable daily Schedule X balance report comparing opening batch counts, GRN receipts, sales, and closing balance, flagging any physical variance immediately:
    $$\text{Opening Balance} + \text{Receipts (GRN)} - \text{Dispensed} = \text{Closing Balance}$$
  - **One-Click State Licensing Authority Statutory Return:** Export format matching Schedule X statutory reporting templates for submission to the Assistant Drugs Controller.
- **Architectural Invariant:** Self-contained store-level compliance. Preserves offline autonomy with zero external cloud dependencies.

#### 2.2 B2B E-Invoicing (IRN) & Dynamic QR Integration
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Chain Scale]`
- **v1.6 Baseline:** Store generates sequential B2C invoices `<STORE_CODE>-INV-YYYYMM-XXXX` locally.
- **Statutory Reality & Architectural Balance:**
  Under Section 31 and Rule 48(4) of the CGST Rules, any registered entity supplying to other registered businesses (B2B) must generate an **Invoice Reference Number (IRN)** and digitally signed QR code via the government's Invoice Registration Portal (IRP). While retail B2C cash sales are exempt, pharmacies regularly supply to local doctor clinics, nursing homes, institutional accounts, and B2B corporate customers.
- **Deferral Rationale for V2 Major Iteration:**
  1. *Predominantly B2C Retail Flow:* Over 95% of retail pharmacy transactions are B2C patient walk-ins (which are legally exempt from IRN under Rule 48(4)).
  2. *External Government Gateway Complexity:* Direct integration with the government IRP via a GST Suvidha Provider (GSP) requires corporate enterprise GST credentials, dedicated static IP whitelisting, HSM SSL certificates, and live sandbox certification.
  3. *Asynchronous Queue Complexity:* An offline provisional queue with delayed IRN synchronization and reconciliation introduces high distributed state complexity on store terminals.
- **Feasible Incremental Interim Slice (Phase 1.7 / 1.8):**
  - Under Rule 46(b) of the CGST Rules, the POS introduces a distinct, sequential B2B invoice numbering series: `<STORE_CODE>-B2B-YYYYMM-XXXX` (decoupled from the retail B2C `<STORE_CODE>-INV-...` series).
  - Cashier enters the customer's 15-digit GSTIN $\rightarrow$ System generates a standard compliant Store-Local B2B Tax Invoice detailing buyer GSTIN, HSN summary, and CGST/SGST/IGST tax breakdowns.
  - The invoice carries an automated note: *"Standard B2B Tax Invoice — Offline Pilot Mode"*. The store accountant manually uploads monthly B2B sales data into the GST portal (GSTR-1) without stalling retail checkout lines or requiring live IRP API handshakes.

---

### 3. Edge Architecture, In-Store Scaling & Distributed Integrity

#### 3.1 In-Store Multi-Counter LAN Topology & Counter Failover
`[Hybrid Delivery: Primary-Worker LAN Feasible in Phase 1.7 | Automated Clustering Deferred for V2]`
- **v1.6 Baseline:** States that each store runs "FastAPI + local Postgres on a local counter PC or in-store mini-server" (§4).
- **Operational Reality & Concurrency Risk:**
  A busy retail pharmacy operates 2 to 4 checkout counters simultaneously. If each counter ran an independent Postgres instance and local event stream, Counter 1 and Counter 2 would maintain separate stock tallies and duplicate invoice number series, causing stock overselling and severe GST invoice sequence collisions.
- **Feasible Incremental Delivery Scope (Phase 1.7 / Pilot Hardening):**
  - **In-Store LAN Primary-Worker Architecture:**
    - **Primary Store Node (Counter 1 PC or In-Store Mini-Server):** Hosts the authoritative Store Postgres database and the Store FastAPI sync engine.
    - **Database Network Security ([architecture_v1_6.md §16](file:///c:/Users/surya/OneDrive/Desktop/med_pos/architecture_v1_6.md#16-security--data-protection)):** Store Postgres remains bound strictly to `127.0.0.1` on Counter 1. Only the Store FastAPI application listens on the store's private Gigabit Ethernet / WPA3 LAN (`0.0.0.0:8000` or `192.168.x.x:8000`).
    - **Worker Terminals (Counter 2, Counter 3):** Run lightweight client applications (desktop web UI / Electron shell) connecting via HTTP/WebSocket to Counter 1's FastAPI server, passing store-scoped session JWTs.
  - **Single Store Sequence Authority:**
    All transactions from all counters in the store commit against the Primary Node's Postgres database within local serializable transactions. Monotonic sequence numbering (`store_seq_no`) and invoice numbering (`<STORE_CODE>-INV-...`) remain strictly linear and gapless across all counters.
- **Deferral Rationale for V2 Major Iteration (Automated Failover Clustering):**
  - Automated zero-downtime database failover, streaming Postgres replication across store PCs, and automated virtual IP (VIP) rerouting introduce distributed split-brain hazards. In an edge environment with non-technical retail staff, automated clustering software often causes more downtime than it prevents.
- **Feasible Incremental Interim Slice (Phase 1.7 / 1.8):**
  Counter 2 is configured as a warm standby receiving automated daily `pg_dump` backups. If Counter 1 suffers physical hardware failure, the store manager executes a simple scripted fallback: `promote_to_primary.bat`, which starts the local Postgres service on Counter 2 and points network shortcuts to Counter 2 within 5 minutes.

#### 3.2 Atomic Push Batches & Delta Master-Data Replication Cursor
`[Hybrid Delivery: Ingestion Atomicity Feasible in Phase 1.7 | Delta Cursor Engine Deferred for V2]`
- **v1.6 Baseline:** Stores push batches of queued events to Central; Central dedupes via `ON CONFLICT (event_id) DO NOTHING` and returns sequence watermarks.
- **Distributed Edge Case:**
  1. *Partial Batch Network Drops:* If a store pushes 100 events, Central processes 40, and the cellular connection drops before Central sends the response, what happens? If Central didn't use an atomic transaction boundary, events 1..40 are committed on Central, but the store believes all 100 failed and will retry all 100.
  2. *Downstream Bandwidth Bloat:* If master data contains 25,000 drug SKUs, returning catalog data in heartbeat responses without cursor tracking exhausts store cellular bandwidth.
- **Feasible Incremental Delivery Scope (Phase 1.7 Quick Win):**
  - **Central Ingestion Push Atomicity:**
    Central wraps each incoming store event batch inside a single atomic database transaction:
    ```sql
    BEGIN;
      INSERT INTO central_events (...) VALUES (...) ON CONFLICT (event_id) DO NOTHING;
      UPDATE store_sync_watermarks SET last_committed_seq = :max_seq WHERE store_id = :store_id;
    COMMIT;
    ```
    If a connection drops mid-batch, the entire batch rolls back on Central. If committed, the store's subsequent retry is completely absorbed by the idempotent PK constraint.
- **Deferral Rationale for V2 Major Iteration (Delta Cursor Engine & Tombstones):**
  - In a pilot with 2–5 stores and catalog sizes under 10,000 SKUs, standard polling with existing version checks operates reliably without exhausting network bandwidth.
  - Designing a distributed delta version cursor engine (`version > :cursor ORDER BY version ASC LIMIT 500`) and bidirectional soft-delete tombstone synchronization across 50+ stores requires coordinated database schema migrations across Central and all store terminals.
- **Feasible Incremental Interim Slice (Phase 1.7 / 1.8):**
  Deploy Central push transaction atomicity in Phase 1.7 immediately; defer delta catalog pagination cursors and tombstone state engines to Phase 2.0.

#### 3.3 Cross-Store Customer Store Credit & Double-Spend Prevention
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Chain Scale]`
- **v1.6 Baseline:** Implements GST Credit Notes for sales returns (§8), restricted offline to the issuing store.
- **Retail Reality & Financial Risk:**
  When customers return medications, pharmacies frequently issue a "Store Credit / Wallet Voucher" instead of physical cash. If a customer receives a ₹1,000 credit voucher at Store A, they may visit Store B in the same chain to buy expensive drugs. If Store B operates offline, Store B has no way to verify whether the voucher was already redeemed at Store A or Store C.
- **Deferral Rationale for V2 Major Iteration:**
  - Real-time distributed voucher locking (Two-Phase Locking - 2PL) across stores requires 99.99% central cloud availability. When network partitions occur, denying customer redemptions causes counter friction.
  - In pilot deployments (2–5 local stores), cross-store voucher double-spending is statistically negligible compared to the operational overhead of a distributed transaction coordinator.
- **Feasible Incremental Interim Slice (Phase 1.7 / 1.8):**
  Preserve the proven [architecture_v1_6.md §8](file:///c:/Users/surya/OneDrive/Desktop/med_pos/architecture_v1_6.md#sales-returns--gst-credit-notes) baseline constraint:
  - Store Credit Vouchers are **strictly redeemable only at the issuing store** where the credit note was originally generated.
  - If a customer attempts to present a Store A voucher at Store B, the POS displays a clear, polite notice: *"Store credit vouchers are redeemable only at the issuing branch (Store A). For cross-store purchases, please pay via Cash/UPI."*
  - Centralized cross-store wallet redemption with real-time 2PL verification is formally deferred to V2.

---

### 4. Edge Resiliency, Peripheral Faults & Security Hardening

#### 4.1 POS Thermal Receipt Printer Jam & Transaction Rollback Resilience
`[Feasible for Incremental Iteration — Phase 1.7 / Quick Win]`
- **v1.6 Baseline:** Hardware module covers barcode scanner and thermal receipt printer (§3, §57).
- **Operational Reality & Cashier Confusion:**
  In retail checkouts, thermal printers frequently run out of paper rolls, suffer cutter blade jams, or have loose USB cables. If the system commits the transaction and immediately attempts to print without hardware status checks:
  - If it fails, cashiers often assume the sale did not register and ring up the customer a second time, charging them twice and double-deducting batch inventory.
- **Incremental Delivery Scope (Phase 1.7):**
  - **Two-Phase Checkout State Machine:**
    1. Financial & Inventory Commit (`STATUS: COMMITTED_PENDING_PRINT`). Database transaction commits, batch stock decrements, cash drawer kicks open via ESC/POS command.
    2. Spooler ACK (`STATUS: COMPLETED`). System queries printer status bytes via ESC/POS command (`DLE EOT 1` / paper-out / error sensor).
  - **Graceful Error Recovery UI:**
    If the printer reports an error or fails to respond, the checkout UI displays a prominent banner:
    *"Sale #INV-1029 Recorded Successfully. Printer Error: Paper Out / Jammed. Replace paper roll and click Reprint."*
  - **Audited Duplicate Reprint Safeguard:**
    Reprinting any invoice prints a prominent header: `*** DUPLICATE COPY ***` along with cashier ID and reprint timestamp, preventing fraudulent multiple returns of the same bill.
- **Architectural Invariant:** Purely client-side UI/hardware state machine; zero schema or sync changes.

#### 4.2 Local Hardware-Bound Cryptographic Key Management (DPAPI / TPM 2.0)
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Enterprise Hardening]`
- **v1.6 Baseline:** Patient names and residential addresses encrypted at rest using AES-256 in store Postgres under DPDP Act, 2023 (§16).
- **Security Vulnerability:**
  If the AES-256 database encryption master key is stored in a plaintext configuration file (`.env` or `config.json`) on the counter PC, an attacker or disgruntled employee stealing the physical PC / hard drive can extract both the database and the key together, defeating the entire encryption architecture.
- **Deferral Rationale for V2 Major Iteration:**
  - Implementing silicon-level Trusted Platform Module (TPM 2.0) Platform Configuration Register (PCR) sealing or Windows Data Protection API (DPAPI) machine key wrapping requires platform-specific native C/Win32 FFI bindings.
  - Pilot pharmacy counters often use budget or legacy PC hardware lacking uniform TPM 2.0 microchips.
  - Disaster recovery key escrow (encrypting recovery keys with Central RSA-4096 keys) introduces substantial centralized key management overhead.
- **Feasible Incremental Interim Slice (Phase 1.7 / 1.8):**
  - **OS File System Access Control Lists (ACLs):** Store the AES-256 key in an OS environment variable or restricted configuration file.
  - Windows file permissions are hardened during setup via standard scripts:
    `icacls "C:\medpos\config" /inheritance:r /grant:r "NT SERVICE\MedPOS":(R)`
    This denies read access to standard non-privileged Windows users on the counter PC, satisfying immediate DPDP Act security audits while deferring TPM silicon sealing to V2.

---

### 5. Enterprise Services & Emerging Capabilities (Phase 2 Roadmap Catalog from §18)

The following 5 capabilities originated as open items in [architecture_v1_6.md §18](file:///c:/Users/surya/OneDrive/Desktop/med_pos/architecture_v1_6.md#18-open-items-phase-2-roadmap). All 5 are intentionally deferred for the V2 Major Iteration, with defined interim operational bridges for Phase 1.7/1.8:

#### 5.1 Central Enterprise Cloud Multi-Tenant Cluster Sizing
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Enterprise Infrastructure]`
- **Scope:** Architecting auto-scaling Kubernetes clusters, managed cloud databases (AWS RDS / GCP Cloud SQL), read-replicas, and multi-region disaster recovery for 50+ store enterprise chains.
- **Deferral Rationale:** Over-engineering for pilot deployments (2–5 stores). Incurs high cloud operational expenditure without pilot business value.
- **Feasible Incremental Interim Slice (Phase 1.7 / 1.8):**
  Deploy a single low-cost Cloud Virtual Machine (e.g. 4 vCPU, 16 GB RAM, Ubuntu LTS) running containerized Postgres 16 and FastAPI with automated nightly off-site S3 backups.

#### 5.2 Customer-Facing Dynamic UPI Secondary LCD Display
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 In-Store Experience]`
- **Scope:** Real-time customer checkout display on a pole-mounted secondary LCD screen rendering dynamic NPCI UPI QR codes linked to live payment gateway Webhooks for automatic cashier screen reconciliation.
- **Deferral Rationale:** Requires dual-head video driver management, USB/serial customer display protocols, and payment aggregator (Razorpay/Pine Labs) enterprise API contracts.
- **Feasible Incremental Interim Slice (Phase 1.7 / 1.8):**
  1. Print a dynamic NPCI UPI QR string (`upi://pay?pa=...&am=...&pn=...&tr=...`) directly at the bottom of the 80mm thermal receipt.
  2. Use a standard counter-top static UPI Soundbox / QR stand (PhonePe / Paytm / Google Pay) where the cashier manually confirms receipt before closing the bill.

#### 5.3 Cashless Insurance / Third-Party Administrator (TPA) Direct Claims
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Enterprise Integration]`
- **Scope:** Direct online pre-authorization, member eligibility verification, and automated co-pay split billing integrated with Indian health insurance TPAs (e.g. Medi Assist, Paramount, Vidal Health) under IRDAI guidelines.
- **Deferral Rationale:** High regulatory overhead, lengthy corporate TPA empaneled onboarding, and complex co-pay billing state machines.
- **Feasible Incremental Interim Slice (Phase 1.7 / 1.8):**
  Add a manual "Insurance / TPA" tender payment method at checkout, capturing the Insurer Name, Policy Number, and Pre-Authorization Claim Approval Code as text metadata on standard GST invoices.

#### 5.4 Prescription Optical Character Recognition (OCR) & AI Parsing
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 In-Store Experience]`
- **Scope:** Automated optical scanning of handwritten doctor prescriptions via edge computer vision / AI models to automatically populate medicine line items and dosages on the dispensing screen.
- **Deferral Rationale:** High error rate on Indian doctors' cursive handwriting; poses extreme legal liability if incorrect dosages are machine-transcribed without 100% human verification.
- **Feasible Incremental Interim Slice (Phase 1.7 / 1.8):**
  Digital webcam / scanner image capture: The cashier clicks "Capture Prescription", attaches the JPEG image to the local dispensing record (meeting D&C Rule 65 custody rules), and manually keys in the line items.

#### 5.5 Automated WhatsApp & SMS Digital Invoice Delivery
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Customer Engagement]`
- **Scope:** Automated background dispatch of digital GST invoices and Credit Note PDFs to customer WhatsApp and SMS channels immediately upon checkout.
- **Deferral Rationale:** Requires Meta WhatsApp Business API accounts, Indian Telecom DLT (Distributed Ledger Technology) commercial template registrations, and external SMS gateway webhooks.
- **Feasible Incremental Interim Slice (Phase 1.7 / 1.8):**
  Cashier checkout screen provides a "Share via WhatsApp" quick-link (`https://wa.me/91<PHONE>?text=...`) which opens the WhatsApp Web client on the counter PC with pre-formatted invoice summary text, while continuing standard 80mm thermal paper receipts.

---

## Part II: Active Priority vs. Complexity Roadmap Matrix

The following matrices organize all active engineering gaps and roadmap items into two distinct, actionable delivery tracks:

### Track A: Feasible for Smaller Incremental Iterations (Phase 1.7 Pilot Hardening & Phase 1.8 Store Ops)

| Area / Feature | Impact | Complexity | Target Milestone | Incremental Delivery Scope & Invariant Protection |
| :--- | :---: | :---: | :---: | :--- |
| **UOM & Loose Tablet Dispensing (§1.1)** | **Critical** (Operational) | Medium | **Phase 1.7 (Pilot Hardening)** | Atomic base units (`tablets`), Legal Metrology rounding, and sealed-blister return policy. 100% local database logic. |
| **Schedule X & NDPS Bound Register (§2.1)** | **Critical** (Legal) | Medium | **Phase 1.7 (Pilot Hardening)** | Duplicate prescription image attachment, registered Pharmacist PIN, and daily running balance SQL report. |
| **In-Store Multi-Counter LAN Billing (§3.1)** | **Critical** (Integrity) | Medium | **Phase 1.7 (Pilot Hardening)** | Worker terminals hit Counter 1 FastAPI over LAN; Postgres stays bound to `127.0.0.1`. Single sequence authority. |
| **Near-Expiry Vendor Return (RTV) (§1.2)** | **High** (Financial) | Medium | **Phase 1.7 (Pilot Hardening)** | Store shelf-expiry alerts (90d/60d/30d), `rtv-quarantine` event, and local sequential GST Debit Notes (`<STORE>-DN-...`). |
| **Rule 55 Delivery Challans (§1.3)** | **High** (Legal/Accounting) | Medium | **Phase 1.7 (Pilot Hardening)** | Offline sequential Delivery Challan printing (`<STORE>-DC-...`) for road transport; receipt breakage/shortage logging. |
| **Central Ingestion Push Atomicity (§3.2)** | **High** (Reliability) | Low | **Phase 1.7 (Pilot Hardening)** | Wrap Central batch ingestion in single database transaction (`BEGIN...COMMIT`) to eliminate mid-batch drop desync. |
| **POS Thermal Printer Resilience (§4.1)** | **High** (Operational) | Low | **Phase 1.7 (Pilot Hardening)** | Two-phase checkout commit (`COMMITTED_PENDING_PRINT`), ESC/POS status polling, and duplicate reprint watermark. |
| **Interim OS File Access Key Lockdown (§4.2)** | **Medium** (Security) | Low | **Phase 1.7 (Pilot Hardening)** | Hardened OS file permissions (`icacls`) restricting AES-256 database keys strictly to the POS service account. |

---

### Track B: Intentionally Deferred for V2 Major Iteration (Phase 2.0 Chain Scale & Enterprise Services)

| Area / Feature | Impact | Complexity | Target Milestone | Deferral Rationale for V2 Major Iteration | Feasible Incremental Interim Slice (Phase 1.7 / 1.8) |
| :--- | :---: | :---: | :---: | :--- | :--- |
| **Automated Central Supplier Settlement (§1.2)** | High (Financial) | High | **Phase 2.0 (Chain Scale)** | Requires distributor EDI software bridges and automated multi-store AP ledger reconciliation. | Stores issue local GST Debit Notes; settlement reconciled manually in AP until V2. |
| **Central In-Transit Virtual Pool (§1.3)** | High (Logistics) | High | **Phase 2.0 (Chain Scale)** | Regional warehouse hub routing, 3PL logistics carrier APIs, and carrier dispute arbitration workflows. | Central aggregates transfer discrepancies purely as an audit shrinkage report. |
| **B2B E-Invoicing (IRN) via IRP Gateway (§2.2)** | Medium (Compliance) | High | **Phase 2.0 (Chain Scale)** | 95%+ retail is B2C (exempt); live NIC/GSP API integration and offline async queue require central infra. | Issue Store-Local B2B Invoice (`<STORE>-B2B-...`) with buyer GSTIN for manual portal upload. |
| **Automated Standby Clustering (§3.1)** | High (Availability) | High | **Phase 2.0 (Chain Scale)** | Streaming Postgres replication, virtual IP (VIP) failover, and split-brain fencing overhead on edge PCs. | Scripted one-step failover (`promote_to_primary.bat`) and daily `pg_dump` replication to standby PC. |
| **Delta Replication Cursor & Tombstones (§3.2)** | High (Reliability) | High | **Phase 2.0 (Chain Scale)** | Pilot catalogs (<10k SKUs) sync fine with standard polling; cursor engine requires central schema overhaul. | Ingestion push atomicity in Phase 1.7; catalog sync continues with standard heartbeat polling. |
| **Cross-Store Voucher Double-Spend 2PL (§3.3)** | High (Financial) | High | **Phase 2.0 (Chain Scale)** | Requires 99.99% central cloud uptime, distributed two-phase locking, and offline rejection fallbacks. | Vouchers are **strictly redeemable only at the issuing branch** (v1.6 rule preserved). |
| **Hardware-Bound TPM 2.0 Key Sealing (§4.2)** | Medium (Security) | High | **Phase 2.0 (Chain Scale)** | Requires C/Win32 FFI bindings, uniform TPM 2.0 hardware availability, and Central RSA key escrow. | Store keys in OS environment variables locked via Windows File System ACLs (`icacls`). |
| **Central Cloud Multi-Tenant Cluster (§5.1 / §18)** | High (Infrastructure) | High | **Phase 2.0 (Chain Scale)** | Over-engineering for 2–5 pilot stores; high cloud operational expenditure without pilot business value. | Single low-cost Cloud VM running containerized Postgres + FastAPI with off-site backups. |
| **Dynamic UPI Customer Secondary Display (§5.2 / §18)**| Medium (Operations) | Medium | **Phase 2.0 (Chain Scale)** | Dual-head display drivers, serial pole display protocols, and payment aggregator webhook matching. | Print dynamic UPI QR on thermal paper receipts, or use static counter UPI Soundbox/card. |
| **Cashless Insurance / TPA Processing (§5.3 / §18)** | High (Business) | High | **Phase 2.0 (Chain Scale)** | High regulatory overhead, lengthy TPA corporate empaneled onboarding, and co-pay billing engines. | Manual "Insurance / TPA" tender method capturing policy and claim reference numbers. |
| **Prescription Vision OCR Parsing (§5.4 / §18)** | High (Experience) | High | **Phase 2.0 (Chain Scale)** | High error rate on cursive handwriting; extreme liability if incorrect dosages are machine-transcribed. | Digital webcam/scanner photo capture attached directly to local dispensing record. |
| **Automated WhatsApp / SMS Gateway (§5.5 / §18)** | Medium (Marketing) | Medium | **Phase 2.0 (Chain Scale)** | Meta WhatsApp Business API compliance, Indian Telecom DLT registration, and external SMS gateways. | Cashier one-click `wa.me` browser link with pre-formatted invoice text, plus thermal paper bill. |

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
