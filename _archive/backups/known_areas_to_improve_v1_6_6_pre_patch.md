# Pharmacy POS — Architecture Roadmap & Engineering Gap Registry

This document serves as the authoritative, living engineering registry tracking architectural gaps, retail edge cases, regulatory requirements, and technical enhancements for the Pharmacy POS system.

The document is organized into four distinct parts:
- **[Part I: Active Tactical Improvement Roadmap (v1.6.6 → v1.7 Pilot Hardening)](#part-i-active-tactical-improvement-roadmap-v166--v17-pilot-hardening)**: 15 verified, sequenced tactical enhancements across Tiers 1–4 with mathematical invariants, statutory citations, and second-order defensive safeguards.
- **[Part II: Active Priority vs. Complexity Roadmap Matrix](#part-ii-active-priority-vs-complexity-roadmap-matrix)**: Strategic matrix evaluating Impact vs. Complexity for both **Track A (Tactical v1.7 Items 1–15)** and **Track B (Deferred Enterprise Items 1–12)**.
- **[Part III: Active Enterprise Roadmap (Phase 2.0 Chain Scale — Track B Deferred Items)](#part-iii-active-enterprise-roadmap-phase-20-chain-scale--track-b-deferred-items)**: Detailed analysis of the 12 enterprise capabilities intentionally deferred for the V2 Major Iteration with codified interim bridges in [architecture_v1_6_6.md](architecture_v1_6_6.md) (§18 D-120).
- **[Part IV: Historical Milestone Archive](#part-iv-historical-milestone-archive)**:
  - **[Section A: v1.6.5 → v1.6.6 Resolved Baseline](#section-a-v165--v166-resolved-baseline)**: Verified record of the 60 verified tactical patch items across Tiers 1–4 codified into [architecture_v1_6_6.md](architecture_v1_6_6.md) and [ROUTED-DETAIL.md](ROUTED-DETAIL.md).
  - **[Section B: v1.6 → v1.6.5 Resolved Baseline](#section-b-v16--v165-resolved-baseline)**: Verified record of the 8 Track A items, 4 interim bridges, and 8 defensive operational safeguards codified into [architecture_v1_6_5.md](architecture_v1_6_5.md).
  - **[Section C: v1.5 → v1.6 Resolved Baseline](#section-c-v15--v16-resolved-baseline)**: Verified record of the 12 core improvements and 8 operational safeguards codified into historical [_archive/Prev_iterations/Architecture/architecture_v1_6.md](_archive/Prev_iterations/Architecture/architecture_v1_6.md).

---

## Part I: Active Tactical Improvement Roadmap (v1.6.6 → v1.7 Pilot Hardening)

> [!NOTE]
> **Status in v1.6.6**: All 60 tactical patch items from previous iterations have been fully resolved and codified into [architecture_v1_6_6.md](architecture_v1_6_6.md) (Decisions D-126 through D-175, Tests 21 through 28) and [ROUTED-DETAIL.md](ROUTED-DETAIL.md). Part I below represents the active engineering registry of 15 verified tactical enhancements identified through line-by-line cross-reference auditing and second-order stress-testing of Architecture Spec v1.6.6.

### Implementation Sequencing & Dependency Chains

Items are sequenced into **four cautious implementation tiers**. Each tier builds upon the architectural primitives of preceding tiers:

| Tier | Focus | Architectural Scope & Rationale |
|---|---|---|
| **Tier 1: Inbound & Supply Chain Integrity** | Goods receipt, trade bonus pricing, 2D barcode parsing | Establishes correct inventory cost and automated identification before billing |
| **Tier 2: Transaction Safety & Edge HA** | Payment timeouts, digital returns, worker failover, DB safety | Hardens multi-counter payment settlement and LAN failover without split-brain |
| **Tier 3: Statutory Governance & Vigilance**| CDSCO recall tracing, DPCO ceilings, pharmacist presence | Enforces strict legal mandates under D&C Act, Pharmacy Act, and DPCO Order |
| **Tier 4: Operational Ergonomics & Storage** | In-line cutting loss, blind recounts, USB disk evacuation, stubs | Protects daily cashier workflows and eliminates cascade sync failures |

#### Mandatory Dependency Chains
| Chain | Items | Architectural Invariant & Constraint |
|---|---|---|
| **Cost & Price Governance** | 2 → 9 | Landed cost derivation (#2) is the prerequisite cost floor for DPCO statutory ceiling enforcement and discount validation (#9). |
| **Quarantine & Discrepancies** | 3 → RTV | Distributor tote staging (#3) is the physical prerequisite for automated RTV Debit Note generation. |
| **Payment & Return Integrity** | 4 → 5 | Late UPI reconciliation (#4) feeds directly into digital tender refund restrictions (#5). |
| **Edge High Availability** | 6 → 7 | Worker dual-host probing (#6) and migration space asserts (#7) jointly guard edge promotion resilience. |
| **Pharmacy Statutory Vigilance**| 10 → 8 → 11 | Pharmacist presence lock (#10) gates prescription dispensing; CDSCO recall traceability (#8) and physical filing slots (#11) form the audit defense triad. |
| **Micro-Inventory Controls** | 12 → 13 | In-line cutting loss (#12) isolates loose unit spoilage before blind recount shift close (#13). |
| **Edge Storage Hardening** | 14 → 15 | USB evacuation (#14) and central stub batch isolation (#15) protect edge and central during storage/sync anomalies. |

---

### Tier 1: Inbound & Supply Chain Integrity

#### 1. GS1 DataMatrix 2D Barcode Native Parser for CDSCO Top 300 Formulations
- **v1.6.6 Baseline ([§6 D-48, D-57](architecture_v1_6_6.md#6-stock-inventory-lifecycle--batch-mechanics), [§8 D-135](architecture_v1_6_6.md#8-invoicing-gst-credit-notes-debit-notes-challans--exchanges)):**
  Specifies that barcode scans bill 1 Packaging Unit and 2D scans override FEFO. Unrecognized barcodes prompt manual search (D-135).
- **Retail Reality & Specification Gap:**
  Under CDSCO Notification G.S.R. 823(E), the top 300 pharmaceutical formulation brands must print GS1 DataMatrix 2D barcodes encoding Application Identifiers (AIs): `(01)` GTIN (14 digits), `(10)` Batch Number (up to 20 alphanumeric chars), `(17)` Expiry Date (YYMMDD), and `(21)` Serial Number. Currently, no parsing grammar or scanner wedge handling is defined. When a 2D scanner in USB Keyboard Wedge mode scans a pack, it outputs an encoded string (e.g. `01089012345678901726093010B1234521987654321`). Without a native parser, the POS treats this as a literal 1D barcode string, fails to match `catalog_items.barcode`, and forces cashiers to manually type batches.
- **Hardened Technical Specification & Invariants:**
  - Client-side GS1 regex parser: Fixed-length elements parse deterministically: AI `(01)` GTIN (14 digits) $\rightarrow$ matches `catalog_items.gtin` or `catalog_items.barcode`; AI `(17)` Expiry (`YYMMDD`) $\rightarrow$ parses to calendar expiry date.
  - Variable-length elements: AI `(10)` Batch and AI `(21)` Serial use ASCII Group Separator `\x1d` (FNC1). If scanner wedge configuration strips `\x1d`, the parser executes a **longest-prefix match** against active batches for that GTIN in `store_batches`.
  - Scanned batch auto-selects in the POS checkout line and defaults to 1 Packaging Unit (D-48).
- **Second-Order Ripple-Effect Guards:**
  - *Expiry Mismatch Alert*: If the scanned 2D expiry date differs from the database batch record (due to manual GRN entry typo), the system allows the scan but prompts an advisory alert: *"Scanned pack expiry (MM/YYYY) differs from batch master. Updating local batch record."*
  - *1D & FEFO Fallback*: Preserves 1D barcode scanning and manual FEFO selection for loose blister strips that lack outer box 2D printing.

#### 2. Distributor Trade Schemes & Landed Cost Derivation ("10 + 2 Free")
- **v1.6.6 Baseline ([§6 D-127, D-128](architecture_v1_6_6.md#6-stock-inventory-lifecycle--batch-mechanics), [§9 D-139](architecture_v1_6_6.md#9-discounts--price-governance)):**
  Defines `purchase_price_per_unit` on GRN, short receipts (D-128), and mandates that sale prices cannot drop below `purchase_price_per_unit` without Manager override (D-139).
- **Financial Reality & Specification Gap:**
  In Indian pharmaceutical distribution, trade schemes are ubiquitous ("Buy 10 packs, get 2 free" or "5% trade discount on bill"). In [ROUTED-DETAIL.md §1.7](ROUTED-DETAIL.md#17-goods-receipt-note-grn--short-receipts-table-schema-v166), `goods_receipt_note_items` only captures `ordered_pack_qty`, `received_pack_qty`, and `purchase_price_per_unit`. If 10 packs are billed at ₹100 each (₹1,000) and 2 packs are received free (12 packs total), the true landed cost is $\text{₹}1,000 / 12 = \text{₹}83.33$. If the system records purchase price as ₹100, selling at ₹90 falsely triggers the D-139 below-cost block, and margin reports show 0% on commercial lines and 100% on bonus lines.
- **Hardened Technical Specification & Invariants:**
  - Extend `goods_receipt_note_items` schema:
    `scheme_free_pack_qty INTEGER NOT NULL DEFAULT 0 CHECK (scheme_free_pack_qty >= 0)`,
    `trade_discount_pct NUMERIC(5,2) NOT NULL DEFAULT 0.00 CHECK (trade_discount_pct >= 0 AND trade_discount_pct <= 100.00)`,
    `effective_landed_cost_per_unit NUMERIC(10,4) NOT NULL`.
  - Mathematical Derivation Invariant:
    $$\text{Effective Unit Cost} = \frac{(\text{Billed Pack Qty} \times \text{Invoice Rate} \times (1 - \frac{\text{Discount \%}}{100})) + \text{Inbound Tax}}{(\text{Billed Pack Qty} + \text{Scheme Free Pack Qty}) \times \text{Pack Size}}$$
  - Total available base inventory increments by: $(\text{received\_pack\_qty} + \text{scheme\_free\_pack\_qty}) \times \text{pack\_size}$.
  - In `store_batches`, `purchase_price_per_unit` is populated with `effective_landed_cost_per_unit`, ensuring D-139 evaluates against true cost.
- **Second-Order Ripple-Effect Guards:**
  - *RTV Debit Note Commercial Reversal Guard*: While internal pricing uses effective landed cost, `goods_receipt_note_items` immutably retains original `purchase_price_per_unit` (gross invoice rate) and `scheme_free_pack_qty`. When issuing a vendor Debit Note (`<STORE>-DN-...`) for near-expiry returns (§8 D-74), the system computes tax and credit reversals based on original distributor contract terms, preventing distributor claim rejections.
  - *GST Section 15(3) Invariant*: Complies with CBIC Circular No. 92/11/2019-GST: volume discounts with free goods are treated as composite price adjustments with 100% allowable Input Tax Credit (ITC) on the net tax charged.

#### 3. Near-Expiry Distributor Quarantine Tote Bins & Pre-Acceptance Rejections (Resolving §18 Q2)
- **v1.6.6 Baseline ([§6 D-50, D-51](architecture_v1_6_6.md#near-expiry-vendor-returns-rtv--transfers), [§18 Open Architecture Questions](architecture_v1_6_6.md#18-open-items-phase-2-roadmap--v2-chain-scale)):**
  Triggers `stock-move: rtv-quarantine` for shelf-expiry alert tiers (90d Amber / 60d Orange / 30d Red). §18 flags Open Question Q2: *"Should RTV shelf-quarantine group expired batches into distributor physical tote bins? Target: v1.7 Sprint 1"*.
- **Operational Reality & Specification Gap:**
  Pharmacies currently dump near-expiry stock from all distributors into a single generic quarantine box. When distributor sales representatives arrive to collect expired goods, the pharmacist must manually search through hundreds of bottles and loose strips to sort batches for that specific distributor's Debit Note. Furthermore, damaged goods delivered on the delivery van (crushed boxes, leaking syrups) lack an auditable pre-acceptance rejection mechanism.
- **Hardened Technical Specification & Invariants:**
  - Formally resolves §18 Q2: Introduce physical/logical `rtv_tote_id` (e.g. `TOTE-DIST-04`) bound to `distributors.distributor_id`.
  - When batches enter Orange (60d) or Red (30d) tiers, POS UI prompts: *"Move Batch {batch_no} to Shelf Tote {rtv_tote_id} ({distributor_name})"*.
  - When generating an RTV Debit Note (`<STORE>-DN-...`), selecting a distributor auto-aggregates all batches currently staged in that distributor's tote.
  - Inbound Pre-Acceptance Rejection: Add `rejected_pack_qty` and `rejection_reason ENUM ('DAMAGED_IN_TRANSIT', 'SHORT_EXPIRY_DELIVERED', 'SPECIFICATION_MISMATCH')` to `goods_receipt_note_items`. Rejected quantities do NOT enter inventory or gross payable totals, logging directly to a Distributor Delivery Rejection Log.
- **Second-Order Ripple-Effect Guards:**
  - *Multi-Distributor Batch Collision Guard*: If the same medicine batch was purchased from Distributor A on Monday and Distributor B on Friday, near-expiry quarantine allocates batches to distributor totes using **FIFO allocation against inbound GRN receipts**, ensuring returns to any distributor never exceed the net quantity supplied by them.

---

### Tier 2: Transaction Safety & Edge High Availability

#### 4. Dynamic UPI Payment Timeout & Soundbox Reversal Race Reconciliation (Resolving §18 Q1)
- **v1.6.6 Baseline ([§8 D-69](architecture_v1_6_6.md#checkout-workflow--peripheral-resilience), [§18 Open Architecture Questions](architecture_v1_6_6.md#18-open-items-phase-2-roadmap--v2-chain-scale)):**
  Prints dynamic NPCI UPI QR string (`upi://pay?...`) on thermal receipts with soundbox confirmation. §18 flags Open Question Q1: *"Dynamic UPI QR scanned but webhook stalls: max cashier wait before cash fallback? Target: v1.7 Sprint 1"*.
- **Operational Reality & Specification Gap:**
  When network latency stalls UPI payment confirmation, cashiers wait 30–60 seconds, switch the transaction to Cash, and complete the sale. 30 seconds later, the customer's UPI payment succeeds and the soundbox announces "₹500 received on UPI". The store merchant account has received ₹500, the physical cash drawer holds ₹500, creating an unallocated surplus and severe cashier theft temptation (cashier pocketing cash from the till).
- **Hardened Technical Specification & Invariants:**
  - Formally resolves §18 Q1: Implements a configurable **60-second UPI polling timeout** on the POS checkout screen.
  - When cashier switches to Cash, POS marks invoice as `COMMITTED_PENDING_UPI_RECONCILE` for a 5-minute window.
  - If a delayed UPI webhook credit confirms within the window:
    - POS triggers an audible chime and displays a **Payment Collision Modal**:
      1. *Immediate Cash Return (Customer Present)*: Cashier returns ₹500 physical cash to the customer. To prevent cashier theft, this **strictly requires customer OTP verification or signature**. System emits `tender_switch_cash_reversal: 500.00`.
      2. *Automated Store Credit (Customer Departed)*: If customer has departed (>60 seconds post-commit), **cash return is strictly locked**. System automatically generates a Customer Store Credit Note (`<STORE>-CN-...`) linked to customer's mobile number, dispatching an automated WhatsApp/SMS voucher link.
- **Second-Order Ripple-Effect Guards:**
  - *Till Variance Invariant (§13 D-103)*: To prevent double-counting or false shortage alerts, the physical till variance formula is updated:
    $$\text{Expected Cash} = \text{Opening Float} + \text{Cash Sales} - \text{Cash Refunds} - \text{Tender Switch Cash Reversals}$$
  - Manual cash payout on delayed collisions requires Store Manager Tier B Argon2id Password.

#### 5. Digital Tender Return & Bank Chargeback Protection Policy
- **v1.6.6 Baseline ([§8 D-133](architecture_v1_6_6.md#returns-cash-refund-limits--atomic-exchanges)):**
  Defines a daily counter cash refund limit and split settlement (`refund_settlement: {cash, store_credit}`).
- **Financial Reality & Specification Gap:**
  D-133 does not restrict cash refunds on items originally paid via digital tenders (UPI / Card). In retail pharmacy operations, refunding cash on card purchases is a primary vector for stolen card cashing and exposes the business to chargeback double-loss (bank claws back digital funds while the pharmacy already handed out physical cash).
- **Hardened Technical Specification & Invariants:**
  - Enforce **Original Tender Alignment Invariant**:
    - If `original_tender == 'CASH'` $\rightarrow$ Cash refund permitted up to counter daily limit (D-133).
    - If `original_tender IN ('UPI', 'CARD', 'ONLINE')` $\rightarrow$ System **defaults strictly to Store Credit Note (`<STORE>-CN-...`)** or digital gateway reversal.
    - If `original_tender == 'STORE_CREDIT'` $\rightarrow$ Return refund is strictly re-credited as `store_credit`. Refunding store credit as cash is unconditionally hard-blocked.
  - Same-Day Digital Gateway Reversal: For same-day returns prior to batch settlement (23:59 IST), POS initiates an automated refund API reversal back to customer's source account.
  - Cash Refund Exception on Digital Sales: Permitted *only* under Store Manager Tier B Argon2id Password verification and mandatory customer government ID (Aadhaar / Voter ID) capture.

#### 6. Counter 3 Worker Discovery & Split-Brain Standby Re-connection Fencing
- **v1.6.6 Baseline ([§2 D-12, D-13, D-14, D-15](architecture_v1_6_6.md#2-tech-stack--edge-infrastructure)):**
  Counter 1 is primary; Counter 2 is warm standby promoted via `promote_to_primary.bat` with ping fencing; Counter 3 is worker UI.
- **High Availability Gap & Network Fragility:**
  1. *Worker Re-routing Failure*: When Counter 2 promotes to Primary, Counter 3 is still pointed at `medpos-primary.local`. If Counter 2 claims `medpos-primary.local` via dynamic mDNS, mDNS conflict resolution (RFC 6762) forces Counter 2 to rename to `medpos-primary-2.local`, stranding Counter 3.
  2. *Reboot Split-Brain Hazard*: If Counter 1 had a temporary power cord disconnect, Counter 2 promoted (adopting epoch `-F1` and jumping sequences +100,000). When Counter 1 boots back up, it starts Postgres and FastAPI on `0.0.0.0:8000`, causing two concurrent primaries on the LAN accepting conflicting writes.
- **Hardened Technical Specification & Invariants:**
  - Worker Deterministic Dual-Host Probing: Counter 3 UI shell is configured with a deterministic host list:
    `Primary: medpos-primary.local (192.168.1.10)` $\rightarrow$ `Standby: medpos-standby.local (192.168.1.11)`.
    If Primary is unreachable for $>5$ seconds, Counter 3 queries `medpos-standby.local:8000/api/node/role`. If standby returns `role: PRIMARY`, Counter 3 connects immediately. Because Counter 2 holds the identical store TLS certificate (D-158), pinned TLS verification succeeds.
  - Counter 1 Boot Fencing Hook: In Counter 1's service startup wrapper (`start_medpos.bat`), execute a pre-flight probe:
    - Queries `http://192.168.1.11:8000/api/node/role` (Counter 2).
    - If Counter 2 responds `role: PRIMARY` (epoch `-F1` active), Counter 1's service **immediately halts and aborts startup**, writing a critical syslog event: `HALT_DEMOTED_STANDBY_ACTIVE`.
    - Counter 1 cannot accept writes until Store Manager or Admin executes a formal WAL resync and demotion script.

#### 7. Pre-Flight Database Migration Free Disk Space Safety Guard
- **v1.6.6 Baseline ([§2 D-163](architecture_v1_6_6.md#2-tech-stack--edge-infrastructure), [§17 D-165](architecture_v1_6_6.md#17-deployment-safety--edge-rollout)):**
  Specifies Alembic migrations with pre-flight edge backups (`pg_dump -Fc`) and tiered disk responses (85% log prune / 90% degraded / 98% read-only).
- **Edge Risk & Specification Gap:**
  In [ROUTED-DETAIL.md §10.4](ROUTED-DETAIL.md#104-alembic-pre-flight-automated-backup-script-v166), `pre_migration_backup.ps1` executes `pg_dump.exe` blindly. If an edge SSD is at 83% capacity, dumping an 8 GB database consumes ~3-5 GB, pushing disk usage past 90% or 98%, bricking the database mid-migration.
- **Hardened Technical Specification & Invariants:**
  - Calibrated Space Capacity Formula: Update `pre_migration_backup.ps1` to assert:
    $$\text{Free Disk Space Bytes} \ge (1.5 \times \text{pg\_database\_size('medpos')}) + 1\text{ GB safety margin}$$
  - Automated Pre-Dump Headroom Reclamation: Script auto-deletes rotated application logs older than 3 days prior to evaluating free space.
  - Safe Abort Invariant: If available disk space remains below the threshold, migration aborts cleanly (`ERR_INSUFFICIENT_MIGRATION_SPACE`) without running `pg_dump` or applying Alembic migrations.

---

### Tier 3: Statutory Governance & Pharmacy Vigilance

#### 8. CDSCO Drug Recall Patient Traceability & Outbound Notification Register
- **v1.6.6 Baseline ([§10.1 D-143](architecture_v1_6_6.md#101-absolute-expiry-hard-block--drug-recalls)):**
  Ingestion of `batch-recall` in sync payload auto-quarantines batches and hard-blocks active checkout transactions with non-destructive line removal.
- **Clinical/Legal Gap & Patient Safety Risk:**
  Decision D-143 protects *future* sales of recalled drugs, but has zero mechanism to trace patients who *already purchased* that batch prior to the recall notice. Under the Drugs & Cosmetics Act and CDSCO Good Distribution Practices, pharmacies must trace and notify patients for Class I/II recalls (e.g. contaminated pediatric syrups).
- **Hardened Technical Specification & Invariants:**
  - Upon ingesting `batch-recall`, Counter 1 automatically queries past sales:
    `SELECT i.invoice_number, i.created_at, p.patient_name, p.phone_number, l.quantity, d.doctor_name FROM invoice_lines l JOIN invoices i ON l.invoice_id = i.id LEFT JOIN patient_directory p ON i.patient_id = p.id LEFT JOIN prescriber_directory d ON i.prescriber_id = d.id WHERE l.batch_id = :recalled_batch_id;`
  - Instantiates a **Patient Recall Action Register** on the Store Manager and Pharmacist dashboard.
  - Generates:
    1. One-click Drug Inspector Statutory Compliance Report (CSV/PDF).
    2. Outbound WhatsApp/SMS notification template queue (*"URGENT: Batch {batch_no} of {drug_name} recalled by CDSCO. Stop use immediately and return to store for full refund."*).
- **Second-Order Ripple-Effect Guards:**
  - *DPDP Act Role-Gating*: Access to the Patient Recall Register is role-gated strictly to **Store Manager and Registered Pharmacist**. Cashiers have zero access.
  - *Clinical Human-in-the-Loop Release*: Alerts do NOT dispatch automatically; the Registered Pharmacist must review clinical severity (Class I toxicity vs Class III packaging typo) and click `[Authorize & Dispatch Recall Alerts]`, preventing public panic over minor labeling defects.

#### 9. DPCO Statutory National Ceiling Price Invariant & Validation
- **v1.6.6 Baseline ([§9 D-139](architecture_v1_6_6.md#9-discounts--price-governance)):**
  Explicitly references: *"DPCO price-controlled scheduled drugs are hard-blocked from cashier discretionary discounts."*
- **Regulatory Gap & Criminal Liability:**
  In [ROUTED-DETAIL.md §1.8](ROUTED-DETAIL.md#18-drug-classification-ndps--zero-mrp-constraints-v166), `catalog_items` only has `drug_schedule`, `is_ndps`, and `is_free_supply`. There is **no field to designate DPCO drugs** and **no ceiling price tracking**. Under the Drugs (Prices Control) Order, 2013, selling a National List of Essential Medicines (NLEM) formulation above the NPPA gazetted ceiling is a criminal offense under the Essential Commodities Act.
- **Hardened Technical Specification & Invariants:**
  - Add to `catalog_items`: `is_dpco BOOLEAN NOT NULL DEFAULT FALSE` and `dpco_ceiling_unit_price NUMERIC(10,4) NULL`.
  - Inbound GRN Ceiling Guard: When receiving stock via GRN, system asserts: `batch.mrp / pack_size <= catalog.dpco_ceiling_unit_price`. If violated, insert is rejected (`DPCO_OVERPRICING_HARD_BLOCK`).
  - Cashier Discount Hard-Block: Fulfills D-139 by evaluating `if (item.is_dpco) { block_cashier_discretionary_discount(); }`.
- **Second-Order Ripple-Effect Guards:**
  - *Pre-WPI Legal Inventory Invariant*: NPPA updates ceiling prices annually on April 1 based on the Wholesale Price Index (WPI). Under DPCO Rule 24 and Legal Metrology, batches manufactured prior to the price notification date remain legally billable at their printed MRP until expiry. The system validates ceiling prices **applicable at the batch's declared manufacturing date**, preventing wrongful bricking of legal pre-revision inventory.

#### 10. Registered Pharmacist Physical Presence & Lunch-Hour Dispensing Lock
- **v1.6.6 Baseline ([§11 D-93](architecture_v1_6_6.md#11-roles--access-control)):**
  States cashiers cannot dispense Schedule H1/X without pharmacist sign-off.
- **Statutory Gap & License Revocation Risk:**
  Under Section 42 of the Pharmacy Act, 1948 and Rule 65(2) of the Drugs & Cosmetics Rules, 1945, dispensing ANY prescription medicine (including Schedule H chronic medicines like Metformin or Amlodipine) without the personal supervision of a Registered Pharmacist is illegal. When the pharmacist steps out for lunch, cashiers frequently continue dispensing Schedule H medicines. Decoy inspections by State Drug Licensing Authorities result in immediate store license suspensions.
- **Hardened Technical Specification & Invariants:**
  - Implement a **Pharmacist Duty Toggle** on Counter 1 UI: `PHARMACIST_ON_DUTY` vs `PHARMACIST_AWAY`.
  - When toggled to `PHARMACIST_AWAY` (or after 15 minutes of pharmacist workstation lock):
    - System enters **OTC-Only Retail Mode**.
    - Scanning any drug where `drug_schedule IN ('SCHEDULE_H', 'SCHEDULE_H1', 'SCHEDULE_X')` or `requires_prescription = TRUE` triggers a UI hard-block: *"Statutory Lock: Registered Pharmacist is away. Prescription dispensing prohibited under Pharmacy Act Sec 42."*
    - Non-prescription OTC retail items (FMCG, bandages, personal care, ayurvedic OTC) remain 100% billable.
    - Pharmacist resumes duty via Tier A Quick-PIN. Duty intervals log to `pharmacist_attendance_log` for regulatory audit.
- **Second-Order Ripple-Effect Guards:**
  - *Non-Destructive Line Dropping*: If a cashier is in the middle of scanning a mixed basket and the pharmacist steps away, checkout commit prompts: *"Registered Pharmacist is away. Prescription item {drug_name} cannot be dispensed. Drop prescription item and proceed with OTC checkout (Y/N)?"*, preventing cart deadlocks.

#### 11. Physical Duplicate Prescription Locked Cabinet Slot Indexing
- **v1.6.6 Baseline ([§10.3 D-86, D-88](architecture_v1_6_6.md#103-schedule-x--ndps-dual-prescription-custody--bound-ledger)):**
  Mandates digital scans of duplicate prescriptions (<250 KB WebP, AES-256 encrypted, 90d retention). [ROUTED-DETAIL.md §1.5](ROUTED-DETAIL.md#15-schedule-h1-register--schedule-x-running-ledger-table-schemas) defines `schedule_x_running_ledger`.
- **Inspection Reality & Specification Gap:**
  Rule 65(4) mandates that physical duplicate carbon copies of Schedule X prescriptions must be preserved in a locked box for 2 years. During Drug Inspector audits, the inspector demands to hold the physical paper to verify doctor wet-ink signature. The digital ledger currently has no reference to where the physical prescription is filed in the physical cabinet.
- **Hardened Technical Specification & Invariants:**
  - Add `physical_box_slot VARCHAR(32) NOT NULL` to `schedule_x_running_ledger` (format: `<STORE>-BOX-YYYYMM-XXXX`).
  - Thermal receipt printer spools a small physical filing adhesive sticker alongside the invoice:
    `[ SCHEDULE X PHYSICAL FILING STICKER ]`
    `Slot: BOX-202609-0142 | Date: 2026-09-24`
    `Patient: Suresh Kumar | Drug: Ketamine 10ml`
  - The pharmacist sticks this onto the physical carbon copy and drops it into the assigned slot in the physical locked box. One-click POS lookup allows pulling the physical prescription in <30 seconds during inspection.
- **Second-Order Ripple-Effect Guards:**
  - *Printer Jam Recovery*: Integrated into the audited `reprint` event workflow (D-124, D-137) with a dedicated UI action: `[Reprint Filing Sticker]`.

---

### Tier 4: Operational Ergonomics, Observability & Data Integrity

#### 12. In-Line Loose Tablet Cutting Loss & Spoilage Write-Off Protocol
- **v1.6.6 Baseline ([§6 D-49, D-170](architecture_v1_6_6.md#6-stock-inventory-lifecycle--batch-mechanics)):**
  Specifies damaged units route to quarantine, and damaged write-offs require photo, reason, and Manager Quick-PIN (D-170).
- **Operational Reality & Shrinkage Leakage:**
  During counter queues, a cashier cuts a 10-tablet blister to sell 3 loose tablets; 1 tablet drops to the floor or is crushed by scissors. Under D-170, logging a write-off requires a smartphone photo and Manager Quick-PIN for a ₹1.50 tablet, causing queue stalls. Cashiers bypass the system by throwing the tablet away unrecorded, accumulating physical vs. system stock discrepancies.
- **Hardened Technical Specification & Invariants:**
  - Introduce **In-Line Fractional Cutting Loss** directly inside the POS cart UI:
    - Cashier clicks `[+] Cutting Loss` on a fractional blister line.
    - Constraints: Allowed *only* during fractional sales; max 2 base units per line item; total loss value capped at $\le \text{₹}20$ per sale.
    - Strictly prohibited on Schedule X and NDPS drugs (all NDPS loss requires dual-custody Tier B password).
    - Automatically emits `stock-move: cutting-spoilage` without requiring supervisor PIN interruption.
- **Second-Order Ripple-Effect Guards:**
  - *Anti-Theft Cumulative Shift Cap*: To prevent dishonest cashiers from skimming tablets across dozens of transactions, in-line cutting loss is governed by a **Cumulative Shift Ceiling of ₹50 or 5 occurrences per cashier shift**. Exceeding the cap locks the button and requires Store Manager Quick-PIN.
  - *Disambiguation Invariant*: Decision D-170 applies to all shelf-level write-offs, full packs, and damage $> \text{₹}20$; Item 12 applies strictly to counter fractional scissors spoilage.

#### 13. Blind Cash Count Variance Recount & Supervisor Dispute Workflow
- **v1.6.6 Baseline ([§13 D-103, D-104](architecture_v1_6_6.md#13-shift-management--day-end-till-reconciliation-z-report)):**
  Defines blind cash declaration and automated variance calculation: $\text{Variance} = \text{Declared Cash} - (\text{Opening Float} + \text{Cash Sales} - \text{Cash Refunds})$.
- **Operational Reality & Specification Gap:**
  In [ROUTED-DETAIL.md §1.6](ROUTED-DETAIL.md#16-shift-session--z-report-table-schemas), if a cashier accidentally mistypes `4500` instead of `5400` (simple digit transposition), the shift immediately commits into `cash_variance = -900.00`. Immutable Z-Reports lock this shortage, resulting in wrongful salary deductions.
- **Hardened Technical Specification & Invariants:**
  - **Two-Stage Blind Count Protocol**:
    1. Cashier enters physical cash breakdown (notes and coins).
    2. If $|\text{Variance}| > \text{₹}200$: System displays: *"A cash discrepancy was detected. Please recount physical drawer cash and re-enter count."* The system **strictly conceals** the system expected figure and the direction of the variance, preserving 100% blind integrity against theft.
    3. Cashier recounts drawer and submits Count 2.
    4. If variance still exceeds ₹200: Manager must sign off via Tier A Quick-PIN, entering supervisory remarks (`"Physical cash recounted in presence of manager; variance confirmed"`).
  - Shift record stores `recount_attempts INT DEFAULT 1` and `supervisor_notes`.
- **Second-Order Ripple-Effect Guards:**
  - *Deadlock Prevention*: Recount attempts are hard-capped at **2 attempts**. Persistent variance transitions shift state to `CLOSED_DISPUTED`, immediately unlocking the register for the incoming shift.

#### 14. Emergency Local USB External Storage Offloading under Disk Pressure
- **v1.6.6 Baseline ([§17 D-165](architecture_v1_6_6.md#17-deployment-safety--edge-rollout)):**
  Defines tiered disk responses: 85% log pruning, 90% degraded write mode, 98% emergency read-only mode. [ROUTED-DETAIL.md §10.5](ROUTED-DETAIL.md#105-tiered-disk-space-health-response-automation-v166) specifies that 98% halts checkouts.
- **Edge Risk & Specification Gap:**
  In remote stores with slow WAN, if disk space reaches 98%, checkout commits halt. Turning patients away because an edge SSD is full of old synced logs is unacceptable. A non-technical store manager cannot run SQL commands or navigate Windows system folders.
- **Hardened Technical Specification & Invariants:**
  - Automated USB Evacuation Workflow:
    - At 90% disk pressure, POS status bar shows an amber prompt: *"Disk 90% full. Insert formatted USB drive (min 16GB) to archive data."*
    - Upon inserting a USB drive, the POS UI presents: `[Evacuate Synced Data to USB]`.
    - Edge daemon:
      1. Copies encrypted prescription photos older than 90 days having `synced_to_central == true` and rotated application logs older than 7 days to `E:\medpos_archive\`.
      2. Validates SHA-256 hashes of the files on the USB drive against database hashes.
      3. Only upon 100% cryptographic verification, unlinks the local edge copies.
      4. Emits `storage-usb-evacuation` audit event.
    - Reclaims 15–30 GB in under 5 minutes without technical support.
- **Second-Order Ripple-Effect Guards:**
  - *BadUSB Malware Defense*: Windows Group Policy strictly disables AutoRun and AutoPlay on all USB mass storage devices. The daemon performs **outward-only read/write operations**; it executes zero binaries or scripts from the USB drive.

#### 15. Poison-Pill Dependent Event Cascade & Central Stub Batch Isolation
- **v1.6.6 Baseline ([§5 D-40, D-41](architecture_v1_6_6.md#central-ingestion-atomicity--poison-pill-quarantine)):**
  Isolates malformed events into `central_sync_quarantine` with `sync-quarantine-tombstone` in `central_events`.
- **Distributed Sync Gap & Cascade Failure Risk:**
  If an inventory-inflating event (`grn` Event 101) is quarantined on Central due to a malformed distributor field, but succeeded on the store, the store subsequently sells those units in Events 102, 103, 104 (`sale`). When Central ingests Events 102-104, foreign key constraints or batch lookup queries fail because the batch from Event 101 was never created. This causes Central to crash or cascade-quarantine 50 valid consumer sales.
- **Hardened Technical Specification & Invariants:**
  - **Synthetic Batch Stub Invariant**:
    - Central event ingestion consumer logic: If a `sale`, `dispense`, or `stock-move` references a `(drug_id, batch_no)` that does not exist in Central batch tables because an upstream `grn` event was quarantined:
      1. Central does NOT reject or quarantine the `sale` events.
      2. Central auto-provisions a **Synthetic Placeholder Batch** in `central_batches` with `status: PENDING_GRN_QUARANTINE_RESOLUTION` and `provisional_stock = -qty_sold`.
      3. Downstream sales commit cleanly to Central reporting tables.
      4. Quarantine alert on Central Admin Dashboard escalates to:
         `CRITICAL: GRN Event 101 quarantined with N downstream sales pending reconciliation.`
- **Second-Order Ripple-Effect Guards:**
  - *Atomic Remediation Re-mapping*: Synthetic stub batches are explicitly tagged: `is_quarantine_stub: true`, `quarantined_event_id: <uuid>`. When Central Admin remediates the GRN (e.g. correcting a batch number typo), Central updates both the GRN and all downstream stub-dependent events in a single atomic database transaction (`BEGIN...COMMIT`).

---

## Part II: Active Priority vs. Complexity Roadmap Matrix

| Item # | Area / Enhancement | Track | Impact | Complexity | Target Milestone | Architectural Focus |
|---|---|:---:|:---:|:---:|:---:|---|
| **#1** | **GS1 2D DataMatrix Parser** | Track A | Critical (Operations) | Low | **v1.7 (Pilot Hardening)** | CDSCO Top 300 2D parsing & longest-prefix batch selection |
| **#2** | **Trade Schemes & Landed Cost** | Track A | Critical (Financial) | Medium | **v1.7 (Pilot Hardening)** | 10+2 free goods, landed cost derivation & RTV gross rate |
| **#3** | **Distributor Quarantine Totes (Q2)**| Track A | High (Logistics) | Low | **v1.7 (Pilot Hardening)** | Resolves §18 Q2; segregated RTV bins & pre-GRN rejection |
| **#4** | **UPI Timeout & Reversal Race (Q1)**| Track A | High (Financial) | Medium | **v1.7 (Pilot Hardening)** | Resolves §18 Q1; 60s timeout, dual-tender collision lock |
| **#5** | **Digital Tender Return Policy** | Track A | High (Financial) | Low | **v1.7 (Pilot Hardening)** | Chargeback defense; digital returns default to Store Credit |
| **#6** | **Worker HA & Reboot Fencing** | Track A | High (Reliability) | Medium | **v1.7 (Pilot Hardening)** | Dual-host probing list & Counter 1 demotion hook |
| **#7** | **Migration Disk Space Assert** | Track A | High (DevOps) | Low | **v1.7 (Pilot Hardening)** | Free space capacity formula guarding pre-flight `pg_dump` |
| **#8** | **CDSCO Recall Patient Trace** | Track A | Critical (Legal) | Medium | **v1.7 (Pilot Hardening)** | Retrospective buyer query & Pharmacist-gated alerts |
| **#9** | **DPCO Statutory Ceiling Price** | Track A | Critical (Legal) | Low | **v1.7 (Pilot Hardening)** | NLEM ceiling validation at manufacture date & discount lock |
| **#10**| **Pharmacist Presence Lock** | Track A | Critical (Legal) | Low | **v1.7 (Pilot Hardening)** | Section 42 Pharmacy Act duty toggle; OTC-only retail mode |
| **#11**| **Duplicate Filing Box Indexing** | Track A | High (Compliance) | Low | **v1.7 (Pilot Hardening)** | Physical slot assignment & thermal adhesive sticker spool |
| **#12**| **In-Line Cutting Loss Protocol** | Track A | Medium (Operations) | Low | **v1.7 (Pilot Hardening)** | Fast-track scissors loss capped at ₹50/shift per cashier |
| **#13**| **Blind Recount & Dispute Close** | Track A | Medium (Operations) | Low | **v1.7 (Pilot Hardening)** | Two-attempt blind count preventing accidental salary cuts |
| **#14**| **Emergency USB Storage Evac** | Track A | High (Disaster Recovery)| Low | **v1.7 (Pilot Hardening)** | Outward-only USB archive offload with SHA-256 validation |
| **#15**| **Poison-Pill Stub Batch Guard** | Track A | High (Reliability) | Medium | **v1.7 (Pilot Hardening)** | Central stub provisioning isolating downstream sales |
| **§1.1**| **Automated Supplier Settlement**| Track B | High (Financial) | High | **Phase 2.0 (Chain Scale)** | Distributor EDI bridges (Marg/MediVision) & central AP |
| **§1.2**| **Central In-Transit Pool** | Track B | High (Logistics) | High | **Phase 2.0 (Chain Scale)** | Regional warehouse hub routing & 3PL freight claims |
| **§2.1**| **B2B E-Invoicing (IRN)** | Track B | Medium (Compliance) | High | **Phase 2.0 (Chain Scale)** | Live NIC/GSP API handshake & signed QR generation |
| **§3.1**| **Automated Standby Clustering** | Track B | High (Availability) | High | **Phase 2.0 (Chain Scale)** | Streaming Postgres replication & virtual IP consensus |
| **§3.2**| **Delta Replication Cursors** | Track B | High (Reliability) | High | **Phase 2.0 (Chain Scale)** | Continuous streaming cursor engine for 50+ stores |
| **§3.3**| **Cross-Store Voucher 2PL** | Track B | High (Financial) | High | **Phase 2.0 (Chain Scale)** | Distributed 2-phase locking cross-store voucher redemption |
| **§4.1**| **Hardware TPM 2.0 Sealing** | Track B | Medium (Security) | High | **Phase 2.0 (Chain Scale)** | PCR register sealing & DPAPI machine key wrapping |
| **§5.1**| **Cloud Multi-Tenant Kubernetes** | Track B | High (Infrastructure) | High | **Phase 2.0 (Chain Scale)** | Managed AWS/GCP Kubernetes & multi-region failover |
| **§5.2**| **Dynamic Secondary LCD Display** | Track B | Medium (Operations) | Medium | **Phase 2.0 (Chain Scale)** | Dual-head video driver & pole display dynamic QR sync |
| **§5.3**| **Cashless Insurance / TPA Claims**| Track B | High (Business) | High | **Phase 2.0 (Chain Scale)** | Real-time TPA co-pay split billing engine |
| **§5.4**| **Prescription Vision OCR Parsing**| Track B | High (Experience) | High | **Phase 2.0 (Chain Scale)** | Edge AI computer vision parsing cursive doctor handwriting |
| **§5.5**| **Automated WhatsApp / SMS Gateway**|Track B | Medium (Marketing) | Medium | **Phase 2.0 (Chain Scale)** | Meta Business API cloud queue & Telecom DLT compliance |

---

## Part III: Active Enterprise Roadmap (Phase 2.0 Chain Scale — Track B Deferred Items)

The following 12 enterprise capabilities are formally deferred for the **V2 Major Iteration (Phase 2.0 Chain Scale)**. Each capability has an active operational bridge codified in [architecture_v1_6_6.md](architecture_v1_6_6.md) (§18 D-120) to support pilot stores (2–5 stores) without enterprise cloud overhead.

### 1. Enterprise Supply Chain & Distributor Settlement
#### 1.1 Automated Central Supplier Settlement (EDI Bridges & AP Ledger)
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Chain Scale]`
- **Scope:** Automated Electronic Data Interchange (EDI) bridges into distributor enterprise software (Marg, MediVision) and automated central Accounts Payable (AP) ledger reconciliation across multi-store chains.
- **Deferral Rationale:** High integration complexity with heterogeneous distributor software. Over-engineering for pilot deployments.
- **Codified Interim Bridge in v1.6.6 ([§8](architecture_v1_6_6.md#returns-cash-refund-limits--atomic-exchanges)):** Stores issue sequential GST Supplier Debit Notes (`<STORE>-DN-...`) locally; reconciliation is managed manually in central AP bookkeeping.

#### 1.2 Central In-Transit Virtual Pool & 3PL Carrier Integration
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Chain Scale]`
- **Scope:** Chain-wide virtual in-transit inventory pool, automated 3PL freight carrier tracking APIs, and formal insurance carrier liability claims for regional warehouse logistics.
- **Deferral Rationale:** Requires enterprise hub-and-spoke infrastructure needed only when scaling beyond 5 pilot stores.
- **Codified Interim Bridge in v1.6.6 ([§6](architecture_v1_6_6.md#near-expiry-vendor-returns-rtv--transfers)):** Sequential Rule 55 Delivery Challans (`<STORE>-DC-...`) for intra-state road transit, and receipt discrepancy ingestion splitting intact vs breakage vs shortage.

---

### 2. Statutory & Government Gateway Integrations
#### 2.1 B2B E-Invoicing (IRN) via Government IRP Gateway
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Chain Scale]`
- **Scope:** Real-time generation of Invoice Reference Numbers (IRN) and signed QR codes via direct NIC/GSP API handshakes and asynchronous edge queues.
- **Deferral Rationale:** Over 95% of retail pharmacy sales are B2C (exempt from IRN under Rule 48(4)). Live government gateway handshakes introduce counter stalls.
- **Codified Interim Bridge in v1.6.6 ([§8](architecture_v1_6_6.md#8-invoicing-gst-credit-notes-debit-notes-challans--exchanges)):** Stores generate sequential Store-Local B2B Tax Invoices (`<STORE>-B2B-...`) with buyer GSTIN for manual monthly GSTR-1 upload.

---

### 3. Distributed Edge Clustering & Synchronization
#### 3.1 Automated Standby Failover Clustering (Streaming Replication & VIP)
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Chain Scale]`
- **Scope:** Streaming Postgres replication, virtual IP (VIP) automatic rerouting, and distributed consensus fencing on edge PC hardware.
- **Deferral Rationale:** High risk of split-brain in retail edge environments with non-technical staff.
- **Codified Interim Bridge in v1.6.6 ([§2](architecture_v1_6_6.md#2-tech-stack--edge-infrastructure)):** Standby WAL replication, scripted promotion (`promote_to_primary.bat`) with LAN fencing, and emergency sequence epoch (`-F1`).

#### 3.2 Delta Replication Cursor Engine & Soft-Delete Tombstones
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Chain Scale]`
- **Scope:** Central pagination cursor engine (`version > :cursor ORDER BY version ASC LIMIT 500`) and bidirectional soft-delete tombstone synchronization across 50+ stores.
- **Deferral Rationale:** Standard polling operates reliably for pilot catalogs (<10k SKUs) without complex cursor migrations.
- **Codified Interim Bridge in v1.6.6 ([§4 / §5](architecture_v1_6_6.md#master-data-delivery--concurrency-control)):** Monotonic watermark sync, paged transport chunking (500 events), MVCC staging, and poison-pill isolation tombstones (`sync-quarantine-tombstone`).

#### 3.3 Cross-Store Store Credit Voucher Double-Spend Coordinator (2PL)
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Chain Scale]`
- **Scope:** Real-time distributed two-phase locking (2PL) across stores to allow redemption of store credit vouchers at any branch in the chain.
- **Deferral Rationale:** Requires 99.99% central cloud uptime; network partitions cause customer friction.
- **Codified Interim Bridge in v1.6.6 ([§8](architecture_v1_6_6.md#returns-cash-refund-limits--atomic-exchanges)):** Store Credit Vouchers are **strictly redeemable only at the issuing branch**.

---

### 4. Enterprise Security & Hardware Integration
#### 4.1 Hardware-Bound TPM 2.0 / DPAPI Silicon Key Sealing
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Enterprise Hardening]`
- **Scope:** Hardware TPM 2.0 Platform Configuration Register (PCR) sealing and Windows DPAPI machine key wrapping for AES-256 keys.
- **Deferral Rationale:** Pilot counters use diverse PC hardware lacking uniform TPM chips; requires C/Win32 FFI bindings.
- **Codified Interim Bridge in v1.6.6 ([§16](architecture_v1_6_6.md#16-security--data-protection)):** Hardened Windows File System ACLs (`icacls`) restricting keys strictly to `NT SERVICE\MedPOS`, plus 4-hour Merkle tree event hashing.

---

### 5. Enterprise Cloud & Customer Experience Capabilities
#### 5.1 Central Cloud Multi-Tenant Kubernetes Cluster
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Enterprise Infrastructure]`
- **Scope:** Auto-scaling Kubernetes clusters, managed cloud databases (AWS RDS / GCP Cloud SQL), and multi-region failover for 50+ stores.
- **Deferral Rationale:** High operational cost without pilot business value.
- **Codified Interim Bridge in v1.6.6 ([§2](architecture_v1_6_6.md#2-tech-stack--edge-infrastructure)):** Single low-cost Cloud VM running containerized Postgres 16 and FastAPI with off-site backups.

#### 5.2 Customer-Facing Dynamic UPI Secondary LCD Pole Display
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 In-Store Experience]`
- **Scope:** Real-time checkout display on a pole-mounted secondary LCD rendering dynamic NPCI UPI QR codes linked to live payment gateway webhooks.
- **Deferral Rationale:** Dual-head video driver complexity and payment aggregator enterprise contracts.
- **Codified Interim Bridge in v1.6.6 ([§8](architecture_v1_6_6.md#checkout-workflow--peripheral-resilience)):** Dynamic NPCI UPI QR string (`upi://pay?...`) printed directly on thermal paper receipts, paired with static counter soundboxes.

#### 5.3 Cashless Insurance / Third-Party Administrator (TPA) Direct Claims
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Enterprise Integration]`
- **Scope:** Real-time online pre-authorization and co-pay split billing with Indian health insurance TPAs (Medi Assist, Paramount).
- **Deferral Rationale:** Lengthy corporate empaneled onboarding and complex co-pay billing engines.
- **Codified Interim Bridge in v1.6.6 ([§9](architecture_v1_6_6.md#9-discounts--price-governance)):** Manual tender metadata fields capturing Insurer Name, Policy Number, and Pre-Auth Code on standard GST invoices.

#### 5.4 Prescription Optical Character Recognition (OCR) AI Parsing
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 In-Store Experience]`
- **Scope:** Edge AI computer vision models automatically scanning and parsing cursive handwritten doctor prescriptions.
- **Deferral Rationale:** High error rate on handwritten prescriptions poses extreme liability if transcribed without 100% human verification.
- **Codified Interim Bridge in v1.6.6 ([§10.3](architecture_v1_6_6.md#103-schedule-x--ndps-dual-prescription-custody--bound-ledger)):** Digital webcam/scanner photo capture attached to dispense records with manual cashier entry.

#### 5.5 Automated WhatsApp & SMS Digital Invoice Delivery
`[Intentionally Deferred for V2 Major Iteration — Phase 2.0 Customer Engagement]`
- **Scope:** Automated background dispatch of digital GST invoices and Credit Notes to WhatsApp and SMS via enterprise cloud gateways.
- **Deferral Rationale:** Meta WhatsApp Business API compliance and Indian Telecom DLT registration overhead.
- **Codified Interim Bridge in v1.6.6 ([§8](architecture_v1_6_6.md#checkout-workflow--peripheral-resilience)):** Cashier one-click WhatsApp Web share link (`wa.me`) with pre-formatted invoice text.

---

## Part IV: Historical Milestone Archive

### Section A: v1.6.5 → v1.6.6 Resolved Baseline

The following 60 verified tactical patch items across 4 implementation tiers were designed, stress-tested against second-order ripple effects, and codified into the authoritative [architecture_v1_6_6.md](architecture_v1_6_6.md) specification (Decisions D-126 through D-175, Tests 21 through 28) with technical DDL and payload schemas in [ROUTED-DETAIL.md](ROUTED-DETAIL.md):

#### 1. Tier 1: Foundation Entities & Regulatory Gating
- **Goods Receipt Note (GRN) & Short Receipts (D-126, D-127, D-128, Test 21):** Defined `grn` event (#19) capturing distributor, purchase invoice ref, batch details, and `purchase_price_per_unit` (role-gated to Manager/Admin). Short receipts capture `ordered_pack_qty` vs `received_pack_qty` internally for Manager review without purchase order dependencies.
- **Zero-MRP Free Supply Guard (D-129, Test 22):** Enforced `CHECK ((is_free_supply = TRUE AND mrp = 0) OR (is_free_supply = FALSE AND mrp > 0))` on catalog and batch tables. Free-supply items bypass discount division to eliminate `(0-0)/0` division-by-zero crashes.
- **Drug Schedule Classification & NDPS Invariant (D-130, Test 25):** Added statutory `drug_schedule ENUM ('NONE', 'SCHEDULE_H', 'SCHEDULE_H1', 'SCHEDULE_X')` and independent `is_ndps BOOLEAN`. Whenever `is_ndps = TRUE`, system unconditionally enforces dual-custody verification and hard-blocks refills under Rule 65(11A).
- **Chapter 30 HSN Code Validation (D-131):** Validates pharmaceutical Chapter 30 codes on invoice creation: soft-warning on B2C retail sales, hard-block on B2B registered sales.

#### 2. Tier 2: Transaction Integrity & Core Workflows
- **Atomic 3-Event Exchanges (D-132, Test 23):** Codified customer exchanges as atomic 3-event groups (`sale-return`, `credit-note-redemption`, `sale`) bound by `exchange_group_id` committed in a single Postgres transaction. Client session staging ensures zero dangling credit; down-sells leave active balances on the Credit Note.
- **Credit Note Redemption & Cash Refund Ceiling (D-133, Test 28):** Added `credit-note-redemption` event (#20) and `store-credit` tender. Enforced daily counter cash refund limit with split settlement (`refund_settlement: {cash, store_credit}`).
- **CDSCO Drug Recall Hard-Block (D-143, Test 24):** Delivered via sync response payloads (`batch-recall`), immediately auto-quarantining batches. Active carts scanning recalled batches hard-block at checkout commit (`COMMITTED_PENDING_PRINT`, HTTP 409 `DRUG_RECALL_BLOCK`) with non-destructive line removal.
- **Rule 65(11) Repeat Dispensing Restriction (D-141, D-142, Test 25):** Prohibits repeat dispensing of Schedule H/H1 drugs unless prescribers explicitly author repeat instructions (`is_repeatable = true`). Prescriptions track cumulative balances (`prescribed_base_units`, `cum_dispensed_base_units`, `unfulfilled_base_units`) locked `FOR UPDATE`.
- **Schedule X Midnight Balance Materialization & DPDP Soft-Consent (D-144, D-145):** Daily running ledger opening balances materialized via scheduled midnight background job. DPDP Act 2023 patient consent captured as soft-required flag.
- **Net Effective Discount Clamping (D-138, D-139, D-140):** Bounded cashier discretionary discounts to $\le 15.0\%$ net effective discount off full Strip MRP. Purchase price floor prevents selling below cost without Manager Quick-PIN override. Manager Quick-PIN override governed by monthly store pool ceiling (₹5,000) with High-Access Argon2id Password fallback.

#### 3. Tier 3: Peripheral Resilience & Two-Tier Authentication
- **Two-Tier Authentication Hierarchy (D-147, Test 26):** Tier A Session-Bound Quick-PIN (4–6 digits, set at shift open, auto-expires at close/12h) authorizes rapid supervisor overrides; Tier B Full Argon2id Password is required for high-liability compliance actions (account disable, Schedule X/NDPS dispense, master change approval, training reset).
- **Progressive Throttling & Token Revocation (D-148, D-150, Test 26):** 5 consecutive failed logins locks `(terminal_id + username)` for 15 minutes. Incremented user `token_generation` counter revokes active JWTs across terminals within 30 seconds.
- **Peer Cashier Shift Isolation & Crash Historic Binding (D-173, D-174):** Terminals enforce peer cashier isolation, blocking Cashier B from viewing or closing Cashier A's shift. Recovered crash transactions bind to their historic shift ID, preventing float distortion on newly opened shifts.
- **Thermal Printer Jam Reprint & Walkaway Void (D-124, D-137, D-125):** Added audited `reprint` event (#21) with `*** DUPLICATE COPY ***` watermark. Walkaways during printer jams trigger cashier void issuing offsetting Credit Notes (`<STORE_CODE>-CN-...`), restoring stock and preserving numbering.
- **Barcode Miss Fallback & Family Phone Disambiguation (D-135, D-136, D-134):** Unrecognized barcodes prompt manual search and log telemetry gap events. Phone search supports family disambiguation while masking medical history from cashiers. Cashier customer bill preview toggle enabled.

#### 4. Tier 4: Edge Hardening, Telemetry & Rollout Safety
- **Sync Transport Paging & Staging MVCC (D-151, D-152, D-153, Test 27):** Monotonic `master_data_version` watermarks enforce sequential delivery. Large catalog releases use transport chunking (`batch_id`, paged chunks of 500 events) staged in `master_data_staging`, activating atomically via MVCC when complete. Outbound sync pushes enforce 500-event batch ceilings.
- **Optimistic Locking Refresh-and-Retry & Advisory Lock (D-155):** Stale edits rejected with HTTP 409 Conflict prompting refresh-and-retry backed by a 5-minute advisory lock (`editing_by`).
- **Store API Key Authentication & LAN Deadlock Elimination (D-156, D-158, D-159):** Store sync uses rotatable API keys; Central Admin uses Argon2id session cookies. Store Postgres operates at `READ COMMITTED` with ascending PK row-locks (`ORDER BY id ASC FOR UPDATE`) preventing multi-counter deadlocks.
- **Automated 4-Hour Merkle Tree Hashing (D-160):** Scheduled daemon computes Merkle root hashes of committed store events, exporting them externally for tamper-evident audit verification.
- **Annual AES-256 Key Rotation & Isolated Training Schema (D-161, D-162):** Annual key rotation with `key_id` tagging and background re-encryption. Training simulation mode executes inside an ephemeral `training.*` Postgres schema with a dedicated `TRAINING-` invoice series.
- **Alembic Pre-Flight Backup & Tiered Disk Space Response (D-163, D-164, D-165, D-167):** Pre-migration automated edge backup (`pg_dump -Fc`). WSUS updates deferred to 2–3 AM maintenance window. Tiered disk health triggers: 85% log prune/VACUUM ANALYZE; 90% degraded write mode; 98% emergency read-only. Shutdown drains active checkouts for 30 seconds.
- **Automated Test Suite Expansion (D-175, Tests 21–28):** Test suite expanded from 20 to 28 automated integration specifications. Scheduled background jobs track SKU sales velocity and cashier return anomalies (D-172).

#### 5. Summary of 8 Hardened Operational Safeguards (v1.6.6)
1. **Zero-MRP Free Supply Guard (§6):** Enforces `CHECK ((is_free_supply = TRUE AND mrp = 0) OR (is_free_supply = FALSE AND mrp > 0))` on catalog and batch tables, barring accidental positive billing and bypassing discount division-by-zero crashes.
2. **CDSCO Drug Recall Hard-Block (§10.1):** Recalls delivered in sync payloads auto-quarantine batches; active checkout transactions hard-block (HTTP 409 `DRUG_RECALL_BLOCK`) while supporting non-destructive line removal.
3. **Rule 65(11) Cumulative Prescription Locking (§10.2):** Prohibits repeat dispensing of Schedule H/H1 drugs without explicit prescriber refill directions, locking prescription balances `FOR UPDATE`.
4. **Two-Tier Authentication Hierarchy (§11):** Tier A Session Quick-PIN (4–6 digits) for high-frequency cashier overrides; Tier B Full Argon2id Password for high-liability compliance actions (Schedule X/NDPS, staff revocation).
5. **Multi-Counter LAN Deadlock Elimination (§2):** Store Postgres operates at `READ COMMITTED` with ascending primary-key row-locks (`ORDER BY id ASC FOR UPDATE`) preventing multi-counter worker lock contention.
6. **Peer Cashier Shift & Float Isolation (§13):** Worker terminals enforce peer shift isolation, blocking cross-terminal inspection/closure, and bind crash-recovered transactions strictly to historic shift IDs.
7. **Automated 4-Hour Merkle Tree Ledger Proofs (§16):** Periodic daemon computes Merkle root hashes of store events for cryptographic tamper-evident audits.
8. **Tiered Edge Disk Space Response Automation (§17):** Triggers graduated responses at 85% (log prune & `VACUUM ANALYZE`), 90% (degraded write mode), and 98% (emergency read-only mode).

---

#### Resolved Baseline Matrix (v1.6.5 → v1.6.6)

| Area / Enhancement | Impact | Complexity | Status in v1.6.6 | Spec Reference |
| :--- | :---: | :---: | :---: | :---: |
| **Goods Receipt Note (GRN) & Short Receipts** | Critical (Operations) | Medium | **Resolved** | [architecture_v1_6_6.md §5, §6](architecture_v1_6_6.md#inbound-goods-receipt-grn--classifications) |
| **Purchase Price / Cost-of-Goods Gating** | High (Financial) | Low | **Resolved** | [architecture_v1_6_6.md §6, §11](architecture_v1_6_6.md#inbound-goods-receipt-grn--classifications) |
| **Zero-MRP Free Supply Guard & Constraint** | High (Integrity) | Low | **Resolved** | [architecture_v1_6_6.md §6, §9](architecture_v1_6_6.md#inbound-goods-receipt-grn--classifications) |
| **Statutory Drug Schedules & NDPS Dual Custody** | Critical (Legal) | Medium | **Resolved** | [architecture_v1_6_6.md §6, §10](architecture_v1_6_6.md#inbound-goods-receipt-grn--classifications) |
| **Atomic 3-Event Customer Exchanges** | Critical (Integrity) | Medium | **Resolved** | [architecture_v1_6_6.md §8](architecture_v1_6_6.md#returns-cash-refund-limits--atomic-exchanges) |
| **Credit Note Redemption & Cash Ceiling** | High (Financial) | Medium | **Resolved** | [architecture_v1_6_6.md §8, §13](architecture_v1_6_6.md#returns-cash-refund-limits--atomic-exchanges) |
| **CDSCO Drug Recall Hard-Block & Line Removal** | Critical (Legal) | Medium | **Resolved** | [architecture_v1_6_6.md §10.1](architecture_v1_6_6.md#101-absolute-expiry-hard-block--drug-recalls) |
| **Rule 65(11) Repeat Dispensing Hard-Block** | Critical (Legal) | Medium | **Resolved** | [architecture_v1_6_6.md §10.2](architecture_v1_6_6.md#102-schedule-h1-register--prescription-reuse-limits) |
| **Two-Tier Authentication (Quick-PIN vs Password)** | Critical (Security) | Medium | **Resolved** | [architecture_v1_6_6.md §11](architecture_v1_6_6.md#selectable-role-presets--authentication-hierarchy) |
| **Progressive Login Throttling & Token Revocation** | High (Security) | Low | **Resolved** | [architecture_v1_6_6.md §11](architecture_v1_6_6.md#selectable-role-presets--authentication-hierarchy) |
| **Peer Cashier Shift & Float Isolation** | High (Financial) | Low | **Resolved** | [architecture_v1_6_6.md §13](architecture_v1_6_6.md#13-shift-management--day-end-till-reconciliation-z-report) |
| **Sync Batch Paging & Transport Chunking** | High (Scale) | Medium | **Resolved** | [architecture_v1_6_6.md §4, §5](architecture_v1_6_6.md#master-data-delivery--concurrency-control) |
| **Optimistic Locking Advisory Refresh-and-Retry** | High (Integrity) | Low | **Resolved** | [architecture_v1_6_6.md §4](architecture_v1_6_6.md#master-data-delivery--concurrency-control) |
| **Multi-Counter Row-Locking Deadlock Elimination**| High (Reliability) | Low | **Resolved** | [architecture_v1_6_6.md §2](architecture_v1_6_6.md#2-tech-stack--edge-infrastructure) |
| **4-Hour Merkle Tree Audit Event Hashing** | High (Compliance) | Medium | **Resolved** | [architecture_v1_6_6.md §16](architecture_v1_6_6.md#16-security--data-protection) |
| **Annual AES-256 Key Rotation Protocol** | High (Security) | Medium | **Resolved** | [architecture_v1_6_6.md §16](architecture_v1_6_6.md#16-security--data-protection) |
| **Isolated Ephemeral Training Schema (`training.*`)**| Medium (Operations)| Low | **Resolved** | [architecture_v1_6_6.md §16](architecture_v1_6_6.md#16-security--data-protection) |
| **Alembic Pre-Flight Automated Edge Backup** | High (DevOps) | Low | **Resolved** | [architecture_v1_6_6.md §2, §17](architecture_v1_6_6.md#17-deployment-safety--edge-rollout) |
| **Tiered Disk Space Health Response Automation** | High (Reliability) | Low | **Resolved** | [architecture_v1_6_6.md §17](architecture_v1_6_6.md#17-deployment-safety--edge-rollout) |
| **Automated Test Suite Expansion (Tests 21–28)** | High (Quality) | Medium | **Resolved** | [architecture_v1_6_6.md §14](architecture_v1_6_6.md#14-testing--verification-suite) |

---

### Section B: v1.6 → v1.6.5 Resolved Baseline

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

#### Resolved Baseline Matrix (v1.6 → v1.6.5)

| Area / Feature | Impact | Complexity | Status in v1.6.5 | Spec Reference |
| :--- | :---: | :---: | :---: | :---: |
| **UOM & Fractional Strip/Tablet Dispensing** | Critical (Operational) | Medium | **Resolved** | [architecture_v1_6_5.md §3, §6](architecture_v1_6_5.md#unit-of-measure-uom-hierarchy-fractional-billing) |
| **Schedule X & NDPS Dual Custody & Ledger** | Critical (Legal) | Medium | **Resolved** | [architecture_v1_6_5.md §10.3](architecture_v1_6_5.md#103-schedule-x-ndps-dual-prescription-custody-bound-ledger) |
| **In-Store Multi-Counter LAN Billing** | Critical (Integrity) | Medium | **Resolved** | [architecture_v1_6_5.md §2, §4](architecture_v1_6_5.md#local-first-store-node-multi-counter-lan) |
| **Near-Expiry Vendor Return (RTV) & Debit Notes**| High (Financial) | Medium | **Resolved** | [architecture_v1_6_5.md §5, §6, §8](architecture_v1_6_5.md#near-expiry-vendor-returns-rtv-transfers) |
| **Rule 55 Statutory Delivery Challans** | High (Legal/Accounting)| Medium | **Resolved** | [architecture_v1_6_5.md §5, §6, §8](architecture_v1_6_5.md#near-expiry-vendor-returns-rtv-transfers) |
| **Central Ingestion Push Atomicity & Quarantine**| High (Reliability) | Low | **Resolved** | [architecture_v1_6_5.md §5](architecture_v1_6_5.md#central-ingestion-atomicity-poison-pill-quarantine) |
| **POS Thermal Printer Resilience & 2-Phase** | High (Operational) | Low | **Resolved** | [architecture_v1_6_5.md §3, §4, §8](architecture_v1_6_5.md#8-invoicing-gst-credit-notes-debit-notes-delivery-challans) |
| **Windows OS File Security Hardening (`icacls`)** | Medium (Security) | Low | **Resolved** | [architecture_v1_6_5.md §16](architecture_v1_6_5.md#16-security-data-protection) |
| **Store-Local Sequential B2B Invoices** | Medium (Compliance) | Low | **Resolved** | [architecture_v1_6_5.md §8](architecture_v1_6_5.md#numbering-series-orthogonality) |
| **Dynamic NPCI UPI QR on Thermal Bill** | Medium (Operations) | Low | **Resolved** | [architecture_v1_6_5.md §8](architecture_v1_6_5.md#invoicing-specifications) |
| **Cashier One-Click WhatsApp Web Share** | Medium (Marketing) | Low | **Resolved** | [architecture_v1_6_5.md §3](architecture_v1_6_5.md#3-core-modules) |
| **Manual Insurance / TPA Tender Metadata** | High (Business) | Low | **Resolved** | [architecture_v1_6_5.md §9](architecture_v1_6_5.md#9-discounts) |

---

### Section C: v1.5 → v1.6 Resolved Baseline

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

#### Resolved Baseline Matrix (v1.5 → v1.6)

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
