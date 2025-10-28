using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Core.Specifications;
using Fuzzbin.Core.Specifications.Queries;
using Fuzzbin.Core.Specifications.Videos;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;
using Microsoft.Extensions.Logging;

namespace Fuzzbin.Services;

public class VideoService : IVideoService
{
    private const string RecycleBinFolderName = ".trash";

    private readonly IRepository<Video> _videoRepository;
    private readonly IUnitOfWork _unitOfWork;
    private readonly IEnumerable<IVideoUpdateNotifier> _updateNotifiers;
    private readonly ISearchService _searchService;
    private readonly ILibraryPathManager _libraryPathManager;
    private readonly ILogger<VideoService> _logger;
    private readonly IActivityLogService _activityLogService;

    public VideoService(
        IRepository<Video> videoRepository,
        IUnitOfWork unitOfWork,
        IEnumerable<IVideoUpdateNotifier> updateNotifiers,
        ISearchService searchService,
        ILibraryPathManager libraryPathManager,
        ILogger<VideoService> logger,
        IActivityLogService activityLogService)
    {
        _videoRepository = videoRepository;
        _unitOfWork = unitOfWork;
        _updateNotifiers = updateNotifiers ?? Enumerable.Empty<IVideoUpdateNotifier>();
        _searchService = searchService;
        _libraryPathManager = libraryPathManager;
        _logger = logger;
        _activityLogService = activityLogService;
    }

    public async Task<List<Video>> GetAllVideosAsync(CancellationToken cancellationToken = default)
    {
        var results = new List<Video>();
        var query = new VideoQuery
        {
            Page = 1,
            PageSize = 200,
            SortBy = VideoSortOption.Title,
            SortDirection = SortDirection.Ascending
        };

        while (true)
        {
            var specification = new VideoQuerySpecification(
                query,
                includeGenres: true,
                includeTags: true,
                includeFeaturedArtists: true,
                includeCollections: true);

            var page = await _videoRepository.ListAsync(specification);
            results.AddRange(page);

            if (page.Count < query.PageSize)
            {
                break;
            }

            query.Page += 1;
        }

        return results;
    }

    public async Task<Video?> GetVideoByIdAsync(Guid id, CancellationToken cancellationToken = default)
    {
        var specification = new VideoByIdSpecification(id);
        return await _videoRepository.FirstOrDefaultAsync(specification);
    }

    public async Task<Video> CreateVideoAsync(Video video, CancellationToken cancellationToken = default)
    {
        await _videoRepository.AddAsync(video);
        await _unitOfWork.SaveChangesAsync();
        _searchService.InvalidateFacetsCache();
        var notification = await BuildNotificationAsync(video.Id);
        if (notification != null)
        {
            await NotifyAsync(notifier => notifier.VideoCreatedAsync(notification));
        }
        return video;
    }

    public async Task<Video> UpdateVideoAsync(Video video, CancellationToken cancellationToken = default)
    {
        await _videoRepository.UpdateAsync(video);
        await _unitOfWork.SaveChangesAsync();
        _searchService.InvalidateFacetsCache();
        var notification = await BuildNotificationAsync(video.Id);
        if (notification != null)
        {
            await NotifyAsync(notifier => notifier.VideoUpdatedAsync(notification));
        }
        return video;
    }

    public async Task<VideoBatchUpdateResult> UpdateVideosAsync(IEnumerable<Video> videos, CancellationToken cancellationToken = default)
    {
        if (videos == null)
        {
            return new VideoBatchUpdateResult();
        }

        var materialized = videos.Where(v => v != null).Distinct().ToList();
        var result = new VideoBatchUpdateResult
        {
            RequestedCount = materialized.Count
        };

        if (materialized.Count == 0)
        {
            return result;
        }

        var successful = new List<Video>();

        foreach (var video in materialized)
        {
            try
            {
                await _videoRepository.UpdateAsync(video);
                successful.Add(video);
                result.UpdatedCount++;
            }
            catch (Exception ex)
            {
                result.Failures.Add(new VideoBatchUpdateResult.VideoUpdateFailure
                {
                    VideoId = video.Id,
                    Title = video.Title,
                    Error = ex.Message
                });
                _logger.LogError(ex, "Failed to update video {VideoId}", video.Id);
            }
        }

        if (successful.Count > 0)
        {
            await _unitOfWork.SaveChangesAsync();
            _searchService.InvalidateFacetsCache();

            foreach (var video in successful)
            {
                // Skip notifying for videos that failed
                if (result.Failures.Any(f => f.VideoId == video.Id))
                {
                    continue;
                }

                var notification = await BuildNotificationAsync(video.Id);
                if (notification != null)
                {
                    await NotifyAsync(notifier => notifier.VideoUpdatedAsync(notification));
                }
            }
        }

        return result;
    }

