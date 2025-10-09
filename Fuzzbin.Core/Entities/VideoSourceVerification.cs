using System;

namespace Fuzzbin.Core.Entities
{
    /// <summary>
    /// Represents a verification record comparing a local video with its source.
    /// </summary>
    public class VideoSourceVerification : BaseEntity
    {
        /// <summary>
        /// Video that was verified.
        /// </summary>
        public Guid VideoId { get; set; }

        /// <summary>
        /// Navigation reference to the associated video.
        /// </summary>
        public virtual Video Video { get; set; } = null!;

        /// <summary>
        /// Source URL used for verification (e.g., YouTube watch URL).
        /// </summary>
        public string? SourceUrl { get; set; }

        /// <summary>
        /// Identifier for the provider that supplied the source data (e.g., youtube, vimeo).
        /// </summary>
        public string? SourceProvider { get; set; }

        /// <summary>
        /// Verification outcome.
        /// </summary>
        public VideoSourceVerificationStatus Status { get; set; } = VideoSourceVerificationStatus.Pending;

        /// <summary>
        /// Confidence score between 0 and 1 representing match quality.
        /// </summary>
        public double Confidence { get; set; }

        /// <summary>
        /// Optional JSON payload containing the comparison snapshot.
        /// </summary>
        public string? ComparisonSnapshotJson { get; set; }

        /// <summary>
        /// Flag set when the user manually overrides the verification result.
        /// </summary>
        public bool IsManualOverride { get; set; }

        /// <summary>
        /// Free-form notes captured during verification.
        /// </summary>
        public string? Notes { get; set; }

        /// <summary>
        /// When the verification task completed.
        /// </summary>
        public DateTime? VerifiedAt { get; set; }
    }

    public enum VideoSourceVerificationStatus
    {
        Pending = 0,
        Verified = 1,
        Mismatch = 2,
        SourceMissing = 3,
        Failed = 4
    }
}
