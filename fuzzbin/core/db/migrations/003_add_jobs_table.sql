-- Jobs table migration
-- Version: 003
-- Description: Add persistent job queue with job groups view for related video operations.
--              Supports job history retention, cancellation, and video-based grouping.

--------------------------------------------------------------------------------
-- JOBS TABLE
--------------------------------------------------------------------------------

-- Jobs table (persistent job queue)
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,  -- UUID from Job model
    type TEXT NOT NULL,  -- JobType enum value
    status TEXT NOT NULL DEFAULT 'pending',  -- JobStatus enum value
    priority INTEGER NOT NULL DEFAULT 5,  -- JobPriority enum value (0=LOW, 5=NORMAL, 10=HIGH, 20=CRITICAL)
    progress REAL NOT NULL DEFAULT 0.0,  -- 0.0 to 1.0
    current_step TEXT DEFAULT 'Initializing...',
    total_items INTEGER NOT NULL DEFAULT 0,
    processed_items INTEGER NOT NULL DEFAULT 0,
    result_json TEXT,  -- JSON-serialized result on completion
    error TEXT,  -- Error message on failure
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    metadata_json TEXT,  -- JSON-serialized job parameters
    timeout_seconds INTEGER,  -- Maximum execution time (NULL = no timeout)
    depends_on_json TEXT,  -- JSON array of job IDs that must complete first
    parent_job_id TEXT,  -- FK to parent job for child workflows
    schedule TEXT,  -- Cron expression for scheduled jobs
    next_run_at TEXT,  -- Next scheduled run time
    -- Video relationship for grouping (NULL for maintenance jobs)
    video_id INTEGER,
    FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE SET NULL,
    FOREIGN KEY (parent_job_id) REFERENCES jobs(id) ON DELETE SET NULL,
    CHECK (status IN ('pending', 'waiting', 'running', 'completed', 'failed', 'cancelled', 'timeout')),
    CHECK (priority IN (0, 5, 10, 20)),
    CHECK (progress >= 0.0 AND progress <= 1.0)
);

--------------------------------------------------------------------------------
-- INDEXES FOR JOBS
--------------------------------------------------------------------------------

-- Index for fetching pending/running jobs on startup
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);

-- Index for filtering by job type
CREATE INDEX IF NOT EXISTS idx_jobs_type ON jobs(type);

-- Composite index for active jobs query (pending/waiting/running by priority)
CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(status, priority DESC, created_at ASC)
    WHERE status IN ('pending', 'waiting', 'running');

-- Index for job retention cleanup (completed_at for old job purge)
CREATE INDEX IF NOT EXISTS idx_jobs_completed_at ON jobs(completed_at)
    WHERE completed_at IS NOT NULL;

-- Index for grouping jobs by video_id
CREATE INDEX IF NOT EXISTS idx_jobs_video_id ON jobs(video_id)
    WHERE video_id IS NOT NULL;

-- Index for finding child jobs of a parent
CREATE INDEX IF NOT EXISTS idx_jobs_parent_job_id ON jobs(parent_job_id)
    WHERE parent_job_id IS NOT NULL;

-- Index for scheduled jobs
CREATE INDEX IF NOT EXISTS idx_jobs_next_run_at ON jobs(next_run_at)
    WHERE schedule IS NOT NULL AND next_run_at IS NOT NULL;

--------------------------------------------------------------------------------
-- JOB GROUPS VIEW
--------------------------------------------------------------------------------

-- View for grouping active jobs by video_id with aggregated status
-- Returns one row per video with active jobs, showing overall progress
CREATE VIEW IF NOT EXISTS job_groups AS
SELECT
    video_id,
    COUNT(*) as job_count,
    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_count,
    SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running_count,
    SUM(CASE WHEN status IN ('pending', 'waiting') THEN 1 ELSE 0 END) as pending_count,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count,
    MIN(created_at) as first_created_at,
    MAX(CASE WHEN status = 'running' THEN started_at END) as current_started_at,
    -- Overall progress: average of all jobs in group
    AVG(progress) as overall_progress,
    -- Group status: running if any running, pending if any pending, else completed/failed
    CASE
        WHEN SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) > 0 THEN 'running'
        WHEN SUM(CASE WHEN status IN ('pending', 'waiting') THEN 1 ELSE 0 END) > 0 THEN 'pending'
        WHEN SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) > 0 THEN 'failed'
        ELSE 'completed'
    END as group_status,
    -- Collect job types as comma-separated list
    GROUP_CONCAT(DISTINCT type) as job_types
FROM jobs
WHERE video_id IS NOT NULL
  AND status NOT IN ('cancelled', 'timeout')
GROUP BY video_id;

--------------------------------------------------------------------------------
-- MAINTENANCE JOBS VIEW
--------------------------------------------------------------------------------

-- View for jobs without video_id (backup, trash_cleanup, etc.)
CREATE VIEW IF NOT EXISTS maintenance_jobs AS
SELECT *
FROM jobs
WHERE video_id IS NULL
ORDER BY
    CASE status
        WHEN 'running' THEN 1
        WHEN 'pending' THEN 2
        WHEN 'waiting' THEN 3
        ELSE 4
    END,
    created_at DESC;
