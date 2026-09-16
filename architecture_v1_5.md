# Pharmacy POS — Architecture Spec (v1.5, Locked)



*Changelog from v1.4: added `write-off` as a stock-move reason (store-local,
offline-capable — reuses the existing event, no new type). Deletion
(`deleted_at`) is now blocked while aggregate stock across all stores is
above zero — applies to both direct edit and request-approval paths. Added
`stock-remaining` rejection reason. Active low-stock alerts now clear on
successful deletion. Added stock-move/write-off to the immutable audit list.
Documented the eventual-consistency risk in the deletion check explicitly —
this is an accepted limitation of offline-first, not something patched away.*

## 1. Scope
- Small chain, 2-5 stores
- Real business use, not portfolio-only
- Hybrid deployment: offline-first, syncs when online — with one narrow
  exception, see §4
- Small single-store operators supported via Simple role preset (see §11)

## 2. Tech Stack
- Backend: Python + FastAPI (store-side and central)
- Central DB: Postgres
- Local DB: Postgres, one instance per store
- Auth: per-user login, JWT session, tied to user not device

## 3. Core Modules
- Inventory: drugs, batches, expiry, per-store stock, low-stock alerts, write-offs
- Prescription/Dispensing: patient, doctor, drug schedule tracking
- Billing: checkout, GST invoice, discounts
- Multi-store: store master, stock transfer, central reporting
- Master-data governance: direct edit/create/delete (Admin/High-access) or
  request-approval (Manager), all concurrency-protected — see §4
- Sync engine: local-first, pushes events to central
- User roles: full 4-role model, or 2-role simple preset
- Settings/Config: compliance mode, role preset, other toggles
- Hardware (phase 1): barcode scanner, receipt printer
- Reporting: sales, expiry, GST, low-stock, per-store and combined

## 4. System Architecture
- Each store runs its own FastAPI instance + local Postgres
- Store operates fully offline for sales, dispensing, billing, stock-moves
  (including write-offs) — no central dependency
- All state changes are append-only events, committed locally first
- Sync agent pushes queued events to central on any of three triggers:
  - fixed time interval
  - automatic on reconnect
  - manual "sync now" button
- Central Postgres is aggregation/reporting only — never authoritative for stock
- Master data (catalog, pricing, tax) is central-owned, pushed down to
  stores. Discount presets are also central-owned but governed separately — see §9
- Stores cannot change master data or discount presets directly, except the roles in §9/§11/§12

**Exception — Concurrency Control for Direct Changes**
- Any direct change to shared central data — edit, creation, or soft-deletion,
  to master-data catalog/pricing/tax or to discount presets — requires live
  central connectivity. This is the one write path that is not offline-capable
- Applies uniformly to: Admin (§11 Full), High-access (§9/§11 Simple), and
  Manager's discount edits (§9 Full)
- Every governed record carries an integer `version` field, incremented on
  each central write
- **Edits and soft-deletes:** submit expected version; central rejects on
  mismatch — "changed by someone else, refresh and retry" (reason: `stale`)
- **Creation:** no prior version to compare, so conflicts are caught by a
  uniqueness constraint on the record's business key (e.g. SKU) instead —
  a concurrent duplicate create fails distinctly (reason: `duplicate`)
- **Deletion additionally requires zero stock chain-wide** — see §6
- Rationale: these are low-frequency governance writes, not core
  transactional flow — an online requirement here doesn't compromise the
  offline-first pitch for sales, dispensing, billing, or stock-moves

## 5. Data Flow / Event Model
- Event types: sale, dispense, stock-move, discount-edit, master-data-edit,
  master-data-created, low-stock-alert, settings-change,
  master-data-change-requested, master-data-change-approved, master-data-change-rejected
- `stock-move` carries `reason`: `transfer-dispatch` | `transfer-receive` | `write-off`
- `write-off` payload: quantity, batch/lot reference, reason category
  (expired/damaged/discontinued/other), performed-by
- `master-data-edit`: direct edits and soft-deletes by Admin/High-access — who, field, old/new value, version
- `master-data-created`: direct creation by Admin/High-access — who, new record payload, version=1
- `master-data-change-rejected` carries `reason`: `manual` | `stale` | `duplicate` | `stock-remaining`
- `master-data-change-requested`/`-approved` carry `action`: `edit` | `create`
- Flow: local action → local commit → queued → synced to central on trigger
- Central recomputes reports from event stream, never writes stock back
- One-way event flow keeps conflict surface near zero for everything except
  the direct-change exception in §4

## 6. Stock & Stock Transfer
- Each store's stock is local truth, computed from its own events only
- No shared real-time stock pool across stores
- Inter-store transfer = two explicit events:
  - dispatch event at source store
  - receive event at destination store
- Avoids concurrent-write conflicts entirely
- No conflict resolution needed for stock — by design, nothing merges it

**Write-Off**
- A `stock-move` event with `reason: write-off` — not a new event type
- Store-local, offline-capable, same as any other stock event — not subject
  to §4's connectivity exception (that exception governs shared central
  records, not per-store stock)
