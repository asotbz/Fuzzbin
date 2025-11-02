using System;

namespace Fuzzbin.Core.Entities;

/// <summary>
/// Join table linking IMVDb videos to artists with role information
/// </summary>
public class ImvdbVideoArtist
{
    public Guid VideoId { get; set; }
    public Guid ArtistId { get; set; }
    
    /// <summary>
    /// Artist role: 'primary' or 'featured'
    /// </summary>
    public string Role { get; set; } = string.Empty;
    
    /// <summary>
    /// Order of this artist in the credit (0-based)
    /// </summary>
    public int ArtistOrder { get; set; }
    
    // Navigation properties
    public virtual ImvdbVideo Video { get; set; } = null!;
    public virtual ImvdbArtist Artist { get; set; } = null!;
}