# Maintenance System Implementation Roadmap

## Overview

This roadmap outlines the step-by-step implementation plan for the complete maintenance system, including all six maintenance tasks, infrastructure, and UI integration.

**Estimated Timeline**: 2-3 weeks  
**Complexity**: Medium  
**Dependencies**: Existing services (LibraryPathManager, MetadataService, BackupService, etc.)

---

## Phase 1: Core Infrastructure (Days 1-2)

### 1.1 Create Base Interface and Models

- [ ] Create `IMaintenanceTask` interface
- [ ] Create `MaintenanceTaskResult` class
- [ ] Add to `Fuzzbin.Core/Interfaces/` directory
- [ ] **Files**: `IMaintenanceTask.cs`

**Priority**: Critical  
**Dependencies**: None

### 1.2 Create Database Entities

- [ ] Create `MaintenanceExecution` entity
- [ ] Create `CacheStatSnapshot` entity
- [ ] Add `IsMissing` and `MissingDetectedAt` to `Video` entity
- [ ] **Files**: 
  - `Fuzzbin.Core/Entities/MaintenanceExecution.cs`
  - `Fuzzbin.Core/Entities/CacheStatSnapshot.cs`
  - Update `Fuzzbin.Core/Entities/Video.cs`

**Priority**: Critical  
**Dependencies**: None

### 1.3 Update Database Context

- [ ] Add `MaintenanceExecutions` DbSet
- [ ] Add `CacheStatSnapshots` DbSet
- [ ] Configure indexes in `OnModelCreating`
- [ ] Update `IUnitOfWork` interface
- [ ] Update `UnitOfWork` implementation
- [ ] **Files**:
  - `Fuzzbin.Data/Context/ApplicationDbContext.cs`
  - `Fuzzbin.Core/Interfaces/IUnitOfWork.cs`
  - `Fuzzbin.Data/UnitOfWork.cs`

**Priority**: Critical  
**Dependencies**: 1.2

### 1.4 Create and Apply Migration

- [ ] Generate migration: `dotnet ef migrations add AddMaintenanceSystem`
- [ ] Review generated migration SQL
- [ ] Add configuration seed data to migration
- [ ] Test migration on dev database
- [ ] Apply migration

**Priority**: Critical  
**Dependencies**: 1.3

**Command**:
```bash
dotnet ef migrations add AddMaintenanceSystem \
  --project Fuzzbin.Data \
  --startup-project Fuzzbin.Web
```

### 1.5 Implement Scheduler Service

- [ ] Create `MaintenanceSchedulerService` class
- [ ] Implement `BackgroundService` pattern
- [ ] Add task discovery logic
- [ ] Add sequential execution logic
- [ ] Add execution history recording
- [ ] **Files**: `Fuzzbin.Services/MaintenanceSchedulerService.cs`

**Priority**: Critical  
**Dependencies**: 1.1, 1.3

---

## Phase 2: Maintenance Tasks (Days 3-7)

Implement tasks in order of dependency and complexity.

### 2.1 Library Scan Task

- [ ] Create `LibraryScanMaintenanceTask` class
- [ ] Implement file discovery logic
- [ ] Implement new file import
- [ ] Implement missing file detection
- [ ] Implement missing file restoration
- [ ] Add configuration loading
- [ ] Add comprehensive logging
- [ ] **Files**: `Fuzzbin.Services/Maintenance/LibraryScanMaintenanceTask.cs`

**Priority**: High  
**Dependencies**: 1.5, existing `LibraryPathManager`, `MetadataService`  
**Estimated Time**: 1 day

### 2.2 Thumbnail Cleanup Task

- [ ] Create `ThumbnailCleanupMaintenanceTask` class
- [ ] Implement orphaned thumbnail detection
- [ ] Implement file deletion logic
- [ ] Implement grace period checking
- [ ] Implement empty directory cleanup
- [ ] Add configuration loading
- [ ] **Files**: `Fuzzbin.Services/Maintenance/ThumbnailCleanupMaintenanceTask.cs`

**Priority**: High  
**Dependencies**: 1.5  
**Estimated Time**: 0.5 days

