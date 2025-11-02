using System.Collections.Generic;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;
using Refit;

namespace Fuzzbin.Services.External.Imvdb;

public interface IImvdbApi
{
    [Get("/search/videos")]
    Task<ImvdbSearchResponse> SearchVideosAsync(
        [AliasAs("q")] string query,
        [AliasAs("page")] int page = 1,
        [AliasAs("per_page")] int perPage = 20,
        CancellationToken cancellationToken = default);

    [Get("/video/{id}")]
    Task<ImvdbVideoResponse> GetVideoAsync(
        string id,
        [AliasAs("include")] string? include = "artists,directors,sources",  // NEW: include parameter for detailed data
        CancellationToken cancellationToken = default);
}

/// <summary>
/// Enhanced search response with pagination metadata
/// </summary>
public class ImvdbSearchResponse
{
    [AliasAs("page")]
    [JsonPropertyName("page")]
    public int Page { get; set; }
    
    [AliasAs("per_page")]
    [JsonPropertyName("per_page")]
    public int PerPage { get; set; }
    
    [AliasAs("total_results")]
    [JsonPropertyName("total_results")]
    public int TotalResults { get; set; }
    
    [AliasAs("results")]
    [JsonPropertyName("results")]
    public List<ImvdbVideoSummary> Results { get; set; } = new();
}

/// <summary>
/// Video summary from search results with enhanced fields
/// </summary>
public class ImvdbVideoSummary
{
    [AliasAs("id")]
    [JsonPropertyName("id")]
    public long Id { get; set; }  // 64-bit for large IDs
    
    [AliasAs("url")]
    [JsonPropertyName("url")]
    public string? Url { get; set; }
    
    [AliasAs("song_title")]
    [JsonPropertyName("song_title")]
    public string? SongTitle { get; set; }
    
    [AliasAs("video_title")]
    [JsonPropertyName("video_title")]
    public string? VideoTitle { get; set; }  // NEW - separate from song_title
    
    [AliasAs("release_date")]
    [JsonPropertyName("release_date")]
    public string? ReleaseDate { get; set; }  // NEW - YYYY-MM-DD or partial
    
    [AliasAs("has_sources")]
    [JsonPropertyName("has_sources")]
    public bool HasSources { get; set; }  // NEW - CRITICAL for YouTube/Vimeo availability
    
    [AliasAs("artists")]
    [JsonPropertyName("artists")]
    public List<ImvdbArtistCredit> Artists { get; set; } = new();  // NEW - structured artist data
    
    [AliasAs("thumbnail")]
    [JsonPropertyName("thumbnail")]
    public ImvdbThumbnail? Thumbnail { get; set; }  // Enhanced with dimensions
    
    // Backward compatibility properties
    [AliasAs("artist")]
    [JsonPropertyName("artist")]
    public string? Artist { get; set; }  // Legacy: simple artist string
    
    [AliasAs("title")]
    [JsonPropertyName("title")]
    public string? Title { get; set; }  // Legacy: simple title
    
    [AliasAs("image")]
    [JsonPropertyName("image")]
    public string? ImageUrl { get; set; }  // Legacy: thumbnail URL
}

/// <summary>
/// Structured artist credit with role and order
/// </summary>
public class ImvdbArtistCredit
{
    [AliasAs("id")]
    [JsonPropertyName("id")]
    public int Id { get; set; }
    
    [AliasAs("name")]
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;
    
    [AliasAs("role")]
    [JsonPropertyName("role")]
    public string Role { get; set; } = string.Empty;  // 'primary', 'featured'
    
    [AliasAs("order")]
    [JsonPropertyName("order")]
    public int Order { get; set; }
}

/// <summary>
/// Structured thumbnail with dimensions
/// </summary>
public class ImvdbThumbnail
{
    [AliasAs("url")]
    [JsonPropertyName("url")]
    public string? Url { get; set; }
    
    [AliasAs("width")]
    [JsonPropertyName("width")]
    public int? Width { get; set; }
    
    [AliasAs("height")]
    [JsonPropertyName("height")]
    public int? Height { get; set; }
}

