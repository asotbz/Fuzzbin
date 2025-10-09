using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Refit;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.External.Imvdb;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;
using YtSearchResult = Fuzzbin.Core.Interfaces.SearchResult;

namespace Fuzzbin.Services;

public class ExternalSearchService : IExternalSearchService
{
    private static readonly Regex QualifierRegex = new(@"[\(\[].*?[\)\]]", RegexOptions.Compiled);
    private readonly IImvdbApi _imvdbApi;
    private readonly IYtDlpService _ytDlpService;
    private readonly IImvdbApiKeyProvider _apiKeyProvider;
    private readonly ILogger<ExternalSearchService> _logger;

    public ExternalSearchService(
        IImvdbApi imvdbApi,
        IYtDlpService ytDlpService,
        IImvdbApiKeyProvider apiKeyProvider,
        ILogger<ExternalSearchService> logger)
    {
        _imvdbApi = imvdbApi;
        _ytDlpService = ytDlpService;
        _apiKeyProvider = apiKeyProvider;
        _logger = logger;
    }

    public async Task<ExternalSearchResult> SearchAsync(ExternalSearchQuery query, CancellationToken cancellationToken = default)
    {
        _logger.LogDebug("External search requested. SearchText={SearchText}, Artist={Artist}, Title={Title}, IncludeImvdb={IncludeImvdb}, IncludeYtDlp={IncludeYtDlp}, MaxResults={MaxResults}",
            query.SearchText,
            query.Artist,
            query.Title,
            query.IncludeImvdb,
            query.IncludeYtDlp,
            query.MaxResults);

        var result = new ExternalSearchResult
        {
            ImvdbEnabled = query.IncludeImvdb,
            YtDlpEnabled = query.IncludeYtDlp
        };

        if (IsQueryEmpty(query))
        {
            result.Warnings.Add("Provide a song title or artist before searching.");
            return result;
        }

        var normalizedQuery = BuildQueryString(query);
        var imvdbItems = new List<ExternalSearchItem>();

        if (query.IncludeImvdb)
        {
            var apiKey = await _apiKeyProvider.GetApiKeyAsync(cancellationToken).ConfigureAwait(false);
            if (string.IsNullOrWhiteSpace(apiKey))
            {
                _logger.LogWarning("Skipping IMVDb search because API key is not configured.");
                result.Warnings.Add("IMVDb API key not configured; skipping IMVDb search.");
            }
            else
            {
                imvdbItems = await SearchImvdbAsync(query, normalizedQuery, result, cancellationToken).ConfigureAwait(false);
            }
        }

        var ytResults = query.IncludeYtDlp
            ? await SearchYoutubeAsync(query, normalizedQuery, result, cancellationToken).ConfigureAwait(false)
            : new List<YtSearchResult>();

        var matchedYoutube = new HashSet<YtSearchResult>();
        if (imvdbItems.Count > 0 && ytResults.Count > 0)
        {
            foreach (var item in imvdbItems)
            {
                var match = FindBestYoutubeMatch(item, ytResults, query);
                if (match != null)
                {
                    item.YtDlp = match;
                    item.Source = ExternalSearchSource.Combined;
                    item.ArtworkUrl ??= match.ThumbnailUrl;
                    item.Description ??= match.Url;
                    item.Confidence = Math.Max(item.Confidence, CalculateConfidence(item.Artist, item.Title, query, isYoutube: true));
                    matchedYoutube.Add(match);
                }
            }
        }

        result.Items.AddRange(imvdbItems);

        foreach (var ytResult in ytResults)
        {
            if (matchedYoutube.Contains(ytResult))
            {
                continue;
            }

            var (artistGuess, titleGuess) = ParseYtDlpTitle(ytResult.Title);
            var item = new ExternalSearchItem
            {
                Title = string.IsNullOrWhiteSpace(titleGuess) ? ytResult.Title : titleGuess,
                Artist = artistGuess,
                Source = ExternalSearchSource.YtDlp,
                YtDlp = ytResult,
                ArtworkUrl = ytResult.ThumbnailUrl,
                Description = ytResult.Url,
                Confidence = CalculateConfidence(artistGuess, titleGuess, query, isYoutube: true)
            };

            result.Items.Add(item);
        }

        result.Items = result.Items
            .OrderByDescending(item => item.Confidence)
            .ThenBy(item => item.Source != ExternalSearchSource.Combined)
            .ThenBy(item => ImvdbMapper.NormalizeSimple(item.Title))
            .ToList();

        _logger.LogDebug("External search completed. Items={ItemCount}, IMVDb={ImvdbCount}, YtDlp={YtCount}, Warnings={WarningCount}",
            result.Items.Count,
            imvdbItems.Count,
            ytResults.Count,
            result.Warnings.Count);

        return result;
    }

