using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;

namespace Fuzzbin.Services.Models
{
    public class LibraryImportRequest
    {
        public string? RootPath { get; set; }
        public bool IncludeSubdirectories { get; set; } = true;
        public IReadOnlyCollection<string> AllowedExtensions { get; set; } = DefaultExtensions;
        public bool ComputeHashes { get; set; } = true;
        public bool RefreshMetadata { get; set; } = true;
        public string? StartedByUserId { get; set; }
        private static readonly string[] DefaultExtensions = new[]
        {
            ".mp4",
            ".mkv",
            ".mov",
            ".avi",
            ".webm"
        };
    }

    public class LibraryImportDecision
    {
        public Guid ItemId { get; set; }
        public LibraryImportDecisionType DecisionType { get; set; } = LibraryImportDecisionType.Approve;
        public Guid? ManualVideoId { get; set; }
        public string? Notes { get; set; }
        public static LibraryImportDecision Approve(Guid itemId) => new()
        {
            ItemId = itemId,
            DecisionType = LibraryImportDecisionType.Approve
        };

        public static LibraryImportDecision Reject(Guid itemId, string? notes = null) => new()
        {
            ItemId = itemId,
            DecisionType = LibraryImportDecisionType.Reject,
            Notes = notes
        };
    }

    public enum LibraryImportDecisionType
    {
        Approve = 0,
        Reject = 1,
        NeedsAttention = 2
    }

    public class LibraryImportMatchCandidate
    {
        public Guid? VideoId { get; set; }
        public string DisplayName { get; set; } = string.Empty;
        public double Confidence { get; set; }
        public string? Notes { get; set; }
        public bool IsExistingVideo => VideoId.HasValue;

        public static string SerializeList(IEnumerable<LibraryImportMatchCandidate> candidates)
        {
            return JsonSerializer.Serialize(candidates ?? Array.Empty<LibraryImportMatchCandidate>());
        }

        public static IReadOnlyList<LibraryImportMatchCandidate> DeserializeList(string? json)
        {
            if (string.IsNullOrWhiteSpace(json))
            {
                return Array.Empty<LibraryImportMatchCandidate>();
            }

            try
            {
                var result = JsonSerializer.Deserialize<List<LibraryImportMatchCandidate>>(json);
                return result ?? new List<LibraryImportMatchCandidate>();
            }
            catch
            {
                return Array.Empty<LibraryImportMatchCandidate>();
            }
        }
    }

    public class LibraryImportSummary
    {
        public int TotalFiles { get; set; }
        public int PendingReview { get; set; }
        public int Approved { get; set; }
        public int Rejected { get; set; }
        public int PotentialDuplicates { get; set; }
        public int ConfirmedDuplicates { get; set; }

        public static LibraryImportSummary FromItems(IEnumerable<Core.Entities.LibraryImportItem> items)
        {
            var list = items?.ToList() ?? new List<Core.Entities.LibraryImportItem>();
            return new LibraryImportSummary
            {
                TotalFiles = list.Count,
                PendingReview = list.Count(i => i.Status == Core.Entities.LibraryImportItemStatus.PendingReview),
                Approved = list.Count(i => i.Status == Core.Entities.LibraryImportItemStatus.Approved),
                Rejected = list.Count(i => i.Status == Core.Entities.LibraryImportItemStatus.Rejected),
                PotentialDuplicates = list.Count(i => i.DuplicateStatus == Core.Entities.LibraryImportDuplicateStatus.PotentialDuplicate),
                ConfirmedDuplicates = list.Count(i => i.DuplicateStatus == Core.Entities.LibraryImportDuplicateStatus.ConfirmedDuplicate)
            };
        }
    }

    public class SourceVerificationRequest
    {
        public string? SourceUrl { get; set; }
        public bool RefreshMetadata { get; set; } = true;
        public bool AllowDownloadProbe { get; set; } = false;
        public int DurationToleranceSeconds { get; set; } = 3;
        public double ConfidenceThreshold { get; set; } = 0.9;
        public string? PreferredProvider { get; set; }
        public SourceVerificationRequest Clone() => (SourceVerificationRequest)MemberwiseClone();
    }

    public class SourceVerificationOverride
    {
        public bool MarkAsVerified { get; set; }
        public double? Confidence { get; set; }
        public string? Notes { get; set; }
    }

    public class SourceVerificationComparison
    {
        public double? DurationDeltaSeconds { get; set; }
        public double? FrameRateDelta { get; set; }
        public double? BitrateDelta { get; set; }
        public string? Resolution { get; set; }
        public string? SourceResolution { get; set; }
        public double Confidence { get; set; }
        public double? SourceDurationSeconds { get; set; }
        public double? LocalDurationSeconds { get; set; }
        public double? SourceFrameRate { get; set; }
        public double? LocalFrameRate { get; set; }
    }

    /// <summary>
    /// DTO for storing NFO metadata in JSON format
    /// </summary>
    public class NfoMetadataDto
    {
        public List<string> Genres { get; set; } = new();
        public List<string> Tags { get; set; } = new();
        public string? Director { get; set; }
        public string? Studio { get; set; }
        public string? RecordLabel { get; set; }
        public string? Description { get; set; }
        public string? ImvdbId { get; set; }
        public string? MusicBrainzId { get; set; }
        public List<string> SourceUrls { get; set; } = new();
        public bool HasCompleteMetadata { get; set; }
    }

    /// <summary>
    /// DTO for storing metadata cache search results in JSON format
    /// </summary>
    public class CacheMetadataDto
    {
        public string? Title { get; set; }
        public string? Artist { get; set; }
        public string? FeaturedArtists { get; set; }
        public int? Year { get; set; }
        public List<string> Genres { get; set; } = new();
        public string? RecordLabel { get; set; }
        public string? Director { get; set; }
        public double Confidence { get; set; }
        public string PrimarySource { get; set; } = string.Empty;
        public bool RequiresManualSelection { get; set; }
        public List<CacheMetadataCandidateDto> AlternativeCandidates { get; set; } = new();
        
        // IDs for applying metadata
        public Guid? QueryId { get; set; }
        public Guid? ImvdbVideoId { get; set; }
        public Guid? MbRecordingId { get; set; }
        public string? YtVideoId { get; set; }
        public Guid? MvLinkId { get; set; }
    }

    /// <summary>
    /// DTO for storing alternative metadata candidates
    /// </summary>
    public class CacheMetadataCandidateDto
    {
        public string Title { get; set; } = string.Empty;
        public string Artist { get; set; } = string.Empty;
        public string? FeaturedArtists { get; set; }
        public int? Year { get; set; }
        public double Confidence { get; set; }
        public string PrimarySource { get; set; } = string.Empty;
    }
}
