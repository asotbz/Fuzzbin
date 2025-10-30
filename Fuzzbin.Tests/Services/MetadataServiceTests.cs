using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using Xunit;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Data.Context;
using Fuzzbin.Data.Repositories;
using Fuzzbin.Services;
using Fuzzbin.Services.External.Imvdb;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;
using ApiImvdbCredit = Fuzzbin.Services.External.Imvdb.ImvdbCredit;

namespace Fuzzbin.Tests.Services;

/// <summary>
/// Unit tests for MetadataService focusing on low-confidence branching logic
/// Tests EnrichVideoMetadataWithResultAsync behavior with different confidence levels
/// </summary>
public class MetadataServiceTests : IAsyncLifetime
{
    private ApplicationDbContext? _context;
    private IUnitOfWork? _unitOfWork;
    private MetadataService? _service;
    private readonly string _databaseName = $"MetadataServiceTests_{Guid.NewGuid()}";

    public Task InitializeAsync() => Task.CompletedTask;

    public async Task DisposeAsync()
    {
        if (_context != null)
        {
            await _context.Database.EnsureDeletedAsync();
            await _context.DisposeAsync();
        }
    }

    private (MetadataService Service, IUnitOfWork UnitOfWork, ApplicationDbContext Context) CreateService(
        double? mockConfidence = null)
    {
        var options = new DbContextOptionsBuilder<ApplicationDbContext>()
            .UseInMemoryDatabase(_databaseName)
            .Options;

        var context = new ApplicationDbContext(options);
        var unitOfWork = new UnitOfWork(context);

        var cache = new MemoryCache(new MemoryCacheOptions());
        var imvdbApi = new FakeImvdbApi { MockConfidence = mockConfidence };
        var imvdbOptions = new FakeOptionsMonitor(new ImvdbOptions
        {
            ApiKey = "test-key",
            CacheDuration = TimeSpan.FromHours(1)
        });
        var apiKeyProvider = new FakeApiKeyProvider();
        var thumbnailService = new FakeThumbnailService();
        var httpClientFactory = new FakeHttpClientFactory();

        var service = new MetadataService(
            NullLogger<MetadataService>.Instance,
            unitOfWork,
            httpClientFactory,
            cache,
            imvdbApi,
            imvdbOptions,
            apiKeyProvider,
            thumbnailService);

        _context = context;
        _unitOfWork = unitOfWork;
        _service = service;

        return (service, unitOfWork, context);
    }

    [Fact]
    public async Task EnrichVideoMetadataWithResultAsync_HighConfidence_AppliesMetadata()
    {
        // Arrange
        var (service, unitOfWork, _) = CreateService(mockConfidence: 0.95);
        
        var video = new Video
        {
            Id = Guid.NewGuid(),
            Title = "Test Song",
            Artist = "Test Artist",
            FilePath = "/test/path.mp4",
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };

        await unitOfWork.Videos.AddAsync(video);
        await unitOfWork.SaveChangesAsync();

        // Act
        var result = await service.EnrichVideoMetadataWithResultAsync(video, fetchOnlineMetadata: true);

        // Assert
        Assert.NotNull(result);
        Assert.NotNull(result.ImvdbMetadata);
        Assert.True(result.MatchConfidence >= 0.9, $"Expected confidence >= 0.9 for high confidence match, got {result.MatchConfidence}");
        Assert.True(result.MetadataApplied, "Metadata should be applied for confidence >= 0.9");
        Assert.False(result.RequiresManualReview, "Should not require manual review for high confidence");
        Assert.NotNull(video.ImvdbId);
    }

