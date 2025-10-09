using System;

namespace Fuzzbin.Core.Entities
{
    public class DownloadQueueItem : BaseEntity
    {
        public string Url { get; set; } = string.Empty;
        public string? Title { get; set; }
        public DownloadStatus Status { get; set; } = DownloadStatus.Queued;
        public int Priority { get; set; } = 5;
        public double Progress { get; set; }
        public string? ErrorMessage { get; set; }
        public int RetryCount { get; set; }
        public Guid? VideoId { get; set; }
        public Video? Video { get; set; }
        public bool IsDeleted { get; set; }
        
        // Additional properties for compatibility
        public DateTime AddedDate { get; set; } = DateTime.UtcNow;
        public DateTime? StartedDate { get; set; }
        public DateTime? CompletedDate { get; set; }
        public DateTime? DeletedDate { get; set; }
        public string? DownloadSpeed { get; set; }
        public string? ETA { get; set; }
        public string? FilePath { get; set; }
        public string? OutputPath { get; set; }
        public string? Format { get; set; }
    }

    public enum DownloadStatus
    {
        Queued,
        Downloading,
        Completed,
        Failed,
        Cancelled
    }
}