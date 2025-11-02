using System.Threading;
using System.Threading.Tasks;

namespace Fuzzbin.Services.External.MusicBrainz;

/// <summary>
/// Client interface for MusicBrainz Web Service v2 API
/// </summary>
public interface IMusicBrainzClient
{
    /// <summary>
    /// Search for recordings by artist and title
    /// </summary>
    /// <param name="artist">Artist name</param>
    /// <param name="title">Recording title</param>
    /// <param name="limit">Maximum number of results (default 5)</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Search response with recordings, or null if request failed</returns>
    Task<MbRecordingSearchResponse?> SearchRecordingsAsync(
        string artist,
        string title,
        int limit = 5,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Get detailed recording information by MBID
    /// </summary>
    /// <param name="mbid">MusicBrainz recording ID</param>
    /// <param name="include">Optional include parameters (artist-credits, releases, release-groups, tags, genres)</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Recording details, or null if not found</returns>
    Task<MbRecording?> GetRecordingAsync(
        string mbid,
        string[]? include = null,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Get release group information by MBID
    /// </summary>
    /// <param name="mbid">MusicBrainz release group ID</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Release group details, or null if not found</returns>
    Task<MbReleaseGroup?> GetReleaseGroupAsync(
        string mbid,
        CancellationToken cancellationToken = default);

    /// <summary>
    /// Get artist information by MBID
    /// </summary>
    /// <param name="mbid">MusicBrainz artist ID</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Artist details, or null if not found</returns>
    Task<MbArtist?> GetArtistAsync(
        string mbid,
        CancellationToken cancellationToken = default);
}