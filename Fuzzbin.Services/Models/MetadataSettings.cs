using System;
using System.Collections.Generic;

namespace Fuzzbin.Services.Models;

/// <summary>
/// Defines how artist names and featured artists are written to NFO files
/// </summary>
public enum NfoArtistMode
{
    /// <summary>
    /// Write primary artist to NFO only. Ignore any featured artists.
    /// </summary>
    PrimaryOnly = 0,

    /// <summary>
    /// Write primary artist and any additional featured artists as individual artist fields.
    /// </summary>
    SeparateFields = 1,

    /// <summary>
    /// Write primary artist, "feat.", and any featured artists to a singular artist field (default behavior).
    /// </summary>
    CombinedArtistField = 2,

    /// <summary>
    /// Write primary artist to singular artist element. Write any featured artists to the title element ({title} feat. {featured artists}).
    /// </summary>
    FeaturedInTitle = 3
}

public sealed class MetadataSettings
{
    public static MetadataSettings Default { get; } = new();

    public bool GeneralizeGenres { get; init; }

    public bool WriteExternalGenreAsTag { get; init; }

    /// <summary>
    /// Defines how artist names and featured artists are written to NFO files
    /// </summary>
    public NfoArtistMode ArtistMode { get; init; } = NfoArtistMode.CombinedArtistField;

    /// <summary>
    /// Legacy property - kept for backwards compatibility during migration
    /// </summary>
    [Obsolete("Use ArtistMode instead")]
    public bool UsePrimaryArtistForNfo { get; init; }

    /// <summary>
    /// Legacy property - kept for backwards compatibility during migration
    /// </summary>
    [Obsolete("Use ArtistMode instead")]
    public bool AppendFeaturedArtistsToTitle { get; init; }

    public bool WriteCollectionsAsNfoTags { get; init; }

    public IReadOnlyDictionary<string, string> GenreMappings { get; init; }
        = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
}
