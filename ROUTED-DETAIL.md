# Pharmacy POS — Routed Architectural Detail (`ROUTED-DETAIL.md`)

This document captures all detailed specifications, code blocks, payload structures, testing suites, and scenario matrices moved out of `architecture_v1_6_6.md` and `architecture_v1_6_5.md` during the Architecture Doc Compression Passes. 

This content is strictly partitioned by destination document (Docs 1–11) to directly seed the authoring of the modular documentation suite.

---

## Historical Version Archive: v1.6.6 Changelog Detail

*(Removed from header of architecture spec per discipline rule: "Collapse version history to one line per version, max 15 words")*

1. **Foundational Entities & Gating (§3, §6, §10)**: Sequential Goods Receipt Notes (GRN) capturing `purchase_price_per_unit` role-gated to Manager/Admin; short-receipt logging; zero-MRP free supply CHECK constraint; statutory drug schedule ENUM and NDPS dual-custody flags; Chapter 30 HSN validation.
2. **Transaction Integrity & Exchanges (§6, §8, §10)**: Atomic 3-event customer exchanges bound by `exchange_group_id` (`sale-return`, `credit-note-redemption`, `sale`) in a single database transaction; daily counter cash refund limit with split settlement; cumulative prescription balance tracking locked FOR UPDATE under Rule 65(11).
3. **Regulatory Hard-Blocks (§10)**: Unconditional checkout commit hard-block for CDSCO drug recalls with non-destructive line removal; scheduled midnight opening balance materialization for Schedule X running ledger; DPDP Act 2023 soft patient consent.
4. **Two-Tier Authentication & Access Governance (§11)**: Tier A Session Quick-PIN (4–6 digits) for high-frequency supervisor overrides; Tier B Full Argon2id Password for high-liability compliance actions; user `token_generation` counter for instantaneous JWT invalidation; progressive login throttling.
5. **Sync Scaling & Edge Resilience (§2, §4, §5)**: Watermark-based paged sync batching (500-event ceiling) with transport chunking and MVCC staging; optimistic locking refresh-and-retry backed by 5-minute advisory lock; store API key auth header; standby WAL replication lag monitoring (>1h alert).
6. **Hardware & Peripheral Defense (§8)**: Audited `reprint` event with duplicate copy watermark; unrecognized barcode manual search fallback and telemetry logging; customer bill preview toggle; family phone search disambiguation with medical history masking.
7. **Shift & Financial Isolation (§13)**: Peer cashier shift isolation blocking cross-terminal inspection/closure; strict physical cash isolation in till variance formula (`sum(tender_split.cash)` vs `refund_settlement.cash`); binding crash-recovered transactions to historic shift IDs.
8. **Security & Cryptographic Audit (§16)**: Automated 4-hour Merkle tree event hashing for tamper-evident ledger proofs; annual AES-256 key rotation protocol with `key_id` tagging; ephemeral `training.*` isolated schema.
9. **Edge Rollout & System Health (§2, §17)**: Alembic pre-flight automated database backup script (`pg_dump -Fc`); tiered disk space health triggers (85% / 90% / 98%); Windows LTSC WSUS maintenance window deferral (2–3 AM); 30-second checkout drain on shutdown.
10. **Testing & Telemetry Expansion (§14, §15)**: Expanded automated test suite from Tests 1–20 to Tests 1–28; scheduled SKU velocity and cashier return anomaly telemetry jobs.

---

## Historical Version Archive: v1.6.5 Changelog Detail

