using System;
using System.Collections.Generic;

namespace Fuzzbin.Core.Entities
{
    /// <summary>
    /// Represents a library import session and its scanned items.
    /// </summary>
    public class LibraryImportSession : BaseEntity
    {
        public LibraryImportSession()
        {
            Items = new List<LibraryImportItem>();
            StartedAt = DateTime.UtcNow;
            Status = LibraryImportStatus.Pending;
        }

        /// <summary>
        /// Absolute root path that was scanned.
        /// </summary>
        public string RootPath { get; set; } = string.Empty;

        /// <summary>
        /// Optional identifier of the user who initiated the import.
        /// </summary>
        public string? StartedByUserId { get; set; }

        /// <summary>
        /// Timestamp for when scanning started.
        /// </summary>
        public DateTime StartedAt { get; set; }

        /// <summary>
        /// Timestamp for when the session completed (imported or rolled back).
        /// </summary>
        public DateTime? CompletedAt { get; set; }

        /// <summary>
        /// Current state of the session workflow.
        /// </summary>
        public LibraryImportStatus Status { get; set; }

        /// <summary>
        /// Collection of scanned items that belong to this session.
        /// </summary>
        public virtual ICollection<LibraryImportItem> Items { get; set; }

        /// <summary>
        /// Serialized record of the video identifiers created when this session was committed.
        /// Used to support rollback operations.
        /// </summary>
        public string? CreatedVideoIdsJson { get; set; }

        /// <summary>
        /// Optional notes recorded during the import flow.
        /// </summary>
        public string? Notes { get; set; }

        /// <summary>
        /// Any error message captured during processing.
        /// </summary>
        public string? ErrorMessage { get; set; }

        /// <summary>
        /// Convenience helper to mark completion metadata.
        /// </summary>
        public void MarkCompleted(LibraryImportStatus status)
        {
            Status = status;
            CompletedAt = DateTime.UtcNow;
        }
    }
}
