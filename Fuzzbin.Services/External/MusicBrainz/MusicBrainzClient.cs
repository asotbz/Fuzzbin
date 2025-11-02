using System;
using System.Net.Http;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Web;
using Microsoft.Extensions.Logging;

namespace Fuzzbin.Services.External.MusicBrainz;

/// <summary>
/// Client implementation for MusicBrainz Web Service v2 API
/// Handles rate limiting via HttpMessageHandler and includes retry logic via Polly
/// </summary>
public class MusicBrainzClient : IMusicBrainzClient
{
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly ILogger<MusicBrainzClient> _logger;
    private readonly JsonSerializerOptions _jsonOptions;

    public MusicBrainzClient(
        IHttpClientFactory httpClientFactory,
        ILogger<MusicBrainzClient> logger)
    {
        _httpClientFactory = httpClientFactory;
        _logger = logger;
        _jsonOptions = new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true
        };
    }

    public async Task<MbRecordingSearchResponse?> SearchRecordingsAsync(
        string artist,
        string title,
        int limit = 5,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var query = $"artist:\"{artist}\" AND recording:\"{title}\"";
            var url = $"recording?query={HttpUtility.UrlEncode(query)}&fmt=json&limit={limit}" +
                     "&inc=artist-credits+releases+release-groups+labels+tags+genres";

            var client = _httpClientFactory.CreateClient("MusicBrainz");
            var response = await client.GetAsync(url, cancellationToken);

            if (!response.IsSuccessStatusCode)
            {
                _logger.LogWarning(
                    "MusicBrainz search failed with status {Status} for {Artist} - {Title}",
                    response.StatusCode,
                    artist,
                    title);
                return null;
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            var result = JsonSerializer.Deserialize<MbRecordingSearchResponse>(json, _jsonOptions);
            
            _logger.LogDebug(
                "MusicBrainz search returned {Count} recordings for {Artist} - {Title}",
                result?.Recordings.Count ?? 0,
                artist,
                title);
            
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error searching MusicBrainz for {Artist} - {Title}", artist, title);
            return null;
        }
    }

    public async Task<MbRecording?> GetRecordingAsync(
        string mbid,
        string[]? include = null,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var includeParam = include != null && include.Length > 0
                ? $"&inc={string.Join("+", include)}"
                : "&inc=artist-credits+releases+release-groups+labels+tags+genres";

            var url = $"recording/{mbid}?fmt=json{includeParam}";

            var client = _httpClientFactory.CreateClient("MusicBrainz");
            var response = await client.GetAsync(url, cancellationToken);

            if (!response.IsSuccessStatusCode)
            {
                _logger.LogWarning(
                    "MusicBrainz recording lookup failed with status {Status} for MBID {Mbid}",
                    response.StatusCode,
                    mbid);
                return null;
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            var result = JsonSerializer.Deserialize<MbRecording>(json, _jsonOptions);
            
            _logger.LogDebug("MusicBrainz recording fetched for MBID {Mbid}: {Title}", mbid, result?.Title);
            
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error fetching MusicBrainz recording {Mbid}", mbid);
            return null;
        }
    }

    public async Task<MbReleaseGroup?> GetReleaseGroupAsync(
        string mbid,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var url = $"release-group/{mbid}?fmt=json&inc=tags+genres";

            var client = _httpClientFactory.CreateClient("MusicBrainz");
            var response = await client.GetAsync(url, cancellationToken);

            if (!response.IsSuccessStatusCode)
            {
                _logger.LogWarning(
                    "MusicBrainz release-group lookup failed with status {Status} for MBID {Mbid}",
                    response.StatusCode,
                    mbid);
                return null;
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            var result = JsonSerializer.Deserialize<MbReleaseGroup>(json, _jsonOptions);
            
            _logger.LogDebug(
                "MusicBrainz release-group fetched for MBID {Mbid}: {Title} ({FirstReleaseDate})",
                mbid,
                result?.Title,
                result?.FirstReleaseDate);
            
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error fetching MusicBrainz release-group {Mbid}", mbid);
            return null;
        }
    }

    public async Task<MbArtist?> GetArtistAsync(
        string mbid,
        CancellationToken cancellationToken = default)
    {
        try
        {
            var url = $"artist/{mbid}?fmt=json&inc=aliases+tags+genres";

            var client = _httpClientFactory.CreateClient("MusicBrainz");
            var response = await client.GetAsync(url, cancellationToken);

            if (!response.IsSuccessStatusCode)
            {
                _logger.LogWarning(
                    "MusicBrainz artist lookup failed with status {Status} for MBID {Mbid}",
                    response.StatusCode,
                    mbid);
                return null;
            }

            var json = await response.Content.ReadAsStringAsync(cancellationToken);
            var result = JsonSerializer.Deserialize<MbArtist>(json, _jsonOptions);
            
            _logger.LogDebug("MusicBrainz artist fetched for MBID {Mbid}: {Name}", mbid, result?.Name);
            
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error fetching MusicBrainz artist {Mbid}", mbid);
            return null;
        }
    }
}