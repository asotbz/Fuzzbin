# Manual QA Checklist

**Purpose**: Comprehensive manual testing checklist to validate functionality before production deployment.  
**Last Updated**: 2025-10-28  
**Target Release**: Post-Implementation Phase

---

## Testing Environment Setup

- [ ] Fresh database or known test data state
- [ ] Test video files available in library (various formats: MP4, MKV, WebM, AVI)
- [ ] IMVDb API key configured
- [ ] Network connectivity for external API calls
- [ ] Multiple browser testing (Chrome, Firefox, Safari, Edge)

---

## 1. Video Library UX

### 1.1 Edit Metadata Flow

- [ ] Click edit button on a video in grid view
- [ ] Click edit button on a video in list view
- [ ] Verify VideoEditorDialog opens with current metadata populated
- [ ] Edit title field and save
- [ ] Edit artist field and save
- [ ] Add/remove genres
- [ ] Add/remove tags
- [ ] Verify required field validation (Title, Artist)
- [ ] **Edge Case**: Try to save with empty title - should show validation error
- [ ] **Edge Case**: Try to save with empty artist - should show validation error
- [ ] Verify success toast appears after save
- [ ] Verify video details update in the library view
- [ ] **Missing Feature**: Validate at least one source URL (not currently implemented)

### 1.2 Delete Video Confirmation

- [ ] Select single video and click delete
- [ ] Verify ConfirmDeleteVideosDialog shows file path
- [ ] Verify recycle bin checkbox is present
- [ ] Delete with recycle bin enabled
- [ ] Verify file moved to recycle bin (check file system)
- [ ] Delete with recycle bin disabled
- [ ] Verify file permanently deleted
- [ ] Select multiple videos and delete
- [ ] Verify summary toast shows count after deletion
- [ ] **Edge Case**: Try to delete video that's already been deleted externally

### 1.3 Stream Playback

- [ ] Click play on a video
- [ ] Verify video player opens
- [ ] Verify video streams and plays
- [ ] Test seek functionality (jump to different timestamps)
- [ ] Test pause/resume
- [ ] Test volume control
- [ ] Test fullscreen mode
- [ ] **Edge Case**: Test with video file that's been moved/deleted
- [ ] **Edge Case**: Test with very large video file (>2GB)
- [ ] **Edge Case**: Test with special characters in filename
- [ ] Verify error message displays for missing files
- [ ] Test range request support (partial content)

---

## 2. Metadata Detail Improvements

### 2.1 Display Enhancements

- [ ] Open VideoDetailsDialog for a video
- [ ] Verify Source URLs panel displays with verification status
- [ ] Verify Collections membership panel shows all collections
- [ ] Verify Record Label/Publisher panel displays correctly
- [ ] Expand/collapse each panel
- [ ] **With IMVDb Data**: Verify verification status shows "Verified"
- [ ] **Without IMVDb Data**: Verify shows "Not Verified"
- [ ] Test with video having multiple source URLs
- [ ] Test with video in multiple collections

### 2.2 Metadata Refresh Workflow

#### Single Video Refresh
- [ ] Select single video with low-quality metadata
- [ ] Click refresh metadata
- [ ] **High Confidence Match**: Verify metadata updates automatically
- [ ] **Low Confidence Match (<0.9)**: Verify ManualMatchSelectionDialog opens
- [ ] In manual selection dialog, review top 5 matches
- [ ] Verify each match shows: Title, Artist, Year, Director, Genres, Confidence
- [ ] Select a match and accept
- [ ] Verify video metadata updates
- [ ] Click skip on low confidence dialog
- [ ] Verify video unchanged

#### Bulk Video Refresh
- [ ] Select multiple videos
- [ ] Click refresh metadata
- [ ] Verify progress dialog shows
- [ ] Verify high-confidence matches auto-update
- [ ] Verify low-confidence matches are skipped with logging
- [ ] Verify summary shows: successful, skipped, failed counts

#### Library-Level Refresh
- [ ] With no videos selected, click refresh metadata
- [ ] Verify confirmation dialog for full library refresh
- [ ] Accept and verify background job queues
- [ ] Verify JobProgressDialog opens
- [ ] Watch real-time progress updates via SignalR
- [ ] Verify completion summary includes skipped count
- [ ] Check activity log for refresh records

---

## 3. Collection Management UX

### 3.1 Bulk Add/Remove Polish

