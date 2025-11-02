using System;

namespace Fuzzbin.Core.Entities;

/// <summary>
/// Represents a MusicBrainz tag/genre associated with an entity
/// </summary>
public class MbTag : BaseEntity
{
    /// <summary>
    /// Entity type: 'artist', 'recording', 'release_group'
    /// </summary>
    public string EntityType { get; set; } = string.Empty;
    
    /// <summary>
    /// ID of the associated entity (references MbArtist.Id, MbRecording.Id, or MbReleaseGroup.Id)
    /// </summary>
    public Guid EntityId { get; set; }
    
    /// <summary>
    /// Tag name (e.g., "rock", "pop", "electronic")
    /// </summary>
    public string Name { get; set; } = string.Empty;
    
    /// <summary>
    /// Tag vote count from MusicBrainz
    /// </summary>
    public int Count { get; set; }
}