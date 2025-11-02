using System;
using System.Collections.Generic;

namespace Fuzzbin.Core.Entities;

/// <summary>
/// Represents a YouTube video entity from yt-dlp metadata
/// </summary>
public class YtVideo : BaseEntity
{
    /// <summary>
    /// YouTube video identifier
    /// </summary>
    public string VideoId { get; set; } = string.Empty;
    
    /// <summary>
    /// Video title
    /// </summary>
    public string Title { get; set; } = string.Empty;
    
    /// <summary>
    /// YouTube channel identifier
    /// </summary>
    public string? ChannelId { get; set; }
    
    /// <summary>
    /// YouTube channel name
    /// </summary>
    public string? ChannelName { get; set; }
    
    /// <summary>
    /// Video duration in seconds
    /// </summary>
    public int? DurationSeconds { get; set; }
    
    /// <summary>
    /// Video width in pixels
    /// </summary>
    public int? Width { get; set; }
    
    /// <summary>
    /// Video height in pixels
    /// </summary>
    public int? Height { get; set; }
    
    /// <summary>
    /// View count
    /// </summary>
    public long? ViewCount { get; set; }
    
    /// <summary>
    /// Publication date in ISO format
    /// </summary>
    public string? PublishedAt { get; set; }
    
    /// <summary>
    /// Thumbnail URL
    /// </summary>
    public string? ThumbnailUrl { get; set; }
    
    /// <summary>
    /// Local thumbnail file path
    /// </summary>
    public string? ThumbnailPath { get; set; }
    
    /// <summary>
    /// Whether the channel is verified/official (e.g., VEVO, artist channels)
    /// </summary>
    public bool? IsOfficialChannel { get; set; }
    
    /// <summary>
    /// Last time this video was seen in a yt-dlp response
    /// </summary>
    public DateTime LastSeenAt { get; set; }
    
    // Navigation properties
    public virtual ICollection<YtVideoCandidate> Candidates { get; set; } = new List<YtVideoCandidate>();
}