- [ ] Select multiple videos
- [ ] Click "Add to Collection"
- [ ] Select a collection and add
- [ ] Verify success message shows count (e.g., "Added 5 videos, Skipped 2 duplicates")
- [ ] **Edge Case**: Try adding videos already in collection - verify skip count
- [ ] Click "Remove from Collections"
- [ ] Remove from multiple collections
- [ ] Verify summary shows per-collection removal counts
- [ ] Apply active filters (e.g., genre, year range)
- [ ] Click "Create Smart Collection from Filters"
- [ ] Verify suggested collection name includes filter criteria
- [ ] Create smart collection and verify videos match criteria

### 3.2 Collection Dialog Enhancements

- [ ] Open add-to-collection dialog with 5 collections - verify no search field
- [ ] Create 6 more collections (total 11)
- [ ] Open dialog again - verify search field appears
- [ ] Search for collection by name
- [ ] Verify smart collections shown as disabled with lock icon
- [ ] Hover over smart collection - verify tooltip explains why disabled
- [ ] Verify helper text explains eligible collection types
- [ ] Try to add to smart collection - verify prevented

---

## 4. Background Operations & Job Tracking

### 4.1 Long-Running Job Service

- [ ] Start a long-running job (e.g., metadata refresh, file organization)
- [ ] Verify job appears in JobProgressDialog
- [ ] Verify progress bar updates in real-time
- [ ] Verify status messages update
- [ ] Click cancel button mid-execution
- [ ] Verify job cancels gracefully
- [ ] Start multiple jobs
- [ ] Verify each tracked separately

### 4.2 Error Handling & Logging

- [ ] Trigger a job failure (e.g., invalid path)
- [ ] Verify error message displays
- [ ] Check activity log for error details
- [ ] Verify correlation ID logged for debugging
- [ ] Verify job marked as failed with error message

---

## 5. Testing Strategy - Automated Test Validation

### 5.1 Run Unit Tests

```bash
dotnet test Fuzzbin.Tests/Services/ImvdbMapperTests.cs
```

- [ ] All ImvdbMapper.ComputeMatchConfidence tests pass
- [ ] Exact match returns >= 0.95 confidence
- [ ] Case-insensitive matches work correctly
- [ ] Partial matches return medium confidence
- [ ] Complete mismatches return low confidence
- [ ] Edge cases handled (null, empty strings)

```bash
dotnet test Fuzzbin.Tests/Services/MetadataServiceTests.cs
```

- [ ] High confidence (>= 0.9) applies metadata automatically
- [ ] Low confidence (< 0.9) sets RequiresManualReview flag
- [ ] Boundary case (exactly 0.9) tested
- [ ] fetchOnlineMetadata=false skips confidence check

### 5.2 Run Integration Tests

```bash
dotnet test Fuzzbin.Tests/Integration/VideoStreamEndpointTests.cs
```

- [ ] Missing path returns 400 Bad Request
- [ ] Non-existent file returns 404 Not Found
- [ ] Valid file streams successfully
- [ ] Range requests return 206 Partial Content
- [ ] Content-Type headers correct for file extensions
- [ ] Path traversal attempts blocked
- [ ] URL-encoded paths decoded correctly
- [ ] Anonymous access allowed

---

## 6. Manage Section (Genres & Tags)

### 6.1 Genres Management

- [ ] Navigate to /manage/genres
- [ ] Verify table loads with genres
- [ ] Sort by name, video count
- [ ] Filter/search genres
- [ ] Select multiple genres
- [ ] Click "Generalize" button
- [ ] Select target genre
- [ ] Verify source genres merged into target
- [ ] Verify videos updated
- [ ] Delete single genre
- [ ] Bulk delete genres
- [ ] Verify genre removal from videos

### 6.2 Tags Management

- [ ] Navigate to /manage/tags
- [ ] Add new tag with color
- [ ] Verify tag appears in list
- [ ] Rename tag
- [ ] Verify tag name updated everywhere
- [ ] Delete tag
- [ ] Bulk delete tags
- [ ] View videos with specific tag
- [ ] Filter tags by search

---

## 7. Collections Page

### 7.1 Collections Overview

- [ ] Navigate to /collections
- [ ] Toggle between grid and list view
- [ ] Verify collection metadata displays (type, count, duration)
- [ ] Test sorting options
- [ ] Click "View Contents" on a collection
- [ ] Verify redirects to /search with collection filter
- [ ] Rename collection
- [ ] Verify name updates
- [ ] Delete manual collection
- [ ] Verify confirmation dialog for smart collections

### 7.2 Bulk Operations

