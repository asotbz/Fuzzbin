using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace Fuzzbin.Services.External.MusicBrainz;

/// <summary>
/// Complete recording search response from MusicBrainz API
/// </summary>
public class MbRecordingSearchResponse
{
    [JsonPropertyName("created")] public DateTime? Created { get; set; }
    [JsonPropertyName("count")] public int Count { get; set; }
    [JsonPropertyName("offset")] public int Offset { get; set; }
    [JsonPropertyName("recordings")] public List<MbRecording> Recordings { get; set; } = new();
}

/// <summary>
/// MusicBrainz recording with full metadata
/// </summary>
public class MbRecording
{
    [JsonPropertyName("id")] public string Id { get; set; } = string.Empty;
    [JsonPropertyName("title")] public string Title { get; set; } = string.Empty;
    [JsonPropertyName("length")] public int? Length { get; set; }  // milliseconds
    [JsonPropertyName("score")] public int Score { get; set; }  // NEW - MusicBrainz relevance score (0-100)
    [JsonPropertyName("artist-credit")] public List<MbArtistCredit> ArtistCredit { get; set; } = new();
    [JsonPropertyName("releases")] public List<MbRelease> Releases { get; set; } = new();
    [JsonPropertyName("tags")] public List<MbTag> Tags { get; set; } = new();  // NEW
    [JsonPropertyName("genres")] public List<MbTag> Genres { get; set; } = new();  // NEW
}

/// <summary>
/// Enhanced artist credit with join phrases for featured artist detection
/// </summary>
public class MbArtistCredit
{
    [JsonPropertyName("name")] public string Name { get; set; } = string.Empty;  // Credited name
    [JsonPropertyName("joinphrase")] public string? JoinPhrase { get; set; }  // NEW - " feat. ", " & ", etc.
    [JsonPropertyName("artist")] public MbArtist Artist { get; set; } = new();
}

/// <summary>
/// MusicBrainz artist entity
/// </summary>
public class MbArtist
{
    [JsonPropertyName("id")] public string Id { get; set; } = string.Empty;
    [JsonPropertyName("name")] public string Name { get; set; } = string.Empty;
    [JsonPropertyName("sort-name")] public string SortName { get; set; } = string.Empty;
    [JsonPropertyName("disambiguation")] public string? Disambiguation { get; set; }  // NEW
    [JsonPropertyName("country")] public string? Country { get; set; }  // NEW
}

/// <summary>
/// Enhanced release with full data including label info
/// </summary>
public class MbRelease
{
    [JsonPropertyName("id")] public string Id { get; set; } = string.Empty;
    [JsonPropertyName("title")] public string Title { get; set; } = string.Empty;
    [JsonPropertyName("date")] public string? Date { get; set; }
    [JsonPropertyName("country")] public string? Country { get; set; }  // NEW
    [JsonPropertyName("barcode")] public string? Barcode { get; set; }  // NEW
    [JsonPropertyName("track-count")] public int? TrackCount { get; set; }  // NEW
    [JsonPropertyName("label-info")] public List<MbLabelInfo>? LabelInfo { get; set; }  // NEW
    [JsonPropertyName("release-group")] public MbReleaseGroup? ReleaseGroup { get; set; }  // Enhanced
}

/// <summary>
/// Label info data for record label tracking
/// </summary>
public class MbLabelInfo
{
    [JsonPropertyName("catalog-number")] public string? CatalogNumber { get; set; }
    [JsonPropertyName("label")] public MbLabel? Label { get; set; }
}

/// <summary>
/// Label entity
/// </summary>
public class MbLabel
{
    [JsonPropertyName("id")] public string Id { get; set; } = string.Empty;
    [JsonPropertyName("name")] public string Name { get; set; } = string.Empty;
}

/// <summary>
/// Release group data - CRITICAL for year scoring
/// </summary>
public class MbReleaseGroup
{
    [JsonPropertyName("id")] public string Id { get; set; } = string.Empty;
    [JsonPropertyName("title")] public string Title { get; set; } = string.Empty;
    [JsonPropertyName("first-release-date")] public string? FirstReleaseDate { get; set; }  // CRITICAL - earliest release year
    [JsonPropertyName("primary-type")] public string? PrimaryType { get; set; }  // Album, Single, EP
    [JsonPropertyName("tags")] public List<MbTag> Tags { get; set; } = new();
    [JsonPropertyName("genres")] public List<MbTag> Genres { get; set; } = new();
}

/// <summary>
/// Tag/Genre data
/// </summary>
public class MbTag
{
    [JsonPropertyName("name")] public string Name { get; set; } = string.Empty;
    [JsonPropertyName("count")] public int? Count { get; set; }
}