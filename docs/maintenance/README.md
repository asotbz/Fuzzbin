# Maintenance System Documentation

## Overview

This directory contains comprehensive documentation for Fuzzbin's modular maintenance system. The maintenance system automatically performs periodic housekeeping tasks to maintain database health, storage efficiency, and system performance.

---

## Key Features

- **Modular Architecture**: Each maintenance task is independent and can be enabled/disabled
- **Extensible**: New tasks can be added without modifying the scheduler
- **Configurable**: Per-task and global configuration via database
- **Observable**: Built-in logging, execution history, and statistics
- **Resilient**: Task failures don't affect other tasks; automatic retry on next run

---

## Maintenance Tasks

The system includes six built-in maintenance tasks:

1. **Library Scan**: Discovers new video files and marks missing ones
2. **Thumbnail Cleanup**: Removes orphaned thumbnail files
3. **Cache Purge**: Expires and removes old metadata cache entries
4. **Cache Statistics**: Collects performance metrics for historical analysis
5. **Recycle Bin Purge**: Permanently deletes old recycle bin files
6. **Auto Backup**: Creates automated database backups with rotation

**Default Schedule**: Every 8 hours (configurable)

---

## Documentation Structure

### Core Architecture

**[01-architecture.md](./01-architecture.md)**
- System design and patterns
- Core interfaces (`IMaintenanceTask`, `MaintenanceTaskResult`)
- Scheduler service implementation
- Configuration system
- Extensibility patterns
- Manual trigger API
- Testing and monitoring

**Read this first** to understand the overall system design.

---

### Task Specifications

Each task has its own detailed specification document:

**[02-library-scan-task.md](./02-library-scan-task.md)**
- File discovery and import
- Missing file detection and restoration
- Configuration options
- UI integration
- Performance considerations

**[03-thumbnail-cleanup-task.md](./03-thumbnail-cleanup-task.md)**
- Orphaned thumbnail detection
- Grace period handling
- Disk space reclamation
- Integration with ThumbnailService

**[04-cache-tasks.md](./04-cache-tasks.md)**
- Cache entry expiration and purging
- Statistics collection and historical analysis
- Orphaned entity cleanup
- Performance monitoring

**[05-recycle-bin-and-backup-tasks.md](./05-recycle-bin-and-backup-tasks.md)**
- Recycle bin retention and purging
- Automated backup creation
- Backup rotation
- Integration with existing services

---

### Database & Implementation

**[06-database-schema.md](./06-database-schema.md)**
- New entities: `MaintenanceExecution`, `CacheStatSnapshot`
- Modified entities: `Video` (missing file tracking)
- Migration instructions
- IUnitOfWork updates
- Configuration seed data

**[07-implementation-roadmap.md](./07-implementation-roadmap.md)**
- 8-phase implementation plan
- Task dependencies and ordering
- Testing strategy
- Risk mitigation
- Success criteria
- MVP quick start guide

---

## Quick Start

### For Developers

1. **Read Architecture**: Start with [01-architecture.md](./01-architecture.md)
2. **Review Database Changes**: See [06-database-schema.md](./06-database-schema.md)
3. **Follow Roadmap**: Implement using [07-implementation-roadmap.md](./07-implementation-roadmap.md)
4. **Add Your Task**: Use extensibility pattern in architecture doc

### For Users

1. **Configuration**: Navigate to Settings > Maintenance
2. **Enable/Disable Tasks**: Toggle individual tasks as needed
3. **Adjust Intervals**: Configure how often maintenance runs
4. **Manual Trigger**: Run maintenance immediately from Settings
5. **View History**: Check execution logs for task results

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│           MaintenanceSchedulerService               │
│         (BackgroundService, runs every 8h)          │
└──────────────────┬──────────────────────────────────┘
                   │
                   │ Discovers all IMaintenanceTask
                   │ implementations via DI
                   │
        ┌──────────┴──────────┐
        │  Task Execution     │
        │  (Sequential)       │
        └──────────┬──────────┘
                   │
      ┌────────────┼────────────┐
      │            │            │
      ▼            ▼            ▼
┌─────────┐  ┌─────────┐  ┌─────────┐
│Library  │  │Thumbnail│  │Cache    │
│Scan     │  │Cleanup  │  │Purge    │
└─────────┘  └─────────┘  └─────────┘
      │            │            │
      ▼            ▼            ▼
┌─────────┐  ┌─────────┐  ┌─────────┐
│Cache    │  │Recycle  │  │Auto     │
│Stats    │  │Bin Purge│  │Backup   │
└─────────┘  └─────────┘  └─────────┘
      │
      │ All tasks record results
      │
      ▼
┌────────────────────────┐
│ MaintenanceExecutions  │
│ (Database Table)       │
└────────────────────────┘
```

---

## Configuration Reference

### Global Settings

```csharp
Category: "Maintenance"
Key: "IntervalHours"
Value: "8"  // Run every 8 hours
```

### Task-Specific Settings

Each task has its own configuration keys. See individual task documentation for details.

**Example**:
```csharp
// Library Scan
"LibraryScan.Enabled" = "true"
"LibraryScan.Recursive" = "true"
"LibraryScan.EnrichOnline" = "false"

// Auto Backup
"AutoBackup.Enabled" = "true"
"AutoBackup.IntervalHours" = "24"
"AutoBackup.MaxBackups" = "7"
```

---

## API Endpoints

### Manual Trigger

```http
POST /api/maintenance/run
Authorization: Bearer <token>

