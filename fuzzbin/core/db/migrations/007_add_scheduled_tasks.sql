-- Add scheduled tasks table
-- Version: 007
-- Description: Create table for persisting scheduled task definitions

-- Scheduled tasks table for cron-based job scheduling
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    job_type TEXT NOT NULL,  -- Maps to JobType enum
    cron_expression TEXT NOT NULL,  -- e.g., "0 2 * * *" for daily at 2 AM
    enabled INTEGER DEFAULT 1 NOT NULL,
    metadata_json TEXT,  -- Optional JSON metadata passed to job handler
    last_run_at TEXT,
    next_run_at TEXT,
    last_status TEXT,  -- Last execution status: success, failed, cancelled
    last_error TEXT,  -- Error message if last run failed
    run_count INTEGER DEFAULT 0 NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (enabled IN (0, 1))
);

-- Indexes for scheduled task management
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_enabled ON scheduled_tasks(enabled);
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_next_run ON scheduled_tasks(next_run_at) WHERE enabled = 1;
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_job_type ON scheduled_tasks(job_type);
