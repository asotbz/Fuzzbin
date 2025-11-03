using System;

namespace Fuzzbin.Core.Entities
{
    /// <summary>
    /// Represents a file that has been moved to the recycle bin instead of being permanently deleted
    /// </summary>
    public class RecycleBin : BaseEntity
    {
        /// <summary>
        /// The original file path before deletion
        /// </summary>
        public string OriginalFilePath { get; set; } = string.Empty;
        
        /// <summary>
        /// The current location of the file in the recycle bin
        /// </summary>
        public string RecycleBinPath { get; set; } = string.Empty;
        
        /// <summary>
        /// The original file size in bytes
        /// </summary>
        public long? FileSize { get; set; }
        
        /// <summary>
        /// When the file was deleted (moved to recycle bin)
        /// </summary>
        public DateTime DeletedAt { get; set; } = DateTime.UtcNow;
        
        /// <summary>
        /// When the file should be automatically purged from the recycle bin (optional)
        /// </summary>
        public DateTime? ExpiresAt { get; set; }
        
        /// <summary>
        /// The ID of the download queue item that owned this file
        /// </summary>
        public Guid? DownloadQueueItemId { get; set; }
        
        /// <summary>
        /// Navigation property to the download queue item
        /// </summary>
        public DownloadQueueItem? DownloadQueueItem { get; set; }
        
        /// <summary>
        /// The ID of the video that owned this file (if applicable)
        /// </summary>
        public Guid? VideoId { get; set; }
        
        /// <summary>
        /// Navigation property to the video
        /// </summary>
        public Video? Video { get; set; }
        
        /// <summary>
        /// The reason for deletion
        /// </summary>
        public string? DeletionReason { get; set; }
        
        /// <summary>
        /// Whether the file can be restored
        /// </summary>
        public bool CanRestore { get; set; } = true;
        
        /// <summary>
        /// Notes about the deletion
        /// </summary>
        public string? Notes { get; set; }
    }
}