- [ ] Select multiple collections
- [ ] Bulk delete
- [ ] Verify confirmation shows count
- [ ] Verify all selected collections deleted

---

## 8. Download Queue Reliability

### 8.1 Failed Queue Actions

#### Single Item Actions
- [ ] Add invalid URL to download queue
- [ ] Wait for download to fail
- [ ] Verify appears in "Failed" tab with error message
- [ ] Click delete on failed item
- [ ] Verify removal and toast notification
- [ ] Verify item marked as deleted (not physically removed)
- [ ] Add another failed download
- [ ] Click retry/restart button
- [ ] Verify status changes from "Failed" to "Queued"
- [ ] Verify retry count incremented
- [ ] Verify error message cleared
- [ ] Verify progress reset to 0%
- [ ] Verify download speed/ETA cleared
- [ ] Verify item re-queued and download starts

#### Bulk Retry
- [ ] Create multiple failed downloads (3-5 items)
- [ ] Navigate to "Failed" tab
- [ ] Click "Retry All Failed" button
- [ ] Verify all failed items reset to "Queued" status
- [ ] Verify retry count incremented for each item
- [ ] Verify all items re-queued in download service
- [ ] Verify downloads begin processing
- [ ] Verify success toast shows count of retried items

#### Delete Safeguards
- [ ] Start a download
- [ ] While downloading, try to delete the item
- [ ] Verify deletion prevented with error message
- [ ] Verify item still shows in "Downloading" tab

### 8.2 Clear Queue

- [ ] Add items to queue in different states (in-progress, completed, failed)
- [ ] Navigate to "Failed" tab
- [ ] Click "Clear Failed" button
- [ ] Verify ConfirmClearQueueDialog shows item count and status-specific message
- [ ] Verify shows up to 10 items that will be removed
- [ ] Confirm and verify only failed items cleared
- [ ] Navigate to "Queued" tab
- [ ] Click "Clear Queued" button
- [ ] Verify warning that action cannot be undone
- [ ] Confirm and verify only queued items cleared
- [ ] Navigate to "Completed" tab
- [ ] Click "Clear Completed" button
- [ ] Confirm and verify only completed items cleared (history cleanup)
- [ ] Verify processing indicator shows during bulk operations
- [ ] Verify success toast appears after completion

### 8.3 Completed Queue

- [ ] Complete a download
- [ ] Navigate to "Completed" tab
- [ ] Verify title displays as "{Artist} - {Title}" format (not "Unknown")
- [ ] Verify title populated from video metadata automatically
- [ ] Click play button on completed item
- [ ] Verify navigates to `/player/{VideoId}` and video plays
- [ ] **Edge Case**: Complete download for video not in library yet
- [ ] Verify warning snackbar shows "Video not found in library"
- [ ] Check VideoDetailsDialog for completed video
- [ ] Verify Source URLs panel shows download source
- [ ] Verify source marked as "Verified" with 100% confidence
- [ ] Verify provider shown (e.g., "youtube")
- [ ] **Edge Case**: Download same video from different source
- [ ] Verify second source added without duplicates

### 8.4 Duplicate Detection

#### Basic Duplicate Detection
- [ ] Add URL to queue (e.g., "https://youtube.com/watch?v=abc123")
- [ ] Wait for status to be "Queued" or "Downloading"
- [ ] Try adding exact same URL again
- [ ] Verify warning toast: "This URL is already in the queue"
- [ ] Verify duplicate NOT added to database
- [ ] Check queue - verify only one instance exists

#### Case-Insensitive Detection
- [ ] Add URL with lowercase: "https://youtube.com/watch?v=abc123"
- [ ] Try adding same URL with uppercase: "HTTPS://YOUTUBE.COM/WATCH?V=ABC123"
- [ ] Verify duplicate detected (case-insensitive)
- [ ] Try mixed case variations
- [ ] Verify all variations detected as duplicates

#### Status-Based Detection
- [ ] Add URL and let download complete
- [ ] Try adding same URL again
- [ ] Verify allowed (completed items ignored for duplicate check)
- [ ] Add URL and let it fail
- [ ] Try adding same URL again
- [ ] Verify allowed (failed items ignored for duplicate check)
- [ ] Add URL in "Queued" state
- [ ] Try adding again
- [ ] Verify blocked (queued items checked)
- [ ] Add URL in "Downloading" state
- [ ] Try adding again
- [ ] Verify blocked (downloading items checked)

