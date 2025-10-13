# Decision Log

This file records architectural and implementation decisions using a list format.
2025-10-13 11:10:49 - Log of updates made.

*

## Decision

* (none yet)

## Rationale

* (n/a)

## Implementation Details

* (n/a)
[2025-10-13 11:15:40 PT] - Milestone M1 Scope & Prioritization Rationale
Decision:
Adopt Milestone M1 feature set: (E1) Job Orchestration & Monitoring, (E2) Library-wide Operation Triggers, (E3) Taxonomy (Genres/Tags) CRUD, (E4) Settings/Admin Console, (E5) Saved Search lifecycle enhancements (rename/delete/favorite).

Rationale:
- Highest composite priority scores (operations + taxonomy + configurability) deliver core operational maturity and data hygiene.
- Orchestration (E1) is foundational dependency for future backup, verification dashboard, and scheduling.
- Library-wide triggers (E2) close functional gaps currently blocked by TODO placeholders.
- Taxonomy management (E3) unlocks quality metadata evolution and future recommendation accuracy.
- Settings console (E4) reduces friction and supports ongoing configuration without rebuild/redeploy.
- Saved Search lifecycle (E5) is a low-complexity UX win improving discoverability workflows.

Implementation Details:
- Introduce BackgroundJobs persistence (single table + optional events) with crash recovery marking orphan InProgress -> Failed.
- Standardize SignalR progress hub for all long-running tasks; unify progress payload schema.
- Enforce single-active job per type policy for global operations (configurable later).
- Genre/Tag merge implemented transactionally with uniqueness constraints; potential background job escalation deferred.
- Settings mutations audited (structured log with category, key set, user).
- SavedSearch adds columns (IsFavorite). Lifecycle operations exposed via existing search UI.

Deferred/Explicitly Out of Scope:
- External Search -> direct download enqueue (next milestone candidate).
- Backup & restore UI (stubbed job type interface only).
- Verification dashboard aggregation view.
- Advanced scheduling (cron-like) layer.

Risks & Mitigations:
- State Explosion: Retention policy (proposed: max 200 job rows, FIFO purge) to be finalized pre-implementation.
- Cancellation Consistency: Define soft-cancel contract; each executor must honor cooperative token.
- Secret Exposure: API key update endpoint write-only; masked retrieval.

Open Items to Confirm:
(A) Include backup job stub now? (default: yes stub, no UI)
(B) Adopt retention purge threshold 200 (configurable later)?
(C) Escalate large taxonomy merge to background job threshold (defer to post-M1)?

[2025-10-13 11:18:00 PT] - M1 Scope Approval & Open Items Resolution
Decision:
User approved M1 plan unchanged.

Resolutions:
A) Include backup job stub (no UI) in scope for future extension.
B) Set job retention policy to keep latest 200 jobs (FIFO purge beyond threshold).
C) Defer large taxonomy merge background escalation; implement synchronous transactional merge for M1.

Implications:
- Implement purge mechanism in JobService after job completion insert.
- Backup job type scaffold added to enum/model; executor returns NotImplemented result placeholder.
- Taxonomy merge kept simple; add metric to log item count to inform future background offload threshold.

Next Actions:
- Update task checklist (mark decision rationale logged).
- Finalize progress.md & activeContext with milestone approval snapshot.