### 2.3 Cache Purge Task

- [ ] Create `CachePurgeMaintenanceTask` class
- [ ] Implement QuerySourceCache purging
- [ ] Implement candidate purging (MB, IMVDb, YT)
- [ ] Implement orphaned query cleanup
- [ ] Implement orphaned entity cleanup
- [ ] Add TTL checking logic
- [ ] **Files**: `Fuzzbin.Services/Maintenance/CachePurgeMaintenanceTask.cs`

**Priority**: High  
**Dependencies**: 1.5, cache system entities (if implemented)  
**Estimated Time**: 1 day

**Note**: If cache system from `cache-integration-strategy.md` isn't implemented yet, this task can be deferred.

### 2.4 Cache Statistics Task

- [ ] Create `CacheStatsMaintenanceTask` class
- [ ] Implement statistics collection
- [ ] Implement snapshot creation
- [ ] Implement old stats purging
- [ ] Calculate derived metrics (hit rate, avg candidates)
- [ ] **Files**: `Fuzzbin.Services/Maintenance/CacheStatsMaintenanceTask.cs`

**Priority**: Medium  
**Dependencies**: 1.5, cache system entities (if implemented)  
**Estimated Time**: 0.5 days

### 2.5 Recycle Bin Purge Task

- [ ] Create `RecycleBinPurgeMaintenanceTask` class
- [ ] Implement retention period checking
- [ ] Implement file deletion logic
- [ ] Implement soft/hard delete options
- [ ] Add comprehensive error handling
- [ ] **Files**: `Fuzzbin.Services/Maintenance/RecycleBinPurgeMaintenanceTask.cs`

**Priority**: High  
**Dependencies**: 1.5, existing `RecycleBin` entity  
**Estimated Time**: 0.5 days

### 2.6 Auto Backup Task

- [ ] Create `AutoBackupMaintenanceTask` class
- [ ] Implement backup scheduling logic
- [ ] Implement backup creation (use existing `BackupService`)
- [ ] Implement backup rotation
- [ ] Track last backup timestamp
- [ ] Add configurable interval
- [ ] **Files**: `Fuzzbin.Services/Maintenance/AutoBackupMaintenanceTask.cs`

**Priority**: High  
**Dependencies**: 1.5, existing `BackupService`  
**Estimated Time**: 0.5 days

---

## Phase 3: Service Registration (Day 8)

### 3.1 Register Services

- [ ] Register `MaintenanceSchedulerService` as hosted service
- [ ] Register all maintenance tasks as scoped services
- [ ] Update `ServiceCollectionExtensions` if needed
- [ ] **Files**: `Fuzzbin.Web/Program.cs`

**Code to add**:
```csharp
// Register maintenance tasks
builder.Services.AddScoped<IMaintenanceTask, LibraryScanMaintenanceTask>();
builder.Services.AddScoped<IMaintenanceTask, ThumbnailCleanupMaintenanceTask>();
builder.Services.AddScoped<IMaintenanceTask, CachePurgeMaintenanceTask>();
builder.Services.AddScoped<IMaintenanceTask, CacheStatsMaintenanceTask>();
builder.Services.AddScoped<IMaintenanceTask, RecycleBinPurgeMaintenanceTask>();
builder.Services.AddScoped<IMaintenanceTask, AutoBackupMaintenanceTask>();

// Register scheduler
builder.Services.AddHostedService<MaintenanceSchedulerService>();
```

**Priority**: Critical  
**Dependencies**: All Phase 2 tasks

---

## Phase 4: API Endpoints (Day 9)

### 4.1 Add Maintenance API Endpoints

- [ ] Add `POST /api/maintenance/run` - Manual trigger all tasks
- [ ] Add `POST /api/maintenance/run-task/{taskName}` - Manual trigger single task
- [ ] Add `GET /api/maintenance/history` - Get execution history
- [ ] Add `GET /api/maintenance/tasks` - List all registered tasks
- [ ] Add `GET /api/cache/stats/history` - Cache statistics history
- [ ] Add authorization requirements
- [ ] **Files**: `Fuzzbin.Web/Program.cs`

