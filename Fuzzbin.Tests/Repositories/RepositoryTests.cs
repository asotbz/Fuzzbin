using System;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Specifications;
using Fuzzbin.Data.Context;
using Fuzzbin.Data.Repositories;
using Xunit;

namespace Fuzzbin.Tests.Repositories;

public class RepositoryTests
{
    [Fact]
    public async Task GetAllAsync_OnlyReturnsActiveEntities()
    {
        await using var context = CreateContext();
        context.Videos.AddRange(
            new Video { Title = "Active 1", Artist = "Artist" },
            new Video { Title = "Active 2", Artist = "Artist" },
            new Video { Title = "Inactive", Artist = "Artist", IsActive = false });
        await context.SaveChangesAsync();

        var repository = new Repository<Video>(context);

        var results = await repository.GetAllAsync();

        Assert.Equal(2, results.Count());
        Assert.All(results, video => Assert.True(video.IsActive));
    }

    [Fact]
    public async Task GetAllAsync_IncludingDeleted_ReturnsAllEntities()
    {
        await using var context = CreateContext();
        context.Videos.AddRange(
            new Video { Title = "Active", Artist = "Artist" },
            new Video { Title = "Inactive", Artist = "Artist", IsActive = false });
        await context.SaveChangesAsync();

        var repository = new Repository<Video>(context);

        var results = await repository.GetAllAsync(includeDeleted: true);

        Assert.Equal(2, results.Count());
        Assert.Contains(results, video => !video.IsActive);
    }

    [Fact]
    public async Task DeleteAsync_MarksEntityInactive()
    {
        await using var context = CreateContext();
        var video = new Video { Title = "ToDelete", Artist = "Artist" };
        context.Videos.Add(video);
        await context.SaveChangesAsync();

        var repository = new Repository<Video>(context);

        await repository.DeleteAsync(video);
        await repository.SaveChangesAsync();

        var stored = await context.Videos.IgnoreQueryFilters().FirstAsync(v => v.Id == video.Id);
        Assert.False(stored.IsActive);

        var activeResults = await repository.GetAllAsync();
        Assert.DoesNotContain(activeResults, v => v.Id == video.Id);
    }

    [Fact]
    public async Task SpecificationQueries_FilterOrderAndTrackEntities()
    {
        await using var context = CreateContext();

        var collection = new Collection { Name = "Mix" };
        var topVideo = new Video { Title = "Top", Artist = "Filter", PlayCount = 10 };
        var secondaryVideo = new Video { Title = "Second", Artist = "Filter", PlayCount = 5 };
        var otherVideo = new Video { Title = "Other", Artist = "Someone Else", PlayCount = 20 };

        var link = new CollectionVideo
        {
            Collection = collection,
            Video = topVideo,
            Position = 1
        };
        topVideo.CollectionVideos.Add(link);
        collection.CollectionVideos.Add(link);

        context.Collections.Add(collection);
        context.Videos.AddRange(topVideo, secondaryVideo, otherVideo);
        context.CollectionVideos.Add(link);
        await context.SaveChangesAsync();
        context.ChangeTracker.Clear();

        var repository = new Repository<Video>(context);
        var specification = new VideosByArtistSpecification("Filter");

        var results = await repository.ListAsync(specification);

        Assert.Equal(2, results.Count);
        Assert.Equal("Top", results[0].Title);
        Assert.Single(results[0].CollectionVideos);
        Assert.Equal(EntityState.Unchanged, context.Entry(results[0]).State);

        var first = await repository.FirstOrDefaultAsync(specification);
        Assert.NotNull(first);
        Assert.Equal("Top", first!.Title);
    }

    [Fact]
    public async Task SpecificationMethods_ThrowOnNullArgument()
    {
        await using var context = CreateContext();
        var repository = new Repository<Video>(context);

        await Assert.ThrowsAsync<ArgumentNullException>(() => repository.ListAsync((ISpecification<Video>)null!));
        await Assert.ThrowsAsync<ArgumentNullException>(() => repository.FirstOrDefaultAsync((ISpecification<Video>)null!));
        await Assert.ThrowsAsync<ArgumentNullException>(() => repository.CountAsync((ISpecification<Video>)null!));
    }

    [Fact]
    public async Task QueryHelpers_RespectActiveFilter()
    {
        await using var context = CreateContext();
        var active = new Video { Title = "Active", Artist = "Artist" };
        var inactive = new Video { Title = "Inactive", Artist = "Artist", IsActive = false };
        context.Videos.AddRange(active, inactive);
        await context.SaveChangesAsync();

        var repository = new Repository<Video>(context);

        var queryable = repository.GetQueryable().ToList();
        Assert.Single(queryable);
        Assert.Equal(active.Id, queryable[0].Id);

        var exists = await repository.ExistsAsync(v => v.Title == "Active");
        var missing = await repository.ExistsAsync(v => v.Title == "Missing");

        Assert.True(exists);
        Assert.False(missing);

        var count = await repository.CountAsync(v => v.Artist == "Artist");
        Assert.Equal(1, count);

        var first = await repository.FirstOrDefaultAsync(v => v.Title == "Active");
        Assert.NotNull(first);
    }

    private static ApplicationDbContext CreateContext()
    {
        var options = new DbContextOptionsBuilder<ApplicationDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .Options;

        return new ApplicationDbContext(options);
    }

    private sealed class VideosByArtistSpecification : BaseSpecification<Video>
    {
        public VideosByArtistSpecification(string artist)
        {
            ApplyCriteria(video => video.Artist == artist && video.IsActive);
            AddInclude(video => video.CollectionVideos);
            AddOrderByDescending(video => video.PlayCount);
            EnableTracking();
        }
    }
}
