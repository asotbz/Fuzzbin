namespace Fuzzbin.Core.Specifications;

/// <summary>
/// Supported sort properties for video catalogue queries.
/// </summary>
public enum VideoSortOption
{
    Title,
    Artist,
    CreatedAt,
    UpdatedAt,
    LastPlayedAt,
    PlayCount,
    Rating,
    Year,
    Duration,
    Random
}