1. **Fractional Inventory & Unit of Measure (UOM) Hierarchy (§3, §6)**: Stores and calculates batch inventory exclusively in atomic integer Base Dispensing Units (tablets, capsules, ml). Batch-level immutability for pack_size, packaging_unit, and base_unit prevents central catalog edits from distorting on-shelf stock counts. Legal Metrology Rule 2011 fractional rounding with statutory MRP price clamping. Scanning 1D/2D barcodes strictly defaults to 1 Packaging Unit (pack_size base units). Sealed blister cavities return to active inventory; cut/punctured cavities route to quarantine-write-off.
2. **Near-Expiry Vendor Returns (RTV) & Local Supplier Debit Notes (§5, §6, §8)**: Configurable shelf-expiry alert tiers (90d Amber FEFO / 60d Orange RTV packing / 30d Red shelf quarantine). Added stock-move: rtv-quarantine event. Introduced sequential, offline GST Debit Notes (<STORE_CODE>-DN-YYYYMM-XXXX) with CGST/SGST/IGST tax reversal breakdowns. Replicated distributor profiles for offline document generation.
3. **Rule 55 Inter-Store Statutory Delivery Challans (§5, §6, §8)**: Offline sequential Delivery Challans (<STORE_CODE>-DC-YYYYMM-XXXX) for physical branch road transport. Statutory guard mandates identical GSTIN and state codes; automatically blocks Challan and requires an IGST Stock Transfer Invoice for inter-state movements. Receipt discrepancy ingestion in transfer-receive splits into received_qty (intact), transit_breakage_qty (quarantine write-off with photo audit), and transit_shortage_qty (shrinkage investigation flag).
4. **Schedule X & NDPS Dual-Prescription Custody & Bound Ledger (§3, §5, §10)**: Mandatory digital scanning/photo capture of duplicate prescriptions (compressed to <250 KB WebP, AES-256 encrypted, 90-day edge retention with 2-year cloud archive). Dispense events capture registered Pharmacist PIN and State Pharmacy Council credentials. Automated, immutable Daily Running Balance Ledger (Opening + Receipts - Dispensed = Closing). One-click State Drug Licensing Authority statutory export.
5. **In-Store Multi-Counter LAN Topology & Failover Fencing (§2, §4)**: Counter 1 (Primary Node) runs authoritative Postgres on 127.0.0.1 and Store FastAPI on LAN (0.0.0.0:8000). Counter 2/3 (Worker Terminals) run lightweight UI connecting over LAN via mDNS (medpos-primary.local:8000) for dynamic DHCP router immunity. Single sequence authority maintains monotonic store_seq_no and gapless invoice series. Standby failover script (promote_to_primary.bat) enforces LAN reachability fencing and applies emergency sequence epoch (<STORE_CODE>-INV-YYYYMM-XXXX-F1) on total hardware loss.
6. **Central Batch Ingestion Push Atomicity & Poison-Pill Quarantine (§5)**: Wraps Central event batch ingestion and sequence watermark updates in a single atomic database transaction (BEGIN...COMMIT). Malformed/schema-violating events route to central_sync_quarantine with sync-quarantine-tombstone records in central_events to preserve sequence continuity without wedging the store retry queue.
7. **Thermal Receipt Printer Jam Resilience & Abandonment Accounting (§3, §4, §8, Hardware)**: Two-phase checkout commit (COMMITTED_PENDING_PRINT -> COMPLETED). Non-blocking 300ms ESC/POS status check with automatic OS print spooler fallback for write-only USB printers. Cash drawer kick synchronized with print spooling. Prominent UI error banner with one-click reprint and audited *** DUPLICATE COPY *** watermark. If customer leaves during a jam, cashier triggers an automated void issuing an offsetting GST Credit Note (<STORE_CODE>-CN-...), preserving gapless numbering.
8. **Windows OS Edge Security Hardening (§16)**: OS file permissions locked via icacls restricting AES-256 database keys and environment files strictly to NT SERVICE\MedPOS.
9. **Pragmatic Interim Enterprise Bridges (§3, §8, §9, §18)**: Sequential Store-Local B2B Invoices (<STORE_CODE>-B2B-YYYYMM-XXXX) under Rule 46(b) for manual monthly GSTR-1 upload; dynamic NPCI UPI QR string on 80mm thermal receipts (upi://pay?...); cashier one-click WhatsApp Web share link (wa.me); manual Insurance/TPA tender metadata fields.

---

## Doc 1: Data Schema Doc

### 1.1 Central Sync & Quarantine Table Schemas
```sql
-- Central sync event log
CREATE TABLE central_events (
    event_id UUID PRIMARY KEY,
    store_seq_no BIGINT NOT NULL,
    store_id VARCHAR(32) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    ingested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_store_event_seq UNIQUE (store_id, store_seq_no)
);

-- Store sequence watermarks
CREATE TABLE store_sync_watermarks (
    store_id VARCHAR(32) PRIMARY KEY,
    last_committed_seq BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Central poison-pill quarantine table
CREATE TABLE central_sync_quarantine (
    quarantine_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id UUID NOT NULL,
    store_id VARCHAR(32) NOT NULL,
    store_seq_no BIGINT NOT NULL,
    raw_payload JSONB NOT NULL,
    quarantine_reason TEXT NOT NULL,
    quarantined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved BOOLEAN NOT NULL DEFAULT FALSE,
    resolution_notes TEXT NULL
);
```

### 1.2 Batch Table UOM Field Schema & Constraints
```sql
-- Batch level immutability schema
ALTER TABLE batches ADD COLUMN packaging_unit VARCHAR(32) NOT NULL; -- e.g., 'Strip of 10', 'Bottle of 60ml'
ALTER TABLE batches ADD COLUMN base_unit VARCHAR(16) NOT NULL;      -- e.g., 'tablet', 'capsule', 'ml'
ALTER TABLE batches ADD COLUMN pack_size INTEGER NOT NULL CHECK (pack_size > 0);
ALTER TABLE batches ADD COLUMN strip_mrp NUMERIC(10,2) NOT NULL CHECK (strip_mrp > 0);
ALTER TABLE batches ADD COLUMN base_unit_mrp NUMERIC(10,4) NOT NULL; -- computed half-up (strip_mrp / pack_size)

-- Batch stock balance stored strictly as integer base dispensing units
ALTER TABLE batch_stock ADD COLUMN current_base_qty INTEGER NOT NULL DEFAULT 0 CHECK (current_base_qty >= 0);
```

### 1.3 Document Series Table Schemas & GST Line-Item Fields
```sql
-- Sequential document trackers
CREATE TABLE store_document_sequences (
    store_id VARCHAR(32) NOT NULL,
    doc_type VARCHAR(16) NOT NULL, -- 'INV', 'INV-F1', 'B2B', 'CN', 'DN', 'DC'
    year_month CHAR(6) NOT NULL,    -- 'YYYYMM'
    last_seq_no INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (store_id, doc_type, year_month)
);

-- GST Invoices (B2C and B2B)
CREATE TABLE invoices (
    invoice_id UUID PRIMARY KEY,
    invoice_number VARCHAR(64) UNIQUE NOT NULL, -- <STORE_CODE>-INV-YYYYMM-XXXX
    store_id VARCHAR(32) NOT NULL,
    invoice_type VARCHAR(16) NOT NULL,          -- 'B2C', 'B2B'
    customer_id UUID NULL,
    buyer_gstin VARCHAR(15) NULL,
    buyer_legal_name VARCHAR(128) NULL,
    gross_amount NUMERIC(10,2) NOT NULL,
    total_cgst NUMERIC(10,2) NOT NULL,
    total_sgst NUMERIC(10,2) NOT NULL,
    total_igst NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    total_discount NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    net_amount NUMERIC(10,2) NOT NULL,
    payment_status VARCHAR(16) NOT NULL,
    print_status VARCHAR(32) NOT NULL DEFAULT 'COMMITTED_PENDING_PRINT',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);

-- GST Invoice Line Items
CREATE TABLE invoice_line_items (
    line_item_id UUID PRIMARY KEY,
    invoice_id UUID NOT NULL REFERENCES invoices(invoice_id),
    drug_id UUID NOT NULL,
    batch_id UUID NOT NULL,
    hsn_code VARCHAR(8) NOT NULL,
    pack_qty INTEGER NOT NULL DEFAULT 0,
    loose_qty INTEGER NOT NULL DEFAULT 0,
    billed_base_qty INTEGER NOT NULL,          -- (pack_qty * pack_size) + loose_qty
    unit_price NUMERIC(10,2) NOT NULL,
    subtotal NUMERIC(10,2) NOT NULL,
    cgst_rate NUMERIC(5,2) NOT NULL,
    sgst_rate NUMERIC(5,2) NOT NULL,
    igst_rate NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    cgst_amount NUMERIC(10,2) NOT NULL,
    sgst_amount NUMERIC(10,2) NOT NULL,
    igst_amount NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    total_line_amount NUMERIC(10,2) NOT NULL
);
```

### 1.4 Discount Preset Table & TPA Metadata Schema
```sql
CREATE TABLE discount_presets (
    preset_id UUID PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    discount_percentage NUMERIC(5,2) NOT NULL CHECK (discount_percentage >= 0 AND discount_percentage <= 100),
    applies_to VARCHAR(16) NOT NULL, -- 'CATEGORY', 'ITEM', 'ALL'
    category_id UUID NULL,
    drug_id UUID NULL,
    version INTEGER NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);

-- TPA / Insurance tender metadata captured on invoices
CREATE TABLE invoice_tpa_metadata (
    invoice_id UUID PRIMARY KEY REFERENCES invoices(invoice_id),
    insurer_name VARCHAR(128) NOT NULL,
    policy_number VARCHAR(64) NOT NULL,
    approval_code VARCHAR(64) NOT NULL,
    claim_amount NUMERIC(10,2) NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### 1.5 Schedule H1 Register & Schedule X Ledger Table Schemas
```sql
CREATE TABLE schedule_h1_register (
    register_id UUID PRIMARY KEY,
    dispense_id UUID NOT NULL,
    store_id VARCHAR(32) NOT NULL,
    supply_date_time TIMESTAMP WITH TIME ZONE NOT NULL,
    patient_name VARCHAR(128) NOT NULL,
    patient_address TEXT NOT NULL,
    doctor_name VARCHAR(128) NOT NULL,
    doctor_address TEXT NOT NULL,
    doctor_council_reg_no VARCHAR(64) NOT NULL,
    drug_generic_name VARCHAR(128) NOT NULL,
    drug_brand_name VARCHAR(128) NOT NULL,
    batch_number VARCHAR(32) NOT NULL,
    manufacturer_name VARCHAR(128) NOT NULL,
    quantity_dispensed_base INTEGER NOT NULL,
    pack_size INTEGER NOT NULL,
    pharmacist_id UUID NOT NULL,
    pharmacist_reg_no VARCHAR(64) NOT NULL
);

CREATE TABLE schedule_x_running_ledger (
    ledger_entry_id UUID PRIMARY KEY,
    store_id VARCHAR(32) NOT NULL,
    batch_id UUID NOT NULL,
    entry_date DATE NOT NULL,
    opening_base_balance INTEGER NOT NULL,
    receipts_base_qty INTEGER NOT NULL DEFAULT 0,
    dispensed_base_qty INTEGER NOT NULL DEFAULT 0,
    closing_base_balance INTEGER NOT NULL,
    prescription_image_path TEXT NOT NULL,
    prescription_image_hash VARCHAR(64) NOT NULL,
    pharmacist_password_verified BOOLEAN NOT NULL DEFAULT TRUE,
    pharmacist_council_reg_no VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_batch_ledger_date UNIQUE (store_id, batch_id, entry_date)
);
```

### 1.6 Shift Session & Z-Report Table Schemas
```sql
CREATE TABLE cashier_shifts (
    shift_id UUID PRIMARY KEY,
    store_id VARCHAR(32) NOT NULL,
    terminal_id VARCHAR(16) NOT NULL,
    cashier_id UUID NOT NULL,
    opened_at TIMESTAMP WITH TIME ZONE NOT NULL,
    opening_cash_float NUMERIC(10,2) NOT NULL,
    closed_at TIMESTAMP WITH TIME ZONE NULL,
    closing_type VARCHAR(16) NULL,           -- 'NORMAL', 'FORCE_CLOSE'
    closed_by UUID NULL,
    declared_physical_cash NUMERIC(10,2) NULL,
    calculated_system_cash NUMERIC(10,2) NULL,
    cash_variance NUMERIC(10,2) NULL,
    total_card_sales NUMERIC(10,2) NULL,
    total_upi_sales NUMERIC(10,2) NULL,
    total_credit_notes_issued NUMERIC(10,2) NULL,
    total_credit_notes_redeemed NUMERIC(10,2) NULL,
    supervisor_notes TEXT NULL
);

CREATE TABLE day_end_z_reports (
    report_id UUID PRIMARY KEY,
    store_id VARCHAR(32) NOT NULL,
    report_date DATE NOT NULL,
    generated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    generated_by UUID NOT NULL,
    gross_sales NUMERIC(12,2) NOT NULL,
    net_sales NUMERIC(12,2) NOT NULL,
    total_tax_collected NUMERIC(12,2) NOT NULL,
    tender_breakdown JSONB NOT NULL,
    returns_summary JSONB NOT NULL,
    debit_notes_summary JSONB NOT NULL,
    shift_variances_summary JSONB NOT NULL,
    z_sequence_no INTEGER NOT NULL,
    CONSTRAINT uq_store_z_date UNIQUE (store_id, report_date)
);
```

### 1.7 Goods Receipt Note (GRN) & Short Receipts Table Schema (v1.6.6)
```sql
CREATE TABLE goods_receipt_notes (
    grn_id UUID PRIMARY KEY,
    grn_number VARCHAR(64) UNIQUE NOT NULL, -- <STORE_CODE>-GRN-YYYYMM-XXXX
    store_id VARCHAR(32) NOT NULL,
    distributor_id UUID NOT NULL,
    purchase_invoice_no VARCHAR(64) NOT NULL,
    purchase_invoice_date DATE NOT NULL,
    received_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    received_by UUID NOT NULL,
    gross_purchase_amount NUMERIC(12,2) NOT NULL,
    total_tax_amount NUMERIC(12,2) NOT NULL,
    net_purchase_amount NUMERIC(12,2) NOT NULL,
    has_short_receipt BOOLEAN NOT NULL DEFAULT FALSE,
    manager_review_notes TEXT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE goods_receipt_note_items (
    grn_item_id UUID PRIMARY KEY,
    grn_id UUID NOT NULL REFERENCES goods_receipt_notes(grn_id),
    drug_id UUID NOT NULL,
    batch_no VARCHAR(32) NOT NULL,
    expiry_date DATE NOT NULL,
    pack_size INTEGER NOT NULL CHECK (pack_size > 0),
    ordered_pack_qty INTEGER NOT NULL CHECK (ordered_pack_qty >= 0),
    received_pack_qty INTEGER NOT NULL CHECK (received_pack_qty >= 0),
    shortage_pack_qty INTEGER NOT NULL GENERATED ALWAYS AS (ordered_pack_qty - received_pack_qty) STORED,
    received_base_qty INTEGER NOT NULL, -- received_pack_qty * pack_size
    mrp NUMERIC(10,2) NOT NULL CHECK (mrp >= 0),
    purchase_price_per_unit NUMERIC(10,4) NOT NULL CHECK (purchase_price_per_unit >= 0),
    cgst_rate NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    sgst_rate NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    igst_rate NUMERIC(5,2) NOT NULL DEFAULT 0.00
);
```

### 1.8 Drug Classification, NDPS & Zero-MRP Constraints (v1.6.6)
```sql
CREATE TYPE drug_schedule_enum AS ENUM ('NONE', 'SCHEDULE_H', 'SCHEDULE_H1', 'SCHEDULE_X');

ALTER TABLE catalog_items ADD COLUMN drug_schedule drug_schedule_enum NOT NULL DEFAULT 'NONE';
ALTER TABLE catalog_items ADD COLUMN is_ndps BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE catalog_items ADD COLUMN is_free_supply BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE catalog_items ADD CONSTRAINT chk_zero_mrp_free_supply 
    CHECK ((is_free_supply = TRUE AND mrp = 0.00) OR (is_free_supply = FALSE AND mrp > 0.00));

ALTER TABLE batches ADD COLUMN rack_location VARCHAR(32) NOT NULL DEFAULT 'UNASSIGNED';
```

### 1.9 Cumulative Prescription Balance Ledger Table Schema (v1.6.6)
```sql
CREATE TABLE prescriptions (
    prescription_id UUID PRIMARY KEY,
    prescription_number VARCHAR(64) NOT NULL,
    patient_id VARCHAR(64) NOT NULL, -- <STORE_CODE>-PAT-UUID
    doctor_id VARCHAR(64) NOT NULL,  -- <STORE_CODE>-DOC-UUID
    prescribed_date DATE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_repeatable BOOLEAN NOT NULL DEFAULT FALSE,
    dpdp_consent_obtained BOOLEAN NOT NULL DEFAULT FALSE,
    dpdp_consent_timestamp TIMESTAMP WITH TIME ZONE NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE prescription_line_items (
    prescription_line_id UUID PRIMARY KEY,
    prescription_id UUID NOT NULL REFERENCES prescriptions(prescription_id),
    drug_id UUID NOT NULL,
    prescribed_base_units INTEGER NOT NULL CHECK (prescribed_base_units > 0),
    cum_dispensed_base_units INTEGER NOT NULL DEFAULT 0 CHECK (cum_dispensed_base_units >= 0),
    unfulfilled_base_units INTEGER NOT NULL CHECK (unfulfilled_base_units >= 0),
    CONSTRAINT chk_cum_dispensed_le_prescribed 
        CHECK (cum_dispensed_base_units + unfulfilled_base_units = prescribed_base_units)
);
```

### 1.10 Master Data Transport Paging & Staging Schema (v1.6.6)
```sql
CREATE TABLE master_data_staging (
    staging_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL,
    page_no INTEGER NOT NULL,
    total_pages INTEGER NOT NULL,
    master_version BIGINT NOT NULL,
    entity_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    ingested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_staging_page UNIQUE (batch_id, page_no)
);
```

### 1.11 Till Tender & Refund Split Isolation Tables (v1.6.6)
```sql
CREATE TABLE invoice_tender_splits (
    tender_split_id UUID PRIMARY KEY,
    invoice_id UUID NOT NULL REFERENCES invoices(invoice_id),
    cash NUMERIC(10,2) NOT NULL DEFAULT 0.00 CHECK (cash >= 0),
    card NUMERIC(10,2) NOT NULL DEFAULT 0.00 CHECK (card >= 0),
    upi NUMERIC(10,2) NOT NULL DEFAULT 0.00 CHECK (upi >= 0),
    credit_note NUMERIC(10,2) NOT NULL DEFAULT 0.00 CHECK (credit_note >= 0),
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE refund_settlements (
    settlement_id UUID PRIMARY KEY,
    credit_note_id UUID NOT NULL,
    cash NUMERIC(10,2) NOT NULL DEFAULT 0.00 CHECK (cash >= 0),
    credit_note_balance NUMERIC(10,2) NOT NULL DEFAULT 0.00 CHECK (credit_note_balance >= 0),
    authorized_by UUID NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE users ADD COLUMN token_generation INTEGER NOT NULL DEFAULT 1;
```

---

## Doc 2: Event Schema Doc

### 2.1 Full Event Payload Schemas for Events 1–21 & Tombstones
Every event payload adheres to JSONB structured typing:
1. `sale`: `{ "invoice_number": "<STORE_CODE>-INV-YYYYMM-XXXX", "customer_id": "UUID|null", "lines": [{ "drug_id": "UUID", "batch_id": "UUID", "pack_qty": 2, "loose_qty": 5, "base_qty": 25, "unit_price": 1.43, "line_total": 35.75, "cgst": 2.14, "sgst": 2.14 }], "payment": { "method": "CASH|CARD|UPI|SPLIT", "details": {} } }`
2. `b2b-sale`: `{ "invoice_number": "<STORE_CODE>-B2B-YYYYMM-XXXX", "buyer_gstin": "29AAAAA0000A1Z5", "buyer_name": "ABC Pharmacy Pvt Ltd", "lines": [...], "taxes": { "cgst": 100, "sgst": 100, "igst": 0 } }`
3. `sale-return`: `{ "credit_note_number": "<STORE_CODE>-CN-YYYYMM-XXXX", "original_invoice_number": "<STORE_CODE>-INV-...", "reason": "WRONG_MEDICATION|EXCESS", "items": [{ "drug_id": "UUID", "batch_id": "UUID", "returned_base_qty": 10, "condition": "SEALED_INTACT|PUNCTURED_CONTAMINATED", "destination": "active-inventory|quarantine-write-off", "refund_amount": 14.30 }] }`
4. `dispense`: `{ "prescription_id": "UUID", "patient_id": "<STORE_CODE>-PAT-UUID", "prescriber_id": "<STORE_CODE>-DOC-UUID", "is_schedule_h1": true, "is_schedule_x": false, "h1_payload": { "doctor_reg_no": "KMC-45920", "doctor_address": "Gupta Polyclinic, Bangalore", "patient_address": "123 Indiranagar, Bangalore", "drug_generic_name": "Amoxicillin + Clavulanate", "brand_name": "Augmentin 625 Duo", "batch_no": "AUG2026-01", "mfg_name": "GSK India", "dispensed_qty_base": 10, "pack_size": 10, "pharmacist_id": "UUID", "pharmacist_reg_no": "KPC-78219" }, "schedule_x_payload": { "duplicate_prescription_scanned": true, "prescription_image_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "dispensed_qty_base": 10, "running_balance_after": 40, "pharmacist_password_verified": true, "pharmacist_reg_no": "KPC-78219" } }`
5. `stock-move`: `{ "reason": "transfer-dispatch|transfer-receive|rtv-quarantine|write-off|adjustment-in", "reference_doc": "<STORE_CODE>-DC-...|<STORE_CODE>-DN-...", "lines": [{ "batch_id": "UUID", "base_qty": 50, "discrepancy_breakdown": { "received": 45, "breakage": 3, "shortage": 2 } }] }`
6. `shift-open`: `{ "terminal_id": "POS-01", "cashier_id": "UUID", "cashier_name": "John Doe", "opening_cash_float": 1000.00, "shift_epoch": 1 }`
7. `shift-close`: `{ "terminal_id": "POS-01", "cashier_id": "UUID", "declared_physical_cash": 14250.00, "system_cash": 14250.00, "variance": 0.00, "tender_totals": { "upi": 3400.00, "card": 5600.00 } }`
8. `shift-force-close`: `{ "terminal_id": "POS-01", "abandoned_cashier_id": "UUID", "authorized_manager_id": "UUID", "reason": "CASHIER_EMERGENCY_LEAVE", "manager_cash_count": 12000.00 }`
9. `patient-created`: `{ "patient_id": "<STORE_CODE>-PAT-UUID", "name": "Anita Roy", "phone": "9876543210", "address": "123 Indiranagar, Bangalore" }`
10. `doctor-created`: `{ "doctor_id": "<STORE_CODE>-DOC-UUID", "name": "Dr. S. K. Gupta", "reg_no": "KMC-45920", "clinic_address": "Gupta Polyclinic, Bangalore" }`
11. `discount-edit`: `{ "preset_id": "UUID", "field": "discount_percentage", "old_value": 10.0, "new_value": 12.5, "authorized_by": "UUID", "version": 4 }`
12. `master-data-edit`: `{ "table": "catalog_items", "record_id": "UUID", "field_name": "hsn_code", "current_value": "30049099", "proposed_value": "30041010", "expected_version": 2 }`
13. `master-data-created`: `{ "table": "catalog_items", "business_key": "8901234567890", "initial_payload": { "brand_name": "Augmentin 625 Duo", "generic_name": "Amoxicillin and Potassium Clavulanate", "hsn_code": "30041010", "gst_rate": 12.00, "drug_schedule": "H1", "is_ndps": false, "pack_size": 10, "packaging_unit": "Strip of 10", "base_unit": "tablet", "mrp": 204.50 }, "version": 1 }`
14. `master-data-change-requested`: `{ "request_id": "UUID", "manager_id": "UUID", "scope": { "field": "mrp", "old": 120, "new": 135 }, "expected_version": 3 }`
15. `master-data-change-approved`: `{ "request_id": "UUID", "decided_by": "UUID", "status": "APPROVED" }`
16. `master-data-change-rejected`: `{ "request_id": "UUID", "decided_by": "UUID", "status": "REJECTED", "rejection_reason": "stale|duplicate|stock-remaining|manual" }`
17. `low-stock-alert`: `{ "item_id": "UUID", "store_id": "STORE-01", "current_stock_base": 14, "threshold_base": 20 }`
18. `settings-change`: `{ "setting_key": "compliance_mode", "old_value": "MANDATORY", "new_value": "OPTIONAL", "changed_by": "UUID" }`
19. `grn`: `{ "grn_number": "<STORE_CODE>-GRN-YYYYMM-XXXX", "distributor_id": "UUID", "purchase_invoice_no": "INV-2026-8812", "purchase_invoice_date": "2026-09-20", "received_at": "2026-09-22T10:00:00Z", "received_by": "UUID", "lines": [{ "drug_id": "UUID", "batch_no": "BCH-9921", "expiry_date": "2028-09-30", "mrp": 120.00, "purchase_price_per_unit": 85.50, "ordered_pack_qty": 10, "received_pack_qty": 10, "pack_size": 10, "base_qty": 100, "hsn_code": "30041010", "cgst_rate": 6.0, "sgst_rate": 6.0 }] }`
20. `credit-note-redemption`: `{ "redemption_id": "UUID", "credit_note_number": "<STORE_CODE>-CN-YYYYMM-XXXX", "redeemed_invoice_number": "<STORE_CODE>-INV-YYYYMM-XXXX", "customer_id": "UUID|null", "redeemed_amount": 250.00, "remaining_credit_balance": 150.00, "authorized_by": "UUID" }`
21. `reprint`: `{ "reprint_id": "UUID", "document_type": "INVOICE|CREDIT_NOTE|DEBIT_NOTE|CHALLAN", "document_number": "<STORE_CODE>-INV-YYYYMM-XXXX", "reason": "PRINTER_PAPER_JAM|CUSTOMER_DAMAGED_COPY|AUDIT_REPRINT", "authorized_by": "UUID", "terminal_id": "POS-01", "timestamp": "2026-09-22T10:15:30Z", "watermark_applied": "*** DUPLICATE COPY ***" }`
- `sync-quarantine-tombstone`: `{ "quarantined_event_id": "UUID", "original_event_type": "sale", "error_code": "SCHEMA_VIOLATION", "quarantine_timestamp": "2026-09-19T23:36:00Z" }`

### 2.2 Atomic Central Batch Ingestion SQL Flow
```sql
BEGIN;
  -- 1. Deduplicated batch insert
  INSERT INTO central_events (event_id, store_seq_no, store_id, created_at, event_type, payload)
  VALUES (:event_id, :store_seq_no, :store_id, :created_at, :event_type, :payload)
  ON CONFLICT (event_id) DO NOTHING;

  -- 2. Watermark progress commit
  UPDATE store_sync_watermarks 
  SET last_committed_seq = :max_batch_seq, updated_at = CURRENT_TIMESTAMP 
  WHERE store_id = :store_id AND last_committed_seq < :max_batch_seq;
COMMIT;
```

### 2.3 Exchange 3-Event Transaction Payload & Recall Message (v1.6.6)
```json
{
  "exchange_group_id": "550e8400-e29b-41d4-a716-446655440000",
  "events": [
    {
      "event_type": "sale-return",
      "credit_note_number": "STORE-01-CN-202609-0012",
      "returned_items": [{"drug_id": "UUID", "batch_id": "UUID", "qty": 10, "credit_amount": 150.00}]
    },
    {
      "event_type": "credit-note-redemption",
      "credit_note_number": "STORE-01-CN-202609-0012",
      "redeemed_amount": 150.00,
      "remaining_credit": 0.00
    },
    {
      "event_type": "sale",
      "invoice_number": "STORE-01-INV-202609-0089",
      "lines": [{"drug_id": "UUID", "batch_id": "UUID", "qty": 1, "line_total": 150.00}],
      "payment": {"method": "STORE_CREDIT_EXCHANGE", "exchange_group_id": "550e8400-e29b-41d4-a716-446655440000"}
    }
  ]
}
```

```json
{
  "event_type": "batch-recall",
  "recall_id": "CDSCO-REC-2026-042",
  "drug_id": "550e8400-e29b-41d4-a716-446655440000",
  "batch_no": "AUG2026-01",
  "reason": "SUB_POTENCY_ALERT",
  "recalled_at": "2026-09-22T08:00:00Z",
  "quarantine_action": "HARD_BLOCK_CHECKOUT"
}
```

---

## Doc 3: API Contract Doc

### 3.1 Central Sync Ingestion Endpoint Contract
- **Endpoint**: `POST /api/v1/sync/events/batch`
- **Caller**: Store Primary Node (Counter 1 Sync Service).
- **Authentication**: Store Mutual TLS / Bearer Store Gateway Token.
- **Request Headers**:
  - `X-Store-ID`: `STORE-01`
  - `Content-Type`: `application/json`
- **Request Schema**:
  ```json
  {
    "store_id": "STORE-01",
    "batch_size": 50,
    "events": [
      {
        "event_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        "store_seq_no": 1042,
        "store_id": "STORE-01",
        "created_at": "2026-09-19T18:00:00.000Z",
        "event_type": "sale",
        "payload": {
          "invoice_number": "STORE-01-INV-202609-0042",
          "net_amount": 1050.00,
          "lines": [{"drug_id": "UUID", "batch_no": "BCH-01", "qty": 10}]
        }
      }
    ]
  }
  ```
- **Response Schema (200 OK)**:
  ```json
  {
    "status": "success",
    "acknowledged_seq": 1042,
    "quarantined_events": [
      "550e8400-e29b-41d4-a716-446655440000"
    ],
    "downstream_master_data": {
      "catalog_updates": [],
      "governance_decisions": []
    }
  }
  ```
- **Error Codes**:
  - `400 BAD_REQUEST`: Malformed envelope structure.
  - `401 UNAUTHORIZED`: Invalid store certificate or expired token.
  - `409 SEQUENCE_GAP`: Store sequence dropped a number.

### 3.2 Central Admin Web Portal Endpoints
- `GET /api/v1/admin/governance/requests` — View pending master-data change requests.
- `POST /api/v1/admin/governance/requests/{id}/approve` — Approve change request with version increment.
- `POST /api/v1/admin/governance/requests/{id}/reject` — Reject change request with reason code.
- `GET /api/v1/admin/reports/shrinkage` — Multi-store aggregate shrinkage and in-line stock adjustment reports.

### 3.3 Paged Sync Pull Endpoint Contract (v1.6.6)
- **Endpoint**: `GET /api/v1/sync/events/pull`
- **Caller**: Store Counter 1 Sync Worker.
- **Query Parameters**:
  - `page`: Integer (default 1)
  - `page_size`: Integer (default 500, max 500)
  - `continuation_watermark`: Monotonic sequence integer
- **Response Schema (200 OK)**:
  ```json
  {
    "page": 1,
    "page_size": 500,
    "total_pages": 4,
    "has_more": true,
    "next_continuation_token": "seq_500",
    "batch_id": "550e8400-e29b-41d4-a716-446655440000",
    "events": []
  }
  ```

### 3.4 Optimistic Locking Refresh-and-Retry & Advisory Lock Contract (v1.6.6)
- **Advisory Lock Endpoint**: `POST /api/v1/master-data/lock`
- **Request**: `{"table": "catalog_items", "record_id": "550e8400-e29b-41d4-a716-446655440000", "lock_duration_sec": 300}`
- **Response (200 OK)**: `{"status": "LOCKED", "locked_by": "UUID", "expires_at": "2026-09-22T10:20:00Z"}`
- **Stale Rejection (409 Conflict)**:
  ```json
  {
    "error": "STALE_VERSION_CONFLICT",
    "table": "catalog_items",
    "record_id": "550e8400-e29b-41d4-a716-446655440000",
    "submitted_version": 4,
    "current_version": 5,
    "current_record": {},
    "message": "Record has been updated remotely. Please refresh and retry."
  }
  ```

### 3.5 Store API Key Authentication Header Specification (v1.6.6)
- **Header**: `X-Store-API-Key: <STORE_CODE>.<SECRET_KEY_HASH>`
- **Key Rotation**: Dual-key support during 30-day rotation grace period.

---

## Doc 4: RBAC Permission Matrix

### 4.1 Comprehensive Action-by-Role Grid
| Action / Capability | Pharmacist | Cashier | Manager | Admin | High-Access (Simple) | Low-Access (Simple) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Front-Desk Checkout (B2C/B2B) | No | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** |
| Apply Configured Discount Presets | No | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** |
| Open / Close Own Shift Float | No | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** |
| Dispense General Drugs | **Yes** | No | **Yes** | **Yes** | **Yes** | No |
| Dispense Schedule H1 / X Drugs | **Yes** | Blocked | **Yes** | **Yes** | **Yes** | Blocked |
| Prescription Digital Capture | **Yes** | No | **Yes** | **Yes** | **Yes** | No |
| Authorize Customer Sales Return | No | No | **Yes** | **Yes** | **Yes** | No |
| Issue Vendor RTV Debit Note | No | No | **Yes** | **Yes** | **Yes** | No |
| Rule 55 Delivery Challan Dispatch/Receive | No | No | **Yes** | **Yes** | **Yes** | No |
| Authorize POS In-line `adjustment-in` | No | No | **Yes** | **Yes** | **Yes** | No |
| Force-Close Abandoned Cashier Shift | No | No | **Yes** | **Yes** | **Yes** | No |
| Disable Compromised Local User Account | No | No | **Yes** | **Yes** | **Yes** | No |
| Direct Edit Discount Presets (Live) | No | No | **Yes** | **Yes** | **Yes** | No |
| Submit Master-Data Change Request | No | No | **Yes** | **Yes** | **Yes** | No |
| Direct Master-Data Edit/Create/Delete | No | No | No | **Yes** | **Yes** | No |
| Approve/Reject Governance Requests | No | No | No | **Yes** | **Yes** | No |
| Configure Compliance Mode | No | No | No | **Yes** | **Yes** | No |

### 4.2 Comprehensive Two-Tier Authentication & Field Visibility Matrix (v1.6.6)
| Operational Capability / Action | Tier A: Quick-PIN (Session) | Tier B: Full Argon2id Password |
|---|:---:|:---:|
| Cashier Ad-Hoc Discount Override ($\le 15\%$) | Permitted | Permitted |
| Manager Quick-PIN Discount Override ($\le 100\%$, $\le ₹5,000$/mo) | **Required** | Permitted |
| High-Liability Offline Discount Override ($> ₹5,000$ pool exhaustion) | Blocked | **Required** |
| Damaged-on-Shelf Inventory Write-Off | **Required** | Permitted |
| Schedule H1 Dispense Pharmacist Sign-Off | **Required** | Permitted |
| Schedule X / NDPS Dispense Custody Verification | Blocked | **Required** |
| Local User Account Disablement / Revocation | Blocked | **Required** |
| Master-Data Change Request Approval | Blocked | **Required** |
| Training Mode Schema Reset / Reinitialization | Blocked | **Required** |
| Purchase Price Per Unit (`purchase_price_per_unit`) Visibility | Manager/Admin Only | Admin Only |

---

## Doc 5: Critical Flow State Machines

### 5.1 Standby Failover Script Steps & Fencing State Machine
Script: `promote_to_primary.bat` on Counter 2:
1. **Step 1 (LAN Fencing Check)**: 
   - Script attempts HTTP GET `http://192.168.1.10:8000/health` and ICMP ping against Counter 1.
   - If Counter 1 returns 200 OK or responds to ping, promotion aborts immediately with error: `SPLIT_BRAIN_HAZARD_ABORT`.
2. **Step 2 (Local Service Activation)**:
   - Starts Windows service `postgresql-x64-16` on Counter 2.
   - Executes `pg_ctl promote` to take local database out of WAL standby mode.
   - Starts `medpos-fastapi` Windows service.
3. **Step 3 (Emergency Sequence Epoch Shift)**:
   - Sets local document configuration parameter: `ACTIVE_INVOICE_EPOCH = '<STORE_CODE>-INV-YYYYMM-XXXX-F1'`.
   - Executes SQL: `SELECT setval('store_seq_no_seq', (SELECT MAX(store_seq_no) + 100000 FROM events));`.

### 5.2 Outbound Sync Retry & Backoff State Machine
```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> SyncTriggered: Interval (30s) / Reconnect / Manual
    SyncTriggered --> PackagingBatch: Query events WHERE store_seq_no > watermark
    PackagingBatch --> Transmitting: POST /api/v1/sync/events/batch
    Transmitting --> AckReceived: HTTP 200 OK
    Transmitting --> NetworkFailed: Connection Timeout / DNS Error
    AckReceived --> AdvanceWatermark: Update local sync watermark
    AdvanceWatermark --> Idle
    NetworkFailed --> ExponentialBackoff: Backoff = min(60s, 2^retries * 2) + jitter
    ExponentialBackoff --> Transmitting
```

### 5.3 Batch Picking & Fractional Return Inspection
- **Picking Priority**:
  1. GS1 DataMatrix 2D Barcode scanned -> Explicit Batch override.
  2. Manual search -> FEFO suggestion (earliest expiring batch with `current_base_qty > 0`).
  3. Multi-batch splitting triggered automatically if requested quantity > selected batch stock.
- **Return Inspection Routing**:
  - Unopened blister strip / intact airtight foil cavities -> Restock to `active-inventory`.
  - Torn foil, punctured cavities, cut blister strip without seal -> Route to `quarantine-write-off`.
  - Cold-chain medication (insulin/vaccines) -> Mandatory route to `quarantine-write-off`.
  - Batch expired since purchase -> Mandatory route to `quarantine-write-off`.

### 5.4 Two-Phase Checkout Print Commit & Abandonment Void Workflow
1. Cashier clicks "Tender & Bill".
2. Transaction commits locally in Postgres: `invoices.print_status = 'COMMITTED_PENDING_PRINT'`.
3. POS queries thermal printer via ESC/POS (`ESC v` / non-blocking status check, 300ms timeout).
4. If printer ready:
   - Spools ESC/POS byte stream.
   - Triggers drawer kick pulse (`ESC p 0 25 250`) via RJ11.
   - Updates status: `invoices.print_status = 'COMPLETED'`.
5. If printer paper jam or offline:
   - Spooler fallback active. UI triggers red error banner: *"Printer Jam / Offline"*.
   - Cashier one-click action: "Reprint Receipt" -> prints with audited watermark `*** DUPLICATE COPY ***`.
   - Customer abandonment: Customer walks away without receipt. Cashier clicks "Void & Offset" -> System creates automated `sale-return` issuing offsetting `<STORE_CODE>-CN-YYYYMM-XXXX`, restoring stock and preserving monotonic gapless invoice numbering.

### 5.5 Low-Stock Alert State Lifecycle & Cooldown Flow
- **State Machine**:
  1. `NORMAL`: Current base stock > configured low-stock threshold.
  2. `ALERT_ACTIVE`: Triggered when available base stock drops $\le$ threshold. POS emits discrete `low-stock-alert` event. Subsequent checkout sales below threshold suppress re-alerting (cooldown period) to prevent log flooding.
  3. `REPLENISHED`: Inbound `grn` or `stock-move: transfer-receive` raises base stock above threshold $\rightarrow$ transitions back to `NORMAL`, clearing alert cooldown.
  4. `CLOSED_DISCONTINUED`: Deliberate Manager `stock-move: write-off` zeroes stock without replenishment intent $\rightarrow$ transitions to `CLOSED_DISCONTINUED`.

### 5.6 Live Discount Edit & Version Verification Flow
- **State Flow**:
  1. Manager/High-access user opens preset edit dialog on store terminal.
  2. Terminal executes `GET /api/v1/presets/{id}` to verify live Central connectivity and fetch current integer `version`.
  3. User submits updated percentage with `expected_version`.
  4. Central evaluates version:
     - If match: Central commits edit, increments `version`, emits `discount-edit` event, returns HTTP 200 OK. Store updates local cache.
     - If conflict (`stale`): Central returns HTTP 409 Conflict with latest record. POS UI prompts: *"Preset updated remotely. Reloading latest values."*
  5. If WAN partition active: Edit UI disables with advisory banner: *"Preset edits require active Central connection."*

### 5.7 Master-Data Change Request State Machine
- **State Flow**:
  1. `DRAFT`: Store Manager prepares single-field, single-record diff (`field_name`, `current_value`, `proposed_value`, `expected_version`).
  2. `SUBMITTED_PENDING`: Event `master-data-change-requested` committed and synced to Central governance queue.
  3. Central Admin Decision:
     - `APPROVED`: Admin approves in Web portal $\rightarrow$ Central applies mutation, increments record version, emits `master-data-change-approved`. Store ingests update via next sync response.
     - `REJECTED`: Admin rejects $\rightarrow$ Central emits `master-data-change-rejected` with reason code (`manual`, `stale`, `duplicate`, `stock-remaining`). Store Manager alerted on dashboard.

### 5.8 Shift Lifecycle & Till Reconciliation State Machine
- **State Flow**:
  1. `CLOSED`: Terminal register locked. Cashier enters credentials and opening cash float $\rightarrow$ POS commits `shift-open` event $\rightarrow$ Transitions to `OPEN`.
  2. `OPEN`: Active billing permitted on this terminal. Transactions record tender split (`cash`, `card`, `upi`, `store-credit`).
  3. `CLOSING_PENDING_DECLARATION`: Cashier initiates shift close $\rightarrow$ prompts blind physical cash count (`declared_physical_cash`).
  4. `RECONCILED`: System calculates Till Variance:
     $$\text{Variance} = \text{Declared Cash} - (\text{Opening Float} + \text{Cash Sales} - \text{Cash Refunds})$$
     - `Cash Sales` strictly isolates physical cash tenders (`sum(tender_split.cash)`), excluding store credit voucher redemptions and digital payments.
     - POS commits `shift-close` event with tender breakdown. Day-End Z-Report aggregates all terminal shifts for store closing.
  5. `CLOSED_FORCE`: If cashier leaves terminal open, Store Manager executes emergency supervisory force-close providing physical cash count $\rightarrow$ commits `shift-force-close` event.

### 5.9 Atomic Exchange 3-Event State Machine (v1.6.6)
```mermaid
stateDiagram-v2
    [*] --> ExchangeInitiated: Customer presents returned item + selected replacement
    ExchangeInitiated --> ReturnStaged: Inspect returned item (sealed vs damaged)
    ReturnStaged --> ReplacementStaged: Select replacement batch & calculate price delta
    ReplacementStaged --> SingleTxBegin: Cashier clicks 'Commit Exchange'
    SingleTxBegin --> EmitReturn: 1. Commit 'sale-return' -> Generates Credit Note
    EmitReturn --> EmitRedemption: 2. Commit 'credit-note-redemption' -> Claims Credit Note balance
    EmitRedemption --> EmitSale: 3. Commit 'sale' -> Bills replacement with Credit Note tender
    EmitSale --> SingleTxCommit: Single Postgres Transaction Commit (All 3 succeed or all rollback)
    SingleTxCommit --> PrintReceipt: Print combined Exchange Receipt with audit ref
    PrintReceipt --> [*]
```

### 5.10 CDSCO Drug Recall Hard-Block & Cart Removal Flow (v1.6.6)
1. Central dispatches `batch-recall` event via sync push payload.
2. Store Primary Node ingests event, immediately setting batch status to `RECALLED_QUARANTINED` in `batches` table.
3. Active checkout carts scanning the batch receive instant blocking notification: *"Batch is subject to statutory CDSCO drug recall. Sale prohibited."*
4. Concurrent checkout race defense: If cashier commits cart while recall arrives, checkout commit executes validation query in `COMMITTED_PENDING_PRINT` phase.
5. If batch recalled, commit aborts with HTTP 409 `DRUG_RECALL_BLOCK`.
6. POS UI provides non-destructive line removal, allowing customer to purchase remaining non-recalled medications without rebuilding cart.

### 5.11 Manager Quick-PIN Discount Override & Pool Exhaustion State Machine (v1.6.6)
- **Monthly Store Pool**: ₹5,000 calendar month allocation.
- **Workflow**:
  - Cashier enters discount $> 15.0\%$. Terminal prompts for Manager Quick-PIN.
  - Manager enters 4–6 digit Quick-PIN. System checks `current_month_consumed + override_discount <= 5000.00`.
  - If pool sufficient: Discount applied, pool incremented, override logged with reason category.
  - If pool exhausted: Terminal prompts for Emergency High-Access Password override.
  - Simple Preset fallback: Single High-Access Argon2id Password permits up to ₹1,500 per sale for non-controlled items with $\ge 20$ character audit remark and `emergency_offline_override = true` flag.

---

## Doc 6: Conflict & Edge Case Matrix

### 6.1 Partition Ghost-Stock Ingestion & Auto-Resurrection
- **Scenario**: Store A is disconnected from WAN for 3 days. Central Admin checks chain-wide stock for Item X; stock shows 0 based on latest sync. Admin soft-deletes Item X (`deleted_at = CURRENT_TIMESTAMP`). Store A sells 5 units of Item X from on-shelf physical stock during day 2 of partition.
- **Ingestion Conflict**: Store A reconnects and pushes `sale` event for soft-deleted Item X.
- **Resolution**:
  1. Central does NOT reject the sale.
  2. Central checks if $Stock_{\text{initial}} - Qty_{\text{sold}} > 0$.
  3. If remaining stock > 0, Central automatically clears soft-deletion: `UPDATE catalog_items SET deleted_at = NULL WHERE item_id = :id;`.
  4. Central dispatches notification to Central Admin and Store Manager: *"Product auto-resurrected due to partition-era stock discovery"*.

### 6.2 Master-Data Version Concurrency Conflicts
- **Scenario**: Manager at Store 1 and Admin at Central simultaneously edit the price of Amoxicillin 500mg. Both start from `version = 4`.
- **Resolution**:
  - Admin commits first -> Version increments to 5.
  - Manager's live request arrives with `expected_version = 4`.
  - Central rejects Manager request with HTTP 409 Conflict: `{"reason": "stale", "current_version": 5}`.
  - Store UI prompts Manager: *"Catalog updated by Central. Reloading latest data."*

### 6.3 V2 Enterprise Distributed Edge Cases & Scenarios
- **Scenario A (Supplier Settlement Partition)**: Store issues sequential vendor return Debit Note (`<STORE>-DN-...`) offline during WAN partition. Distributor settlement is managed locally via physical credit memo; central AP ledger reconciles asynchronously upon sync reconnection via manual GSTR-1 return matching bridge.
- **Scenario B (Branch Transit Discrepancy Arbitration)**: Inter-store transfer of 100 units arrives at Store B with 10 broken in transit. Store B `transfer-receive` logs 90 received, 10 `transit_breakage_qty` with photo audit. Automatic Delivery Challan (`<STORE>-DC-...`) variance breakdown allocates loss to transit write-off without wedging destination inventory.
- **Scenario C (Offline Store Credit Cross-Branch Attempt)**: Customer attempts to redeem `<STORE_A>-CN-...` voucher at Store B. Terminal UI enforces issuing-store restriction: *"Store Credit redeemable solely at issuing branch (Store A)."* Distributed 2PL cross-store voucher coordinator is deferred to V2.

### 6.4 CDSCO Recall Race Condition at Checkout (v1.6.6)
- **Scenario**: Cashier scans Batch BCH-99 at 10:14:50. At 10:14:55, sync worker receives CDSCO recall for BCH-99. Cashier clicks "Tender & Bill" at 10:14:58.
- **Resolution**:
  - Backend checkout transaction begins with `SELECT is_recalled FROM batches WHERE batch_id = :id FOR UPDATE;`.
  - Lock acquires latest state `is_recalled = TRUE`.
  - Checkout rolls back immediately and returns HTTP 409 Conflict: `{"code": "DRUG_RECALL_BLOCK", "batch_no": "BCH-99"}`.
  - UI offers non-destructive removal of BCH-99 while retaining other items in cart.

### 6.5 Net Effective Discount Clamping & Stacking Prevention (v1.6.6)
- **Validation Formula**:
  $$\text{Line Discount \%} = \frac{\text{Line MRP} - \text{Billed Unit Price}}{\text{Line MRP}} \times 100 \le 15.0\%$$
- **Zero-MRP Free Supply Exemption**: Zero-MRP items (`is_free_supply = true`) are strictly barred from discount application; formulas bypass division by zero.
- **Purchase Price Floor**: Billed unit price cannot fall below `purchase_price_per_unit` without Tier B Manager Password override.

### 6.6 Rack Micro-Freeze Concurrent Billing Resolution (v1.6.6)
- During physical stock-take, Manager applies 5–10 minute rack micro-freeze to `rack_location = 'RACK-B4'`.
- Batches located on `RACK-B4` are temporarily locked against checkout picking (`picking_status = 'MICRO_FREEZE'`).
- Cashiers attempting to bill batch from `RACK-B4` are prompted: *"Rack B4 undergoing stock-take (est. 4 min). Select alternate batch or wait."*
- `rack_location` is store-local and never overwritten by central sync catalog updates.

### 6.7 Unrecognized Barcode Fallback & Phone Search History Masking (v1.6.6)
- Barcode miss: Scanner reads unregistered EAN/UPC. POS pops up rapid manual drug search modal, while logging gap telemetry event `barcode_gap_miss`.
- Phone search privacy: Cashier searching by customer phone number views family member names and ages for disambiguation, but previous prescription drug histories remain masked until customer profile is selected and verified.

---

## Doc 7: Dependency Map

### 7.1 Core Module Build Order
```mermaid
graph TD
    M-11[M-11: User Roles & Auth] --> M-08[M-08: Multi-Store Master Data]
    M-08 --> M-12[M-12: Settings & Config]
    M-08 --> M-01[M-01: Inventory & UOM Hierarchy]
    M-01 --> M-09[M-09: Operational Directories]
    M-01 --> M-06[M-06: Billing & Cashier Operations]
    M-01 --> M-05[M-05: Prescription & Dispensing]
    M-06 --> M-02[M-02: Customer Returns]
    M-06 --> M-07[M-07: Hardware Peripherals]
    M-01 --> M-03[M-03: Vendor RTV]
    M-01 --> M-04[M-04: Branch Stock Transfers]
    M-06 --> M-13[M-13: Reporting & Till Reconciliation]
    M-01 --> M-10[M-10: Sync Engine]
```

### 7.2 V2 Enterprise Module Dependencies & Architectural Roadmap
- **Phase 2.0 Module Evolution**:
  1. `M-14: Distributor EDI & AP Settlement Gateway` (Depends on M-03, M-08, M-10)
  2. `M-15: Central In-Transit Virtual Logistics Pool` (Depends on M-04, M-10)
  3. `M-16: Government NIC/IRP E-Invoicing Gateway` (Depends on M-06, M-08)
  4. `M-17: Cross-Store Voucher Distributed 2PL Coordinator` (Depends on M-02, M-06, M-10)
  5. `M-18: Edge Prescription Computer Vision OCR` (Depends on M-05, M-07)

### 7.3 Core Dependency Graph & Tier 1–4 Build Order (v1.6.6)
```mermaid
graph TD
    subgraph Tier 1: Foundation Entities
        T1_GRN[M-01: GRN & Purchase Price]
        T1_ZeroMRP[M-01: Zero-MRP & DPCO]
        T1_NDPS[M-05: NDPS & Schedules]
        T1_UOM[M-01: UOM Immutability]
    end

    subgraph Tier 2: Core Transactions
        T2_Exch[M-02: Atomic Exchanges]
        T2_Refund[M-06: Daily Cash Refund Ceiling]
        T2_Presc[M-05: Repeat Dispense & Cum Balances]
        T2_Recall[M-01/M-06: Recall Hard-Block]
    end

    subgraph Tier 3: Peripheral & Auth
        T3_Auth[M-11: Two-Tier Auth & Token Gen]
        T3_Sync[M-10: Paged Transport Staging]
        T3_Till[M-13: Tender Split Isolation]
    end

    subgraph Tier 4: Edge Hardening
        T4_Disk[M-12: Tiered Disk Health]
        T4_Merkle[M-11/M-13: Merkle Audit Hashing]
        T4_Backup[M-12: Pre-Flight Migrations]
    end

    T1_GRN --> T2_Exch
    T1_NDPS --> T2_Presc
    T2_Exch --> T3_Till
    T2_Presc --> T3_Auth
    T3_Sync --> T4_Disk
    T3_Auth --> T4_Merkle
```

---

## Doc 8: Test Plan Doc

### 8.1 Automated Unit & Integration Test Specifications (Tests 1–20)
1. **Absolute Expiry Hard-Block**: Bill batch with $\text{expiry} < \text{current\_date (IST)}$ in `Optional` compliance mode. Assert: Batches on final day of expiry month remain valid; batches past expiry date are unconditionally hard-blocked.
2. **UOM Integer Division & Rounding**: Test packaging with MRP ₹10.00 and pack size 7. Assert: Base unit price ₹1.43; buying 7 loose units clamped to ₹10.00 (not ₹10.01).
3. **UOM Barcode Scan Default**: Scan 2D DataMatrix for strip of 10. Assert: POS defaults to 10 base units on invoice line.
4. **Schedule H1 Completeness**: Dispense Schedule H1 drug without patient address or prescriber registration. Assert: Validation error, dispense blocked.
5. **Schedule X Prescription & Ledger**: Dispense Schedule X drug without prescription image or pharmacist Tier B Argon2id password verification. Assert: Blocked. Ingest valid dispense; assert daily balance equation reconciles.
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

### 8.2 Automated Test Suite Expansion: Tests 21 through 28 (v1.6.6)
21. **GRN Short Receipts & Role Gating**: Attempt GRN creation with Cashier role -> Blocked with HTTP 403. Ingest GRN with 10 ordered, 8 received -> Verify 8 added to base stock, shortage of 2 recorded in `goods_receipt_note_items`, Manager review flag set.
22. **Zero-MRP Validation & Discount Block**: Attempt creating item with `mrp = 0` and `is_free_supply = false` -> Blocked by CHECK constraint. Apply discount to free supply item -> Blocked with zero division bypass.
23. **Atomic Exchange 3-Event Transaction**: Execute exchange: return ₹150 item and buy ₹150 replacement. Assert single transaction atomicity (`exchange_group_id` links `sale-return`, `credit-note-redemption`, and `sale`). Simulate DB failure on step 3 -> Assert steps 1 and 2 roll back completely, zero dangling credit.
24. **CDSCO Drug Recall Checkout Hard-Block**: Deliver `batch-recall` event. Attempt checkout of cart containing recalled batch -> Commits fail with HTTP 409 `DRUG_RECALL_BLOCK`. Perform non-destructive line removal -> Verify remaining cart items bill successfully.
25. **Rule 65(11) Repeat Dispensing Enforcement**: Dispense Schedule H drug with `is_repeatable = false`. Attempt subsequent dispense against same prescription -> Hard-blocked. Ingest repeatable prescription for 30 units -> Dispense 10 units -> Assert cumulative balance shows 20 unfulfilled units.
26. **Two-Tier Authentication & Token Revocation**: Execute Damaged-on-shelf write-off with Quick-PIN -> Succeeds. Attempt Schedule X dispense with Quick-PIN -> Blocked, requiring Tier B Password. Increment user `token_generation` -> Verify existing JWT rejected within 30 seconds.
27. **Sync Batch Transport Chunking & Paging**: Transmit 1,200 events partitioned into three 500-event paged payloads (`batch_id`, pages 1/3, 2/3, 3/3). Verify staging in `master_data_staging` and atomic MVCC activation only after final page arrives.
28. **Till Variance Tender Split Cash Isolation**: Complete sale with split tender ₹200 cash, ₹300 UPI, and ₹100 credit voucher. Settle return with ₹50 cash and ₹50 credit note. Verify till cash formula strictly aggregates ₹200 cash sale and ₹50 cash refund without digital/voucher distortion.

---

## Doc 9: Security & Audit Log Spec

### 9.1 Local Auth JWT Claim Schema & Argon2id Hash Parameters
- **Argon2id Salt & Key Derivation**:
  - Memory cost: $64\text{ MB}$ (`m=65536`)
  - Time cost: 3 iterations (`t=3`)
  - Parallelism: 4 threads (`p=4`)
  - Salt: 16-byte cryptographically secure random per user
- **Store-Scoped Session JWT Claims**:
  ```json
  {
    "sub": "usr_550e8400-e29b-41d4-a716-446655440000",
    "store_id": "STORE-01",
    "role": "PHARMACIST",
    "shift_id": "shf_880e8400-e29b-41d4-a716-446655440000",
    "iat": 1774100000,
    "exp": 1774143200
  }
  ```

### 9.2 Prescription WebP AES-256 Storage & Retention Specification
- **Directory**: `C:\medpos\prescriptions\`
- **Image Compression**: Local WebP conversion at 150–200 DPI, max target file size $< 250\text{ KB}$.
- **Encryption at Rest**: AES-256-GCM using encryption key stored in `C:\medpos\config\db_key.env`.
- **Edge Retention Policy**: Automated nightly background worker scans directory; files older than 90 days with confirmed sync watermark acknowledgment on Central are permanently unlinked.

### 9.3 Windows OS Edge File Security Hardening (`icacls`)
```bat
icacls "C:\medpos\config" /inheritance:r /grant:r "NT SERVICE\MedPOS":(R) /grant:r "SYSTEM":(F)
icacls "C:\medpos\data" /inheritance:r /grant:r "NT SERVICE\MedPOS":(F) /grant:r "SYSTEM":(F)
```

### 9.4 Structured Log Schema & Audit Correlation ID Spec
- **JSON Log Envelope**:
  ```json
  {
    "timestamp": "2026-09-22T10:14:00.123Z",
    "level": "INFO|WARN|ERROR|AUDIT",
    "correlation_id": "corr_550e8400-e29b-41d4-a716-446655440000",
    "store_id": "STORE-01",
    "terminal_id": "POS-01",
    "user_id": "usr_880e8400-e29b-41d4-a716-446655440000",
    "event_type": "sale",
    "action": "CHECKOUT_COMMIT",
    "message": "Invoice STORE-01-INV-202609-0042 committed successfully",
    "execution_duration_ms": 8.4
  }
  ```
- **Correlation Propagation**: Every checkout transaction, sync batch push, and manager override generates a UUIDv4 `correlation_id` attached to all downstream DB queries, print spoolers, and audit log entries.

### 9.5 Merkle Tree Audit Hashing Algorithm Specification (v1.6.6)
- **Algorithm**: Every 4 hours, background daemon queries all events committed in the previous 4-hour window ordered by `store_seq_no ASC`.
- Each event row computes leaf hash: $H_i = \operatorname{SHA-256}(\text{event\_id} \parallel \text{store\_seq\_no} \parallel \text{created\_at} \parallel \text{payload})$.
- Pairwise concatenated hashing constructs Merkle tree: $H_{parent} = \operatorname{SHA-256}(H_{left} \parallel H_{right})$.
- Root hash commits to `audit_merkle_roots` table and exports in next sync heartbeat to Central for tamper detection.

### 9.6 Annual AES-256 Key Rotation & Re-encryption Workflow (v1.6.6)
- Keys tagged with integer `key_id` in `db_key.env`.
- Scheduled annual job generates new `key_id = N + 1`.
- New writes immediately encrypt with Key N+1.
- Low-priority background worker re-encrypts historic records and prescription scans from Key N to Key N+1, updating `encryption_key_id`.

### 9.7 Progressive Login Throttling & Token Generation Invalidation (v1.6.6)
- 5 consecutive failed login attempts on `(terminal_id, username)` triggers a 15-minute lock.
- User table contains `token_generation INTEGER DEFAULT 1`.
- On security revocation: `UPDATE users SET token_generation = token_generation + 1 WHERE user_id = :id;`.
- Local JWT verification checks cached `token_generation` (cached in memory with 30s TTL). If mismatch, HTTP 401 Unauthorized is immediately returned.

---

## Doc 10: Deployment & Rollout Plan

### 10.1 Unattended Edge Backup, Pruning & Watchdog Service Spec
- **Automated Backup**: Nightly `pg_dump -Fc` executed at 02:00 local time to secondary drive partition `D:\medpos_backups\`.
- **Rolling Pruning**: Python script deletes backup archives older than 7 calendar days.
- **NSSM Watchdog**:
  - Service: `MedPOSService`
  - Restart throttle: Delay 5000ms on exit; max 3 restarts within 600,000ms (10 min).

### 10.2 Operational Telemetry Metrics & Alerting Thresholds
- Metrics exported over internal Prometheus endpoint `127.0.0.1:8000/metrics`:
  - `medpos_sync_queue_lag_seconds`
  - `medpos_quarantined_events_total`
  - `medpos_lan_roundtrip_latency_ms`
  - `medpos_printer_jam_events_total`
  - `medpos_till_variance_rupees`
  - `medpos_clock_skew_seconds`
- Alerting Rules:
  - Critical: `medpos_sync_queue_lag_seconds > 1800` (Sync offline > 30 minutes).
  - Critical: `medpos_quarantined_events_total > 0` (Poison-pill detected).
  - High: `medpos_till_variance_rupees < -500` (Cash shortage > ₹500).

### 10.3 Canary Rollout Protocol, Rollback Procedures & Edge Checklist
- **Canary Stage Gate (Store 1 Soak)**:
  - Single pilot store runs new software build for 7 consecutive calendar days.
  - Go/No-Go Criteria: Zero database rollbacks, zero poison-pill quarantines, zero unreconciled till variance anomalies, sync queue latency $\le 60$s.
- **Alembic Pre-Flight & Rollback Protocol**:
  - Pre-migration edge automated backup: `pg_dump -Fc` before applying migration.
  - Migration scripts must be bidirectional with tested downgrade paths (`alembic downgrade -1`).
  - Pre-migration version verification against `migration_history` table.
- **Edge Hardware Deployment Checklist**:
  - Primary PC (Counter 1) configured with static IP `192.168.1.10` or mDNS `medpos-primary.local`.
  - Self-signed TLS certificate provisioned with 10-year validity and replicated to Counter 2 standby.
  - Counter 2 standby configured with `promote_to_primary.bat` and WAL replication slot.
  - NSSM Windows service wrapper installed with 5000ms crash throttle backoff.
  - Thermal printer ESC/POS status checking verified with cash drawer RJ11 pulse kick.

### 10.4 Alembic Pre-Flight Automated Backup Script (v1.6.6)
```powershell
# Pre-migration automated edge backup script (run before alembic upgrade head)
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupFile = "C:\medpos\backups\pre_migration_$timestamp.dump"
Write-Host "Creating pre-migration database snapshot to $backupFile..."
& "C:\Program Files\PostgreSQL\16\bin\pg_dump.exe" -U postgres -Fc -f $backupFile medpos
if ($LASTEXITCODE -ne 0) {
    Write-Error "Pre-migration backup failed! Aborting Alembic migration."
    exit 1
}
Write-Host "Backup completed successfully. Proceeding with Alembic migration..."
```

### 10.5 Tiered Disk Space Health Response Automation (v1.6.6)
- **85% Disk Full**: Automated cleanup triggers: deletes application log files $> 14$ days old, runs standard `VACUUM ANALYZE` on Postgres (strictly forbidding `VACUUM FULL` to prevent disk thrashing).
- **90% Disk Full**: Degraded write mode: non-critical operational telemetry and performance metrics suspended. Sync heartbeats and statutory Schedule X prescription image captures remain prioritized.
- **98% Disk Full**: Emergency read-only mode: local checkout commits halted to prevent database transaction log corruption; prominent UI banner prompts immediate disk clearing.

### 10.6 Windows LTSC WSUS Maintenance Window & Shutdown Drain (v1.6.6)
- Windows Update Group Policy configured on Windows 10/11 LTSC: Automatic Updates deferred strictly to 02:00–03:00 local time window.
- Graceful shutdown daemon: OS shutdown signal triggers 30-second drain period, allowing active checkout commits to finalize while rejecting new cart initiations.

---

## Doc 11: Glossary

### 11.1 Legal Metrology Rule 2011 & Schedule Compliance Glossary
- **Legal Metrology (Packaged Commodities) Rules, 2011**: Statutory regulations governing sale of packaged consumer and pharmaceutical commodities. Mandates that fractional sales of packages (such as loose blister tablets) must calculate price proportionally based on declared Maximum Retail Price (MRP), strictly clamped to prevent rounding overcharge accumulators.
- **Schedule H1**: Class of prescription medications (third- and fourth-generation antibiotics, habit-forming drugs) requiring 3-year mandatory transaction register under Rule 65(9) of the Drugs and Cosmetics Rules.
- **Schedule X / NDPS**: Highly controlled narcotics and psychotropics governed under Rule 65(4) and the NDPS Act, requiring duplicate prescription custody, registered pharmacist credentials, and daily running balance ledgers.

### 11.2 GST Statutory Invoicing, Credit/Debit Note & Challan Clauses
- **CGST Section 31 (Tax Invoice)**: Legal requirement for registered suppliers to issue formal tax invoices containing prescribed fields (GSTIN, HSN, tax rate, batch).
- **CGST Section 34 (Credit Note)**: Formal document issued by supplier when goods are returned, reversing output tax liability.
- **CGST Section 34(3) (Debit Note)**: Accounting document issued to vendors when returning goods, reversing Input Tax Credit (ITC).
- **Rule 46(b) CGST Rules (B2B Offline Pilot Mode)**: Standard B2B tax invoice provisions allowing offline generation with manual monthly upload to GST portal.
- **Rule 55 CGST Rules (Delivery Challan)**: Statutory document authorizing physical road transport of goods without immediate sale (internal branch transfers within same legal entity/GSTIN).

### 11.3 India Pharmaceutical & GST Statutory Clauses (v1.6.6)
- **Rule 65(11) Drugs and Cosmetics Rules, 1945**: Explicit statutory prohibition against dispensing medications listed in Schedule H and Schedule H1 more than once on the same prescription unless the prescriber has explicitly written directions indicating the number of times it may be refilled.
- **Rule 65(11A) NDPS Custody**: Statutory mandate requiring physical and cryptographic dual custody for dispensing narcotics and psychotropics, including state licensing council verification.
- **Chapter 30 HSN Codes**: Harmonized System of Nomenclature classification for pharmaceutical products (3003, 3004). Enforces mandatory 8-digit HSN codes on all B2B invoices and soft-warning on B2C retail invoices.
- **DPDP Act 2023 (Digital Personal Data Protection)**: Statutory patient consent requirements for storing personal and prescription medical data in commercial retail systems. Soft-consent capture enabled by default.
