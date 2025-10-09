using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Core.Specifications;
using Fuzzbin.Core.Specifications.Queries;
using Fuzzbin.Core.Specifications.Videos;
using Fuzzbin.Data.Context;
using SearchContracts = Fuzzbin.Services.Interfaces;

namespace Fuzzbin.Services;

public class SearchService : SearchContracts.ISearchService
{
    private const string FacetCacheKey = "Fuzzbin:SearchFacets";

    private readonly ApplicationDbContext _context;
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILogger<SearchService> _logger;
    private readonly IMemoryCache _cache;

    public SearchService(
        ApplicationDbContext context,
        IUnitOfWork unitOfWork,
        ILogger<SearchService> logger,
        IMemoryCache cache)
    {
        _context = context ?? throw new ArgumentNullException(nameof(context));
        _unitOfWork = unitOfWork ?? throw new ArgumentNullException(nameof(unitOfWork));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
        _cache = cache ?? throw new ArgumentNullException(nameof(cache));
    }

    public async Task<SearchContracts.SearchResult> SearchAsync(SearchContracts.SearchQuery query)
    {
        if (query == null)
        {
            throw new ArgumentNullException(nameof(query));
        }

        var videoQuery = BuildVideoQuery(query);

        var listingSpecification = new VideoQuerySpecification(
            videoQuery,
            includeGenres: true,
            includeTags: true,
            includeFeaturedArtists: true,
            includeCollections: true,
            applyPaging: true);

        var countSpecification = new VideoQuerySpecification(
            videoQuery,
            includeGenres: false,
            includeTags: false,
            includeFeaturedArtists: false,
            includeCollections: false,
            applyPaging: false);

        var videos = await _unitOfWork.Videos.ListAsync(listingSpecification);
        var totalCount = await _unitOfWork.Videos.CountAsync(countSpecification);

        IReadOnlyList<Video> facetSource;
        if (totalCount <= videoQuery.PageSize)
        {
            facetSource = videos;
        }
        else
        {
            var facetSpecification = new VideoQuerySpecification(
                videoQuery,
                includeGenres: true,
                includeTags: false,
                includeFeaturedArtists: false,
                includeCollections: true,
                applyPaging: false);

            facetSource = await _unitOfWork.Videos.ListAsync(facetSpecification);
        }

        var facets = GenerateFacets(facetSource);

        return new SearchContracts.SearchResult
        {
            Videos = videos.ToList(),
            TotalCount = totalCount,
            PageNumber = videoQuery.Page,
            PageSize = videoQuery.PageSize,
            Facets = facets
        };
    }

    public async Task<List<SavedSearch>> GetSavedSearchesAsync()
    {
        return await _context.Set<SavedSearch>()
            .AsNoTracking()
            .Where(s => s.IsActive)
            .OrderBy(s => s.Name)
            .ToListAsync();
    }

    public async Task<SavedSearch> GetSavedSearchAsync(Guid id)
    {
        var search = await _context.Set<SavedSearch>()
            .AsNoTracking()
            .FirstOrDefaultAsync(s => s.Id == id && s.IsActive);

        if (search == null)
        {
            throw new KeyNotFoundException($"Saved search with ID {id} not found");
        }

        return search;
    }

    public async Task<SavedSearch> SaveSearchAsync(SavedSearch savedSearch)
    {
        if (savedSearch == null)
        {
            throw new ArgumentNullException(nameof(savedSearch));
        }

        if (savedSearch.Id == Guid.Empty)
        {
            savedSearch.Id = Guid.NewGuid();
            savedSearch.CreatedAt = DateTime.UtcNow;
            await _context.Set<SavedSearch>().AddAsync(savedSearch);
        }
        else
        {
            savedSearch.UpdatedAt = DateTime.UtcNow;
            _context.Set<SavedSearch>().Update(savedSearch);
        }

        await _context.SaveChangesAsync();
        return savedSearch;
    }

    public async Task DeleteSavedSearchAsync(Guid id)
    {
        var search = await GetSavedSearchAsync(id);
        search.IsActive = false;
        search.UpdatedAt = DateTime.UtcNow;
        _context.Set<SavedSearch>().Update(search);
        await _context.SaveChangesAsync();
    }

    public async Task<SearchContracts.SearchFacets> GetSearchFacetsAsync()
    {
        if (_cache.TryGetValue(FacetCacheKey, out SearchContracts.SearchFacets? cachedFacets) && cachedFacets is not null)
        {
            return cachedFacets;
        }

        var facets = await BuildFacetSnapshotAsync();
        _cache.Set(
            FacetCacheKey,
            facets,
            new MemoryCacheEntryOptions
            {
                AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(10),
                SlidingExpiration = TimeSpan.FromMinutes(3)
            });

        return facets;
    }

    public void InvalidateFacetsCache()
    {
        _cache.Remove(FacetCacheKey);
    }