    public async Task DeleteVideoAsync(Guid id, bool deleteFiles = true, CancellationToken cancellationToken = default)
    {
        var video = await _videoRepository.GetByIdAsync(id);
        if (video == null)
        {
            await LogActivityAsync(() => _activityLogService.LogErrorAsync(
                ActivityCategories.Video,
                ActivityActions.Delete,
                "Video not found",
                entityType: nameof(Video),
                entityId: id.ToString(),
                entityName: null,
                details: "Attempted to delete missing video"));
            return;
        }

        var displayName = GetVideoDisplayName(video);

        try
        {
            await DeleteVideoInternalAsync(video, deleteFiles, cancellationToken);
            await _unitOfWork.SaveChangesAsync();
            _searchService.InvalidateFacetsCache();
            await NotifyAsync(notifier => notifier.VideoDeletedAsync(id));

            await LogActivityAsync(() => _activityLogService.LogSuccessAsync(
                ActivityCategories.Video,
                ActivityActions.Delete,
                entityType: nameof(Video),
                entityId: video.Id.ToString(),
                entityName: displayName,
                details: deleteFiles
                    ? $"Deleted video {displayName} and moved files to recycle bin"
                    : $"Deleted video {displayName} (files retained)"));
        }
        catch (Exception ex)
        {
            await LogActivityAsync(() => _activityLogService.LogErrorAsync(
                ActivityCategories.Video,
                ActivityActions.Delete,
                ex.Message,
                entityType: nameof(Video),
                entityId: video.Id.ToString(),
                entityName: displayName,
                details: "Failed to delete video"));
            throw;
        }
    }

    public async Task<VideoDeletionResult> DeleteVideosAsync(IEnumerable<Guid> ids, bool deleteFiles = true, CancellationToken cancellationToken = default)
    {
        if (ids == null)
        {
            return new VideoDeletionResult();
        }

        var uniqueIds = ids.Where(id => id != Guid.Empty).Distinct().ToList();
        var result = new VideoDeletionResult
        {
            RequestedCount = uniqueIds.Count
        };

        if (uniqueIds.Count == 0)
        {
            return result;
        }

        var deletedIds = new List<Guid>();
        var deletedSummaries = new List<(Guid VideoId, string DisplayName)>();

        foreach (var videoId in uniqueIds)
        {
            Video? currentVideo = null;
            try
            {
                currentVideo = await _videoRepository.GetByIdAsync(videoId);
                if (currentVideo == null)
                {
                    result.Failures.Add(new VideoDeletionResult.VideoDeletionFailure
                    {
                        VideoId = videoId,
                        Title = "Unknown video",
                        Error = "Video not found"
                    });
                    await LogActivityAsync(() => _activityLogService.LogErrorAsync(
                        ActivityCategories.Video,
                        ActivityActions.Delete,
                        "Video not found",
                        entityType: nameof(Video),
                        entityId: videoId.ToString(),
                        entityName: null,
                        details: "Attempted to delete missing video"));
                    continue;
                }

                var displayName = GetVideoDisplayName(currentVideo);

                await DeleteVideoInternalAsync(currentVideo, deleteFiles, cancellationToken);
                deletedIds.Add(videoId);
                deletedSummaries.Add((videoId, displayName));
                result.DeletedCount++;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to delete video {VideoId}", videoId);
                result.Failures.Add(new VideoDeletionResult.VideoDeletionFailure
                {
                    VideoId = videoId,
                    Title = currentVideo?.Title ?? "Unknown",
                    Error = ex.Message
                });
                var displayName = currentVideo != null ? GetVideoDisplayName(currentVideo) : videoId.ToString();
                await LogActivityAsync(() => _activityLogService.LogErrorAsync(
                    ActivityCategories.Video,
                    ActivityActions.Delete,
                    ex.Message,
                    entityType: nameof(Video),
                    entityId: videoId.ToString(),
                    entityName: displayName,
                    details: "Failed to delete video"));
            }
        }

        if (deletedIds.Count > 0)
        {
            await _unitOfWork.SaveChangesAsync();
            _searchService.InvalidateFacetsCache();

            foreach (var videoId in deletedIds)
            {
                await NotifyAsync(notifier => notifier.VideoDeletedAsync(videoId));
            }

            foreach (var summary in deletedSummaries)
            {
                await LogActivityAsync(() => _activityLogService.LogSuccessAsync(
                    ActivityCategories.Video,
                    ActivityActions.Delete,
                    entityType: nameof(Video),
                    entityId: summary.VideoId.ToString(),
                    entityName: summary.DisplayName,
                    details: deleteFiles
                        ? $"Deleted video {summary.DisplayName} and moved files to recycle bin"
                        : $"Deleted video {summary.DisplayName} (files retained)"));
            }
        }

        return result;
    }

