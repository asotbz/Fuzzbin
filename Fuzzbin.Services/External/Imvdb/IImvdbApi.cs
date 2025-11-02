using System.Threading;
using System.Threading.Tasks;
using Refit;

namespace Fuzzbin.Services.External.Imvdb;

/// <summary>
/// Refit interface for IMVDb API
/// </summary>
public interface IImvdbApi
{
    /// <summary>
    /// Search for music videos by query string
    /// </summary>
    [Get("/search/videos")]
    Task<ImvdbSearchResponse> SearchVideosAsync(
        [AliasAs("q")] string query,
        [AliasAs("page")] int page = 1,
        [AliasAs("per_page")] int perPage = 20,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Get detailed video information by ID
    /// </summary>
    [Get("/video/{id}")]
    Task<ImvdbVideoResponse> GetVideoAsync(
        string id,
        [AliasAs("include")] string? include = "artists,directors,sources",
        CancellationToken cancellationToken = default);
}