- Who can write off: Manager/Admin (Full preset), High-access (Simple preset)

**Deletion Requires Zero Stock**
- A product cannot be soft-deleted (`deleted_at` set) while aggregate stock
  across *all* stores is above zero — applies to both direct edit (Admin/
  High-access) and request-approval (Manager→Admin) paths
- The product record is chain-wide, so the check sums the latest-synced
  stock figure from every store that carries it — this is the same
  read-only aggregation §6 already does for central reporting, reused as a
  precondition check, not a new shared-stock mechanism
- A blocked attempt reports which store(s) still show stock, and how much
- Rejection reason: `stock-remaining`
- **Known limitation, accepted:** this check reflects last-synced data, not
  live truth. If a store has stock changes that haven't synced yet, the
  check can be wrong in either direction — most plausibly, a store receives
  new stock that hasn't synced, central still sees zero, and deletion goes
  through while physical stock remains. This is an inherent consequence of
  offline-first, not something closeable without breaking that design.
  Written down here so it's a known tradeoff, not a silent gap.
- Reactivating a deleted product needs no new mechanism — it's just another
  edit of `deleted_at` back to null, same as any field edit

## 7. Low Stock Alerts
- Reorder threshold set per item, per store (admin-editable)
- Alert fires when local stock drops to or below threshold
- Alert logged as its own event (low-stock-alert), not just a UI popup
- Cooldown after first trigger — no repeat alert until restocked above threshold
- Surfaced two places: store dashboard (immediate) and central reporting (aggregated across stores)
- On successful product deletion, all active alerts for that product close
  chain-wide — system-generated closure, distinct from the restock-based cooldown clear

## 8. Invoicing (GST)
- Per-store invoice number series, prefixed by store code
- Sequential and gapless within a store
- Avoids global-sequence conflicts under offline mode

## 9. Discounts
- Discount presets live on item/group records, centrally owned
- Cashier can apply the preset only, no edit rights
- Manager (Full preset) or High-access (Simple preset) can change a preset
  value directly — **not** governed by §12's request flow
- This is a direct-edit path: requires live connectivity and version-locking,
  see §4 exception
- Every discount-preset change is logged as a discount-edit event (who, what, when, version)
- Insurance/TPA billing excluded from v1; schema reserves a field for future linkage

## 10. Regulatory Compliance (India, Drugs & Cosmetics Act)
- Schedule H1 drugs require a mandatory register at dispense time:
  - patient name
  - doctor name/registration number
  - quantity dispensed
- Compliance mode is a settings switch: Mandatory / Optional (default: Mandatory)
  - Mandatory: register entry non-skippable, expiry auto-blocks sale
  - Optional: register becomes a soft prompt, expiry becomes a warning
  - Admin-only switch, logged as a settings-change event
- Audit log for dispensing is append-only, no update or delete allowed, regardless of mode
- Soft-deleted products are blocked from sale/dispense — same block pattern
  as expired batches. A product can only reach deleted state once stock is
  zero chain-wide, see §6

## 11. Roles & Access
- Two selectable presets, set per store at setup:
  - **Full (4-role)**: Pharmacist, Cashier, Manager, Admin — separate permissions each
  - **Simple (2-role)**: High access, Low access — for small/single-operator stores
    - High access: dispense, direct discount-preset edit, direct master-data
      edit/create/delete, stock write-offs, all reports (merges
      pharmacist+manager+admin)
    - Low access: billing only, apply discounts, no dispense, no edits, no
      master-data access, no write-offs (= cashier)
- Both High-access edit paths (master-data and discount) are subject to the
  §4 concurrency exception — same as Admin. Preset is chosen per store, so a
  chain can run several Simple-preset stores; the version-lock/uniqueness
  check protects that case exactly as it protects Admin
- **Small single-store recommendation:** use Simple preset — no request/approval
  loop needed, direct changes are protected regardless
- Preset choice is a settings item, admin-only, logged as settings-change event

## 12. Master-Data Change Request Flow (Full preset only, catalog/pricing/tax — not discounts, see §9)
- Applies only where Full (4-role) preset is active — Simple preset never uses this, see §11
- **Direct edit/create/delete, no request needed:** Admin (subject to §4 exception)
- **Must request, cannot change directly:** Manager
- **No access at all, not even request:** Cashier, Pharmacist
- `action` field: `edit` | `create` — deletion is not a separate action, see below
- **Edit requests:** scoped to one field, one record — no batched or
  full-record diffs. Includes soft-deletes (`field_name: deleted_at`,
  `proposed_value: <timestamp>`) — deletion reuses the edit mechanism, but
  is additionally gated by the zero-stock check in §6
- **Create requests:** no existing record to diff against, so
  `expected_version`/`current_value` don't apply and `proposed_value` holds
  the full new-record payload instead of a single field — a deliberate,
  scoped exception to the one-field-one-record rule above, limited to this action only