**Priority**: High  
**Dependencies**: Phase 2, Phase 3

---

## Phase 5: UI Integration (Days 10-12)

### 5.1 Settings Page Updates

- [ ] Add "Maintenance" section to Settings page
- [ ] Add maintenance interval configuration
- [ ] Add task-specific configuration sections:
  - [ ] Library Scan settings
  - [ ] Thumbnail Cleanup settings
  - [ ] Cache Stats settings
  - [ ] Recycle Bin Purge settings
  - [ ] Auto Backup settings
- [ ] Add "Run Maintenance Now" button
- [ ] Add last run timestamps display
- [ ] **Files**: Update existing `Fuzzbin.Web/Components/Pages/Settings.razor`

**Priority**: High  
**Dependencies**: Phase 4

### 5.2 Videos Page Updates

- [ ] Add "Missing" indicator chip for missing videos
- [ ] Add "Missing Videos" filter option
- [ ] Add visual styling for missing videos
- [ ] Update video actions to handle missing state
- [ ] **Files**: Update existing `Fuzzbin.Web/Components/Pages/Videos.razor`

**Priority**: Medium  
**Dependencies**: Phase 1

### 5.3 Maintenance History Page (Optional)

- [ ] Create new `MaintenanceHistory.razor` page
- [ ] Display execution history table
- [ ] Add filtering by task name, success/failure
- [ ] Add date range filtering
- [ ] Show detailed metrics in expandable rows
- [ ] **Files**: `Fuzzbin.Web/Components/Pages/MaintenanceHistory.razor`

**Priority**: Low  
**Dependencies**: Phase 4

### 5.4 Cache Statistics Dashboard (Optional)

- [ ] Create or update `CacheStatsDialog.razor`
- [ ] Add historical performance charts
- [ ] Add real-time statistics display
- [ ] Add export functionality
- [ ] **Files**: `Fuzzbin.Web/Components/Dialogs/CacheStatsDialog.razor`

**Priority**: Low  
**Dependencies**: Phase 2.4, Phase 4

---

## Phase 6: Testing (Days 13-15)

### 6.1 Unit Tests

- [ ] Test `MaintenanceSchedulerService` task discovery
- [ ] Test `MaintenanceSchedulerService` execution flow
- [ ] Test `LibraryScanMaintenanceTask` file discovery
- [ ] Test `LibraryScanMaintenanceTask` import logic
- [ ] Test `LibraryScanMaintenanceTask` missing detection
- [ ] Test `ThumbnailCleanupMaintenanceTask` orphan detection
- [ ] Test `CachePurgeMaintenanceTask` expiration logic
- [ ] Test `CacheStatsMaintenanceTask` snapshot creation
- [ ] Test `RecycleBinPurgeMaintenanceTask` retention logic
- [ ] Test `AutoBackupMaintenanceTask` scheduling logic
- [ ] **Files**: `Fuzzbin.Tests/Services/Maintenance/` directory

**Priority**: High  
**Estimated Time**: 2 days

### 6.2 Integration Tests

- [ ] Test maintenance scheduler with multiple tasks
- [ ] Test task execution order
- [ ] Test configuration changes affecting tasks
- [ ] Test manual trigger via API
- [ ] Test execution history recording
- [ ] Test error handling and recovery
- [ ] **Files**: `Fuzzbin.Tests/Integration/MaintenanceTests.cs`

**Priority**: High  
**Estimated Time**: 1 day

### 6.3 End-to-End Tests

- [ ] Test full maintenance run from scheduler
- [ ] Test UI configuration updates
- [ ] Test manual trigger from Settings page
- [ ] Test missing video detection and display
- [ ] Test cache statistics collection and display
- [ ] **Files**: `Fuzzbin.Tests/E2E/` directory (if using E2E framework)

**Priority**: Medium  
**Estimated Time**: 0.5 days

---

## Phase 7: Documentation (Day 16)

### 7.1 Code Documentation

- [ ] Add XML comments to all public interfaces
- [ ] Add XML comments to all maintenance tasks
- [ ] Update README with maintenance system overview
- [ ] **Files**: All implementation files, `README.md`