    [Fact]
    public async Task EnrichVideoMetadataWithResultAsync_LowConfidence_DoesNotApplyMetadata()
    {
        // Arrange
        var (service, unitOfWork, _) = CreateService(mockConfidence: 0.75);
        
        var video = new Video
        {
            Id = Guid.NewGuid(),
            Title = "Test Song Different",
            Artist = "Test Artist Different",
            FilePath = "/test/path.mp4",
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };

        await unitOfWork.Videos.AddAsync(video);
        await unitOfWork.SaveChangesAsync();

        // Act
        var result = await service.EnrichVideoMetadataWithResultAsync(video, fetchOnlineMetadata: true);

        // Assert
        Assert.NotNull(result);
        Assert.NotNull(result.ImvdbMetadata);
        Assert.True(result.MatchConfidence < 0.9, $"Expected confidence < 0.9 for low confidence match, got {result.MatchConfidence}");
        Assert.False(result.MetadataApplied, "Metadata should NOT be applied for confidence < 0.9");
        Assert.True(result.RequiresManualReview, "Should require manual review for low confidence");
        Assert.Null(video.ImvdbId);
    }

    [Fact]
    public async Task EnrichVideoMetadataWithResultAsync_ConfidenceExactly90Percent_AppliesMetadata()
    {
        // Arrange
        var (service, unitOfWork, _) = CreateService(mockConfidence: 0.90);
        
        var video = new Video
        {
            Id = Guid.NewGuid(),
            Title = "Test Song",
            Artist = "Test Artist",
            FilePath = "/test/path.mp4",
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };

        await unitOfWork.Videos.AddAsync(video);
        await unitOfWork.SaveChangesAsync();

        // Act
        var result = await service.EnrichVideoMetadataWithResultAsync(video, fetchOnlineMetadata: true);

        // Assert
        Assert.NotNull(result);
        Assert.True(result.MatchConfidence >= 0.9, $"Expected confidence >= 0.9, got {result.MatchConfidence}");
        Assert.True(result.MetadataApplied, "Metadata should be applied for confidence >= 0.9 (threshold is >=)");
        Assert.False(result.RequiresManualReview);
    }

    [Fact]
    public async Task EnrichVideoMetadataWithResultAsync_ConfidenceJustBelow90Percent_RequiresReview()
    {
        // Arrange
        var (service, unitOfWork, _) = CreateService(mockConfidence: 0.89);
        
        var video = new Video
        {
            Id = Guid.NewGuid(),
            Title = "Test Song Different",
            Artist = "Test Artist Different",
            FilePath = "/test/path.mp4",
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };

        await unitOfWork.Videos.AddAsync(video);
        await unitOfWork.SaveChangesAsync();

        // Act
        var result = await service.EnrichVideoMetadataWithResultAsync(video, fetchOnlineMetadata: true);

        // Assert
        Assert.NotNull(result);
        Assert.True(result.MatchConfidence < 0.9, $"Expected confidence < 0.9, got {result.MatchConfidence}");
        Assert.False(result.MetadataApplied);
        Assert.True(result.RequiresManualReview, "Should require manual review for confidence just below 0.9");
    }

    [Fact]
    public async Task EnrichVideoMetadataWithResultAsync_NoOnlineMetadata_SkipsConfidenceCheck()
    {
        // Arrange
        var (service, unitOfWork, _) = CreateService(mockConfidence: 0.50);
        
        var video = new Video
        {
            Id = Guid.NewGuid(),
            Title = "Test Video",
            Artist = "Test Artist",
            FilePath = "/test/path.mp4",
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };

        await unitOfWork.Videos.AddAsync(video);
        await unitOfWork.SaveChangesAsync();

        // Act
        var result = await service.EnrichVideoMetadataWithResultAsync(video, fetchOnlineMetadata: false);

        // Assert
        Assert.NotNull(result);
        Assert.Null(result.ImvdbMetadata);
        Assert.Equal(0.0, result.MatchConfidence);
        Assert.False(result.MetadataApplied);
        Assert.False(result.RequiresManualReview);
    }