    private async Task<List<ExternalSearchItem>> SearchImvdbAsync(
        ExternalSearchQuery query,
        string normalizedQuery,
        ExternalSearchResult result,
        CancellationToken cancellationToken)
    {
        var items = new List<ExternalSearchItem>();

        try
        {
            var response = await _imvdbApi.SearchVideosAsync(
                normalizedQuery,
                perPage: Math.Clamp(query.MaxResults, 5, 20),
                cancellationToken: cancellationToken).ConfigureAwait(false);

            if (response?.Results == null || response.Results.Count == 0)
            {
                return items;
            }

            var summaries = response.Results
                .Where(summary => summary != null)
                .Take(query.MaxResults)
                .ToList();

            var detailLimit = Math.Min(5, summaries.Count);

            for (var index = 0; index < summaries.Count; index++)
            {
                var summary = summaries[index];
                ImvdbMetadata? metadata = null;

                if (index < detailLimit)
                {
                    try
                    {
                        var detail = await _imvdbApi.GetVideoAsync(
                            summary.Id.ToString(),
                            cancellationToken).ConfigureAwait(false);
                        metadata = ImvdbMapper.MapToMetadata(detail, summary);
                    }
                    catch (ApiException apiException)
                    {
                        _logger.LogWarning(apiException, "Failed to fetch IMVDb details for video {Id}", summary.Id);
                        result.Warnings.Add($"IMVDb detail fetch failed for ID {summary.Id}: {apiException.StatusCode}");
                    }
                }

                metadata ??= new ImvdbMetadata
                {
                    ImvdbId = summary.Id,
                    Title = ImvdbMapper.FirstNonEmpty(summary.SongTitle, summary.Title) ?? string.Empty,
                    Artist = summary.Artist ?? string.Empty,
                    ImageUrl = summary.ImageUrl,
                    VideoUrl = summary.Url
                };

                var item = new ExternalSearchItem
                {
                    Title = metadata.Title ?? string.Empty,
                    Artist = metadata.Artist ?? string.Empty,
                    Source = ExternalSearchSource.Imvdb,
                    Imvdb = metadata,
                    ArtworkUrl = metadata.ImageUrl,
                    Description = metadata.Description,
                    Confidence = CalculateConfidence(metadata.Artist, metadata.Title, query)
                };

                items.Add(item);
            }
        }
        catch (ApiException apiException)
        {
            _logger.LogWarning(apiException, "IMVDb search failed with status {StatusCode} for query {Query}", apiException.StatusCode, normalizedQuery);
            result.Warnings.Add($"IMVDb search failed: {apiException.StatusCode}");
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "IMVDb search failed for query {Query}", normalizedQuery);
            result.Warnings.Add($"IMVDb search failed: {ex.Message}");
        }