Response: 200 OK
{
  "message": "Maintenance run completed",
  "startedAt": "2025-11-03T14:30:00Z",
  "completedAt": "2025-11-03T14:32:15Z",
  "results": [...]
}
```

### Execution History

```http
GET /api/maintenance/history?limit=50
Authorization: Bearer <token>

Response: 200 OK
[
  {
    "id": "...",
    "taskName": "LibraryScan",
    "startedAt": "2025-11-03T14:30:00Z",
    "success": true,
    "summary": "Scanned 1,245 files...",
    ...
  }
]
```

### Cache Statistics

```http
GET /api/cache/stats/history?days=7
Authorization: Bearer <token>

Response: 200 OK
[
  {
    "snapshotAt": "2025-11-03T14:00:00Z",
    "totalQueries": 1532,
    "hitRatePercent": 87.3,
    ...
  }
]
```

---

## Testing

### Unit Tests

Located in: `Fuzzbin.Tests/Services/Maintenance/`

```bash
dotnet test --filter "FullyQualifiedName~Maintenance"
```

### Integration Tests

Located in: `Fuzzbin.Tests/Integration/MaintenanceTests.cs`

```bash
dotnet test --filter "Category=Integration&FullyQualifiedName~Maintenance"
```

---

## Monitoring

### Logs

All maintenance operations are logged with structured logging:

```log
[14:30:00 INF] Starting maintenance run with 6 registered tasks
[14:30:05 INF] Executing maintenance task: LibraryScan - Scan library for new and missing videos
[14:31:12 INF] Maintenance task completed: LibraryScan - Scanned 1,245 files: 12 imported, 3 marked missing, 0 errors (Duration: 00:01:07)
...
[14:32:15 INF] Maintenance run completed: 6 succeeded, 0 failed (Total Duration: 00:02:15)
```

### Metrics

Query execution history for analysis:

```sql
-- Success rate by task
SELECT TaskName, 
       COUNT(*) as TotalRuns,
       SUM(CASE WHEN Success THEN 1 ELSE 0 END) as SuccessCount,
       ROUND(AVG(DurationMs), 0) as AvgDurationMs
FROM MaintenanceExecutions
WHERE StartedAt >= datetime('now', '-30 days')
GROUP BY TaskName;

-- Recent failures
SELECT TaskName, StartedAt, ErrorMessage
FROM MaintenanceExecutions
WHERE Success = 0
ORDER BY StartedAt DESC
LIMIT 10;
```

---

## Troubleshooting

### Common Issues

**Issue**: Maintenance never runs  
**Solution**: Check that `MaintenanceSchedulerService` is registered as hosted service in `Program.cs`

**Issue**: Specific task always fails  
**Solution**: Check task `IsEnabled` property and configuration, review logs for error details

**Issue**: Library scan takes too long  
**Solution**: Reduce scan frequency, disable online enrichment, or implement batch processing

**Issue**: Database growing too large  
**Solution**: Reduce retention periods for stats and execution history, implement automatic purging

### Debug Mode

Enable verbose logging:

```json
{
  "Logging": {
    "LogLevel": {
      "Fuzzbin.Services.Maintenance": "Debug",
      "Fuzzbin.Services.MaintenanceSchedulerService": "Debug"
    }
  }
}
```

---

## Performance Impact

### Expected Overhead

- **CPU**: < 5% during maintenance runs (typically 2-5 minutes)
- **Memory**: < 50 MB additional during execution
- **Disk I/O**: Moderate during library scan and backup
- **Database**: < 1 MB/month for execution history and stats

### Optimization

- Run during off-peak hours (configure interval accordingly)
- Disable expensive tasks (online metadata enrichment)
- Implement batch processing for large datasets
- Monitor and adjust intervals based on actual performance

---

## Security Considerations

- All API endpoints require authentication
- File operations respect system permissions
- Database backups encrypted (if configured)
- Execution history may contain sensitive paths (sanitize if needed)
- Manual triggers logged for audit trail

---

## Future Enhancements

Potential additions to the maintenance system:

- **Email notifications** for failures or summaries
- **Webhook integration** for external monitoring
- **Scheduled maintenance windows** (specific times, not just intervals)
- **Parallel task execution** for independent tasks
- **Cloud backup integration** (S3, Azure Blob, GCS)
- **Machine learning** for optimal cache TTL prediction
- **Predictive maintenance** (disk space warnings, etc.)
- **Custom task plugin system** for third-party tasks

---

## Contributing

To add a new maintenance task:

1. Read the extensibility section in [01-architecture.md](./01-architecture.md)
2. Implement `IMaintenanceTask` interface
3. Register task in `Program.cs`
4. Add configuration entries
5. Write tests
6. Update documentation

---

## Support

For questions or issues:

1. Check troubleshooting section above
2. Review logs in `MaintenanceExecutions` table
3. Consult individual task documentation
4. Review implementation roadmap for known limitations

---

## License

This documentation is part of the Fuzzbin project.

---

## Changelog

### v1.0.0 (Planned)

- Initial implementation of maintenance system
- All six core tasks
- Configuration UI
- API endpoints
- Execution history tracking
- Cache statistics collection

---

## Related Documentation

- **Cache System**: `docs/cache/cache-integration-strategy.md`
- **Library Import**: Existing `LibraryImportService` documentation
- **Backup System**: Existing `BackupService` documentation
- **Architecture**: Main project architecture documentation