    [Fact]
    public async Task EnrichVideoMetadataWithResultAsync_MissingArtistOrTitle_DoesNotFetchMetadata()
    {
        // Arrange
        var (service, unitOfWork, _) = CreateService(mockConfidence: 0.95);
        
        var video = new Video
        {
            Id = Guid.NewGuid(),
            Title = "", // Empty title
            Artist = "Test Artist",
            FilePath = "/test/path.mp4",
            CreatedAt = DateTime.UtcNow,
            UpdatedAt = DateTime.UtcNow
        };

        await unitOfWork.Videos.AddAsync(video);
        await unitOfWork.SaveChangesAsync();

        // Act
        var result = await service.EnrichVideoMetadataWithResultAsync(video, fetchOnlineMetadata: true);

        // Assert
        Assert.NotNull(result);
        Assert.Null(result.ImvdbMetadata);
        Assert.Equal(0.0, result.MatchConfidence);
        Assert.False(result.MetadataApplied);
        Assert.False(result.RequiresManualReview);
    }

    // Fake implementations for testing

    private sealed class FakeImvdbApi : IImvdbApi
    {
        public double? MockConfidence { get; set; }

        public Task<ImvdbVideoResponse> GetVideoAsync(string id, CancellationToken cancellationToken = default)
        {
            return Task.FromResult(new ImvdbVideoResponse
            {
                Id = 12345,
                SongTitle = "Test Song",
                Artist = "Test Artist",
                Description = "Test description",
                ReleaseDate = "2024-01-01",
                Credits = new List<ApiImvdbCredit>(),
                Genres = new List<ImvdbGenre>()
            });
        }

        public Task<ImvdbSearchResponse> SearchVideosAsync(string query, int page = 1, int perPage = 20, CancellationToken cancellationToken = default)
        {
            // Create a summary that will produce the desired confidence when compared
            // Use sufficiently different strings to produce lower confidence scores
            var summary = new ImvdbVideoSummary
            {
                Id = 12345,
                Artist = MockConfidence.HasValue && MockConfidence.Value >= 0.9
                    ? "Test Artist"
                    : MockConfidence.HasValue && MockConfidence.Value < 0.9
                        ? "Completely Different Artist Name"
                        : "Test Artist Different",
                SongTitle = MockConfidence.HasValue && MockConfidence.Value >= 0.9
                    ? "Test Song"
                    : MockConfidence.HasValue && MockConfidence.Value < 0.9
                        ? "Completely Different Song Title"
                        : "Test Song Different",
                Title = "Test Song",
                Url = "https://imvdb.com/test"
            };

            return Task.FromResult(new ImvdbSearchResponse
            {
                Results = new List<ImvdbVideoSummary> { summary },
                Meta = new ImvdbSearchMeta { Total = 1, Page = 1, PerPage = 20 }
            });
        }
    }

    private sealed class FakeApiKeyProvider : IImvdbApiKeyProvider
    {
        public Task<string?> GetApiKeyAsync(CancellationToken cancellationToken = default)
        {
            return Task.FromResult<string?>("test-api-key");
        }
    }

    private sealed class FakeThumbnailService : IThumbnailService
    {
        public string GetThumbnailPath(Video video) => "/test/thumbnail.jpg";
        public string GetThumbnailUrl(Video video) => "/thumbnails/test.jpg";
        public bool HasThumbnail(Video video) => false;
        public Task<bool> GenerateThumbnailAsync(string videoPath, string outputPath, double? timePosition = null, CancellationToken cancellationToken = default) => Task.FromResult(true);
        public Task<int> GenerateMissingThumbnailsAsync(IProgress<(int current, int total, string currentVideo)>? progress = null, CancellationToken cancellationToken = default) => Task.FromResult(0);
        public Task<bool> DeleteThumbnailAsync(Video video) => Task.FromResult(true);
    }

    private sealed class FakeHttpClientFactory : IHttpClientFactory
    {
        public System.Net.Http.HttpClient CreateClient(string name)
        {
            return new System.Net.Http.HttpClient();
        }
    }

    private sealed class FakeOptionsMonitor : IOptionsMonitor<ImvdbOptions>
    {
        private readonly ImvdbOptions _options;

        public FakeOptionsMonitor(ImvdbOptions options)
        {
            _options = options;
        }

        public ImvdbOptions CurrentValue => _options;

        public ImvdbOptions Get(string? name) => _options;

        public IDisposable? OnChange(Action<ImvdbOptions, string?> listener) => null;
    }
}