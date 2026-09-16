# Pharmacy POS — Known Areas to Improve & Architecture Roadmap

This document captures architectural gaps, operational edge cases, regulatory requirements, and technical enhancements identified during the review of [architecture_v1_5.md](file:///c:/Users/surya/OneDrive/Desktop/med_pos/architecture_v1_5.md).

---

## 1. Statutory & Regulatory Compliance (High Priority)

### 1.1 Expiry Hard-Block in All Modes (§10)
- **Current Spec:** Section 10 allows an `Optional` compliance mode switch where *"expiry becomes a warning"*.
- **Risk:** Under Section 18 of the Drugs and Cosmetics Act, 1940, stocking, selling, or dispensing expired drugs in India is a strict liability offense carrying criminal penalties and pharmacy license cancellation.
- **Improvement:**
  - Expiry must **always hard-block** billing and dispensing, regardless of whether compliance mode is `Mandatory` or `Optional`.
  - `Optional` mode should only relax non-statutory or internal metadata fields (e.g., patient phone numbers, soft prompts for non-H1 drugs).

### 1.2 Schedule H1 Register Record Completeness (§10)
- **Current Spec:** Captures patient name, doctor name/registration number, and quantity dispensed.
- **Requirement:** Rules require maintaining the Schedule H1 register for a minimum of 3 years with:
  - Patient name and full address.
  - Prescribing doctor's name, address, and state medical council registration number.
  - Drug name, batch number, manufacturer, and date of dispensing.
- **Improvement:** Ensure the dispense audit payload schema accommodates these specific fields and provides a one-click export for drug inspector audits.

### 1.3 Offline Walk-in Patient & Prescriber Creation
- **Current Spec:** Master data (catalog/pricing/tax) requires live central connectivity for direct edits (§4).
- **Risk:** If doctors or patients are treated as central master data, a store cannot bill an unscheduled or H1 prescription for a new patient or doctor while offline.
- **Improvement:** Explicitly define patient and doctor records as **store-local operational entities** that are 100% offline-creatable and synced upward asynchronously.

---

## 2. Retail Pharmacy & Inventory Lifecycle Gaps

### 2.1 Customer Sales Returns, Exchanges & GST Credit Notes
- **Current Spec:** Covers sales, dispenses, transfers, and write-offs (§5), but omits customer returns.
- **Requirement:** Patients frequently return unconsumed, sealed blister packs or exchange medications.
- **Improvement:**
  - Add event type `sale-return` with references to the original invoice and batch ID.
  - Define return stock destination: back into active batch inventory (if sealed/valid) or into a quarantined write-off bucket (if damaged/returned after cold-chain breach).
  - Implement sequential per-store **Credit Note numbering** conforming to Indian GST rules.

### 2.2 Batch Selection Mechanics & Line-Item Splitting
- **Current Spec:** Tracks batches and expiry, but does not define selection or deduction rules.
- **Improvement:**
  - **FEFO (First Expired, First Out):** POS must suggest the earliest expiring valid batch by default.
  - **Manual Batch Override:** Allow cashiers/pharmacists to scan or select a different batch if the physical package pulled differs from the system suggestion.
  - **Split-Batch Line Items:** Allow a single prescription item to split across multiple batches when one batch has insufficient stock (e.g., customer needs 15 tablets; Batch A has 10, Batch B has 20).

### 2.3 Physical vs. System Discrepancy & Negative Stock Policy
- **Current Spec:** Store stock is computed purely from local events.
- **Gap:** In high-volume retail counters, physical stock counts often differ from digital counts due to misplaced boxes or unrecorded breakage. If system stock is 0 but the medicine is physically in hand, a hard-block stops patient treatment.
- **Improvement:** Define an explicit stock policy (e.g., allow emergency negative stock with an auto-generated discrepancy flag, or enforce immediate write-in adjustment with manager authorization).

---

## 3. Distributed Systems & Sync Engine Mechanics

### 3.1 Store-Initiated Outbound Sync Architecture (§4)
- **Current Spec:** *"Master data (catalog, pricing, tax) is central-owned, pushed down to stores."*
- **Networking Reality:** Store broadband connections typically sit behind ISP CGNAT or dynamic IP routers without public IPs or open inbound ports. Central cannot initiate inbound TCP connections to stores.
- **Improvement:**
  - Formalize that all sync operations are **store-initiated outbound** (HTTP polling, long-polling, or store-connected WebSockets/gRPC).
  - Central sends master data updates and request approval decisions as response payloads to the store's heartbeat/sync requests.

### 3.2 Idempotent Event Ingestion & Replay Protection (§5)
- **Current Spec:** Mentions pushing queued events and testing duplicate sync attempts.
- **Improvement:**
  - Every event generated at the store must carry a client-generated UUID (`event_id`) and a monotonic store sequence number (`store_seq_no`).
  - Central ingestion must enforce strict idempotency via `ON CONFLICT (event_id) DO NOTHING`.
  - Sync acknowledgment must return a confirmed sequence watermark so stores can prune or mark sent events.

### 3.3 Partition-Era Sales Ingestion for Soft-Deleted Products (§6)
- **Edge Case:** Central soft-deletes a product based on zero aggregate synced stock while Store A is offline. Store A, while offline, sells 5 units that had not yet synced.
- **Improvement:** Central must **never reject sales events for soft-deleted products** arriving from an offline partition. Historical transactions are valid and must be ingested for accounting, tax, and ledger accuracy. Deletion only prevents *future* sales once the deletion event reaches the store.

---

## 4. Authentication, Security & Store Autonomy

### 4.1 Local Authentication During Network Partitions (§2)
- **Current Spec:** *"Auth: per-user login, JWT session, tied to user not device."*
- **Gap:** If store hardware reboots or crashes while the internet is down, users must still be able to log in to bill and dispense.
- **Improvement:**
  - User credentials (hashed passwords, role permissions) must be replicated to the local store Postgres instance.
  - Store FastAPI instances must be equipped with local token generation/verification (e.g., shared asymmetric public key or store-local signing key) to issue valid sessions offline.

### 4.2 Central Admin Session Isolation
- **Improvement:** Ensure Admin users can manage multi-store governance and review master-data requests from a centralized Web portal without requiring direct remote database access to store nodes.

---

## 5. Cashier & Financial Operations

### 5.1 Shift Management & Day-End Till Reconciliation (Z-Report)
- **Current Spec:** Focuses on GST billing and discounts (§8, §9).
- **Gap:** In retail operations, multiple cashiers use the counter across morning and evening shifts. Discrepancies between cash drawer contents and digital sales must be tracked.
- **Improvement:**
  - Add `shift-open` (recording opening cash float) and `shift-close` events.
  - Provide a standard **Day-End Z-Report** comparing total cash, card, and UPI sales against declared physical cash to detect shrinkage.

---

## 6. Store Infrastructure & Database Maintenance

### 6.1 Unattended Store Postgres Maintenance
- **Current Spec:** Local Postgres instance per store (§2).
- **Operational Reality:** Retail terminals are managed by non-technical pharmacy staff.
- **Improvement:**
  - Automated local database backup scripts (daily dumps stored on a secondary partition/drive).
  - Background WAL cleanup and scheduled `VACUUM` jobs to prevent disk exhaustion on compact POS terminals.
  - Self-healing watchdog service to restart the local FastAPI and Postgres services if Windows crashes or updates.

---

## Summary Matrix: Priority vs. Impact

| Area | Impact | Complexity | Target Milestone |
| :--- | :---: | :---: | :---: |
| **Absolute Expiry Hard-Block** | Critical (Legal) | Low | Pre-v1.6 Lock |
| **Store-Initiated Outbound Sync Spec** | Critical (Architecture) | Low | Pre-v1.6 Lock |
| **Sales Returns & GST Credit Notes** | High (Business) | Medium | v1.6 Core |
| **Batch Picking (FEFO) & Line Splitting** | High (Operations) | Medium | v1.6 Core |
| **Offline Walk-in Patient/Doctor Creation** | High (Operations) | Low | v1.6 Core |
| **Event Idempotency Keys (UUIDs)** | High (Reliability) | Low | v1.6 Core |
| **Shift / Till Cash Reconciliation (Z-Report)**| Medium (Business) | Medium | v1.6 / v2.0 |
| **Store Postgres Auto-Backup / Watchdog** | Medium (DevOps) | Medium | Deployment Phase |