#### Search Page Integration
- [ ] Navigate to /search page
- [ ] Find external result (YouTube video)
- [ ] Click "+" (Add to Queue) button
- [ ] Verify success snackbar
- [ ] Click "+" again on same result
- [ ] Verify duplicate detection snackbar
- [ ] Navigate to /downloads page
- [ ] Verify only one instance in queue

---

## 9. Search Experience

- [ ] Perform search without filters
- [ ] Verify "Local Library" toggle defaults to ON
- [ ] Toggle off - verify external results shown
- [ ] Click external link icon on result
- [ ] Verify opens in new tab with security attributes
- [ ] Click "Add to Queue" on external result
- [ ] Verify duplicate detection works
- [ ] Verify results count displays correctly
- [ ] Apply filters (genre, year, artist)
- [ ] Verify results update
- [ ] Clear filters
- [ ] Test pagination with large result sets

---

## 10. Activity Log Visibility

### 10.1 Activity Page

- [ ] Navigate to /activity
- [ ] Verify recent activities display
- [ ] Test pagination
- [ ] Apply date filter
- [ ] Apply activity type filter (Download, Metadata Refresh, Delete, etc.)
- [ ] **Verification Needed**: Confirm "No activity yet" message for empty state
- [ ] Verify correlation IDs shown for debugging

---

## 11. Settings Overhaul

### 11.1 General Settings

- [ ] Navigate to /settings
- [ ] Test "Change Password" section
- [ ] Enter current password
- [ ] Enter new password and confirmation
- [ ] Submit with non-matching passwords - verify error
- [ ] Submit with weak password - verify validation error
- [ ] Submit with wrong current password - verify error
- [ ] Submit with correct passwords
- [ ] Verify success message and loading state during submission
- [ ] Sign out and sign in with new password
- [ ] Verify old password no longer works

### 11.2 Organization Settings

- [ ] Edit organization path template
- [ ] Include `{primary_artist}` token (e.g., `{primary_artist}/{year}`)
- [ ] Test with artist "Artist feat. Other Artist"
- [ ] Trigger file organization
- [ ] Verify token expands to "Artist" (featuring text stripped)
- [ ] Test with " ft. " and " featuring " variations
- [ ] Verify all featuring tokens stripped correctly
- [ ] Enable "Normalize file names" option
- [ ] Test with files containing: uppercase, spaces, special chars, diacritics
- [ ] Organize files
- [ ] Verify normalization applied:
  - [ ] Converted to lowercase
  - [ ] Spaces replaced with underscores
  - [ ] Diacritics removed (ä→a, é→e, ñ→n)
  - [ ] Special characters stripped
  - [ ] Multiple underscores collapsed to single
  - [ ] File extensions preserved
- [ ] Disable "Normalize file names"
- [ ] Organize same files
- [ ] Verify normalization NOT applied

### 11.3 Metadata/NFO Settings

- [ ] Test "Use primary artist only for NFO" setting:
  - [ ] Select video with artist "Main Artist feat. Guest"
  - [ ] Enable "Use primary artist only for NFO"
  - [ ] Generate NFO file
  - [ ] Open NFO and verify `<artist>` contains only "Main Artist"
  - [ ] Disable setting
  - [ ] Regenerate NFO
  - [ ] Verify `<artist>` now includes full "Main Artist feat. Guest"
- [ ] Test "Append featured artists to title" setting:
  - [ ] Enable "Use primary artist only for NFO" (prerequisite)
  - [ ] Enable "Append featured artists to title"
  - [ ] Generate NFO for video with featuring artists
  - [ ] Verify `<title>` includes " (feat. Guest)" appended
  - [ ] Verify setting is disabled when "Use primary artist only" is off
- [ ] Test "Write collections as NFO tags" setting:
  - [ ] Add video to multiple collections
  - [ ] Enable "Write collections as NFO tags"
  - [ ] Generate NFO
  - [ ] Verify each collection appears as `<tag>` element in NFO
  - [ ] Disable setting
  - [ ] Regenerate NFO
  - [ ] Verify no collection `<tag>` elements present
- [ ] Test genre mappings:
  - [ ] Navigate to genre mappings section
  - [ ] Add mapping: "Electro" → "Electronic"
  - [ ] Save and verify mapping persists after page refresh
  - [ ] Generate NFO for video with "Electro" genre
  - [ ] Verify NFO contains "Electronic" instead
  - [ ] Click "Reset to Defaults"
  - [ ] Verify mappings revert to default set
  - [ ] Verify custom mappings cleared

### 11.4 Backup & Restore

