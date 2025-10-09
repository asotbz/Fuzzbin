using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Fuzzbin.Core.Entities;
using Fuzzbin.Data.Context;
using Fuzzbin.Data.Repositories;
using Xunit;

namespace Fuzzbin.Tests.Repositories;

public class CollectionRepositoryTests
{
    [Fact]
    public async Task AddVideoToCollectionAsync_AddsVideoAndUpdatesCount()
    {
        await using var context = CreateContext();
        var collection = new Collection { Name = "Mix" };
        var video = new Video { Title = "New", Artist = "Artist" };
        context.Collections.Add(collection);
        context.Videos.Add(video);
        await context.SaveChangesAsync();
        context.ChangeTracker.Clear();

        var repository = new CollectionRepository(context);

        var added = await repository.AddVideoToCollectionAsync(collection.Id, video.Id);

        Assert.True(added);

        context.ChangeTracker.Clear();
        var reloaded = await context.Collections
            .Include(c => c.CollectionVideos)
            .FirstAsync(c => c.Id == collection.Id);

        Assert.Equal(1, reloaded.VideoCount);
        var link = Assert.Single(reloaded.CollectionVideos);
        Assert.Equal(video.Id, link.VideoId);
        Assert.Equal(1, link.Position);
    }

    [Fact]
    public async Task AddVideoToCollectionAsync_DetectsDuplicates()
    {
        await using var context = CreateContext();
        var collection = new Collection { Name = "Mix" };
        var video = new Video { Title = "New", Artist = "Artist" };
        context.Collections.Add(collection);
        context.Videos.Add(video);
        await context.SaveChangesAsync();
        context.ChangeTracker.Clear();

        var repository = new CollectionRepository(context);

        var firstAdd = await repository.AddVideoToCollectionAsync(collection.Id, video.Id);
        var secondAdd = await repository.AddVideoToCollectionAsync(collection.Id, video.Id);

        Assert.True(firstAdd);
        Assert.False(secondAdd);

        var count = await context.CollectionVideos.CountAsync(cv => cv.CollectionId == collection.Id);
        Assert.Equal(1, count);
    }

    [Fact]
    public async Task RemoveVideoFromCollectionAsync_RemovesAndReorders()
    {
        await using var context = CreateContext();
        var (collection, videos, _) = await SeedCollectionAsync(context, 3);
        collection.VideoCount = 3;
        await context.SaveChangesAsync();
        context.ChangeTracker.Clear();

        var repository = new CollectionRepository(context);

        var removed = await repository.RemoveVideoFromCollectionAsync(collection.Id, videos[1].Id);

        Assert.True(removed);

        var remaining = await context.CollectionVideos
            .Where(cv => cv.CollectionId == collection.Id)
            .OrderBy(cv => cv.Position)
            .ToListAsync();

        Assert.Equal(2, remaining.Count);
        Assert.DoesNotContain(remaining, cv => cv.VideoId == videos[1].Id);
        Assert.Equal(new[] { 1, 2 }, remaining.Select(cv => cv.Position).ToArray());

        var reloadedCollection = await context.Collections.FindAsync(collection.Id);
        Assert.Equal(2, reloadedCollection!.VideoCount);
    }

    [Fact]
    public async Task UpdateVideoPositionAsync_AdjustsNeighborPositions()
    {
        await using var context = CreateContext();
        var (collection, videos, collectionVideos) = await SeedCollectionAsync(context, 3);
        collection.VideoCount = 3;
        await context.SaveChangesAsync();
        context.ChangeTracker.Clear();

        var repository = new CollectionRepository(context);

        var moved = await repository.UpdateVideoPositionAsync(collection.Id, videos[0].Id, 3);

        Assert.True(moved);

        var reloaded = await context.CollectionVideos
            .Include(cv => cv.Video)
            .Where(cv => cv.CollectionId == collection.Id)
            .OrderBy(cv => cv.Video.Title)
            .ToListAsync();

        var videoPositions = reloaded.ToDictionary(cv => cv.Video.Title, cv => cv.Position);

        Assert.Equal(3, videoPositions[videos[0].Title]);
        Assert.Equal(1, videoPositions[videos[1].Title]);
        Assert.Equal(2, videoPositions[videos[2].Title]);
    }

    [Fact]
    public async Task ReorderVideosAsync_ReassignsPositions()
    {
        await using var context = CreateContext();
        var (collection, videos, _) = await SeedCollectionAsync(context, 3);
        await context.SaveChangesAsync();
        context.ChangeTracker.Clear();

        var repository = new CollectionRepository(context);
        var desiredOrder = new List<Guid> { videos[2].Id, videos[0].Id, videos[1].Id };

        var reordered = await repository.ReorderVideosAsync(collection.Id, desiredOrder);

        Assert.True(reordered);

        var result = await context.CollectionVideos
            .Where(cv => cv.CollectionId == collection.Id)
            .OrderBy(cv => cv.Position)
            .Select(cv => cv.VideoId)
            .ToListAsync();

        Assert.Equal(desiredOrder, result);
    }