/// <summary>
/// Enhanced detail response with full metadata
/// </summary>
public class ImvdbVideoResponse
{
    [AliasAs("id")]
    [JsonPropertyName("id")]
    public long Id { get; set; }
    
    [AliasAs("url")]
    [JsonPropertyName("url")]
    public string? Url { get; set; }
    
    [AliasAs("song_title")]
    [JsonPropertyName("song_title")]
    public string? SongTitle { get; set; }
    
    [AliasAs("video_title")]
    [JsonPropertyName("video_title")]
    public string? VideoTitle { get; set; }  // NEW
    
    [AliasAs("release_date")]
    [JsonPropertyName("release_date")]
    public string? ReleaseDate { get; set; }
    
    [AliasAs("runtime_seconds")]
    [JsonPropertyName("runtime_seconds")]
    public int? RuntimeSeconds { get; set; }  // NEW - duration metadata
    
    [AliasAs("thumbnail")]
    [JsonPropertyName("thumbnail")]
    public ImvdbThumbnail? Thumbnail { get; set; }
    
    [AliasAs("artists")]
    [JsonPropertyName("artists")]
    public List<ImvdbArtistCredit> Artists { get; set; } = new();
    
    [AliasAs("directors")]
    [JsonPropertyName("directors")]
    public List<ImvdbDirector> Directors { get; set; } = new();  // Enhanced
    
    [AliasAs("sources")]
    [JsonPropertyName("sources")]
    public List<ImvdbSource> Sources { get; set; } = new();  // NEW - CRITICAL for cache strategy
    
    // Backward compatibility properties
    [AliasAs("artist")] public string? Artist { get; set; }  // Legacy: simple artist string
    [AliasAs("title")] public string? Title { get; set; }  // Legacy: simple title
    [AliasAs("description")] public string? Description { get; set; }  // Legacy: description field
    [AliasAs("thumbnail_url")] public string? ThumbnailUrl { get; set; }  // Legacy: thumbnail URL
    [AliasAs("imvdb_url")] public string? ImvdbUrl { get; set; }  // Legacy: IMVDb URL
    [AliasAs("explicit")] public bool? IsExplicit { get; set; }  // Legacy: explicit flag
    [AliasAs("unofficial")] public bool? IsUnofficial { get; set; }  // Legacy: unofficial flag
    [AliasAs("genres")] public List<ImvdbGenre> Genres { get; set; } = new();  // Legacy: genres
    [AliasAs("credits")] public List<ImvdbCredit> Credits { get; set; } = new();  // Legacy: credits
}

/// <summary>
/// Legacy genre structure for backward compatibility
/// </summary>
public class ImvdbGenre
{
    [AliasAs("name")] public string? Name { get; set; }
}

/// <summary>
/// Legacy credit structure for backward compatibility
/// </summary>
public class ImvdbCredit
{
    [AliasAs("role")] public string? Role { get; set; }
    [AliasAs("person")] public ImvdbPerson? Person { get; set; }
}

/// <summary>
/// Legacy person structure for backward compatibility
/// </summary>
public class ImvdbPerson
{
    [AliasAs("name")] public string? Name { get; set; }
}

/// <summary>
/// Structured director information
/// </summary>
public class ImvdbDirector
{
    [AliasAs("id")]
    [JsonPropertyName("id")]
    public int Id { get; set; }
    
    [AliasAs("name")]
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;
}

/// <summary>
/// Structured source - CRITICAL for cache strategy and scoring
/// </summary>
public class ImvdbSource
{
    [AliasAs("source")]
    [JsonPropertyName("source")]
    public string Source { get; set; } = string.Empty;  // 'youtube', 'vimeo'
    
    [AliasAs("external_id")]
    [JsonPropertyName("external_id")]
    public string ExternalId { get; set; } = string.Empty;  // YouTube video ID
    
    [AliasAs("url")]
    [JsonPropertyName("url")]
    public string Url { get; set; } = string.Empty;
    
    [AliasAs("is_official")]
    [JsonPropertyName("is_official")]
    public bool IsOfficial { get; set; }  // CRITICAL for scoring bonus
}
