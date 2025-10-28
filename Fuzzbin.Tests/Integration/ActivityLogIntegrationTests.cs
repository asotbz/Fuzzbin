using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Claims;
using System.Threading;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Data.Context;
using Fuzzbin.Data.Repositories;
using Fuzzbin.Services;
using Fuzzbin.Services.Interfaces;
using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;
using Xunit;

using ServiceSearchFacets = Fuzzbin.Services.Interfaces.SearchFacets;
using ServiceSearchQuery = Fuzzbin.Services.Interfaces.SearchQuery;
using ServiceSearchResult = Fuzzbin.Services.Interfaces.SearchResult;

namespace Fuzzbin.Tests.Integration;

public class ActivityLogIntegrationTests
{
    [Fact]
    public async Task DeleteVideoAsync_WritesActivityLogEntry()
    {
        var options = new DbContextOptionsBuilder<ApplicationDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .Options;

        await using var context = new ApplicationDbContext(options);
        var unitOfWork = new UnitOfWork(context);
        var activityLogRepository = new ActivityLogRepository(context);

        var httpContext = new DefaultHttpContext();
        httpContext.User = new ClaimsPrincipal(new ClaimsIdentity(
            new[] { new Claim(ClaimTypes.Name, "integration.user") },
            "TestAuth"));

        var activityLogService = new ActivityLogService(
            activityLogRepository,
            new HttpContextAccessor { HttpContext = httpContext },
            NullLogger<ActivityLogService>.Instance);

        var video = new Video
        {
            Title = "Integration Song",
            Artist = "Integration Artist"
        };

        await unitOfWork.Videos.AddAsync(video);
        await unitOfWork.SaveChangesAsync();

        var videoService = new VideoService(
            unitOfWork.Videos,
            unitOfWork,
            Enumerable.Empty<IVideoUpdateNotifier>(),
            new TestSearchService(),
            new TestLibraryPathManager(),
            NullLogger<VideoService>.Instance,
            activityLogService);

        await videoService.DeleteVideoAsync(video.Id, deleteFiles: false);

        var log = await context.ActivityLogs.SingleAsync();

        Assert.Equal(ActivityCategories.Video, log.Category);
        Assert.Equal(ActivityActions.Delete, log.Action);
        Assert.Equal(video.Id.ToString(), log.EntityId);
        Assert.Equal("integration.user", log.UserId);
        Assert.True(log.IsSuccess);
        Assert.Contains("Integration Song", log.EntityName);
    }

    private sealed class TestSearchService : ISearchService
    {
        public Task DeleteSavedSearchAsync(Guid id) => Task.CompletedTask;

        public Task<ServiceSearchFacets> GetSearchFacetsAsync() => Task.FromResult(new ServiceSearchFacets());

        public Task<SavedSearch> GetSavedSearchAsync(Guid id) => Task.FromResult(new SavedSearch { Id = id });

        public Task<List<SavedSearch>> GetSavedSearchesAsync() => Task.FromResult(new List<SavedSearch>());

        public void InvalidateFacetsCache()
        {
            // No caching in tests.
        }

        public Task<ServiceSearchResult> SearchAsync(ServiceSearchQuery query) => Task.FromResult(new ServiceSearchResult());

        public Task<SavedSearch> SaveSearchAsync(SavedSearch savedSearch) => Task.FromResult(savedSearch);
    }

    private sealed class TestLibraryPathManager : ILibraryPathManager
    {
        public void EnsureDirectoryExists(string path)
        {
            // No-op for tests.
        }

        public Task<string> GetArtworkRootAsync(CancellationToken cancellationToken = default) => Task.FromResult(Path.GetTempPath());

        public Task<string> GetLibraryRootAsync(CancellationToken cancellationToken = default) => Task.FromResult(Path.GetTempPath());

        public Task<string> GetMetadataRootAsync(CancellationToken cancellationToken = default) => Task.FromResult(Path.GetTempPath());

        public Task<string> GetVideoRootAsync(CancellationToken cancellationToken = default) => Task.FromResult(Path.GetTempPath());

        public string NormalizePath(string? path) => path ?? string.Empty;

        public string SanitizeDirectoryName(string value) => value;

        public string SanitizeFileName(string value, string? extension = null) => value;
    }
}
