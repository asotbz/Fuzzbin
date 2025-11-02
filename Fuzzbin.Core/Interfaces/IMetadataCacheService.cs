using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Interfaces;

/// <summary>
/// Unified metadata cache service that coordinates searches across MusicBrainz, IMVDb, and YouTube
/// with intelligent caching, candidate ranking, and aggregation
/// </summary>
public interface IMetadataCacheService
{
    /// <summary>
    /// Searches for metadata across all sources with intelligent caching and candidate ranking
    /// </summary>
    /// <param name="artist">Artist name</param>
    /// <param name="title">Song/video title</param>
    /// <param name="knownDurationSeconds">Optional known duration for scoring</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Search result with best match and alternatives</returns>
    Task<MetadataCacheResult> SearchAsync(
        string artist,
        string title,
        int? knownDurationSeconds = null,
        CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Gets aggregated candidate results for manual selection
    /// </summary>
    /// <param name="artist">Artist name</param>
    /// <param name="title">Song/video title</param>
    /// <param name="maxResults">Maximum number of candidates to return</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>List of ranked candidates</returns>
    Task<List<AggregatedCandidate>> GetCandidatesAsync(
        string artist,
        string title,
        int maxResults = 10,
        CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Applies selected candidate metadata to a video entity
    /// </summary>
    /// <param name="video">Video entity to update</param>
    /// <param name="candidate">Selected candidate with metadata</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Updated video entity</returns>
    Task<Video> ApplyMetadataAsync(
        Video video,
        AggregatedCandidate candidate,
        CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Checks if query has cached results (without triggering new searches)
    /// </summary>
    /// <param name="artist">Artist name</param>
    /// <param name="title">Song/video title</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>True if results are cached and valid</returns>
    Task<bool> IsCachedAsync(
        string artist,
        string title,
        CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Clears all cached metadata (useful for settings changes)
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    Task ClearCacheAsync(CancellationToken cancellationToken = default);
}

/// <summary>
/// Result of a metadata cache search operation
/// </summary>
public class MetadataCacheResult
{
    /// <summary>
    /// Whether any metadata was found
    /// </summary>
    public bool Found { get; set; }
    
    /// <summary>
    /// Best matching candidate based on scoring
    /// </summary>
    public AggregatedCandidate? BestMatch { get; set; }
    
    /// <summary>
    /// Alternative candidates for manual selection
    /// </summary>
    public List<AggregatedCandidate> AlternativeCandidates { get; set; } = new();
    
    /// <summary>
    /// Whether manual selection is recommended (confidence < 0.9)
    /// </summary>
    public bool RequiresManualSelection { get; set; }
    
    /// <summary>
    /// Notes from each source about the search results
    /// </summary>
    public Dictionary<string, string> SourceNotes { get; set; } = new();
}

/// <summary>
/// Aggregated candidate from multiple metadata sources
/// </summary>
public class AggregatedCandidate
{
    /// <summary>
    /// Song/video title
    /// </summary>
    public string Title { get; set; } = string.Empty;
    
    /// <summary>
    /// Primary artist name
    /// </summary>
    public string Artist { get; set; } = string.Empty;
    
    /// <summary>
    /// Featured artists (comma-separated)
    /// </summary>
    public string? FeaturedArtists { get; set; }
    
    /// <summary>
    /// Release year
    /// </summary>
    public int? Year { get; set; }
    
    /// <summary>
    /// Genre tags
    /// </summary>
    public List<string> Genres { get; set; } = new();
    
    /// <summary>
    /// Record label name
    /// </summary>
    public string? RecordLabel { get; set; }
    
    /// <summary>
    /// Video director name
    /// </summary>
    public string? Director { get; set; }
    
    /// <summary>
    /// Overall confidence score (0.0-1.0)
    /// </summary>
    public double OverallConfidence { get; set; }
    
    /// <summary>
    /// Primary metadata source ('imvdb', 'musicbrainz', 'youtube')
    /// </summary>
    public string PrimarySource { get; set; } = string.Empty;
    
    // Source-specific IDs for applying metadata
    
    /// <summary>
    /// Query entity ID
    /// </summary>
    public Guid? QueryId { get; set; }
    
    /// <summary>
    /// IMVDb video entity ID
    /// </summary>
    public Guid? ImvdbVideoId { get; set; }
    
    /// <summary>
    /// MusicBrainz recording entity ID
    /// </summary>
    public Guid? MbRecordingId { get; set; }
    
    /// <summary>
    /// YouTube video ID
    /// </summary>
    public string? YtVideoId { get; set; }
    
    /// <summary>
    /// MvLink entity ID for cross-linked metadata
    /// </summary>
    public Guid? MvLinkId { get; set; }
}