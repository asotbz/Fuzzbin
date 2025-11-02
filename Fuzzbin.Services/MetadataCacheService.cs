using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.External.Imvdb;
using Fuzzbin.Services.External.MusicBrainz;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Metadata;

namespace Fuzzbin.Services;

/// <summary>
/// Unified metadata cache service that coordinates searches across MusicBrainz, IMVDb, and YouTube
/// with intelligent caching, candidate ranking, and aggregation
/// </summary>
public class MetadataCacheService : IMetadataCacheService
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly IMusicBrainzClient _mbClient;
    private readonly IImvdbApi _imvdbApi;
    private readonly IYtDlpService _ytDlpService;
    private readonly IExternalCacheSettingsProvider _settingsProvider;
    private readonly ILogger<MetadataCacheService> _logger;

    public MetadataCacheService(
        IUnitOfWork unitOfWork,
        IMusicBrainzClient mbClient,
        IImvdbApi imvdbApi,
        IYtDlpService ytDlpService,
        IExternalCacheSettingsProvider settingsProvider,
        ILogger<MetadataCacheService> logger)
    {
        _unitOfWork = unitOfWork;
        _mbClient = mbClient;
        _imvdbApi = imvdbApi;
        _ytDlpService = ytDlpService;
        _settingsProvider = settingsProvider;
        _logger = logger;
    }

    public async Task<MetadataCacheResult> SearchAsync(
        string artist,
        string title,
        int? knownDurationSeconds = null,
        CancellationToken cancellationToken = default)
    {
        // 1. Normalize query and check/create Query entity
        var (normTitle, normArtist, comboKey) = QueryNormalizer.NormalizePair(title, artist);
        var query = await GetOrCreateQueryAsync(artist, title, normTitle, normArtist, comboKey, cancellationToken);

        // 2. Check if cache is still valid
        var settings = _settingsProvider.GetSettings();
        if (!settings.IsCacheEnabled())
        {
            _logger.LogDebug("Cache disabled, fetching fresh metadata for {Artist} - {Title}", artist, title);
            await FetchAllSourcesAsync(query, artist, title, knownDurationSeconds, cancellationToken);
        }
        else
        {
            var cacheExpiry = DateTime.UtcNow - settings.GetCacheDuration();
            var needsRefresh = await NeedsRefreshAsync(query.Id, cacheExpiry, cancellationToken);

            if (needsRefresh)
            {
                _logger.LogInformation("Cache expired for {Artist} - {Title}, refreshing", artist, title);
                await FetchAllSourcesAsync(query, artist, title, knownDurationSeconds, cancellationToken);
            }
            else
            {
                _logger.LogDebug("Using cached metadata for {Artist} - {Title}", artist, title);
            }
        }

        // 3. Aggregate candidates from all sources
        var candidates = await AggregateAndRankCandidatesAsync(query.Id, cancellationToken);

        // 4. Determine best match and if manual selection needed
        var result = new MetadataCacheResult
        {
            Found = candidates.Any(),
            BestMatch = candidates.FirstOrDefault(),
            AlternativeCandidates = candidates.Skip(1).Take(4).ToList(),
            RequiresManualSelection = candidates.Any() && candidates.First().OverallConfidence < 0.9
        };

        _logger.LogInformation(
            "Metadata search for {Artist} - {Title}: Found={Found}, Confidence={Confidence:P0}, Source={Source}",
            artist, title, result.Found, result.BestMatch?.OverallConfidence, result.BestMatch?.PrimarySource);

        return result;
    }

    public async Task<List<AggregatedCandidate>> GetCandidatesAsync(
        string artist,
        string title,
        int maxResults = 10,
        CancellationToken cancellationToken = default)
    {
        var (normTitle, normArtist, comboKey) = QueryNormalizer.NormalizePair(title, artist);
        
        var query = await _unitOfWork.Queries
            .GetQueryable()
            .FirstOrDefaultAsync(q => q.NormComboKey == comboKey, cancellationToken);

        if (query == null)
        {
            _logger.LogWarning("No cached results found for {Artist} - {Title}", artist, title);
            return new List<AggregatedCandidate>();
        }

        var candidates = await AggregateAndRankCandidatesAsync(query.Id, cancellationToken);
        return candidates.Take(maxResults).ToList();
    }

    public async Task<Video> ApplyMetadataAsync(
        Video video,
        AggregatedCandidate candidate,
        CancellationToken cancellationToken = default)
    {
        _logger.LogInformation(
            "Applying metadata from {Source} to video {VideoId}",
            candidate.PrimarySource, video.Id);

        // Apply basic metadata
        video.Title = candidate.Title;
        video.Artist = candidate.Artist;
        
        if (candidate.Year.HasValue)
        {
            video.Year = candidate.Year.Value;
        }

        if (!string.IsNullOrEmpty(candidate.FeaturedArtists))
        {
            // TODO: Parse and create FeaturedArtist entities
            _logger.LogDebug("Featured artists found: {FeaturedArtists}", candidate.FeaturedArtists);
        }

        if (!string.IsNullOrEmpty(candidate.Director))
        {
            video.Director = candidate.Director;
        }

        if (!string.IsNullOrEmpty(candidate.RecordLabel))
        {
            video.Publisher = candidate.RecordLabel;
        }

        // Apply genres
        if (candidate.Genres.Any())
        {
            // TODO: Map genres to video entity
            _logger.LogDebug("Genres found: {Genres}", string.Join(", ", candidate.Genres));
        }

        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation("Metadata applied successfully to video {VideoId}", video.Id);
        return video;
    }

    public async Task<bool> IsCachedAsync(
        string artist,
        string title,
        CancellationToken cancellationToken = default)
    {
        var (normTitle, normArtist, comboKey) = QueryNormalizer.NormalizePair(title, artist);
        
        var query = await _unitOfWork.Queries
            .GetQueryable()
            .Include(q => q.SourceCaches)
            .FirstOrDefaultAsync(q => q.NormComboKey == comboKey, cancellationToken);

        if (query == null)
        {
            return false;
        }

        var settings = _settingsProvider.GetSettings();
        if (!settings.IsCacheEnabled())
        {
            return false;
        }

        var cacheExpiry = DateTime.UtcNow - settings.GetCacheDuration();
        var isValid = query.SourceCaches.Any(sc => sc.LastCheckedAt >= cacheExpiry);

        return isValid;
    }

    public async Task ClearCacheAsync(CancellationToken cancellationToken = default)
    {
        _logger.LogWarning("Clearing all cached metadata");

        // Delete all cache-related entities
        var queries = await _unitOfWork.Queries.GetQueryable().ToListAsync(cancellationToken);
        
        foreach (var query in queries)
        {
            await _unitOfWork.Queries.DeleteAsync(query);
        }

        await _unitOfWork.SaveChangesAsync();

        _logger.LogInformation("Cleared {Count} cached queries", queries.Count);
    }

    // Helper methods

    private async Task<Query> GetOrCreateQueryAsync(
        string rawArtist,
        string rawTitle,
        string normArtist,
        string normTitle,
        string comboKey,
        CancellationToken cancellationToken)
    {
        var query = await _unitOfWork.Queries
            .GetQueryable()
            .FirstOrDefaultAsync(q => q.NormComboKey == comboKey, cancellationToken);

        if (query == null)
        {
            query = new Query
            {
                RawArtist = rawArtist,
                RawTitle = rawTitle,
                NormArtist = normArtist,
                NormTitle = normTitle,
                NormComboKey = comboKey,
                CreatedAt = DateTime.UtcNow,
                UpdatedAt = DateTime.UtcNow,
                IsActive = true
            };

            await _unitOfWork.Queries.AddAsync(query);
            await _unitOfWork.SaveChangesAsync();

            _logger.LogDebug("Created new query entity for {ComboKey}", comboKey);
        }

        return query;
    }

    private async Task<bool> NeedsRefreshAsync(
        Guid queryId,
        DateTime cacheExpiry,
        CancellationToken cancellationToken)
    {
        var sourceCaches = await _unitOfWork.QuerySourceCaches
            .GetQueryable()
            .Where(sc => sc.QueryId == queryId)
            .ToListAsync(cancellationToken);

        // If no source caches exist, needs refresh
        if (!sourceCaches.Any())
        {
            return true;
        }

        // If any source cache is expired, needs refresh
        return sourceCaches.Any(sc => sc.LastCheckedAt < cacheExpiry);
    }

    private async Task FetchAllSourcesAsync(
        Query query,
        string rawArtist,
        string rawTitle,
        int? knownDurationSeconds,
        CancellationToken cancellationToken)
    {
        _logger.LogDebug("Fetching metadata from all sources for {Artist} - {Title}", rawArtist, rawTitle);

        // Execute in parallel with proper error handling
        var mbTask = FetchMusicBrainzAsync(query, rawArtist, rawTitle, cancellationToken);
        var imvdbTask = FetchImvdbAsync(query, rawArtist, rawTitle, cancellationToken);

        await Task.WhenAll(mbTask, imvdbTask);

        // Only fetch YouTube if IMVDb didn't provide sources
        var imvdbHasSources = await CheckImvdbHasSourcesAsync(query.Id, cancellationToken);
        if (!imvdbHasSources)
        {
            _logger.LogDebug("IMVDb has no sources, fetching YouTube");
            await FetchYouTubeAsync(query, rawArtist, rawTitle, knownDurationSeconds, cancellationToken);
        }
        else
        {
            _logger.LogDebug("IMVDb has sources, skipping YouTube fetch");
        }
    }

    private async Task FetchMusicBrainzAsync(
        Query query,
        string artist,
        string title,
        CancellationToken cancellationToken)
    {
        try
        {
            _logger.LogDebug("Fetching MusicBrainz metadata for {Artist} - {Title}", artist, title);

            var response = await _mbClient.SearchRecordingsAsync(artist, title, limit: 5, cancellationToken);

            // Update source cache
            await UpdateSourceCacheAsync(query.Id, "musicbrainz", 
                response != null ? 200 : 404, 
                response != null ? $"Found {response.Count} recordings" : "No results",
                cancellationToken);

            if (response == null || !response.Recordings.Any())
            {
                _logger.LogDebug("No MusicBrainz results for {Artist} - {Title}", artist, title);
                return;
            }

            // Store recordings and create candidates
            // TODO: Implement full MusicBrainz entity storage and candidate creation
            _logger.LogInformation("Found {Count} MusicBrainz recordings for {Artist} - {Title}", 
                response.Recordings.Count, artist, title);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error fetching MusicBrainz metadata for {Artist} - {Title}", artist, title);
            await UpdateSourceCacheAsync(query.Id, "musicbrainz", null, $"Error: {ex.Message}", cancellationToken);
        }
    }

    private async Task FetchImvdbAsync(
        Query query,
        string artist,
        string title,
        CancellationToken cancellationToken)
    {
        try
        {
            _logger.LogDebug("Fetching IMVDb metadata for {Artist} - {Title}", artist, title);

            var searchQuery = $"{artist} {title}";
            var response = await _imvdbApi.SearchVideosAsync(searchQuery, page: 1, perPage: 5, cancellationToken);

            // Update source cache
            await UpdateSourceCacheAsync(query.Id, "imvdb",
                response != null ? 200 : 404,
                response != null ? $"Found {response.Results.Count} videos" : "No results",
                cancellationToken);

            if (response == null || !response.Results.Any())
            {
                _logger.LogDebug("No IMVDb results for {Artist} - {Title}", artist, title);
                return;
            }

            // Store videos and create candidates
            // TODO: Implement full IMVDb entity storage and candidate creation
            _logger.LogInformation("Found {Count} IMVDb videos for {Artist} - {Title}",
                response.Results.Count, artist, title);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error fetching IMVDb metadata for {Artist} - {Title}", artist, title);
            await UpdateSourceCacheAsync(query.Id, "imvdb", null, $"Error: {ex.Message}", cancellationToken);
        }
    }

    private async Task FetchYouTubeAsync(
        Query query,
        string artist,
        string title,
        int? knownDurationSeconds,
        CancellationToken cancellationToken)
    {
        try
        {
            _logger.LogDebug("Fetching YouTube metadata for {Artist} - {Title}", artist, title);

            // TODO: Implement YouTube search via yt-dlp
            // This will require extending IYtDlpService with search capabilities

            await UpdateSourceCacheAsync(query.Id, "youtube", 200, "Search not yet implemented", cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error fetching YouTube metadata for {Artist} - {Title}", artist, title);
            await UpdateSourceCacheAsync(query.Id, "youtube", null, $"Error: {ex.Message}", cancellationToken);
        }
    }

    private async Task<bool> CheckImvdbHasSourcesAsync(
        Guid queryId,
        CancellationToken cancellationToken)
    {
        var hasSources = await _unitOfWork.ImvdbVideos
            .GetQueryable()
            .Where(v => v.Candidates.Any(c => c.QueryId == queryId) && v.HasSources)
            .AnyAsync(cancellationToken);

        return hasSources;
    }

    private async Task UpdateSourceCacheAsync(
        Guid queryId,
        string source,
        int? httpStatus,
        string? notes,
        CancellationToken cancellationToken)
    {
        var sourceCache = await _unitOfWork.QuerySourceCaches
            .GetQueryable()
            .FirstOrDefaultAsync(sc => sc.QueryId == queryId && sc.Source == source, cancellationToken);

        if (sourceCache == null)
        {
            sourceCache = new QuerySourceCache
            {
                QueryId = queryId,
                Source = source,
                LastCheckedAt = DateTime.UtcNow,
                HttpStatus = httpStatus,
                Notes = notes,
                CreatedAt = DateTime.UtcNow,
                UpdatedAt = DateTime.UtcNow,
                IsActive = true
            };
            await _unitOfWork.QuerySourceCaches.AddAsync(sourceCache);
        }
        else
        {
            sourceCache.LastCheckedAt = DateTime.UtcNow;
            sourceCache.HttpStatus = httpStatus;
            sourceCache.Notes = notes;
            sourceCache.UpdatedAt = DateTime.UtcNow;
            await _unitOfWork.QuerySourceCaches.UpdateAsync(sourceCache);
        }

        await _unitOfWork.SaveChangesAsync();
    }

    private async Task<List<AggregatedCandidate>> AggregateAndRankCandidatesAsync(
        Guid queryId,
        CancellationToken cancellationToken)
    {
        // 1. Get all candidates from all sources
        var mbCandidates = await _unitOfWork.MbRecordingCandidates
            .GetQueryable()
            .Where(c => c.QueryId == queryId && c.Rank <= 5)
            .Include(c => c.Recording)
                .ThenInclude(r => r.Artists)
                    .ThenInclude(ra => ra.Artist)
            .Include(c => c.Recording)
                .ThenInclude(r => r.Releases)
                    .ThenInclude(rr => rr.Release)
                        .ThenInclude(rel => rel.ReleaseGroups)
                            .ThenInclude(rtg => rtg.ReleaseGroup)
            .ToListAsync(cancellationToken);

        var imvdbCandidates = await _unitOfWork.ImvdbVideoCandidates
            .GetQueryable()
            .Where(c => c.QueryId == queryId && c.Rank <= 5)
            .Include(c => c.Video)
                .ThenInclude(v => v.Artists)
                    .ThenInclude(va => va.Artist)
            .Include(c => c.Video)
                .ThenInclude(v => v.Sources)
            .ToListAsync(cancellationToken);

        var ytCandidates = await _unitOfWork.YtVideoCandidates
            .GetQueryable()
            .Where(c => c.QueryId == queryId && c.Rank <= 5)
            .Include(c => c.Video)
            .ToListAsync(cancellationToken);

        // 2. Convert to aggregated form and merge duplicates
        var aggregated = new List<AggregatedCandidate>();

        // Process IMVDb first (highest priority per spec)
        foreach (var candidate in imvdbCandidates)
        {
            aggregated.Add(MapImvdbToAggregated(candidate));
        }

        // Add MusicBrainz enrichment or new candidates
        foreach (var candidate in mbCandidates)
        {
            var existing = FindMatchingCandidate(aggregated, candidate.TitleNorm, candidate.ArtistNorm);
            if (existing != null)
            {
                EnrichWithMusicBrainz(existing, candidate);
            }
            else
            {
                aggregated.Add(MapMbToAggregated(candidate));
            }
        }

        // Add YouTube if not already matched
        foreach (var candidate in ytCandidates)
        {
            var existing = FindMatchingCandidate(aggregated, candidate.TitleNorm, candidate.ArtistNorm);
            if (existing == null)
            {
                aggregated.Add(MapYtToAggregated(candidate));
            }
        }

        // 3. Sort by overall confidence
        return aggregated
            .OrderByDescending(c => c.OverallConfidence)
            .ToList();
    }

    private AggregatedCandidate MapImvdbToAggregated(ImvdbVideoCandidate candidate)
    {
        var video = candidate.Video;
        var primaryArtist = video.Artists
            .Where(va => va.Role == "primary")
            .OrderBy(va => va.ArtistOrder)
            .FirstOrDefault();

        var featuredArtists = video.Artists
            .Where(va => va.Role == "featured")
            .OrderBy(va => va.ArtistOrder)
            .Select(va => va.Artist.Name)
            .ToList();

        return new AggregatedCandidate
        {
            Title = video.SongTitle ?? video.VideoTitle ?? string.Empty,
            Artist = primaryArtist?.Artist.Name ?? string.Empty,
            FeaturedArtists = featuredArtists.Any() ? string.Join(", ", featuredArtists) : null,
            Year = ParseYear(video.ReleaseDate),
            Director = video.DirectorCredit,
            OverallConfidence = candidate.OverallScore,
            PrimarySource = "imvdb",
            QueryId = candidate.QueryId,
            ImvdbVideoId = candidate.VideoId
        };
    }

    private AggregatedCandidate MapMbToAggregated(MbRecordingCandidate candidate)
    {
        var recording = candidate.Recording;
        var primaryArtist = recording.Artists
            .OrderBy(ra => ra.ArtistOrder)
            .FirstOrDefault();

        var releaseGroup = recording.Releases
            .SelectMany(rr => rr.Release.ReleaseGroups)
            .FirstOrDefault()?.ReleaseGroup;

        var year = ParseYear(releaseGroup?.FirstReleaseDate);

        return new AggregatedCandidate
        {
            Title = recording.Title,
            Artist = primaryArtist?.Artist.Name ?? string.Empty,
            Year = year,
            OverallConfidence = candidate.OverallScore,
            PrimarySource = "musicbrainz",
            QueryId = candidate.QueryId,
            MbRecordingId = candidate.RecordingId
        };
    }

    private AggregatedCandidate MapYtToAggregated(YtVideoCandidate candidate)
    {
        var video = candidate.Video;

        return new AggregatedCandidate
        {
            Title = video.Title,
            Artist = video.ChannelName ?? string.Empty,
            Year = ParseYear(video.PublishedAt),
            OverallConfidence = candidate.OverallScore,
            PrimarySource = "youtube",
            QueryId = candidate.QueryId,
            YtVideoId = candidate.VideoId
        };
    }

    private AggregatedCandidate? FindMatchingCandidate(
        List<AggregatedCandidate> candidates,
        string titleNorm,
        string artistNorm)
    {
        // Use simple string matching for now
        // Could be enhanced with fuzzy matching in the future
        return candidates.FirstOrDefault(c =>
            QueryNormalizer.NormalizeTitle(c.Title) == titleNorm &&
            QueryNormalizer.NormalizeArtist(c.Artist) == artistNorm);
    }

    private void EnrichWithMusicBrainz(AggregatedCandidate candidate, MbRecordingCandidate mbCandidate)
    {
        // Enrich existing candidate with MusicBrainz data
        var recording = mbCandidate.Recording;

        // Add year if not present
        if (!candidate.Year.HasValue)
        {
            var releaseGroup = recording.Releases
                .SelectMany(rr => rr.Release.ReleaseGroups)
                .FirstOrDefault()?.ReleaseGroup;
            candidate.Year = ParseYear(releaseGroup?.FirstReleaseDate);
        }

        // Add record label if not present
        if (string.IsNullOrEmpty(candidate.RecordLabel))
        {
            var label = recording.Releases
                .FirstOrDefault()?.Release.RecordLabel;
            if (!string.IsNullOrEmpty(label))
            {
                candidate.RecordLabel = label;
            }
        }

        // Store MusicBrainz ID for cross-linking
        candidate.MbRecordingId = mbCandidate.RecordingId;

        _logger.LogDebug("Enriched candidate {Title} with MusicBrainz data", candidate.Title);
    }

    private int? ParseYear(string? dateString)
    {
        if (string.IsNullOrEmpty(dateString))
        {
            return null;
        }

        // Try to extract year from various date formats (YYYY, YYYY-MM-DD, etc.)
        if (dateString.Length >= 4 && int.TryParse(dateString.Substring(0, 4), out var year))
        {
            if (year >= 1900 && year <= DateTime.UtcNow.Year + 1)
            {
                return year;
            }
        }

        return null;
    }
}