    private async Task DeleteVideoInternalAsync(Video video, bool deleteFiles, CancellationToken cancellationToken)
    {
        if (deleteFiles)
        {
            await MoveMediaToRecycleBinAsync(video, cancellationToken).ConfigureAwait(false);
        }

        await _videoRepository.DeleteAsync(video);
    }

    private async Task MoveMediaToRecycleBinAsync(Video video, CancellationToken cancellationToken)
    {
        try
        {
            var videoRoot = await _libraryPathManager.GetVideoRootAsync(cancellationToken).ConfigureAwait(false);
            var metadataRoot = await _libraryPathManager.GetMetadataRootAsync(cancellationToken).ConfigureAwait(false);
            var recycleRoot = Path.Combine(videoRoot, RecycleBinFolderName);
            _libraryPathManager.EnsureDirectoryExists(recycleRoot);

            MoveFileToRecycleBin(ResolveFullPath(video.FilePath, videoRoot), recycleRoot);
            MoveFileToRecycleBin(ResolveFullPath(video.NfoPath, metadataRoot), recycleRoot);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to move media for video {VideoId} to recycle bin", video.Id);
        }
    }

    private static string? ResolveFullPath(string? storedPath, string baseRoot)
    {
        if (string.IsNullOrWhiteSpace(storedPath))
        {
            return null;
        }

        var candidates = new List<string>();

        if (Path.IsPathRooted(storedPath))
        {
            candidates.Add(storedPath);
        }

        if (!string.IsNullOrWhiteSpace(baseRoot))
        {
            candidates.Add(Path.Combine(baseRoot, storedPath));
        }

        foreach (var candidate in candidates)
        {
            try
            {
                var fullPath = Path.GetFullPath(candidate);
                if (File.Exists(fullPath))
                {
                    return fullPath;
                }
            }
            catch
            {
                // Ignore malformed paths.
            }
        }

        return null;
    }

    private void MoveFileToRecycleBin(string? fullPath, string recycleRoot)
    {
        if (string.IsNullOrWhiteSpace(fullPath) || !File.Exists(fullPath))
        {
            return;
        }

        try
        {
            _libraryPathManager.EnsureDirectoryExists(recycleRoot);

            var fileName = Path.GetFileName(fullPath);
            var destination = Path.Combine(recycleRoot, fileName);

            if (File.Exists(destination))
            {
                var name = Path.GetFileNameWithoutExtension(fileName);
                var extension = Path.GetExtension(fileName);
                destination = Path.Combine(recycleRoot, $"{name}_{DateTime.UtcNow:yyyyMMddHHmmssfff}{extension}");
            }

#if NET6_0_OR_GREATER
            File.Move(fullPath, destination, false);
#else
            File.Move(fullPath, destination);
#endif
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to move file {FilePath} to recycle bin", fullPath);
        }
    }

    public async Task<List<Video>> GetVideosByArtistAsync(string artist, CancellationToken cancellationToken = default)
    {
        var specification = new VideosByArtistSpecification(artist);
        var results = await _videoRepository.ListAsync(specification);
        return new List<Video>(results);
    }

    public async Task<List<Video>> GetVideosByGenreAsync(Guid genreId, CancellationToken cancellationToken = default)
    {
        var specification = new VideosByGenreSpecification(genreId);
        var results = await _videoRepository.ListAsync(specification);
        return new List<Video>(results);
    }

    public async Task<List<Video>> GetRecentVideosAsync(int count = 10, CancellationToken cancellationToken = default)
    {
        var specification = new VideoRecentImportsSpecification(count);
        var results = await _videoRepository.ListAsync(specification);
        return new List<Video>(results);
    }

    private static string GetVideoDisplayName(Video video)
    {
        if (!string.IsNullOrWhiteSpace(video.Artist) && !string.IsNullOrWhiteSpace(video.Title))
        {
            return $"{video.Artist} - {video.Title}";
        }

        if (!string.IsNullOrWhiteSpace(video.Title))
        {
            return video.Title;
        }

        return video.Id.ToString();
    }