    [Fact]
    public async Task GetCollectionVideosAsync_ReturnsOrderedActiveVideos()
    {
        await using var context = CreateContext();
        var (collection, videos, collectionVideos) = await SeedCollectionAsync(context, 3);
        collectionVideos[1].Position = 3;
        collectionVideos[2].Position = 2;
        collectionVideos[1].Video.IsActive = false;
        await context.SaveChangesAsync();
        context.ChangeTracker.Clear();

        var repository = new CollectionRepository(context);

        var result = (await repository.GetCollectionVideosAsync(collection.Id)).ToList();

        Assert.Equal(2, result.Count);
        Assert.True(result.All(video => video.IsActive));
        Assert.Equal(new[] { videos[0].Id, videos[2].Id }, result.Select(video => video.Id).ToArray());
    }

    [Fact]
    public async Task DuplicateCollectionAsync_CopiesVideosAndMetadata()
    {
        await using var context = CreateContext();
        var (collection, videos, collectionVideos) = await SeedCollectionAsync(context, 2);
        collection.Description = "Original";
        collection.Type = CollectionType.Series;
        collection.SmartCriteria = "{}";
        collection.IsPublic = true;
        collection.IsFavorite = true;
        collection.VideoCount = collectionVideos.Count;
        collection.TotalDuration = TimeSpan.FromMinutes(10);
        await context.SaveChangesAsync();
        context.ChangeTracker.Clear();

        var repository = new CollectionRepository(context);

        var duplicate = await repository.DuplicateCollectionAsync(collection.Id, "Clone");

        Assert.NotNull(duplicate);
        Assert.Equal("Clone", duplicate!.Name);
        Assert.Equal("Original", duplicate.Description);
        Assert.Equal(CollectionType.Series, duplicate.Type);
        Assert.False(duplicate.IsFavorite);
        Assert.Equal(collection.TotalDuration, duplicate.TotalDuration);

        var clonedLinks = await context.CollectionVideos
            .Where(cv => cv.CollectionId == duplicate.Id)
            .OrderBy(cv => cv.Position)
            .ToListAsync();

        Assert.Equal(collectionVideos.Count, clonedLinks.Count);
        Assert.Equal(collectionVideos.Select(cv => cv.VideoId), clonedLinks.Select(cv => cv.VideoId));
    }

    [Fact]
    public async Task MergeCollectionsAsync_AppendsUniqueVideosAndSoftDeletesSource()
    {
        await using var context = CreateContext();
        var (source, sourceVideos, sourceLinks) = await SeedCollectionAsync(context, 2, name: "Source");
        var (target, targetVideos, targetLinks) = await SeedCollectionAsync(context, 1, name: "Target");

        // Share one video between source and target to verify duplicates are skipped
        targetLinks[0].VideoId = sourceVideos[0].Id;
        targetLinks[0].Video = sourceVideos[0];
        target.VideoCount = 1;
        source.VideoCount = sourceLinks.Count;
        await context.SaveChangesAsync();
        context.ChangeTracker.Clear();

        var repository = new CollectionRepository(context);

        Assert.NotEqual(source.Id, target.Id);
        var merged = await repository.MergeCollectionsAsync(source.Id, target.Id);

        Assert.True(merged);

        var targetVideoIds = await context.CollectionVideos
            .Where(cv => cv.CollectionId == target.Id)
            .OrderBy(cv => cv.Position)
            .Select(cv => cv.VideoId)
            .ToListAsync();

        Assert.True(targetVideoIds.Count > 1);
        Assert.Contains(sourceVideos[1].Id, targetVideoIds);
        Assert.Equal(targetVideoIds.Distinct().Count(), targetVideoIds.Count);

        var targetCollection = await context.Collections.FindAsync(target.Id);
        Assert.NotNull(targetCollection);
        Assert.Equal(targetVideoIds.Count, targetCollection!.VideoCount);

        var sourceCollection = await context.Collections.FindAsync(source.Id);
        Assert.False(sourceCollection!.IsActive);
    }

    private static async Task<(Collection collection, List<Video> videos, List<CollectionVideo> links)> SeedCollectionAsync(
        ApplicationDbContext context,
        int count,
        string name = "Collection")
    {
        var collection = new Collection { Name = name };
        var videos = new List<Video>();
        var links = new List<CollectionVideo>();

        for (var i = 0; i < count; i++)
        {
            var video = new Video { Title = $"Video {i + 1}", Artist = "Artist" };
            var link = new CollectionVideo
            {
                Collection = collection,
                Video = video,
                Position = i + 1
            };

            collection.CollectionVideos.Add(link);
            video.CollectionVideos.Add(link);

            videos.Add(video);
            links.Add(link);
        }

        context.Collections.Add(collection);
        context.Videos.AddRange(videos);
        context.CollectionVideos.AddRange(links);
        await context.SaveChangesAsync();

        return (collection, videos, links);
    }

    private static ApplicationDbContext CreateContext()
    {
        var options = new DbContextOptionsBuilder<ApplicationDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .Options;

        return new ApplicationDbContext(options);
    }
}