    private static SearchContracts.SearchFacets GenerateFacets(IEnumerable<Video> videos)
    {
        var videoList = videos.Where(v => v != null).ToList();

        var facets = new SearchContracts.SearchFacets
        {
            Artists = videoList
                .Where(v => !string.IsNullOrWhiteSpace(v.Artist))
                .GroupBy(v => v.Artist!)
                .ToDictionary(g => g.Key, g => g.Count(), StringComparer.OrdinalIgnoreCase),

            Genres = videoList
                .SelectMany(v => v.Genres ?? Enumerable.Empty<Genre>())
                .Where(g => g != null && g.IsActive && !string.IsNullOrWhiteSpace(g.Name))
                .GroupBy(g => g.Name)
                .ToDictionary(g => g.Key, g => g.Count(), StringComparer.OrdinalIgnoreCase),

            Formats = videoList
                .Where(v => !string.IsNullOrWhiteSpace(v.Format))
                .GroupBy(v => v.Format!)
                .ToDictionary(g => g.Key, g => g.Count(), StringComparer.OrdinalIgnoreCase),

            Resolutions = videoList
                .Where(v => !string.IsNullOrWhiteSpace(v.Resolution))
                .GroupBy(v => v.Resolution!)
                .ToDictionary(g => g.Key, g => g.Count(), StringComparer.OrdinalIgnoreCase),

            Years = videoList
                .Where(v => v.Year.HasValue)
                .GroupBy(v => v.Year!.Value.ToString())
                .ToDictionary(g => g.Key, g => g.Count()),

            Collections = videoList
                .SelectMany(v => v.CollectionVideos ?? Enumerable.Empty<CollectionVideo>())
                .Where(cv => cv.Collection != null && cv.Collection.IsActive && !string.IsNullOrWhiteSpace(cv.Collection.Name))
                .GroupBy(cv => cv.Collection!.Name)
                .ToDictionary(g => g.Key, g => g.Count(), StringComparer.OrdinalIgnoreCase)
        };

        return facets;
    }

    private async Task<SearchContracts.SearchFacets> BuildFacetSnapshotAsync()
    {
        var baseQuery = _context.Videos
            .AsNoTracking()
            .Where(v => v.IsActive);

        var artistTask = baseQuery
            .Where(v => !string.IsNullOrWhiteSpace(v.Artist))
            .GroupBy(v => v.Artist!)
            .Select(g => new { g.Key, Count = g.Count() })
            .ToDictionaryAsync(x => x.Key, x => x.Count, StringComparer.OrdinalIgnoreCase);

        var genreTask = baseQuery
            .SelectMany(v => v.Genres
                .Where(g => g.IsActive && !string.IsNullOrWhiteSpace(g.Name))
                .Select(g => g.Name!))
            .GroupBy(name => name)
            .Select(g => new { Key = g.Key, Count = g.Count() })
            .ToDictionaryAsync(x => x.Key, x => x.Count, StringComparer.OrdinalIgnoreCase);

        var formatTask = baseQuery
            .Where(v => !string.IsNullOrWhiteSpace(v.Format))
            .GroupBy(v => v.Format!)
            .Select(g => new { g.Key, Count = g.Count() })
            .ToDictionaryAsync(x => x.Key, x => x.Count, StringComparer.OrdinalIgnoreCase);

        var resolutionTask = baseQuery
            .Where(v => !string.IsNullOrWhiteSpace(v.Resolution))
            .GroupBy(v => v.Resolution!)
            .Select(g => new { g.Key, Count = g.Count() })
            .ToDictionaryAsync(x => x.Key, x => x.Count, StringComparer.OrdinalIgnoreCase);

        var yearTask = baseQuery
            .Where(v => v.Year.HasValue)
            .GroupBy(v => v.Year!.Value.ToString())
            .Select(g => new { g.Key, Count = g.Count() })
            .ToDictionaryAsync(x => x.Key, x => x.Count);

        var collectionsTask = baseQuery
            .SelectMany(v => v.CollectionVideos
                .Where(cv => cv.Collection != null && cv.Collection.IsActive && !string.IsNullOrWhiteSpace(cv.Collection.Name))
                .Select(cv => cv.Collection!.Name))
            .GroupBy(name => name)
            .Select(g => new { Key = g.Key, Count = g.Count() })
            .ToDictionaryAsync(x => x.Key, x => x.Count, StringComparer.OrdinalIgnoreCase);

        await Task.WhenAll(artistTask, genreTask, formatTask, resolutionTask, yearTask, collectionsTask);

        return new SearchContracts.SearchFacets
        {
            Artists = await artistTask,
            Genres = await genreTask,
            Formats = await formatTask,
            Resolutions = await resolutionTask,
            Years = await yearTask,
            Collections = await collectionsTask
        };
    }

    private static VideoQuery BuildVideoQuery(SearchContracts.SearchQuery query)
    {
        var videoQuery = new VideoQuery
        {
            Search = query.SearchText,
            Page = query.PageNumber,
            PageSize = query.PageSize,
            SortBy = MapSortOption(query.SortBy),
            SortDirection = query.SortDescending ? SortDirection.Descending : SortDirection.Ascending,
            YearFrom = query.YearFrom,
            YearTo = query.YearTo,
            DurationFrom = query.DurationMin,
            DurationTo = query.DurationMax,
            HasCollections = query.HasCollections,
            HasYouTubeId = query.HasYouTubeId,
            HasImvdbId = query.HasImvdbId,
            AddedAfter = query.AddedAfter,
            AddedBefore = query.AddedBefore
        };

        videoQuery.ArtistNames.AddRange(query.Artists);
        videoQuery.GenreNames.AddRange(query.Genres);
        videoQuery.Formats.AddRange(query.Formats);
        videoQuery.Resolutions.AddRange(query.Resolutions);

        if (query.CollectionIds.Any())
        {
            videoQuery.CollectionIds.AddRange(query.CollectionIds);
        }

        return videoQuery;
    }

    private static VideoSortOption MapSortOption(string? sortBy)
    {
        return sortBy?.ToLowerInvariant() switch
        {
            "artist" => VideoSortOption.Artist,
            "year" => VideoSortOption.Year,
            "duration" => VideoSortOption.Duration,
            "created" => VideoSortOption.CreatedAt,
            "modified" => VideoSortOption.UpdatedAt,
            _ => VideoSortOption.Title
        };
    }
}