        return items;
    }

    private async Task<List<YtSearchResult>> SearchYoutubeAsync(
        ExternalSearchQuery query,
        string normalizedQuery,
        ExternalSearchResult result,
        CancellationToken cancellationToken)
    {
        try
        {
            return await _ytDlpService.SearchVideosAsync(
                normalizedQuery,
                Math.Clamp(query.MaxResults, 5, 20),
                cancellationToken).ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "yt-dlp search failed for query {Query}", normalizedQuery);
            result.Warnings.Add($"yt-dlp search failed: {ex.Message}");
            return new List<YtSearchResult>();
        }
    }

    private static bool IsQueryEmpty(ExternalSearchQuery query)
    {
        return string.IsNullOrWhiteSpace(query.SearchText)
            && string.IsNullOrWhiteSpace(query.Artist)
            && string.IsNullOrWhiteSpace(query.Title);
    }

    private static string BuildQueryString(ExternalSearchQuery query)
    {
        if (!string.IsNullOrWhiteSpace(query.SearchText))
        {
            return query.SearchText.Trim();
        }

        var parts = new List<string>();
        if (!string.IsNullOrWhiteSpace(query.Artist))
        {
            parts.Add(query.Artist.Trim());
        }
        if (!string.IsNullOrWhiteSpace(query.Title))
        {
            parts.Add(query.Title.Trim());
        }

        return string.Join(" ", parts);
    }

    private static YtSearchResult? FindBestYoutubeMatch(
        ExternalSearchItem item,
        IEnumerable<YtSearchResult> candidates,
        ExternalSearchQuery query)
    {
        var itemKey = ImvdbMapper.NormalizeKey($"{item.Artist} {item.Title}");
        YtSearchResult? best = null;
        double bestScore = 0;

        foreach (var candidate in candidates)
        {
            var (artist, title) = ParseYtDlpTitle(candidate.Title);
            var candidateKey = ImvdbMapper.NormalizeKey($"{artist} {title}");

            double score;
            if (!string.IsNullOrWhiteSpace(candidateKey) && candidateKey == itemKey)
            {
                score = 1.0;
            }
            else
            {
                score = CalculateConfidence(artist, title, query, isYoutube: true);
                if (!string.IsNullOrWhiteSpace(candidateKey) && !string.IsNullOrWhiteSpace(itemKey) && itemKey.Contains(candidateKey))
                {
                    score += 0.1;
                }
            }

            if (score > bestScore && score >= 0.5)
            {
                bestScore = score;
                best = candidate;
            }
        }

        return best;
    }

    private static double CalculateConfidence(string? artist, string? title, ExternalSearchQuery query, bool isYoutube = false)
    {
        double score = 0.2;

        if (!string.IsNullOrWhiteSpace(query.Artist) && !string.IsNullOrWhiteSpace(artist))
        {
            var queryArtistKey = ImvdbMapper.NormalizeKey(query.Artist);
            var artistKey = ImvdbMapper.NormalizeKey(artist);
            if (artistKey == queryArtistKey)
            {
                score += 0.45;
            }
            else if (ImvdbMapper.NormalizeSimple(artist).Contains(ImvdbMapper.NormalizeSimple(query.Artist)))
            {
                score += 0.2;
            }
        }

        if (!string.IsNullOrWhiteSpace(query.Title) && !string.IsNullOrWhiteSpace(title))
        {
            var queryTitleKey = ImvdbMapper.NormalizeKey(query.Title);
            var titleKey = ImvdbMapper.NormalizeKey(title);
            if (titleKey == queryTitleKey)
            {
                score += 0.45;
            }
            else if (ImvdbMapper.NormalizeSimple(title).Contains(ImvdbMapper.NormalizeSimple(query.Title)))
            {
                score += 0.2;
            }
        }

        if (!string.IsNullOrWhiteSpace(query.SearchText))
        {
            var normalizedSearch = ImvdbMapper.NormalizeSimple(query.SearchText);
            if (!string.IsNullOrWhiteSpace(title) && ImvdbMapper.NormalizeSimple(title).Contains(normalizedSearch))
            {
                score += 0.1;
            }
            if (!string.IsNullOrWhiteSpace(artist) && ImvdbMapper.NormalizeSimple(artist).Contains(normalizedSearch))
            {
                score += 0.1;
            }
        }

        if (isYoutube)
        {
            score -= 0.05; // Slight penalty when only YouTube data is available
        }

        return Math.Clamp(score, 0.1, 1.0);
    }

    private static (string Artist, string Title) ParseYtDlpTitle(string? title)
    {
        if (string.IsNullOrWhiteSpace(title))
        {
            return (string.Empty, string.Empty);
        }

        var cleaned = StripQualifiers(title);
        var separators = new[] { " - ", " – ", " — ", " — ", " | " };

        foreach (var separator in separators)
        {
            var index = cleaned.IndexOf(separator, StringComparison.Ordinal);
            if (index > 0 && index < cleaned.Length - separator.Length)
            {
                var artist = cleaned[..index].Trim();
                var songTitle = cleaned[(index + separator.Length)..].Trim();
                return (artist, songTitle);
            }
        }

        return (string.Empty, cleaned);
    }

    private static string StripQualifiers(string value)
    {
        var withoutBrackets = QualifierRegex.Replace(value, string.Empty);
        var tokens = new[]
        {
            "official music video",
            "official video",
            "music video",
            "official audio",
            "lyrics",
            "hd",
            "4k"
        };

        var cleaned = withoutBrackets;
        foreach (var token in tokens)
        {
            cleaned = cleaned.Replace(token, string.Empty, StringComparison.OrdinalIgnoreCase);
        }

        return cleaned.Trim(' ', '-', '|');
    }
}