**Priority**: Medium

### 7.2 User Documentation

- [ ] Create user guide for maintenance configuration
- [ ] Document each maintenance task purpose
- [ ] Document troubleshooting common issues
- [ ] **Files**: `docs/maintenance/user-guide.md`

**Priority**: Medium

### 7.3 Developer Documentation

- [ ] Document how to add new maintenance tasks
- [ ] Update architecture diagrams
- [ ] Document testing strategy
- [ ] **Files**: Already completed in `docs/maintenance/` directory

**Priority**: Low (Already mostly complete)

---

## Phase 8: Deployment (Days 17-18)

### 8.1 Staging Deployment

- [ ] Deploy to staging environment
- [ ] Run migrations
- [ ] Verify services start correctly
- [ ] Monitor first maintenance run
- [ ] Check logs for errors

**Priority**: Critical

### 8.2 Production Deployment

- [ ] Deploy to production
- [ ] Run migrations
- [ ] Verify scheduler starts
- [ ] Monitor first few maintenance runs
- [ ] Set up alerts for task failures

**Priority**: Critical

### 8.3 Post-Deployment Monitoring

- [ ] Monitor maintenance execution times
- [ ] Monitor database growth
- [ ] Monitor system performance during maintenance
- [ ] Collect user feedback
- [ ] Adjust intervals if needed

**Priority**: High

---

## Dependencies Summary

### External Dependencies

- **Existing Services** (already implemented):
  - `ILibraryPathManager`
  - `IMetadataService`
  - `IBackupService`
  - `IConfigurationPathService`

- **Cache System** (may not be implemented yet):
  - If cache system from `cache-integration-strategy.md` is not yet implemented, defer cache-related tasks (2.3, 2.4) until after cache implementation

### Internal Dependencies

```
Phase 1 (Infrastructure) → Phase 2 (Tasks) → Phase 3 (Registration) → Phase 4 (API) → Phase 5 (UI)
                                                                              ↓
                                                                        Phase 6 (Testing)
```

---

## Risk Mitigation

### High Risk Areas

1. **Library Scan Performance**
   - **Risk**: Slow scans on large libraries (>10,000 files)
   - **Mitigation**: Implement batch processing, add timeouts, make async

2. **Database Locks During Maintenance**
   - **Risk**: Long-running tasks block user operations
   - **Mitigation**: Use read-uncommitted where appropriate, keep transactions short

3. **Disk Space for Backups**
   - **Risk**: Backup rotation fails, fills disk
   - **Mitigation**: Check available space before backup, aggressive rotation

4. **Cache Purge Timing**
   - **Risk**: Purge removes recently used cache
   - **Mitigation**: Conservative TTL defaults, test thoroughly

### Medium Risk Areas

1. **Missing File False Positives**
   - **Risk**: Network drives report files as missing temporarily
   - **Mitigation**: Add grace period, multiple checks before marking missing

2. **Thumbnail Cleanup Aggressiveness**
   - **Risk**: Delete thumbnails still in use
   - **Mitigation**: Grace period, conservative defaults, thorough testing

---

## Testing Checklist

### Critical Paths

- [ ] Maintenance scheduler starts on application startup
- [ ] Tasks execute on configured interval
- [ ] Manual trigger via API works
- [ ] Execution history is recorded correctly
- [ ] Task failures don't crash scheduler
- [ ] Configuration changes take effect
- [ ] UI displays maintenance status correctly

### Edge Cases

- [ ] Empty library directory
- [ ] All tasks disabled
- [ ] Database migration failures
- [ ] Concurrent manual triggers
- [ ] Task execution timeout
- [ ] Disk full during backup
- [ ] Network drive disconnects during scan

---

## Success Criteria

### Functional Requirements

- ✅ All six maintenance tasks implemented and working
- ✅ Scheduler runs on configurable interval
- ✅ Manual trigger available via UI and API
- ✅ Execution history recorded and queryable
- ✅ Configuration UI in Settings page
- ✅ Missing videos displayed in Videos page

### Performance Requirements

