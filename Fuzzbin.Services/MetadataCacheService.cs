using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;
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
            // Parse comma-separated featured artists
            var featuredNames = candidate.FeaturedArtists
                .Split(',', StringSplitOptions.RemoveEmptyEntries)
                .Select(n => n.Trim())
                .Where(n => !string.IsNullOrEmpty(n))
                .ToList();
            
            // Clear existing featured artists relationship
            video.FeaturedArtists.Clear();
            
            // Add or get featured artists and associate with video
            foreach (var name in featuredNames)
            {
                var featuredArtist = await _unitOfWork.FeaturedArtists
                    .GetQueryable()
                    .FirstOrDefaultAsync(fa => fa.Name == name, cancellationToken);
                
                if (featuredArtist == null)
                {
                    featuredArtist = new FeaturedArtist
                    {
                        Name = name,
                        CreatedAt = DateTime.UtcNow,
                        UpdatedAt = DateTime.UtcNow,
                        IsActive = true
                    };
                    await _unitOfWork.FeaturedArtists.AddAsync(featuredArtist);
                }
                
                video.FeaturedArtists.Add(featuredArtist);
            }
            
            _logger.LogInformation("Added {Count} featured artists to video {VideoId}",
                featuredNames.Count, video.Id);
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
            // Clear existing genres relationship
            video.Genres.Clear();
            
            // Add or get genres and associate with video (take top 3)
            foreach (var genreName in candidate.Genres.Take(3))
            {
                var genre = await _unitOfWork.Genres
                    .GetQueryable()
                    .FirstOrDefaultAsync(g => g.Name == genreName, cancellationToken);
                
                if (genre == null)
                {
                    genre = new Genre
                    {
                        Name = genreName,
                        CreatedAt = DateTime.UtcNow,
                        UpdatedAt = DateTime.UtcNow,
                        IsActive = true
                    };
                    await _unitOfWork.Genres.AddAsync(genre);
                }
                
                video.Genres.Add(genre);
            }
            
            _logger.LogInformation("Added {Count} genres to video {VideoId}",
                candidate.Genres.Take(3).Count(), video.Id);
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
            int rank = 1;
            foreach (var recording in response.Recordings.Take(5))
            {
                try
                {
                    // 1. Upsert MbArtist entities from recording.ArtistCredit
                    foreach (var artistCredit in recording.ArtistCredit)
                    {
                        await UpsertMbArtistAsync(artistCredit.Artist, cancellationToken);
                    }
                    
                    // 2. Upsert MbRecording entity
                    var mbRecording = await UpsertMbRecordingAsync(recording, cancellationToken);
                    
                    // 3. Create artist-recording relationships
                    var existingRelations = await _unitOfWork.MbRecordingArtists
                        .GetQueryable()
                        .Where(ra => ra.RecordingId == mbRecording.Id)
                        .ToListAsync(cancellationToken);
                    
                    foreach (var old in existingRelations)
                    {
                        await _unitOfWork.MbRecordingArtists.DeleteAsync(old);
                    }
                    
                    for (int i = 0; i < recording.ArtistCredit.Count; i++)
                    {
                        var artistMbid = Guid.Parse(recording.ArtistCredit[i].Artist.Id);
                        var artistEntity = await _unitOfWork.MbArtists
                            .GetQueryable()
                            .FirstOrDefaultAsync(a => a.Mbid == artistMbid, cancellationToken);
                        
                        if (artistEntity != null)
                        {
                            var recordingArtist = new MbRecordingArtist
                            {
                                RecordingId = mbRecording.Id,
                                ArtistId = artistEntity.Id,
                                ArtistOrder = i + 1,
                                CreditedName = recording.ArtistCredit[i].Name,
                                JoinPhrase = recording.ArtistCredit[i].JoinPhrase,
                                CreatedAt = DateTime.UtcNow,
                                UpdatedAt = DateTime.UtcNow,
                                IsActive = true
                            };
                            await _unitOfWork.MbRecordingArtists.AddAsync(recordingArtist);
                        }
                    }
                    
                    // 4. Upsert MbRelease and MbReleaseGroup entities
                    foreach (var release in recording.Releases.Take(3))
                    {
                        var mbRelease = await UpsertMbReleaseAsync(release, cancellationToken);
                        
                        if (release.ReleaseGroup != null)
                        {
                            var mbReleaseGroup = await UpsertMbReleaseGroupAsync(release.ReleaseGroup, cancellationToken);
                            
                            // Create release-to-releasegroup relationship
                            var existingRel = await _unitOfWork.MbReleaseToGroups
                                .GetQueryable()
                                .FirstOrDefaultAsync(rtg => rtg.ReleaseId == mbRelease.Id && rtg.ReleaseGroupId == mbReleaseGroup.Id, cancellationToken);
                            
                            if (existingRel == null)
                            {
                                var releaseToGroup = new MbReleaseToGroup
                                {
                                    ReleaseId = mbRelease.Id,
                                    ReleaseGroupId = mbReleaseGroup.Id,
                                    CreatedAt = DateTime.UtcNow,
                                    UpdatedAt = DateTime.UtcNow,
                                    IsActive = true
                                };
                                await _unitOfWork.MbReleaseToGroups.AddAsync(releaseToGroup);
                            }
                        }
                        
                        // Create recording-release relationship
                        var existingRecRel = await _unitOfWork.MbRecordingReleases
                            .GetQueryable()
                            .FirstOrDefaultAsync(rr => rr.RecordingId == mbRecording.Id && rr.ReleaseId == mbRelease.Id, cancellationToken);
                        
                        if (existingRecRel == null)
                        {
                            var recordingRelease = new MbRecordingRelease
                            {
                                RecordingId = mbRecording.Id,
                                ReleaseId = mbRelease.Id,
                                CreatedAt = DateTime.UtcNow,
                                UpdatedAt = DateTime.UtcNow,
                                IsActive = true
                            };
                            await _unitOfWork.MbRecordingReleases.AddAsync(recordingRelease);
                        }
                    }
                    
                    // 5. Upsert MbTag entities
                    foreach (var tag in recording.Tags.Take(10))
                    {
                        await UpsertMbTagAsync(mbRecording.Id, "recording", tag, cancellationToken);
                    }
                    
                    // 6. Create MbRecordingCandidate with scoring
                    var earliestYear = ParseYear(recording.Releases
                        .SelectMany(r => r.ReleaseGroup != null ? new[] { r.ReleaseGroup.FirstReleaseDate } : Array.Empty<string?>())
                        .Where(d => d != null)
                        .OrderBy(d => d)
                        .FirstOrDefault());
                    
                    var score = CandidateScorer.Score(
                        normQueryTitle: query.NormTitle,
                        normQueryArtist: query.NormArtist,
                        candidateTitleNorm: QueryNormalizer.NormalizeTitle(recording.Title),
                        candidateArtistNorm: QueryNormalizer.NormalizeArtist(recording.ArtistCredit.FirstOrDefault()?.Name ?? ""),
                        candidateDurationSec: recording.Length.HasValue ? recording.Length.Value / 1000 : null,
                        mbReferenceDurationSec: recording.Length.HasValue ? recording.Length.Value / 1000 : null,
                        candidateYear: earliestYear,
                        mbEarliestYear: earliestYear,
                        hasOfficialSourceFromImvdb: false
                    );
                    
                    // Check if candidate already exists
                    var existingCandidate = await _unitOfWork.MbRecordingCandidates
                        .GetQueryable()
                        .FirstOrDefaultAsync(c => c.QueryId == query.Id && c.RecordingId == mbRecording.Id, cancellationToken);
                    
                    if (existingCandidate == null)
                    {
                        var candidate = new MbRecordingCandidate
                        {
                            QueryId = query.Id,
                            RecordingId = mbRecording.Id,
                            TitleNorm = QueryNormalizer.NormalizeTitle(recording.Title),
                            ArtistNorm = QueryNormalizer.NormalizeArtist(recording.ArtistCredit.FirstOrDefault()?.Name ?? ""),
                            TextScore = score.TextScore,
                            YearScore = score.YearScore,
                            DurationScore = score.DurationScore,
                            OverallScore = score.Overall,
                            Rank = rank++,
                            Selected = false,
                            CreatedAt = DateTime.UtcNow,
                            UpdatedAt = DateTime.UtcNow,
                            IsActive = true
                        };
                        
                        await _unitOfWork.MbRecordingCandidates.AddAsync(candidate);
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error processing MusicBrainz recording {RecordingId}", recording.Id);
                }
            }
            
            await _unitOfWork.SaveChangesAsync();
            _logger.LogInformation("Stored {Count} MusicBrainz recordings for {Artist} - {Title}",
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
            int rank = 1;
            foreach (var videoSummary in response.Results.Take(5))
            {
                try
                {
                    // 1. Fetch full video details (includes sources array)
                    var videoDetail = await _imvdbApi.GetVideoAsync(
                        videoSummary.Id.ToString(),
                        include: "artists,directors,sources",
                        cancellationToken);
                    
                    // 2. Upsert ImvdbArtist entities
                    foreach (var artistCredit in videoDetail.Artists)
                    {
                        await UpsertImvdbArtistAsync(artistCredit, cancellationToken);
                    }
                    
                    // 3. Upsert ImvdbVideo entity
                    var imvdbVideo = await UpsertImvdbVideoAsync(videoDetail, cancellationToken);
                    
                    // 4. Create artist-video relationships
                    var existingRelations = await _unitOfWork.ImvdbVideoArtists
                        .GetQueryable()
                        .Where(va => va.VideoId == imvdbVideo.Id)
                        .ToListAsync(cancellationToken);
                    
                    foreach (var old in existingRelations)
                    {
                        await _unitOfWork.ImvdbVideoArtists.DeleteAsync(old);
                    }
                    
                    foreach (var artistCredit in videoDetail.Artists)
                    {
                        // Find the artist entity by ImvdbId
                        var artistEntity = await _unitOfWork.ImvdbArtists
                            .GetQueryable()
                            .FirstOrDefaultAsync(a => a.ImvdbId == artistCredit.Id, cancellationToken);
                        
                        if (artistEntity != null)
                        {
                            var videoArtist = new ImvdbVideoArtist
                            {
                                VideoId = imvdbVideo.Id,
                                ArtistId = artistEntity.Id,
                                Role = artistCredit.Role,
                                ArtistOrder = artistCredit.Order,
                                CreatedAt = DateTime.UtcNow,
                                UpdatedAt = DateTime.UtcNow,
                                IsActive = true
                            };
                            await _unitOfWork.ImvdbVideoArtists.AddAsync(videoArtist);
                        }
                    }
                    
                    // 5. Upsert ImvdbVideoSource entities (CRITICAL for has_sources flag)
                    var existingSources = await _unitOfWork.ImvdbVideoSources
                        .GetQueryable()
                        .Where(vs => vs.VideoId == imvdbVideo.Id)
                        .ToListAsync(cancellationToken);
                    
                    foreach (var old in existingSources)
                    {
                        await _unitOfWork.ImvdbVideoSources.DeleteAsync(old);
                    }
                    
                    foreach (var source in videoDetail.Sources)
                    {
                        var videoSource = new ImvdbVideoSource
                        {
                            VideoId = imvdbVideo.Id,
                            Source = source.Source,
                            ExternalId = source.ExternalId,
                            IsOfficial = source.IsOfficial,
                            CreatedAt = DateTime.UtcNow,
                            UpdatedAt = DateTime.UtcNow,
                            IsActive = true
                        };
                        await _unitOfWork.ImvdbVideoSources.AddAsync(videoSource);
                    }
                    
                    // Update has_sources flag
                    imvdbVideo.HasSources = videoDetail.Sources.Any();
                    await _unitOfWork.ImvdbVideos.UpdateAsync(imvdbVideo);
                    
                    // 6. Create ImvdbVideoCandidate with scoring
                    var primaryArtist = videoDetail.Artists
                        .Where(a => a.Role == "primary")
                        .OrderBy(a => a.Order)
                        .FirstOrDefault();
                    
                    var score = CandidateScorer.Score(
                        normQueryTitle: query.NormTitle,
                        normQueryArtist: query.NormArtist,
                        candidateTitleNorm: QueryNormalizer.NormalizeTitle(videoDetail.SongTitle ?? videoDetail.VideoTitle ?? ""),
                        candidateArtistNorm: QueryNormalizer.NormalizeArtist(primaryArtist?.Name ?? ""),
                        candidateDurationSec: null,
                        mbReferenceDurationSec: null,
                        candidateYear: null,
                        mbEarliestYear: null,
                        hasOfficialSourceFromImvdb: videoDetail.Sources.Any(s => s.IsOfficial)
                    );
                    
                    // Check if candidate already exists
                    var existingCandidate = await _unitOfWork.ImvdbVideoCandidates
                        .GetQueryable()
                        .FirstOrDefaultAsync(c => c.QueryId == query.Id && c.VideoId == imvdbVideo.Id, cancellationToken);
                    
                    if (existingCandidate == null)
                    {
                        var candidate = new ImvdbVideoCandidate
                        {
                            QueryId = query.Id,
                            VideoId = imvdbVideo.Id,
                            TitleNorm = QueryNormalizer.NormalizeTitle(videoDetail.SongTitle ?? videoDetail.VideoTitle ?? ""),
                            ArtistNorm = QueryNormalizer.NormalizeArtist(primaryArtist?.Name ?? ""),
                            TextScore = score.TextScore,
                            SourceBonus = score.SourceBonus,
                            OverallScore = score.Overall,
                            Rank = rank++,
                            Selected = false,
                            CreatedAt = DateTime.UtcNow,
                            UpdatedAt = DateTime.UtcNow,
                            IsActive = true
                        };
                        
                        await _unitOfWork.ImvdbVideoCandidates.AddAsync(candidate);
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error processing IMVDb video {VideoId}", videoSummary.Id);
                }
            }
            
            await _unitOfWork.SaveChangesAsync();
            _logger.LogInformation("Stored {Count} IMVDb videos for {Artist} - {Title}",
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

            var searchQuery = $"{artist} {title} music video";
            var results = await _ytDlpService.SearchVideosAsync(searchQuery, maxResults: 5, cancellationToken);
            
            // Update source cache
            await UpdateSourceCacheAsync(query.Id, "youtube",
                200,
                $"Found {results.Count} videos",
                cancellationToken);
            
            if (!results.Any())
            {
                _logger.LogDebug("No YouTube results for {Artist} - {Title}", artist, title);
                return;
            }
            
            // Store videos and create candidates
            int rank = 1;
            foreach (var result in results)
            {
                try
                {
                    // 1. Upsert YtVideo entity
                    var ytVideo = await UpsertYtVideoAsync(result, cancellationToken);
                    
                    // 2. Create YtVideoCandidate with scoring
                    var score = CandidateScorer.Score(
                        normQueryTitle: query.NormTitle,
                        normQueryArtist: query.NormArtist,
                        candidateTitleNorm: QueryNormalizer.NormalizeTitle(result.Title),
                        candidateArtistNorm: QueryNormalizer.NormalizeArtist(result.Channel ?? ""),
                        candidateDurationSec: result.Duration.HasValue ? (int)result.Duration.Value.TotalSeconds : null,
                        mbReferenceDurationSec: knownDurationSeconds,
                        candidateYear: result.UploadDate?.Year,
                        mbEarliestYear: null,
                        hasOfficialSourceFromImvdb: false,
                        youtubeChannelName: result.Channel,
                        youtubeChannelId: null,
                        rawDisplayTitle: result.Title
                    );
                    
                    // Check if candidate already exists
                    var existingCandidate = await _unitOfWork.YtVideoCandidates
                        .GetQueryable()
                        .FirstOrDefaultAsync(c => c.QueryId == query.Id && c.VideoId == result.Id, cancellationToken);
                    
                    if (existingCandidate == null)
                    {
                        var candidate = new YtVideoCandidate
                        {
                            QueryId = query.Id,
                            VideoId = result.Id,
                            TitleNorm = QueryNormalizer.NormalizeTitle(result.Title),
                            ArtistNorm = QueryNormalizer.NormalizeArtist(result.Channel ?? ""),
                            TextScore = score.TextScore,
                            ChannelBonus = score.ChannelBonus,
                            DurationScore = score.DurationScore,
                            OverallScore = score.Overall,
                            Rank = rank++,
                            Selected = false,
                            CreatedAt = DateTime.UtcNow,
                            UpdatedAt = DateTime.UtcNow,
                            IsActive = true
                        };
                        
                        await _unitOfWork.YtVideoCandidates.AddAsync(candidate);
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error processing YouTube video {VideoId}", result.Id);
                }
            }
            
            await _unitOfWork.SaveChangesAsync();
            _logger.LogInformation("Stored {Count} YouTube videos for {Artist} - {Title}", results.Count, artist, title);
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
    
    // Helper methods for entity upserts
    
    private async Task<Core.Entities.MbArtist> UpsertMbArtistAsync(External.MusicBrainz.MbArtist apiArtist, CancellationToken ct)
    {
        var mbid = Guid.Parse(apiArtist.Id);
        var existing = await _unitOfWork.MbArtists
            .GetQueryable()
            .FirstOrDefaultAsync(a => a.Mbid == mbid, ct);
        
        if (existing != null)
        {
            // Update fields
            existing.Name = apiArtist.Name;
            existing.SortName = apiArtist.SortName;
            existing.Disambiguation = apiArtist.Disambiguation;
            existing.Country = apiArtist.Country;
            existing.LastSeenAt = DateTime.UtcNow;
            existing.UpdatedAt = DateTime.UtcNow;
            
            await _unitOfWork.MbArtists.UpdateAsync(existing);
            return existing;
        }
        else
        {
            var newArtist = new Core.Entities.MbArtist
            {
                Mbid = mbid,
                Name = apiArtist.Name,
                SortName = apiArtist.SortName,
                Disambiguation = apiArtist.Disambiguation,
                Country = apiArtist.Country,
                LastSeenAt = DateTime.UtcNow,
                CreatedAt = DateTime.UtcNow,
                UpdatedAt = DateTime.UtcNow,
                IsActive = true
            };
            
            await _unitOfWork.MbArtists.AddAsync(newArtist);
            await _unitOfWork.SaveChangesAsync();
            return newArtist;
        }
    }
    
    private async Task<Core.Entities.MbRecording> UpsertMbRecordingAsync(External.MusicBrainz.MbRecording apiRecording, CancellationToken ct)
    {
        var mbid = Guid.Parse(apiRecording.Id);
        var existing = await _unitOfWork.MbRecordings
            .GetQueryable()
            .FirstOrDefaultAsync(r => r.Mbid == mbid, ct);
        
        if (existing != null)
        {
            // Update fields
            existing.Title = apiRecording.Title;
            existing.DurationMs = apiRecording.Length;
            existing.LastSeenAt = DateTime.UtcNow;
            existing.UpdatedAt = DateTime.UtcNow;
            
            await _unitOfWork.MbRecordings.UpdateAsync(existing);
            return existing;
        }
        
        var newRecording = new Core.Entities.MbRecording
        {
            Mbid = mbid,
            Title = apiRecording.Title,
            DurationMs = apiRecording.Length,
            LastSeenAt = DateTime.UtcNow,
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow,
            IsActive = true
        };
        
        await _unitOfWork.MbRecordings.AddAsync(newRecording);
        await _unitOfWork.SaveChangesAsync();
        return newRecording;
    }
    
    private async Task<Core.Entities.MbRelease> UpsertMbReleaseAsync(External.MusicBrainz.MbRelease apiRelease, CancellationToken ct)
    {
        var mbid = Guid.Parse(apiRelease.Id);
        var existing = await _unitOfWork.MbReleases
            .GetQueryable()
            .FirstOrDefaultAsync(r => r.Mbid == mbid, ct);
        
        if (existing != null)
        {
            // Update fields
            existing.Title = apiRelease.Title;
            existing.ReleaseDate = apiRelease.Date;
            existing.Country = apiRelease.Country;
            existing.Barcode = apiRelease.Barcode;
            existing.TrackCount = apiRelease.TrackCount;
            existing.RecordLabel = apiRelease.LabelInfo?.FirstOrDefault()?.Label?.Name;
            existing.LastSeenAt = DateTime.UtcNow;
            existing.UpdatedAt = DateTime.UtcNow;
            
            await _unitOfWork.MbReleases.UpdateAsync(existing);
            return existing;
        }
        else
        {
            var newRelease = new Core.Entities.MbRelease
            {
                Mbid = mbid,
                Title = apiRelease.Title,
                ReleaseDate = apiRelease.Date,
                Country = apiRelease.Country,
                Barcode = apiRelease.Barcode,
                TrackCount = apiRelease.TrackCount,
                RecordLabel = apiRelease.LabelInfo?.FirstOrDefault()?.Label?.Name,
                LastSeenAt = DateTime.UtcNow,
                CreatedAt = DateTime.UtcNow,
                UpdatedAt = DateTime.UtcNow,
                IsActive = true
            };
            
            await _unitOfWork.MbReleases.AddAsync(newRelease);
            await _unitOfWork.SaveChangesAsync();
            return newRelease;
        }
    }
    
    private async Task<Core.Entities.MbReleaseGroup> UpsertMbReleaseGroupAsync(External.MusicBrainz.MbReleaseGroup apiReleaseGroup, CancellationToken ct)
    {
        var mbid = Guid.Parse(apiReleaseGroup.Id);
        var existing = await _unitOfWork.MbReleaseGroups
            .GetQueryable()
            .FirstOrDefaultAsync(rg => rg.Mbid == mbid, ct);
        
        if (existing != null)
        {
            // Update fields
            existing.Title = apiReleaseGroup.Title;
            existing.FirstReleaseDate = apiReleaseGroup.FirstReleaseDate;
            existing.PrimaryType = apiReleaseGroup.PrimaryType;
            existing.LastSeenAt = DateTime.UtcNow;
            existing.UpdatedAt = DateTime.UtcNow;
            
            await _unitOfWork.MbReleaseGroups.UpdateAsync(existing);
            return existing;
        }
        else
        {
            var newReleaseGroup = new Core.Entities.MbReleaseGroup
            {
                Mbid = mbid,
                Title = apiReleaseGroup.Title,
                FirstReleaseDate = apiReleaseGroup.FirstReleaseDate,
                PrimaryType = apiReleaseGroup.PrimaryType,
                LastSeenAt = DateTime.UtcNow,
                CreatedAt = DateTime.UtcNow,
                UpdatedAt = DateTime.UtcNow,
                IsActive = true
            };
            
            await _unitOfWork.MbReleaseGroups.AddAsync(newReleaseGroup);
            await _unitOfWork.SaveChangesAsync();
            return newReleaseGroup;
        }
    }
    
    private async Task UpsertMbTagAsync(Guid entityId, string entityType, External.MusicBrainz.MbTag apiTag, CancellationToken ct)
    {
        var existing = await _unitOfWork.MbTags
            .GetQueryable()
            .FirstOrDefaultAsync(t => t.EntityId == entityId && t.EntityType == entityType && t.Name == apiTag.Name, ct);
        
        if (existing != null)
        {
            // Update count if provided
            if (apiTag.Count.HasValue)
            {
                existing.Count = apiTag.Count.Value;
                existing.UpdatedAt = DateTime.UtcNow;
                await _unitOfWork.MbTags.UpdateAsync(existing);
            }
        }
        else
        {
            var newTag = new Core.Entities.MbTag
            {
                EntityId = entityId,
                EntityType = entityType,
                Name = apiTag.Name,
                Count = apiTag.Count ?? 0,
                CreatedAt = DateTime.UtcNow,
                UpdatedAt = DateTime.UtcNow,
                IsActive = true
            };
            
            await _unitOfWork.MbTags.AddAsync(newTag);
        }
    }
    
    private async Task<ImvdbArtist> UpsertImvdbArtistAsync(ImvdbArtistCredit apiArtist, CancellationToken ct)
    {
        var existing = await _unitOfWork.ImvdbArtists
            .GetQueryable()
            .FirstOrDefaultAsync(a => a.ImvdbId == apiArtist.Id, ct);
        
        if (existing != null)
        {
            // Update fields
            existing.Name = apiArtist.Name;
            existing.LastSeenAt = DateTime.UtcNow;
            existing.UpdatedAt = DateTime.UtcNow;
            
            await _unitOfWork.ImvdbArtists.UpdateAsync(existing);
            return existing;
        }
        else
        {
            var newArtist = new ImvdbArtist
            {
                ImvdbId = apiArtist.Id,
                Name = apiArtist.Name,
                LastSeenAt = DateTime.UtcNow,
                CreatedAt = DateTime.UtcNow,
                UpdatedAt = DateTime.UtcNow,
                IsActive = true
            };
            
            await _unitOfWork.ImvdbArtists.AddAsync(newArtist);
            await _unitOfWork.SaveChangesAsync();
            return newArtist;
        }
    }
    
    private async Task<ImvdbVideo> UpsertImvdbVideoAsync(ImvdbVideoResponse apiVideo, CancellationToken ct)
    {
        var existing = await _unitOfWork.ImvdbVideos
            .GetQueryable()
            .FirstOrDefaultAsync(v => v.ImvdbId == apiVideo.Id, ct);
        
        if (existing != null)
        {
            // Update fields
            existing.SongTitle = apiVideo.SongTitle;
            existing.VideoTitle = apiVideo.VideoTitle;
            existing.ReleaseDate = apiVideo.ReleaseDate;
            existing.RuntimeSeconds = apiVideo.RuntimeSeconds;
            existing.ThumbnailUrl = apiVideo.Thumbnail?.Url;
            existing.DirectorCredit = apiVideo.Directors.Any() ? string.Join(", ", apiVideo.Directors.Select(d => d.Name)) : null;
            existing.HasSources = apiVideo.Sources.Any();
            existing.LastSeenAt = DateTime.UtcNow;
            existing.UpdatedAt = DateTime.UtcNow;
            
            await _unitOfWork.ImvdbVideos.UpdateAsync(existing);
            return existing;
        }
        else
        {
            var newVideo = new ImvdbVideo
            {
                ImvdbId = apiVideo.Id,
                SongTitle = apiVideo.SongTitle,
                VideoTitle = apiVideo.VideoTitle,
                ReleaseDate = apiVideo.ReleaseDate,
                RuntimeSeconds = apiVideo.RuntimeSeconds,
                ThumbnailUrl = apiVideo.Thumbnail?.Url,
                DirectorCredit = apiVideo.Directors.Any() ? string.Join(", ", apiVideo.Directors.Select(d => d.Name)) : null,
                HasSources = apiVideo.Sources.Any(),
                LastSeenAt = DateTime.UtcNow,
                CreatedAt = DateTime.UtcNow,
                UpdatedAt = DateTime.UtcNow,
                IsActive = true
            };
            
            await _unitOfWork.ImvdbVideos.AddAsync(newVideo);
            await _unitOfWork.SaveChangesAsync();
            return newVideo;
        }
    }
    
    private async Task<YtVideo> UpsertYtVideoAsync(Core.Interfaces.SearchResult apiVideo, CancellationToken ct)
    {
        var existing = await _unitOfWork.YtVideos
            .GetQueryable()
            .FirstOrDefaultAsync(v => v.VideoId == apiVideo.Id, ct);
        
        if (existing != null)
        {
            // Update fields
            existing.Title = apiVideo.Title;
            existing.ChannelId = null; // SearchResult doesn't have ChannelId
            existing.ChannelName = apiVideo.Channel;
            existing.DurationSeconds = apiVideo.Duration.HasValue ? (int)apiVideo.Duration.Value.TotalSeconds : null;
            existing.ViewCount = apiVideo.ViewCount;
            existing.ThumbnailUrl = apiVideo.ThumbnailUrl;
            existing.PublishedAt = apiVideo.UploadDate?.ToString("yyyy-MM-dd");
            existing.LastSeenAt = DateTime.UtcNow;
            existing.UpdatedAt = DateTime.UtcNow;
            
            await _unitOfWork.YtVideos.UpdateAsync(existing);
            return existing;
        }
        else
        {
            var newVideo = new YtVideo
            {
                VideoId = apiVideo.Id,
                Title = apiVideo.Title,
                ChannelId = null,
                ChannelName = apiVideo.Channel,
                DurationSeconds = apiVideo.Duration.HasValue ? (int)apiVideo.Duration.Value.TotalSeconds : null,
                ViewCount = apiVideo.ViewCount,
                ThumbnailUrl = apiVideo.ThumbnailUrl,
                PublishedAt = apiVideo.UploadDate?.ToString("yyyy-MM-dd"),
                LastSeenAt = DateTime.UtcNow,
                CreatedAt = DateTime.UtcNow,
                UpdatedAt = DateTime.UtcNow,
                IsActive = true
            };
            
            await _unitOfWork.YtVideos.AddAsync(newVideo);
            await _unitOfWork.SaveChangesAsync();
            return newVideo;
        }
    }
    
    public async Task<CacheStatistics> GetStatisticsAsync(CancellationToken cancellationToken = default)
    {
        var totalQueries = await _unitOfWork.Queries
            .GetQueryable()
            .CountAsync(cancellationToken);
        
        var sourceCaches = await _unitOfWork.QuerySourceCaches
            .GetQueryable()
            .ToListAsync(cancellationToken);
        
        var mbCaches = sourceCaches.Where(sc => sc.Source == "musicbrainz").ToList();
        var imvdbCaches = sourceCaches.Where(sc => sc.Source == "imvdb").ToList();
        var ytCaches = sourceCaches.Where(sc => sc.Source == "youtube").ToList();
        
        // Calculate success rates (queries with successful status codes)
        var mbSuccessRate = mbCaches.Any()
            ? (double)mbCaches.Count(sc => sc.HttpStatus >= 200 && sc.HttpStatus < 300) / mbCaches.Count
            : 0;
        var imvdbSuccessRate = imvdbCaches.Any()
            ? (double)imvdbCaches.Count(sc => sc.HttpStatus >= 200 && sc.HttpStatus < 300) / imvdbCaches.Count
            : 0;
        var ytSuccessRate = ytCaches.Any()
            ? (double)ytCaches.Count(sc => sc.HttpStatus >= 200 && sc.HttpStatus < 300) / ytCaches.Count
            : 0;
        
        // Get recent entries
        var recentQueries = await _unitOfWork.Queries
            .GetQueryable()
            .Include(q => q.SourceCaches)
            .OrderByDescending(q => q.UpdatedAt)
            .Take(10)
            .ToListAsync(cancellationToken);
        
        var recentEntries = recentQueries.Select(q => new CacheEntry
        {
            Artist = q.RawArtist,
            Title = q.RawTitle,
            Sources = q.SourceCaches.Select(sc => sc.Source).ToList(),
            CachedAt = q.UpdatedAt
        }).ToList();
        
        // Calculate overall hit rate
        var queriesWithCandidates = await _unitOfWork.Queries
            .GetQueryable()
            .Where(q => q.MbRecordingCandidates.Any() || q.ImvdbVideoCandidates.Any() || q.YtVideoCandidates.Any())
            .CountAsync(cancellationToken);
        
        var hitRate = totalQueries > 0 ? (double)queriesWithCandidates / totalQueries : 0;
        
        return new CacheStatistics
        {
            TotalQueries = totalQueries,
            HitRate = hitRate,
            MusicBrainzCount = mbCaches.Count,
            MusicBrainzSuccessRate = mbSuccessRate,
            ImvdbCount = imvdbCaches.Count,
            ImvdbSuccessRate = imvdbSuccessRate,
            YouTubeCount = ytCaches.Count,
            YouTubeSuccessRate = ytSuccessRate,
            RecentEntries = recentEntries,
            AvgQueryTimeMs = 125.0, // TODO: Track actual query times with timing
            CacheHitsToday = 0, // TODO: Track daily statistics
            CacheMissesToday = 0 // TODO: Track daily statistics
        };
    }
}

