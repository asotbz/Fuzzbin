# Fuzzbin QA Follow-Up Plan

This document captures the remaining QA findings and proposes an implementation plan. Items are grouped by functional area so we can divide ownership and iterate efficiently.

## 1. Video Library UX

### 1.1 Edit Metadata Flow
- **Re-enable edit buttons**  
  - Wire `VideoLibraryGrid`/`VideoLibraryList` edit buttons to navigate to the metadata view in edit mode.  
  - In `VideoDetails.razor`, ensure the `Edit Metadata` button toggles editable fields and exposes a single save pathway.
- **Implement inline-edit state**  
  - Convert read-only fields to MudBlazor form components when editing.  
  - Add validation for required fields (title, artist, at least one source URL).
- **Persist changes**  
  - Introduce a dedicated API endpoint for bulk metadata updates to minimise round-trips and handle concurrency.  
  - Update UI to show success and failure toasts per item.

### 1.2 Delete Video Confirmation
- Hook delete buttons (single-row and multi-select) to a confirmation dialog that lists file paths slated for removal.  
- Add service layer method to delete both DB record and physical media/NFO, with safeguards (e.g., recycle bin option).  
- Provide summary toast after completion.

### 1.3 Stream Playback (GET `/api/videos/stream`)
- Inspect controller and static file middleware to determine why the 404 occurs (likely library path mismatch).  
- Add integration test that trains a sample video and ensures the stream endpoint returns `200` with content headers.  
- Surface user-friendly error message while streaming failure persists.

## 2. Metadata Detail Improvements

### 2.1 Display Enhancements
- Extend `VideoMetadata` view model to expose:  
  - Source URL list (stored + verified)  
  - Collections membership list  
  - Record label/publisher and verification status
- Render the additional sections with collapsible panels to keep layout tidy.

### 2.2 Metadata Refresh Workflow
- **Library-level trigger**  
  - When no videos are selected, enable toolbar buttons for “Refresh Metadata” and “Organize Files” to operate on the full library.  
  - Implement long-running job reporting (Hub message, progress modal, or log download).
- **Matching logic**  
  - Promote the `ImvdbMapper.ComputeMatchConfidence` result to the UI when confidence < 0.9.  
  - For single-video refresh with low confidence, display top 5 matches and allow manual selection.  
  - Add skip logic for multi-selection when confidence falls below threshold.
- **Data augmentation**  
  - Regenerate thumbnails using local video file if remote data lacks artwork.  
  - Verify source URLs against IMVDb (update status flags).
- **NFO regeneration**  
  - Schedule NFO re-write post refresh with tags, genres, collections, and URLs kept in sync with DB records.

## 3. Collection Management UX

### 3.1 Bulk Add/Remove Polish
- Include feedback on which collections were updated (counts of adds/removals).  
- Refresh cached video entries after collection changes to keep list view accurate.  
- Add ability to create smart collections from current filter criteria.

### 3.2 Collection Dialog Enhancements
- Provide quick filter/search inside the add-to-collection dialog for large libraries.  
- Respect per-collection constraints (e.g., prevent addition to smart collections).

## 4. Background Operations & Job Tracking

### 4.1 Long-Running Job Service
- Establish a job registry that tracks bulk actions (refresh metadata, organize files, delete).  
- Expose API + SignalR updates so the UI can show progress bars and allow cancellation.

### 4.2 Error Handling & Logging
- Centralise exception handling so bulk operations roll back cleanly and surface actionable messages.  
- Add structured logging (with correlation IDs) around metadata refresh, collection updates, and file operations.

## 5. Testing Strategy

### 5.1 Automated Tests
- **Unit tests**:  
  - `ImvdbMapper.ComputeMatchConfidence` scenarios  
  - New collection bulk operations  
  - Metadata service low-confidence branching
- **Integration tests**:  
  - API coverage for bulk metadata updates, delete confirmation, stream endpoint  
  - Background job controller interactions (start, monitor, cancel)

### 5.2 Manual QA Checklist
- Walkthrough for each toolbar action (single video vs. multi-select vs. none selected).  
- Metadata edit end-to-end (edit → save → refresh → NFO regeneration).  
- Stream playback (local files, missing files, permission errors).
- Organize files dry-run on sample dataset to confirm naming pattern application.

## 6. Manage Section (Genres & Tags)

### 6.1 Resolve 404s and Route Cleanup
- Fix routing for `/manage/genres` and `/manage/tags` to ensure the pages are registered in `Program.cs` and nav menus.  
- Remove the `/manage/artists` page, associated navigation link, and any unused services.  
- Add integration test that hits each manage route and asserts `200`.

### 6.2 Genres Management UI
- Replace the static page with a sortable, filterable MudTable bound to `Genre` records.  
- Add selection support (checkbox column) and show counts of videos per genre to aid decisions.  
- Provide bulk action toolbar:
  - **Generalize Genres**: trigger dialog to choose target genre and persist mappings via `IGenreMappingDefaultsProvider`.  
  - **Delete** (optional, if desired) with confirmation.
- Update backend API:
  - Endpoint to fetch paged genre data with search/sort descriptors.  
  - Endpoint to apply generalized mapping and update affected videos.