- ✅ Maintenance run completes within 5 minutes on typical library (1,000 videos)
- ✅ No user-visible performance impact during maintenance
- ✅ Database grows < 10 MB/month from maintenance tables

### Quality Requirements

- ✅ All tests passing (unit, integration, E2E)
- ✅ Code coverage > 80% for maintenance code
- ✅ Zero critical bugs in first week of production
- ✅ Comprehensive logging for debugging

---

## Future Enhancements

### Phase 9 (Future)

- [ ] Email notifications for maintenance failures
- [ ] Prometheus metrics export
- [ ] Maintenance scheduling (specific times, not just intervals)
- [ ] Parallel task execution (for independent tasks)
- [ ] Task priority/ordering configuration
- [ ] Cloud backup integration (S3, Azure, GCS)
- [ ] Advanced cache analytics dashboard
- [ ] Machine learning for optimal cache TTL
- [ ] Predictive maintenance (disk space warnings, etc.)

---

## Quick Start (For Development)

### Minimum Viable Implementation

If you need to get started quickly, implement in this order:

1. **Core Infrastructure** (Phase 1) - Required
2. **Library Scan Task** (Phase 2.1) - High value
3. **Auto Backup Task** (Phase 2.6) - High value
4. **Service Registration** (Phase 3) - Required
5. **Basic Settings UI** (Phase 5.1 partial) - Required

This gets you:
- ✅ Automatic library scanning for new/missing files
- ✅ Automated backups
- ✅ Basic configuration
- ✅ Foundation for adding more tasks later

**Estimated Time**: 4-5 days for MVP

---

## Questions & Decisions

### Open Questions

1. **Should cache purge be enabled by default if cache system isn't implemented yet?**
   - **Recommendation**: No, add `IsEnabled` check that returns false if cache tables don't exist

2. **Should maintenance run immediately on startup or wait for first interval?**
   - **Recommendation**: Run immediately (with small delay like 30s) to catch issues early

3. **Should failed tasks prevent other tasks from running?**
   - **Recommendation**: No, continue with remaining tasks and log failures

4. **Should we add a "dry run" mode for testing?**
   - **Recommendation**: Yes, add as future enhancement

### Configuration Decisions

- ✅ Default interval: 8 hours (3 runs per day)
- ✅ Default recycle bin retention: 7 days
- ✅ Default backup interval: 24 hours
- ✅ Default thumbnail grace period: 7 days
- ✅ Default cache stats retention: 14 days

---

## Support & Resources

### Documentation

- **Architecture**: `docs/maintenance/01-architecture.md`
- **Tasks**: `docs/maintenance/02-*.md` through `05-*.md`
- **Database**: `docs/maintenance/06-database-schema.md`
- **This Roadmap**: `docs/maintenance/07-implementation-roadmap.md`

### Code References

- **Existing Background Services**: 
  - `Fuzzbin.Services/BackgroundJobProcessorService.cs`
  - `Fuzzbin.Services/DownloadBackgroundService.cs`
  - `Fuzzbin.Services/ThumbnailBackgroundService.cs`

- **Similar Implementations**:
  - `Fuzzbin.Services/LibraryImportService.cs` (file scanning)
  - `Fuzzbin.Services/BackupService.cs` (backup creation)
  - `Fuzzbin.Services/RecycleBinService.cs` (file management)

---

## Completion Checklist

Use this to track overall progress:

- [ ] Phase 1: Core Infrastructure (100%)
- [ ] Phase 2: Maintenance Tasks (100%)
- [ ] Phase 3: Service Registration (100%)
- [ ] Phase 4: API Endpoints (100%)
- [ ] Phase 5: UI Integration (100%)
- [ ] Phase 6: Testing (100%)
- [ ] Phase 7: Documentation (100%)
- [ ] Phase 8: Deployment (100%)

**Overall Progress**: 0% (Not Started)

---

## Next Steps

1. **Review this roadmap** with stakeholders
2. **Prioritize phases** based on business value
3. **Allocate resources** (developers, time)
4. **Create sprint/milestone structure** if using Agile
5. **Begin Phase 1** implementation
6. **Set up project tracking** (Jira, GitHub Projects, etc.)
