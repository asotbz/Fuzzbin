using System;
using System.Collections.Generic;
using System.Linq;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Core.Specifications;
using Fuzzbin.Core.Specifications.Queries;
using Fuzzbin.Core.Specifications.Videos;
using Fuzzbin.Services.Interfaces;

namespace Fuzzbin.Services;

public class VideoService : IVideoService
{
    private readonly IRepository<Video> _videoRepository;
    private readonly IUnitOfWork _unitOfWork;
    private readonly IEnumerable<IVideoUpdateNotifier> _updateNotifiers;
    private readonly ISearchService _searchService;

    public VideoService(
        IRepository<Video> videoRepository,
        IUnitOfWork unitOfWork,
        IEnumerable<IVideoUpdateNotifier> updateNotifiers,
        ISearchService searchService)
    {
        _videoRepository = videoRepository;
        _unitOfWork = unitOfWork;
        _updateNotifiers = updateNotifiers ?? Enumerable.Empty<IVideoUpdateNotifier>();
        _searchService = searchService;
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

    public async Task DeleteVideoAsync(Guid id, CancellationToken cancellationToken = default)
    {
        var video = await _videoRepository.GetByIdAsync(id);
        if (video != null)
        {
            await _videoRepository.DeleteAsync(video);
            await _unitOfWork.SaveChangesAsync();
            _searchService.InvalidateFacetsCache();
            await NotifyAsync(notifier => notifier.VideoDeletedAsync(id));
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
            includeCollections: false,
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
