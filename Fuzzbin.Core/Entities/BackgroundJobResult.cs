using System;

namespace Fuzzbin.Core.Entities
{
    /// <summary>
    /// Standard structured result payload for a background job, serialized into BackgroundJob.ResultJson.
    /// Provides uniform shape for UI / API consumption (counts, timing, status).
    /// </summary>
    public class BackgroundJobResult
    {
        /// <summary>Job identifier</summary>
        public Guid JobId { get; set; }

        /// <summary>Job type</summary>
        public BackgroundJobType Type { get; set; }

        /// <summary>Total items intended to process (may be 0 if not itemized).</summary>
        public int TotalItems { get; set; }

        /// <summary>Items actually processed (attempted).</summary>
        public int ProcessedItems { get; set; }

        /// <summary>Items that failed processing.</summary>
        public int FailedItems { get; set; }

        /// <summary>Items succeeded (Processed - Failed, floored at 0).</summary>
        public int SucceededItems => Math.Max(0, ProcessedItems - FailedItems);

        /// <summary>Optional human readable summary (executor supplied).</summary>
        public string? Summary { get; set; }

        /// <summary>UTC start time (fallback to CreatedAt if executor did not set).</summary>
        public DateTime StartedAt { get; set; }

        /// <summary>UTC completion time.</summary>
        public DateTime CompletedAt { get; set; }

        /// <summary>Duration in seconds (double for sub-second precision).</summary>
        public double DurationSeconds => (CompletedAt - StartedAt).TotalSeconds;

        /// <summary>Top-level error message (for Failed) or null.</summary>
        public string? ErrorMessage { get; set; }

        /// <summary>True if job ended in Cancelled state.</summary>
        public bool Cancelled { get; set; }

        /// <summary>
        /// Helper factory for terminal job states.
        /// </summary>
        public static BackgroundJobResult Create(BackgroundJob job, string? summary = null)
        {
            return new BackgroundJobResult
            {
                JobId = job.Id,
                Type = job.Type,
                TotalItems = job.TotalItems,
                ProcessedItems = job.ProcessedItems,
                FailedItems = job.FailedItems,
                Summary = summary,
                StartedAt = job.StartedAt ?? job.CreatedAt,
                CompletedAt = job.CompletedAt ?? DateTime.UtcNow,
                ErrorMessage = job.ErrorMessage,
                Cancelled = job.Status == BackgroundJobStatus.Cancelled
            };
        }
    }
}