using System;

namespace Fuzzbin.Core.Entities;

/// <summary>
/// Represents a scored YouTube video candidate for a query
/// </summary>
public class YtVideoCandidate : BaseEntity
{
    public Guid QueryId { get; set; }
    
    /// <summary>
    /// YouTube video ID (FK to YtVideo.VideoId)
    /// </summary>
    public string VideoId { get; set; } = string.Empty;
    
    /// <summary>
    /// Normalized title used for scoring
    /// </summary>
    public string TitleNorm { get; set; } = string.Empty;
    
    /// <summary>
    /// Normalized artist used for scoring
    /// </summary>
    public string ArtistNorm { get; set; } = string.Empty;
    
    /// <summary>
    /// Text similarity score (0.0-1.0)
    /// </summary>
    public double TextScore { get; set; }
    
    /// <summary>
    /// Bonus for official/verified channel (0.0-1.0)
    /// </summary>
    public double? ChannelBonus { get; set; }
    
    /// <summary>
    /// Duration matching score (0.0-1.0)
    /// </summary>
    public double? DurationScore { get; set; }
    
    /// <summary>
    /// Overall weighted score (0.0-1.0)
    /// </summary>
    public double OverallScore { get; set; }
    
    /// <summary>
    /// Ranking within this query (1-based, 1 = best match)
    /// </summary>
    public int Rank { get; set; }
    
    /// <summary>
    /// Whether this candidate was selected as the final match
    /// </summary>
    public bool Selected { get; set; }
    
    // Navigation properties
    public virtual Query Query { get; set; } = null!;
    public virtual YtVideo Video { get; set; } = null!;
}