using System;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.Logging.Abstractions;
using Fuzzbin.Core.Entities;
using Fuzzbin.Data.Context;
using Fuzzbin.Data.Repositories;
using Fuzzbin.Services;
using Fuzzbin.Services.Interfaces;
using Xunit;

namespace Fuzzbin.Tests.Services;

public class SearchServiceTests
{
    private static (ApplicationDbContext Context, UnitOfWork UnitOfWork, SearchService Service) CreateService()
    {
        var options = new DbContextOptionsBuilder<ApplicationDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .Options;

        var context = new ApplicationDbContext(options);
        var unitOfWork = new UnitOfWork(context);
        var cache = new MemoryCache(new MemoryCacheOptions());
        var service = new SearchService(context, unitOfWork, NullLogger<SearchService>.Instance, cache);
        return (context, unitOfWork, service);
    }

    [Fact]
    public async Task SearchAsync_AppliesExtendedFiltersAndFacets()
    {
        var (context, _, service) = CreateService();
        await using var _ = context;

        var genre = new Genre { Name = "Electronic" };
        var collection = new Collection { Name = "Favorites" };

        var matchingVideo = new Video
        {
            Title = "Matching Track",
            Artist = "Artist Alpha",
            Format = "mp4",
            Resolution = "1080p",
            YouTubeId = "yt123",
            ImvdbId = "imvdb123",
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };
        matchingVideo.Genres.Add(genre);

        var collectionVideo = new CollectionVideo
        {
            Collection = collection,
            Video = matchingVideo,
            Position = 1
        };

        matchingVideo.CollectionVideos.Add(collectionVideo);
        collection.CollectionVideos.Add(collectionVideo);

        var otherVideo = new Video
        {
            Title = "Other Track",
            Artist = "Artist Beta",
            Format = "mkv",
            Resolution = "720p",
            CreatedAt = DateTime.UtcNow.AddDays(-10),
            UpdatedAt = DateTime.UtcNow.AddDays(-5)
        };

        context.Genres.Add(genre);
        context.Collections.Add(collection);
        context.Videos.AddRange(matchingVideo, otherVideo);
        context.CollectionVideos.Add(collectionVideo);
        await context.SaveChangesAsync();

        var query = new SearchQuery
        {
            SearchText = "Matching",
            Formats = { "mp4" },
            Resolutions = { "1080p" },
            CollectionIds = { collection.Id },
            Genres = { "Electronic" },
            HasYouTubeId = true,
            HasImvdbId = true,
            HasCollections = true,
            AddedAfter = DateTime.UtcNow.AddDays(-1),
            PageNumber = 1,
            PageSize = 10
        };

        var result = await service.SearchAsync(query);

        Assert.Single(result.Videos);
        Assert.Equal(matchingVideo.Id, result.Videos.First().Id);
        Assert.NotNull(result.Facets);
        Assert.True(result.Facets!.Artists.ContainsKey("Artist Alpha"));
        Assert.True(result.Facets.Genres.ContainsKey("Electronic"));
        Assert.True(result.Facets.Formats.ContainsKey("mp4"));
    }
}
