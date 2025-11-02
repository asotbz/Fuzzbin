using System;

namespace Fuzzbin.Core.Entities;

/// <summary>
/// Represents a scored IMVDb video candidate for a query
/// </summary>
public class ImvdbVideoCandidate : BaseEntity
{
    public Guid QueryId { get; set; }
    public Guid VideoId { get; set; }
    
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
    /// Bonus for having official sources (0.0-1.0)
    /// </summary>
    public double SourceBonus { get; set; }
    
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
    public virtual ImvdbVideo Video { get; set; } = null!;
}