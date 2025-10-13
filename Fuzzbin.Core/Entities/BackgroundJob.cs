using System;

namespace Fuzzbin.Core.Entities
{
    /// <summary>
    /// Represents a long-running background job
    /// </summary>
    public class BackgroundJob : BaseEntity
    {
        /// <summary>
        /// Job type identifier
        /// </summary>
        public BackgroundJobType Type { get; set; }

        /// <summary>
        /// Current status of the job
        /// </summary>
        public BackgroundJobStatus Status { get; set; } = BackgroundJobStatus.Pending;

        /// <summary>
        /// Progress percentage (0-100)
        /// </summary>
        public int Progress { get; set; }

        /// <summary>
        /// Current status message
        /// </summary>
        public string? StatusMessage { get; set; }

        /// <summary>
        /// Total items to process
        /// </summary>
        public int TotalItems { get; set; }

        /// <summary>
        /// Items processed so far
        /// </summary>
        public int ProcessedItems { get; set; }

        /// <summary>
        /// Items that failed processing
        /// </summary>
        public int FailedItems { get; set; }

        /// <summary>
        /// When the job started
        /// </summary>
        public DateTime? StartedAt { get; set; }

        /// <summary>
        /// When the job completed (success or failure)
        /// </summary>
        public DateTime? CompletedAt { get; set; }

        /// <summary>
        /// Error message if job failed
        /// </summary>
        public string? ErrorMessage { get; set; }

        /// <summary>
        /// Whether the job can be cancelled
        /// </summary>
        public bool CanCancel { get; set; } = true;

        /// <summary>
        /// Cancellation requested flag
        /// </summary>
        public bool CancellationRequested { get; set; }

        /// <summary>
        /// JSON-serialized job parameters
        /// </summary>
        public string? ParametersJson { get; set; }

        /// <summary>
        /// JSON-serialized job result
        /// </summary>
        public string? ResultJson { get; set; }
    }

    public enum BackgroundJobType
    {
        RefreshMetadata = 1,
        OrganizeFiles = 2,
        GenerateThumbnails = 3,
        VerifySourceUrls = 4,
        ExportNfo = 5,
        DeleteVideos = 6
    }

    public enum BackgroundJobStatus
    {
        Pending = 0,
        Running = 1,
        Completed = 2,
        Failed = 3,
        Cancelled = 4
    }
}