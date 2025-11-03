using System;

namespace Fuzzbin.Core.Entities;

/// <summary>
/// Snapshot of cache statistics at a point in time
/// </summary>
public class CacheStatSnapshot : BaseEntity
{
    /// <summary>
    /// When this snapshot was taken
    /// </summary>
    public DateTime SnapshotAt { get; set; }
    
    /// <summary>
    /// Total queries in cache
    /// </summary>
    public int TotalQueries { get; set; }
    
    /// <summary>
    /// MusicBrainz source cache entries
    /// </summary>
    public int MbSourceCaches { get; set; }
    
    /// <summary>
    /// IMVDb source cache entries
    /// </summary>
    public int ImvdbSourceCaches { get; set; }
    
    /// <summary>
    /// YouTube source cache entries
    /// </summary>
    public int YtSourceCaches { get; set; }
    
    /// <summary>
    /// Total query resolutions
    /// </summary>
    public int TotalResolutions { get; set; }
    
    /// <summary>
    /// MusicBrainz candidates
    /// </summary>
    public int MbCandidates { get; set; }
    
    /// <summary>
    /// IMVDb candidates
    /// </summary>
    public int ImvdbCandidates { get; set; }
    
    /// <summary>
    /// YouTube candidates
    /// </summary>
    public int YtCandidates { get; set; }
    
    /// <summary>
    /// Cache hit rate percentage
    /// </summary>
    public double HitRatePercent { get; set; }
    
    /// <summary>
    /// Average candidates per query
    /// </summary>
    public double AvgCandidatesPerQuery { get; set; }
}
