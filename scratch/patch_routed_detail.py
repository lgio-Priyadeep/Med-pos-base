import sys, re

with open('ROUTED-DETAIL.md', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    # 1. Update pharmacist_pin_verified in Doc 1 §1.5
    if 'pharmacist_pin_verified BOOLEAN NOT NULL DEFAULT TRUE,' in line:
        line = line.replace('pharmacist_pin_verified BOOLEAN NOT NULL DEFAULT TRUE,', 'pharmacist_password_verified BOOLEAN NOT NULL DEFAULT TRUE,')
    
    # 2. Update Doc 2 §2.1 header
    if '2.1 Full Event Payload Schemas for Events' in line:
        line = '### 2.1 Full Event Payload Schemas for Events 1–19 & Tombstones\n'
    
    # 3. Expand dispense payload in 2.1
    if line.startswith('4. `dispense`:'):
        line = '4. `dispense`: `{ "prescription_id": "UUID", "patient_id": "<STORE_CODE>-PAT-UUID", "prescriber_id": "<STORE_CODE>-DOC-UUID", "is_schedule_h1": true, "is_schedule_x": false, "h1_payload": { "doctor_reg_no": "KMC-45920", "doctor_address": "Gupta Polyclinic, Bangalore", "patient_address": "123 Indiranagar, Bangalore", "drug_generic_name": "Amoxicillin + Clavulanate", "brand_name": "Augmentin 625 Duo", "batch_no": "AUG2026-01", "mfg_name": "GSK India", "dispensed_qty_base": 10, "pack_size": 10, "pharmacist_id": "UUID", "pharmacist_reg_no": "KPC-78219" }, "schedule_x_payload": { "duplicate_prescription_scanned": true, "prescription_image_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "dispensed_qty_base": 10, "running_balance_after": 40, "pharmacist_password_verified": true, "pharmacist_reg_no": "KPC-78219" } }`\n'
    
    # 4. Expand master-data-created in 2.1
    if line.startswith('13. `master-data-created`:'):
        line = '13. `master-data-created`: `{ "table": "catalog_items", "business_key": "8901234567890", "initial_payload": { "brand_name": "Augmentin 625 Duo", "generic_name": "Amoxicillin and Potassium Clavulanate", "hsn_code": "30041010", "gst_rate": 12.00, "drug_schedule": "H1", "is_ndps": false, "pack_size": 10, "packaging_unit": "Strip of 10", "base_unit": "tablet", "mrp": 204.50 }, "version": 1 }`\n'
    
    # 5. Add events 18 and 19 after event 17
    if line.startswith('17. `settings-change`:'):
        line = line + """18. `grn`: `{ "grn_number": "<STORE_CODE>-GRN-YYYYMM-XXXX", "distributor_id": "UUID", "purchase_invoice_no": "INV-2026-8812", "purchase_invoice_date": "2026-09-20", "received_at": "2026-09-22T10:00:00Z", "received_by": "UUID", "lines": [{ "drug_id": "UUID", "batch_no": "BCH-9921", "expiry_date": "2028-09-30", "mrp": 120.00, "purchase_price_per_unit": 85.50, "ordered_pack_qty": 10, "received_pack_qty": 10, "pack_size": 10, "base_qty": 100, "hsn_code": "30041010", "cgst_rate": 6.0, "sgst_rate": 6.0 }] }`
19. `credit-note-redemption`: `{ "redemption_id": "UUID", "credit_note_number": "<STORE_CODE>-CN-YYYYMM-XXXX", "redeemed_invoice_number": "<STORE_CODE>-INV-YYYYMM-XXXX", "customer_id": "UUID|null", "redeemed_amount": 250.00, "remaining_credit_balance": 150.00, "authorized_by": "UUID" }`
"""
    
    # 6. Update Test 1 and Test 5 in Doc 8
    if line.startswith('1. **Absolute Expiry Hard-Block**:'):
        line = '1. **Absolute Expiry Hard-Block**: Bill batch with $\\text{expiry} < \\text{current\\_date (IST)}$ in `Optional` compliance mode. Assert: Batches on final day of expiry month remain valid; batches past expiry date are unconditionally hard-blocked.\n'
    if line.startswith('5. **Schedule X Prescription & Ledger**:'):
        line = '5. **Schedule X Prescription & Ledger**: Dispense Schedule X drug without prescription image or pharmacist Tier B Argon2id password verification. Assert: Blocked. Ingest valid dispense; assert daily balance equation reconciles.\n'
    
    # 7. Update Mermaid nodes in Doc 7 §7.1
    if 'M11[M11: User Roles & Auth]' in line:
        line = line.replace('M11', 'M-11')
    if 'M08[M08: Multi-Store Master Data]' in line:
        line = '    M-11[M-11: User Roles & Auth] --> M-08[M-08: Multi-Store Master Data]\n    M-08 --> M-12[M-12: Settings & Config]\n'
    if 'M08 --> M01' in line:
        line = line.replace('M08', 'M-08').replace('M01', 'M-01')
    if 'M01 --> M09' in line:
        line = line.replace('M01', 'M-01').replace('M09', 'M-09')
    if 'M01 --> M06' in line:
        line = line.replace('M01', 'M-01').replace('M06', 'M-06')
    if 'M01 --> M05' in line:
        line = line.replace('M01', 'M-01').replace('M05', 'M-05')
    if 'M06 --> M02' in line:
        line = line.replace('M06', 'M-06').replace('M02', 'M-02')
    if 'M06 --> M07' in line:
        line = line.replace('M06', 'M-06').replace('M07', 'M-07')
    if 'M01 --> M03' in line:
        line = line.replace('M01', 'M-01').replace('M03', 'M-03')
    if 'M01 --> M04' in line:
        line = line.replace('M01', 'M-01').replace('M04', 'M-04')
    if 'M06 --> M13' in line:
        line = line.replace('M06', 'M-06').replace('M13', 'M-13')
    if 'M01 --> M10' in line:
        line = line.replace('M01', 'M-01').replace('M10', 'M-10')

    new_lines.append(line)

text = "".join(new_lines)

# Insert Doc 5 sections §5.5, §5.6, §5.7, §5.8
doc5_additions = """
### 5.5 Low-Stock Alert State Lifecycle & Cooldown Flow
- **State Machine**:
  1. `NORMAL`: Current base stock > configured low-stock threshold.
  2. `ALERT_ACTIVE`: Triggered when available base stock drops $\\\\le$ threshold. POS emits discrete `low-stock-alert` event. Subsequent checkout sales below threshold suppress re-alerting (cooldown period) to prevent log flooding.
  3. `REPLENISHED`: Inbound `grn` or `stock-move: transfer-receive` raises base stock above threshold $\\\\rightarrow$ transitions back to `NORMAL`, clearing alert cooldown.
  4. `CLOSED_DISCONTINUED`: Deliberate Manager `stock-move: write-off` zeroes stock without replenishment intent $\\\\rightarrow$ transitions to `CLOSED_DISCONTINUED`.

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
     - `APPROVED`: Admin approves in Web portal $\\\\rightarrow$ Central applies mutation, increments record version, emits `master-data-change-approved`. Store ingests update via next sync response.
     - `REJECTED`: Admin rejects $\\\\rightarrow$ Central emits `master-data-change-rejected` with reason code (`manual`, `stale`, `duplicate`, `stock-remaining`). Store Manager alerted on dashboard.

### 5.8 Shift Lifecycle & Till Reconciliation State Machine
- **State Flow**:
  1. `CLOSED`: Terminal register locked. Cashier enters credentials and opening cash float $\\\\rightarrow$ POS commits `shift-open` event $\\\\rightarrow$ Transitions to `OPEN`.
  2. `OPEN`: Active billing permitted on this terminal. Transactions record tender split (`cash`, `card`, `upi`, `store-credit`).
  3. `CLOSING_PENDING_DECLARATION`: Cashier initiates shift close $\\\\rightarrow$ prompts blind physical cash count (`declared_physical_cash`).
  4. `RECONCILED`: System calculates Till Variance:
     $$\\\\text{Variance} = \\\\text{Declared Cash} - (\\\\text{Opening Float} + \\\\text{Cash Sales} - \\\\text{Cash Refunds})$$
     - `Cash Sales` strictly isolates physical cash tenders (`sum(tender_split.cash)`), excluding store credit voucher redemptions and digital payments.
     - POS commits `shift-close` event with tender breakdown. Day-End Z-Report aggregates all terminal shifts for store closing.
  5. `CLOSED_FORCE`: If cashier leaves terminal open, Store Manager executes emergency supervisory force-close providing physical cash count $\\\\rightarrow$ commits `shift-force-close` event.
"""

doc6_idx = text.find('## Doc 6: Conflict & Edge Case Matrix')
text = text[:doc6_idx] + doc5_additions.strip() + '\n\n---\n\n' + text[doc6_idx:]

# Insert Doc 6 §6.3
doc6_additions = """
### 6.3 V2 Enterprise Distributed Edge Cases & Scenarios
- **Scenario A (Supplier Settlement Partition)**: Store issues sequential vendor return Debit Note (`<STORE>-DN-...`) offline during WAN partition. Distributor settlement is managed locally via physical credit memo; central AP ledger reconciles asynchronously upon sync reconnection via manual GSTR-1 return matching bridge.
- **Scenario B (Branch Transit Discrepancy Arbitration)**: Inter-store transfer of 100 units arrives at Store B with 10 broken in transit. Store B `transfer-receive` logs 90 received, 10 `transit_breakage_qty` with photo audit. Automatic Delivery Challan (`<STORE>-DC-...`) variance breakdown allocates loss to transit write-off without wedging destination inventory.
- **Scenario C (Offline Store Credit Cross-Branch Attempt)**: Customer attempts to redeem `<STORE_A>-CN-...` voucher at Store B. Terminal UI enforces issuing-store restriction: *"Store Credit redeemable solely at issuing branch (Store A)."* Distributed 2PL cross-store voucher coordinator is deferred to V2.
"""
doc7_idx = text.find('## Doc 7: Dependency Map')
text = text[:doc7_idx] + doc6_additions.strip() + '\n\n---\n\n' + text[doc7_idx:]

# Insert Doc 7 §7.2
doc7_additions = """
### 7.2 V2 Enterprise Module Dependencies & Architectural Roadmap
- **Phase 2.0 Module Evolution**:
  1. `M-14: Distributor EDI & AP Settlement Gateway` (Depends on M-03, M-08, M-10)
  2. `M-15: Central In-Transit Virtual Logistics Pool` (Depends on M-04, M-10)
  3. `M-16: Government NIC/IRP E-Invoicing Gateway` (Depends on M-06, M-08)
  4. `M-17: Cross-Store Voucher Distributed 2PL Coordinator` (Depends on M-02, M-06, M-10)
  5. `M-18: Edge Prescription Computer Vision OCR` (Depends on M-05, M-07)
"""
doc8_idx = text.find('## Doc 8: Test Plan Doc')
text = text[:doc8_idx] + doc7_additions.strip() + '\n\n---\n\n' + text[doc8_idx:]

# Insert Doc 9 §9.4
doc9_additions = """
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
"""
doc10_idx = text.find('## Doc 10: Deployment & Rollout Plan')
text = text[:doc10_idx] + doc9_additions.strip() + '\n\n---\n\n' + text[doc10_idx:]

# Insert Doc 10 §10.3
doc10_additions = """
### 10.3 Canary Rollout Protocol, Rollback Procedures & Edge Checklist
- **Canary Stage Gate (Store 1 Soak)**:
  - Single pilot store runs new software build for 7 consecutive calendar days.
  - Go/No-Go Criteria: Zero database rollbacks, zero poison-pill quarantines, zero unreconciled till variance anomalies, sync queue latency $\\\\le 60$s.
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
"""
doc11_idx = text.find('## Doc 11: Glossary')
text = text[:doc11_idx] + doc10_additions.strip() + '\n\n---\n\n' + text[doc11_idx:]

# Cleanup any encoding glitches
text = text.replace('117', '1–19').replace('120', '1–20')

with open('ROUTED-DETAIL.md', 'w', encoding='utf-8') as f:
    f.write(text)

print('Updated ROUTED-DETAIL.md successfully')