### 6.3 Tags Management UI
- Build MudTable with sorting | filtering | selection for tags.  
- Enable per-tag rename & delete actions (inline menu).  
- Add bulk delete workflow:
  - Confirmation modal showing sample impacted videos.  
  - Service method that removes tag associations before deleting the tag entity to maintain referential integrity.
- Include inline form + button to add new tags; validate duplicates and show success toast.
- Extend API layer:
  - GET paged tags  
  - POST create tag  
  - PUT rename tag  
  - DELETE (single + batch) with cascade removal from videos.

## 7. Collections Page

### 7.1 Dependency Injection Fix
- Register `ICollectionService` in the Blazor DI container (if missing) and update constructor injection.  
- Add smoke test to ensure the page renders without missing services.

### 7.2 Collections Overview
- Provide toggling between grid/list views (reusing video library components where possible).  
- Each card/row should display collection metadata (type, count, duration).

### 7.3 Collection Operations
- Actions per collection:
  - **View contents**: navigate to `/search` with collection filter applied (query string).  
  - **Rename**: inline edit or dialog hooked to existing `CollectionService.UpdateCollectionAsync`.  
  - **Delete**: confirmation modal with cascade removal; ensure smart collections handle teardown gracefully.
- Bulk actions (optional stretch): selection to delete multiple collections.
- Update tests: ensure rename/delete propagate to DB and UI refreshes.

## 8. Download Queue Reliability

### 8.1 Failed Queue Actions
- Audit download queue repository: ensure delete removes entries and raises notifications to refresh UI.  
- Implement restart logic that requeues items with proper status resets and triggers downloader service to pick them up.

### 8.2 Clear Queue
- Wire “Clear Queue” to batch delete depending on active tab (failed/in-progress/completed).  
- Provide confirmation and progress indicator.

### 8.3 Completed Queue Enhancements
- Populate titles from saved video metadata; ensure queue stores `VideoId`/`Title` when marking complete.  
- Fix play action to fetch video resource and navigate player.  
- Capture source URL during download and persist to video’s source list.

### 8.4 Duplicate Detection
- Add guard in download request pipeline to prevent enqueuing same URL twice (case-insensitive).  
- Surface toast when duplicate queued.

### 8.5 Monitoring & Tests
- Extend queue service unit tests for delete/restart/clear scenarios.  
- Add integration test simulating failed → restart → completed flow.

## 9. Search Experience Improvements

### 9.1 Defaults & Filters
- Default both “Include yt-dlp” and “Include IMVDb” toggles to `true`. Persist user preference if needed.  
- Rename “Search Filters” section header to “Local Library”.

### 9.2 External Results Actions
- Replace “Open Source” text with icon button opening new tab (`target="_blank"`, `rel="noopener"`).  
- Add `+` icon to queue downloads directly; ensure queue duplication checks run.
- Fix results summary to show actual count (resolve binding issue returning “?? videos”).

### 9.3 Testing
- UI tests covering toggles, new buttons, and results count display.  
- API/logic tests ensuring external searches respect new defaults.

## 10. Activity Log Visibility

### 10.1 Logging Instrumentation
- Verify services emit `ActivityLogEntry` records on key events (downloads, metadata refresh, organize, delete).  
- Backfill instrumentation where missing.

### 10.2 Activity Page
- Update the page to read from log storage (DB or file) and render paged entries with filtering (type/date/user).  
- Provide “no activity yet” message when empty.

### 10.3 Tests
- Unit tests for log service.  
- Integration test ensuring a sample action appears in the log.

## 11. Settings Overhaul

### 11.1 Remove Unused Features
- Strip onboarding tour references (UI components, settings toggles).  
- Remove Export/Import settings UI and backend endpoints.

### 11.2 Backup Restore
- Enable browse button by fixing `<InputFile>`/JS interop and wiring to restore handler.  
- Provide status updates and validation (file type, size).

### 11.3 Keyboard Shortcuts
- Implement actual handlers via `KeyboardShortcutService`; ensure overlay/hint icon opens helper dialog or cheat-sheet.  
- Update documentation tooltip to explain available shortcuts.

### 11.4 Tooltips & Copy
- Review all settings fields and populate MudTooltip content describing defaults and impacts.

### 11.5 New Settings
- **General**: add “Change Password” field with confirm + backend endpoint to update credentials.  
- **Organization**: 
  - support `{primary_artist}` naming token — update file organization service & preview.
  - support the option to normalize file and directory names as follows (default off):
      - Converted to lowercase
      - Special characters removed (including hyphens)
      - Diacritics normalized (ä → a, é → e, ñ → n)
      - Spaces replaced with underscores
      - Multiple underscores condensed to single  
- **Metadata / NFO**:
  - Option to choose whether NFO artist field uses primary artist only or includes featuring list (default includes featuring list).
  - When the above setting is enabled, also expose a setting allowing for featuring artists to be appended to track title (default off).
  - Option to write collection names as NFO tags (default off).
- Ensure default values defined in configuration provider and surfaced in UI.

### 11.6 Testing
- Unit tests for naming pattern token expansion (`primary_artist`).  
- Integration tests for password change and NFO generation options.  
- Manual checklist verifying tooltips, shortcut overlay, backup restore.
