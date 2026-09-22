---
trigger: always_on
---

## ARCHITECTURE DOC DISCIPLINE

You maintain the Architecture Doc for the pharmacy POS.
It is a decision and boundary document, not a specification dump.
Detail lives in 11 downstream docs, generated only after this doc is locked.

### 1. What belongs in the Architecture Doc
- Purpose, scope, non-goals.
- Modules, responsibilities, and boundaries.
- Store vs central split: what lives where, and why.
- Roles and presets: definitions and principles only.
- Workflow summaries: main path plus key failure behavior.
- Decisions with one-line rationale.
- Compliance mode: intent and principle only.
- Constraints, NFRs, open questions.

### 2. Routing table: where detail goes
Before adding any content, find its home. If it belongs elsewhere, do not write it here.

| Content type | Home doc |
|---|---|
| Tables, fields, types, constraints, FKs | 1. Data Schema |
| Event payloads, versioning rules | 2. Event Schema |
| Endpoints, request/response, error codes, per-endpoint role | 3. API Contract |
| Role × action yes/no cells | 4. RBAC Matrix |
| States, transitions, blocking rules per flow | 5. State Machines |
| Scenario → expected behavior | 6. Edge Case Matrix |
| Build order, module dependencies | 7. Dependency Map |
| Test cases | 8. Test Plan |
| Immutability, hidden fields, input validation | 9. Security & Audit Spec |
| Feature flags, canary, rollback, go/no-go | 10. Deployment Plan |
| Domain term definitions | 11. Glossary |

### 3. Hard rules
- No code, SQL, JSON, or config in this doc.
- No field lists, column lists, or endpoint lists.
- No full permission grids. State the principle; the matrix holds the cells.
- No scenario tables. Name the risk in one line; the edge case doc holds the behavior.
- No term definitions beyond one short clause. Glossary holds the rest.
- State each fact once. Link by ID; never copy.
- No history or changelog prose. One line per version, max 15 words.

### 4. Size limits
- Soft cap: 2,500 words. Hard cap: 3,500 words.
- Any section over one page: shrink it to a 3-line summary. Move detail to its home doc.
- Workflow summary: max 8 lines. Mermaid diagram: max 15 nodes.
- Open questions: max 10, each with owner and target.
- At the hard cap, refuse to add. Compress or route first.

### 5. Deferral markers
Downstream docs do not exist until lock. Do not inline their content to compensate.
- Write a marker: `[DEFERRED → Doc N: <topic>]`.
- Keep a "Deferred Items" register at the end: one line per marker, grouped by doc.
- At lock, the register becomes each doc's input list.
- Every rule must be testable. Flag anything ambiguous so Doc 8 can derive a test.

### 6. Stable IDs
- Modules `M-01`, decisions `D-01`, requirements `FR-01` / `NFR-01`, flows `F-01`.
- Downstream docs reference IDs only.
- Never renumber. Retire an ID; do not reuse it.

### 7. Before every edit, check
1. Is this a decision, boundary, workflow summary, or constraint? If not, route it.
2. Does it duplicate an existing fact? If yes, link instead.
3. Does it push the doc past a limit? If yes, compress first.
4. Does it conflict with an existing decision? If yes, flag it. Do not silently overwrite.
5. Does it add a new dependency between modules? If yes, record it for Doc 7.

### 8. After lock
- Changes need an explicit approval and a version bump.
- After each change, list which downstream docs it affects.
- Never patch a downstream doc without checking the Architecture Doc first.
- If the two disagree, the Architecture Doc wins. Report the conflict; do not resolve it silently.

### 9. When the user asks for detail that belongs elsewhere
- Do not add it to the Architecture Doc.
- Say which doc it belongs in.
- Add or update the deferral marker.
- Offer to draft that content as a separate note.