- [ ] Click "Backup Database" button
- [ ] Verify backup file downloads
- [ ] Click "Browse" for restore
- [ ] Select non-ZIP file - verify validation error
- [ ] Select valid backup file
- [ ] Click restore
- [ ] Verify confirmation dialog
- [ ] Complete restore
- [ ] Verify data restored correctly

### 11.5 Keyboard Shortcuts

- [ ] Look for keyboard shortcuts help icon/button in UI
- [ ] Click keyboard shortcuts help icon (or press Shift+?)
- [ ] Verify KeyboardShortcutsDialog opens
- [ ] Review all listed shortcuts:
  - [ ] Media controls (Space, Arrow keys, M, F)
  - [ ] Navigation (Ctrl+V, Ctrl+C, Ctrl+D, Ctrl+H)
  - [ ] Help trigger (Shift+?)
- [ ] Close dialog with Escape key
- [ ] Test actual keyboard shortcuts:
  - [ ] Navigate to player page
  - [ ] Press Space - verify play/pause toggles
  - [ ] Press arrow keys - verify seek forward/backward
  - [ ] Press M - verify mute toggle
  - [ ] Press F - verify fullscreen toggle
  - [ ] Press Ctrl+V - verify navigates to /videos
  - [ ] Press Ctrl+C - verify navigates to /collections
  - [ ] Press Ctrl+D - verify navigates to /downloads
  - [ ] Press Ctrl+H - verify navigates to home
- [ ] **Known Gap**: Help icon may not be visible in main layout

### 11.6 Settings Tooltips

- [ ] Navigate to /settings
- [ ] Hover over all checkbox settings
- [ ] Verify each has explanatory tooltip or HelperText:
  - [ ] Downloads tab:
    - [ ] Extract metadata from downloads
    - [ ] Generate NFO files
    - [ ] Download subtitles if available
    - [ ] Embed thumbnails in video files
  - [ ] Metadata tab:
    - [ ] Enable online metadata fetching
    - [ ] Automatically fetch missing metadata
    - [ ] Overwrite existing metadata with online data
    - [ ] Generalize genres when writing metadata
    - [ ] Enable debug logging
    - [ ] Enable automatic database backups
- [ ] Verify all text input fields have HelperText
- [ ] Verify tooltips are clear and user-friendly

---

## 12. Cross-Browser Testing

Repeat critical flows in each browser:

- [ ] Chrome/Edge (Chromium)
- [ ] Firefox
- [ ] Safari (macOS)

Focus on:
- Video playback
- SignalR real-time updates
- File upload/download
- Responsive UI components

---

## 13. Performance Testing

- [ ] Library with 100+ videos loads within 3 seconds
- [ ] Search returns results within 1 second
- [ ] Video streaming starts within 2 seconds
- [ ] Metadata refresh processes 10 videos/minute
- [ ] No memory leaks during extended session (2+ hours)

---

## 14. Security Testing

- [ ] Verify authentication required for protected endpoints
- [ ] Test path traversal protection in stream endpoint
- [ ] Verify CSRF tokens on form submissions
- [ ] Test SQL injection protection in search
- [ ] Verify file upload size limits enforced
- [ ] Test XSS protection in user input fields

---

## Edge Cases & Error Scenarios

- [ ] Library directory deleted while app running
- [ ] Network interruption during download
- [ ] Database locked during operation
- [ ] Extremely long video title (>500 characters)
- [ ] Special characters in all text fields
- [ ] Concurrent edits to same video
- [ ] Session timeout during long operation
- [ ] Browser refresh during background job
- [ ] Download queue: Try deleting actively downloading item
- [ ] Download queue: Add duplicate URL with different casing
- [ ] Download queue: Retry download that's already queued
- [ ] File organization: Files with no artist/title metadata
- [ ] File organization: Path longer than OS limit (260 chars on Windows)
- [ ] NFO generation: Video with no genres or collections
- [ ] Password change: Submit while another request in progress

---

## Regression Testing

Before each release, re-test:
- [ ] Core playback functionality
- [ ] Download queue end-to-end
- [ ] Metadata enrichment workflow
- [ ] File organization
- [ ] Collection management
- [ ] Search and filter
- [ ] User authentication

---

## Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| QA Lead | | | |
| Dev Lead | | | |
| Product Owner | | | |

---

## Notes & Issues Found

Use this space to document issues discovered during testing:

```
Issue #1: [Description]
- Steps to reproduce:
- Expected behavior:
- Actual behavior:
- Severity: [Critical/High/Medium/Low]

Issue #2: [Description]
...