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

[2025-10-13 21:11:30 UTC] - Background Job Orchestration Consolidation & Policies
Decision:
- Consolidate duplicate progress notifier implementations into single SignalRJobProgressNotifier and remove inner JobProgressNotifier class.
- Introduce new BackgroundJobType values: Backup (stub) and RegenerateAllThumbnails (future use).
- Add singleton enqueue semantics: one Pending/Running job per BackgroundJobType enforced via TryEnqueueSingletonJobAsync and processor duplicate cancellation.
- Implement processor-side duplicate Pending job cancellation (earliest kept, later duplicates marked Cancelled with reason).
- Establish retention policy implementation in CleanupOldJobsAsync: keep most recent 200 terminal-state jobs (Completed/Failed/Cancelled) and purge excess by reverse chronological order.

Rationale:
- Eliminates divergent payload shapes and reduces maintenance surface.
- Singleton model prevents resource contention and user confusion from stacking identical global operations.
- Early retention implementation aligns with previously approved M1 decision (keep 200) and prevents unbounded growth.
- Adding enum members now avoids migration churn later when executors are added.

Implementation Details:
- Removed JobProgressNotifier class from JobProgressHub file; hub now only manages group subscription.
- Enhanced SignalRJobProgressNotifier to publish structured objects to per-job groups (job_{id}).
- Added GetActiveJobByTypeAsync and TryEnqueueSingletonJobAsync to IBackgroundJobService and implementation with transactional guard.
- BackgroundJobProcessorService updated to:
  * Query only Pending jobs directly.
  * Cancel later Pending duplicates before execution and notify clients.
  * Emit lifecycle notifications (Started, Completed, Failed, Cancelled).
  * Respect pre-start cancellation and mid-execution cancellation, setting Cancelled status and CompletedAt.
- Retention logic replaced time-based cleanup in BackgroundJobService with count-based purge (skip 200 most recent, soft delete older via existing repository soft delete).
- Added new enum values (Backup=7, RegenerateAllThumbnails=8); future executors will serialize result summaries.

Implications:
- Clients subscribing to per-job groups receive consistent payload shapes.
- API/UI must treat Cancelled as terminal; progress may show &lt;100 when cancellation occurs mid-loop.
- Future addition of per-type configurability (allow multiple jobs) would require relaxing singleton guard logic.
- Retention now independent of a time horizon; optional future config could parameterize retentionCount.

Follow-ups:
- Add structured ResultJson models and BaseJobExecutor abstraction (pending).
- Add indices/migration if needed for new enum strings (Type already indexed).
- Document notifier contract and singleton semantics in architecture guide (pending).

[2025-10-13 23:27:55 UTC] - Background Job Documentation & Test Finalization
Decision:
- Incorporated comprehensive background job orchestration section into architecture guide (singleton semantics, structured result schema, SignalR event contract, retention).
- Added implementation details section to implementation guide describing components (entity, processor, executors, notifier, API endpoints) and extension workflow.
- Confirmed structured result payload (`BackgroundJobResult`) as canonical contract; no separate per-job result DTOs required for M1.
- Added SignalR integration smoke test validating JobStarted -> (JobCompleted|JobFailed) event sequence.
Rationale:
- Centralized documentation reduces onboarding friction and ensures consistent extension patterns.
- Structured single result schema avoids proliferation of ad hoc JSON payloads per job type.
- Integration test provides early warning if notifier/hub routing breaks during refactors.
Implementation Details:
- Updated [`Fuzzbin.architecture-csharp.md`](Fuzzbin.architecture-csharp.md:1) with “Background Job Orchestration” section (model, lifecycle, progress, retention).
- Updated [`Fuzzbin.implementation-guide.md`](Fuzzbin.implementation-guide.md:1) inserting “Background Job Orchestration Implementation” before Testing Strategy.
- Created integration test file `SignalRJobProgressTests` asserting reception of lifecycle events.
Implications:
- Task #17 (documentation update) can be closed.
- Future additions (new job types) must follow documented executor pattern & switch registration.
Follow-ups:
- (Future) Add crash recovery behavior (mark orphan Running -> Failed) on startup.
- (Future) Add unified Job Dashboard UI consuming structured result & live events.