- Request states: `pending` → `approved` / `rejected` (`manual`, `stale`, `duplicate`, or `stock-remaining`)
- While pending: store keeps the existing value (or non-existence, for
  creates); no partial preview, no auto-apply
- **Staleness check (edit only):** request stores `expected_version` +
  human-readable `current_value`. If the live version no longer matches at
  review time, auto-reject as `stale`. Resolves the two-stores-same-field
  case: first approval wins, second is auto-rejected as stale
- **Duplicate check (create only):** a concurrent create of the same
  business key (e.g. SKU) fails a uniqueness constraint at approval —
  auto-reject as `duplicate`, distinct from `stale`
- **Stock check (deletion only):** a deletion request (edit of `deleted_at`)
  is rejected as `stock-remaining` if aggregate stock across stores is above
  zero at review time — see §6
- On approval: change flows through the normal master-data central-to-store push (§4)
- On rejection (any reason): request closed, no change applied, decision note stored
- **Preset-switch interaction:** if a store switches Full→Simple while a
  request is pending, the request is auto-cancelled (`reviewed_by: null`,
  system-generated decision note) — Simple preset has no Manager role.
  Simple→Full needs no rule, since Simple preset never creates requests
- Table: `master_data_change_requests`
- Columns: action, target table, target record (nullable for create), field
  name (nullable for create), current_value (nullable for create),
  expected_version (nullable for create), proposed_value, status,
  requested_by, requested_at, store_id, reviewed_by, reviewed_at, decision_note
- Locality, per field: target/proposed_value/expected_version/requested_by/
  requested_at/action are store-authoritative until synced; status/reviewed_by/
  reviewed_at/decision_note are central-authoritative, set only post-sync
- Events: `master-data-change-requested` (store-origin), `master-data-change-approved`
  / `master-data-change-rejected` with `reason` (central-origin) — append-only,
  same audit rules as all other events

## 13. Testing Requirements
- Unit tests for every business rule (discount logic, invoice numbering, H1
  register, low-stock threshold, master-data request/approval, version-mismatch
  rejection, duplicate-key rejection on create, zero-stock rejection on delete)
- Integration tests for store↔central sync flow
- Regression tests before any deployment
- Explicit edge cases: offline for N days, duplicate sync attempt, expired
  batch sale attempt, compliance mode switched mid-session, request pending
  when preset switched Full→Simple (expect: auto-cancel), two stores
  requesting the same field concurrently (expect: second auto-rejected as
  stale), two stores creating the same SKU concurrently (expect: second
  auto-rejected as duplicate), direct edit/create/delete attempted offline
  (expect: blocked), deletion attempted with stock > 0 (expect: blocked,
  reason stock-remaining), deletion after write-off brings all stores to
  zero (expect: succeeds), deletion attempted while a store's write-off
  hasn't synced yet (expect: still blocked — eventual consistency), active
  low-stock alert cleared on successful deletion, soft-deleted product sale
  attempt (expect: blocked)

## 14. Observability
- Structured logs for every event, including the master-data direct-change,
  request-flow, and stock-move/write-off events
- Metrics: sync lag, sync failure rate, event queue depth per store, active
  low-stock alerts, pending master-data requests, version-mismatch rejection
  rate, duplicate-key rejection rate, deletion-blocked-stock-remaining count
- Alerting on: sync failure beyond threshold, expiry-block triggered, failed
  H1 entry, compliance mode changed, master-data request pending beyond SLA
  (default 48h — adjustable business parameter, not an engineering constraint)

## 15. Security
- Input validation on all API endpoints, store and central
- Role-based access enforced server-side, not just UI-hidden
- Dispensing, discount-edit, master-data-edit, master-data-created,
  master-data-request, and stock-move (including write-off) logs are all
  immutable (append-only)
- Settings changes (compliance mode, role preset) restricted to admin, logged immutably
- Version field on governed records is central-write-only — no client can set it directly
- Dependencies kept current, no known-vulnerable packages

## 16. Deployment Safety
- Feature flags for any new module rollout
- Staged rollout: one store first, then remaining stores
- Rollback path required before any store goes live on a new version
- No direct full-chain deployment without a canary store

## 17. Settings & Configuration Module
- Central-managed, admin-only, per-store override allowed
- Toggles in v1:
  - Regulatory compliance mode: Mandatory / Optional (default: Mandatory)
  - Role preset: Full (4-role) / Simple (2-role) (default: Full)
- Switching Full→Simple auto-cancels any pending §12 request for that store (see §12)
- Every settings change is its own immutable event, tied to admin user + timestamp
- Settings changes sync like any other event, subject to same offline/sync rules

## 18. Open Items (Phase 2 / Not Blocking Lock)
- Central hosting: self-hosted VM vs managed cloud — undecided, doesn't affect this design
- Insurance/TPA claims module — deferred
- Cash drawer and weighing scale hardware — deferred, barcode + printer only for v1
- 48h SLA default for pending requests — business-tunable, not locked

---
*Status: Locked. Any change to sections 1-17 requires re-review before implementation begins.*