    private async Task LogActivityAsync(Func<Task> logOperation)
    {
        try
        {
            await logOperation();
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to write activity log entry for video service operation");
        }
    }

    public async Task<PagedResult<Video>> GetVideosAsync(VideoQuery query, CancellationToken cancellationToken = default)
    {
        if (query == null)
        {
            throw new ArgumentNullException(nameof(query));
        }

        var listingSpecification = new VideoQuerySpecification(
            query,
            includeGenres: true,
            includeTags: true,
            includeFeaturedArtists: true,
            includeCollections: true,
            applyPaging: true);

        var countSpecification = new VideoQuerySpecification(
            query,
            includeGenres: false,
            includeTags: false,
            includeFeaturedArtists: false,
            includeCollections: false,
            applyPaging: false);

        var items = await _videoRepository.ListAsync(listingSpecification);
        var total = await _videoRepository.CountAsync(countSpecification);

        return new PagedResult<Video>(items, total, query.Page, query.PageSize);
    }

    public async Task<IReadOnlyList<Video>> GetVideosUnpagedAsync(VideoQuery query, CancellationToken cancellationToken = default)
    {
        if (query == null)
        {
            throw new ArgumentNullException(nameof(query));
        }

        var accumulator = new List<Video>();
        var workingQuery = CloneQuery(query);
        workingQuery.Page = 1;
        workingQuery.PageSize = workingQuery.PageSize <= 0 ? 200 : Math.Min(workingQuery.PageSize, 200);

        while (true)
        {
            var page = await GetVideosAsync(workingQuery, cancellationToken);
            if (page.Items.Count == 0)
            {
                break;
            }

            accumulator.AddRange(page.Items);

            if (accumulator.Count >= page.TotalCount || page.Items.Count < workingQuery.PageSize)
            {
                break;
            }

            workingQuery.Page += 1;
        }

        return accumulator;
    }

    private static VideoQuery CloneQuery(VideoQuery source)
    {
        return new VideoQuery
        {
            Search = source.Search,
            GenreIds = new List<Guid>(source.GenreIds),
            TagIds = new List<Guid>(source.TagIds),
            CollectionIds = new List<Guid>(source.CollectionIds),
            GenreNames = new List<string>(source.GenreNames),
            ArtistNames = new List<string>(source.ArtistNames),
            Formats = new List<string>(source.Formats),
            Resolutions = new List<string>(source.Resolutions),
            Years = new List<int>(source.Years),
            YearFrom = source.YearFrom,
            YearTo = source.YearTo,
            DurationFrom = source.DurationFrom,
            DurationTo = source.DurationTo,
            MinRating = source.MinRating,
            HasFile = source.HasFile,
            MissingMetadata = source.MissingMetadata,
            HasCollections = source.HasCollections,
            HasYouTubeId = source.HasYouTubeId,
            HasImvdbId = source.HasImvdbId,
            AddedAfter = source.AddedAfter,
            AddedBefore = source.AddedBefore,
            IncludeInactive = source.IncludeInactive,
            SortBy = source.SortBy,
            SortDirection = source.SortDirection,
            Page = source.Page,
            PageSize = source.PageSize
        };
    }

    private async Task NotifyAsync(Func<IVideoUpdateNotifier, Task> callback)
    {
        foreach (var notifier in _updateNotifiers)
        {
            await callback(notifier);
        }
    }

    private async Task<VideoUpdateNotification?> BuildNotificationAsync(Guid videoId)
    {
        var spec = new VideoByIdSpecification(videoId, includeRelations: true, trackForUpdate: false);
        var entity = await _videoRepository.FirstOrDefaultAsync(spec);
        if (entity == null)
        {
            return null;
        }

        var genres = entity.Genres?.Select(g => g.Name).Where(name => !string.IsNullOrWhiteSpace(name)).Distinct(StringComparer.OrdinalIgnoreCase).ToArray() ?? Array.Empty<string>();
        var tags = entity.Tags?.Select(t => t.Name).Where(name => !string.IsNullOrWhiteSpace(name)).Distinct(StringComparer.OrdinalIgnoreCase).ToArray() ?? Array.Empty<string>();

        return new VideoUpdateNotification(
            entity.Id,
            entity.Title,
            entity.Artist,
            entity.Album,
            entity.Year,
            entity.Duration,
            entity.Format,
            entity.ThumbnailPath,
            entity.ImportedAt,
            entity.UpdatedAt,
            genres,
            tags);
    }
}
