using System;
using System.Collections.Generic;

namespace Fuzzbin.Core.Entities
{
    /// <summary>
    /// Represents a file discovered during a library import scan.
    /// </summary>
    public class LibraryImportItem : BaseEntity
    {
        /// <summary>
        /// Foreign key to the owning session.
        /// </summary>
        public Guid SessionId { get; set; }

        /// <summary>
        /// Navigation property to the owning session.
        /// </summary>
        public virtual LibraryImportSession Session { get; set; } = null!;

        /// <summary>
        /// Absolute file path on disk.
        /// </summary>
        public string FilePath { get; set; } = string.Empty;

        /// <summary>
        /// Path relative to the session root.
        /// </summary>
        public string? RelativePath { get; set; }

        /// <summary>
        /// File name extracted from the path for quick display.
        /// </summary>
        public string FileName { get; set; } = string.Empty;

        /// <summary>
        /// File extension (including the leading dot).
        /// </summary>
        public string? Extension { get; set; }

        /// <summary>
        /// Hash of the file contents, used for duplicate detection.
        /// </summary>
        public string? FileHash { get; set; }

        /// <summary>
        /// File size in bytes.
        /// </summary>
        public long FileSize { get; set; }

        /// <summary>
        /// Extracted or inferred duration of the video.
        /// </summary>
        public double? DurationSeconds { get; set; }

        /// <summary>
        /// Extracted or inferred resolution like 1920x1080.
        /// </summary>
        public string? Resolution { get; set; }

        /// <summary>
        /// Detected primary video codec (e.g., h264).
        /// </summary>
        public string? VideoCodec { get; set; }

        /// <summary>
        /// Detected primary audio codec (e.g., aac).
        /// </summary>
        public string? AudioCodec { get; set; }

        /// <summary>
        /// Aggregate bitrate in kbps if available.
        /// </summary>
        public int? BitrateKbps { get; set; }

        /// <summary>
        /// Average frame rate in frames per second.
        /// </summary>
        public double? FrameRate { get; set; }

        /// <summary>
        /// Suggested title parsed from metadata or filename.
        /// </summary>
        public string? Title { get; set; }

        /// <summary>
        /// Suggested artist parsed from metadata or filename.
        /// </summary>
        public string? Artist { get; set; }

        /// <summary>
        /// Suggested album/collection metadata.
        /// </summary>
        public string? Album { get; set; }

        /// <summary>
        /// Inferred release year.
        /// </summary>
        public int? Year { get; set; }

        /// <summary>
        /// Current review status for the item.
        /// </summary>
        public LibraryImportItemStatus Status { get; set; } = LibraryImportItemStatus.PendingReview;

        /// <summary>
        /// Duplicate classification for this item.
        /// </summary>
        public LibraryImportDuplicateStatus DuplicateStatus { get; set; } = LibraryImportDuplicateStatus.None;

        /// <summary>
        /// Identifier of an existing video flagged as a duplicate.
        /// </summary>
        public Guid? DuplicateVideoId { get; set; }

        /// <summary>
        /// Identifier of a suggested video match (highest confidence).
        /// </summary>
        public Guid? SuggestedVideoId { get; set; }

        /// <summary>
        /// Identifier chosen manually by the reviewer to override automated suggestions.
        /// </summary>
        public Guid? ManualVideoId { get; set; }

        /// <summary>
        /// Confidence score between 0 and 1 for the suggested match.
        /// </summary>
        public double? Confidence { get; set; }

        /// <summary>
        /// Raw match candidate data stored as JSON for UI review.
        /// </summary>
        public string? CandidateMatchesJson { get; set; }

        /// <summary>
        /// Human readable note captured during review.
        /// </summary>
        public string? Notes { get; set; }

        /// <summary>
        /// Indicates whether this item has been committed to the library.
        /// </summary>
        public bool IsCommitted { get; set; }

        /// <summary>
        /// Timestamp for when the item review was last updated.
        /// </summary>
        public DateTime? ReviewedAt { get; set; }
    }

    /// <summary>
    /// Workflow states for the overall import session.
    /// </summary>
    public enum LibraryImportStatus
    {
        Pending = 0,
        Scanning = 1,
        ReadyForReview = 2,
        Committing = 3,
        Completed = 4,
        RolledBack = 5,
        Failed = 6
    }

    /// <summary>
    /// Review status of a single import item.
    /// </summary>
    public enum LibraryImportItemStatus
    {
        PendingReview = 0,
        Approved = 1,
        Rejected = 2,
        NeedsAttention = 3
    }

    /// <summary>
    /// Duplicate detection classification for an import item.
    /// </summary>
    public enum LibraryImportDuplicateStatus
    {
        None = 0,
        PotentialDuplicate = 1,
        ConfirmedDuplicate = 2
    }
}
