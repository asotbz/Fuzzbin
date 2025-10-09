using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Specifications;
using Fuzzbin.Core.Specifications.Queries;
using Fuzzbin.Core.Specifications.Videos;
using Fuzzbin.Data.Context;
using Fuzzbin.Data.Repositories;
using Xunit;

namespace Fuzzbin.Tests.Specifications;

public class VideoSpecificationTests
{
    [Fact]
    public async Task VideoQuerySpecification_FiltersAndSorts()
    {
        var options = new DbContextOptionsBuilder<ApplicationDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .Options;

        await using var context = new ApplicationDbContext(options);

        var genre = new Genre { Name = "Electronic" };
        var videoA = new Video { Title = "Track A", Artist = "Artist Alpha", PlayCount = 5 };
        videoA.Genres.Add(genre);

        var videoB = new Video { Title = "Track B", Artist = "Artist Beta", PlayCount = 10 };
        videoB.Genres.Add(genre);

        var videoC = new Video { Title = "Other", Artist = "Artist Alpha", PlayCount = 20, IsActive = false };
        videoC.Genres.Add(genre);

        context.Genres.Add(genre);
        context.Videos.AddRange(videoA, videoB, videoC);
        await context.SaveChangesAsync();
        context.ChangeTracker.Clear();

        var repository = new Repository<Video>(context);

        var query = new VideoQuery
        {
            Search = "Track",
            GenreIds = new List<Guid> { genre.Id },
            SortBy = VideoSortOption.PlayCount,
            SortDirection = SortDirection.Descending,
            Page = 1,
            PageSize = 50
        };

        var specification = new VideoQuerySpecification(query);
        var results = await repository.ListAsync(specification);

        Assert.Equal(2, results.Count);
        Assert.Equal(videoB.Id, results[0].Id);
        Assert.Equal(videoA.Id, results[1].Id);

        var countSpecification = new VideoQuerySpecification(
            query,
            includeGenres: false,
            includeTags: false,
            includeFeaturedArtists: false,
            includeCollections: false,
            applyPaging: false);

        var total = await repository.CountAsync(countSpecification);
        Assert.Equal(2, total);
    }

    [Fact]
    public async Task VideoBulkByIdsSpecification_PreservesOrder()
    {
        var options = new DbContextOptionsBuilder<ApplicationDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .Options;

        await using var context = new ApplicationDbContext(options);

        var first = new Video { Title = "First", Artist = "A" };
        var second = new Video { Title = "Second", Artist = "B" };
        var third = new Video { Title = "Third", Artist = "C" };

        context.Videos.AddRange(first, second, third);
        await context.SaveChangesAsync();
        context.ChangeTracker.Clear();

        var repository = new Repository<Video>(context);
        var order = new[] { third.Id, first.Id };
        var specification = new VideoBulkByIdsSpecification(order);

        var results = await repository.ListAsync(specification);
        Assert.Equal(order.Length, results.Count);
        Assert.Equal(order[0], results[0].Id);
        Assert.Equal(order[1], results[1].Id);
    }

    [Fact]
    public async Task VideoByIdSpecification_TrackingBehavior()
    {
        var options = new DbContextOptionsBuilder<ApplicationDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .Options;

        await using var context = new ApplicationDbContext(options);
        var video = new Video { Title = "Tracked", Artist = "Artist" };
        context.Videos.Add(video);
        await context.SaveChangesAsync();

        context.ChangeTracker.Clear();
        var repository = new Repository<Video>(context);

        var nonTrackingSpec = new VideoByIdSpecification(video.Id);
        var nonTracked = await repository.FirstOrDefaultAsync(nonTrackingSpec);
        Assert.NotNull(nonTracked);
        Assert.Equal(EntityState.Detached, context.Entry(nonTracked!).State);

        context.ChangeTracker.Clear();

        var trackingSpec = new VideoByIdSpecification(video.Id, includeRelations: false, trackForUpdate: true);
        var tracked = await repository.FirstOrDefaultAsync(trackingSpec);
        Assert.NotNull(tracked);
        Assert.Equal(EntityState.Unchanged, context.Entry(tracked!).State);
    }

    [Fact]
    public async Task VideoQuerySpecification_AdvancedFilters()
    {
        var options = new DbContextOptionsBuilder<ApplicationDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .Options;

        await using var context = new ApplicationDbContext(options);

        var genre = new Genre { Name = "Electronic" };
        var collection = new Collection { Name = "Favorites" };

        var matchingVideo = new Video
        {
            Title = "Match",
            Artist = "Artist Alpha",
            Format = "mp4",
            Resolution = "1080p",
            YouTubeId = "yt123",
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
            Title = "Other",
            Artist = "Different Artist",
            Format = "mkv",
            Resolution = "720p",
            YouTubeId = null,
            CreatedAt = DateTime.UtcNow.AddDays(-10),
            UpdatedAt = DateTime.UtcNow.AddDays(-5)
        };

        context.Genres.Add(genre);
        context.Collections.Add(collection);
        context.Videos.AddRange(matchingVideo, otherVideo);
        context.CollectionVideos.Add(collectionVideo);
        await context.SaveChangesAsync();
        context.ChangeTracker.Clear();

        var repository = new Repository<Video>(context);

        var query = new VideoQuery
        {
            ArtistNames = { "artist alpha" },
            GenreNames = { "Electronic" },
            Formats = { "MP4" },
            Resolutions = { "1080P" },
            HasYouTubeId = true,
            HasCollections = true,
            AddedAfter = DateTime.UtcNow.AddDays(-1),
            AddedBefore = DateTime.UtcNow.AddDays(1),
            Page = 1,
            PageSize = 50
        };

        var specification = new VideoQuerySpecification(
            query,
            includeGenres: true,
            includeTags: false,
            includeFeaturedArtists: false,
            includeCollections: true);

        var results = await repository.ListAsync(specification);

        Assert.Single(results);
        Assert.Equal(matchingVideo.Id, results[0].Id);
    }
}
