using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Storage;
using Microsoft.Extensions.Logging.Abstractions;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Data.Context;
using Fuzzbin.Data.Repositories;
using Fuzzbin.Services;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;
using Xunit;

namespace Fuzzbin.Tests.Services;

public class LibraryImportServiceTests : IAsyncLifetime
{
    private readonly string _tempRoot = Path.Combine(Path.GetTempPath(), $"fz-import-tests-{Guid.NewGuid():N}");

    [Fact]
    public async Task StartImportAsync_IdentifiesDuplicatesAndMatches()
    {
        var options = CreateOptions();
        await using var context = new ApplicationDbContext(options);
        var (service, unitOfWork) = CreateService(context);
        var rootPath = Path.Combine(_tempRoot, Guid.NewGuid().ToString("N"));

        var existingVideo = new Video
        {
            Title = "Known Hit",
            Artist = "Existing Artist",
            FilePath = "Existing Artist - Known Hit.mp4",
            Duration = 200,
            Resolution = "1920x1080"
        };

        await unitOfWork.Videos.AddAsync(existingVideo);
        await unitOfWork.SaveChangesAsync();

        Directory.CreateDirectory(rootPath);
        var duplicatePath = Path.Combine(rootPath, "Existing Artist - Known Hit.mp4");
        await File.WriteAllTextAsync(duplicatePath, "existing-content");
        var newPath = Path.Combine(rootPath, "New Artist - Fresh Track.mp4");
        await File.WriteAllTextAsync(newPath, "new-content");

        var request = new LibraryImportRequest
        {
            RootPath = rootPath,
            ComputeHashes = true,
            RefreshMetadata = true
        };

        var session = await service.StartImportAsync(request);

        Assert.Equal(LibraryImportStatus.ReadyForReview, session.Status);
        Assert.Equal(2, session.Items.Count);

        var duplicateItem = Assert.Single(session.Items, i => i.FileName.Equals("Existing Artist - Known Hit.mp4", StringComparison.OrdinalIgnoreCase));
        Assert.Equal(LibraryImportDuplicateStatus.ConfirmedDuplicate, duplicateItem.DuplicateStatus);
        Assert.Equal(existingVideo.Id, duplicateItem.DuplicateVideoId);

        var newItem = Assert.Single(session.Items, i => i.FileName.Equals("New Artist - Fresh Track.mp4", StringComparison.OrdinalIgnoreCase));
        Assert.Equal(LibraryImportItemStatus.PendingReview, newItem.Status);
        Assert.Equal("New Artist", newItem.Artist);
        Assert.Equal("Fresh Track", newItem.Title);
        Assert.NotNull(newItem.CandidateMatchesJson);
        var candidates = LibraryImportMatchCandidate.DeserializeList(newItem.CandidateMatchesJson);
        Assert.NotEmpty(candidates);
    }

    private DbContextOptions<ApplicationDbContext> CreateOptions(string? databaseName = null, Microsoft.EntityFrameworkCore.Storage.InMemoryDatabaseRoot? root = null)
    {
        var builder = new DbContextOptionsBuilder<ApplicationDbContext>();
        if (root == null)
        {
            builder.UseInMemoryDatabase(databaseName ?? Guid.NewGuid().ToString());
        }
        else
        {
            builder.UseInMemoryDatabase(databaseName ?? Guid.NewGuid().ToString(), root);
        }

        return builder.Options;
    }

    private (LibraryImportService Service, IUnitOfWork UnitOfWork) CreateService(ApplicationDbContext context)
    {
        var unitOfWork = new UnitOfWork(context);
        var sessionRepository = new Repository<LibraryImportSession>(context);
        var itemRepository = new Repository<LibraryImportItem>(context);
        var videoRepository = new Repository<Video>(context);
        var metadataService = new TestMetadataService();
        var metadataCacheService = new TestMetadataCacheService();
        var configPathService = new TestConfigurationPathService(_tempRoot);
        var pathManager = new LibraryPathManager(unitOfWork, configPathService, NullLogger<LibraryPathManager>.Instance);

        var service = new LibraryImportService(
            NullLogger<LibraryImportService>.Instance,
            sessionRepository,
            itemRepository,
            videoRepository,
            unitOfWork,
            metadataService,
            pathManager,
            metadataCacheService);

        return (service, unitOfWork);
    }

    public Task InitializeAsync()
    {
        Directory.CreateDirectory(_tempRoot);
        return Task.CompletedTask;
    }

    public Task DisposeAsync()
    {
        if (Directory.Exists(_tempRoot))
        {
            TryDeleteDirectory(_tempRoot);
        }
        return Task.CompletedTask;
    }

    private static void TryDeleteDirectory(string path)
    {
        try
        {
            Directory.Delete(path, recursive: true);
        }
        catch
        {
            // Ignore cleanup errors in tests
        }
    }

    private sealed class TestMetadataCacheService : IMetadataCacheService
    {
        public Task<MetadataCacheResult> SearchAsync(string artist, string title, int? knownDurationSeconds = null, CancellationToken cancellationToken = default)
        {
            var candidate = new AggregatedCandidate
            {
                Title = title,
                Artist = artist,
                OverallConfidence = 0.95,
                PrimarySource = "test"
            };

            return Task.FromResult(new MetadataCacheResult
            {
                Found = true,
                BestMatch = candidate,
                RequiresManualSelection = false
            });
        }

        public Task<List<AggregatedCandidate>> GetCandidatesAsync(string artist, string title, int maxResults = 10, CancellationToken cancellationToken = default)
        {
            var candidates = new List<AggregatedCandidate>
            {
                new AggregatedCandidate
                {
                    Title = title,
                    Artist = artist,
                    OverallConfidence = 0.95,
                    PrimarySource = "test"
                }
            };
            return Task.FromResult(candidates);
        }

        public Task<Video> ApplyMetadataAsync(Video video, AggregatedCandidate candidate, CancellationToken cancellationToken = default)
        {
            return Task.FromResult(video);
        }

        public Task<bool> IsCachedAsync(string artist, string title, CancellationToken cancellationToken = default)
        {
            return Task.FromResult(false);
        }

        public Task ClearCacheAsync(CancellationToken cancellationToken = default)
        {
            return Task.CompletedTask;
        }

        public Task<CacheStatistics> GetStatisticsAsync(CancellationToken cancellationToken = default)
        {
            return Task.FromResult(new CacheStatistics());
        }
    }

    private sealed class TestMetadataService : IMetadataService
    {
        public Task<VideoMetadata> ExtractMetadataAsync(string filePath, CancellationToken cancellationToken = default)
        {
            var name = Path.GetFileNameWithoutExtension(filePath) ?? string.Empty;
            var parts = name.Split('-', StringSplitOptions.TrimEntries);
            var artist = parts.Length > 0 ? parts[0].Trim() : "Unknown Artist";
            var title = parts.Length > 1 ? string.Join("-", parts.Skip(1)).Trim() : name;

            var metadata = new VideoMetadata
            {
                Artist = artist,
                Title = title,
                Duration = TimeSpan.FromMinutes(3),
                Width = 1920,
                Height = 1080,
                FrameRate = 29.97
            };

            return Task.FromResult(metadata);
        }

        // Unused members for testing
        public Task<ImvdbMetadata?> GetImvdbMetadataAsync(string artist, string title, CancellationToken cancellationToken = default) => Task.FromResult<ImvdbMetadata?>(null);
        public Task<MusicBrainzMetadata?> GetMusicBrainzMetadataAsync(string artist, string title, CancellationToken cancellationToken = default) => Task.FromResult<MusicBrainzMetadata?>(null);
        public Task<string> GenerateNfoAsync(Video video, string outputPath, CancellationToken cancellationToken = default) => Task.FromResult(string.Empty);
        public Task<NfoData?> ReadNfoAsync(string nfoPath, CancellationToken cancellationToken = default) => Task.FromResult<NfoData?>(null);
        public Task<Video> EnrichVideoMetadataAsync(Video video, bool fetchOnlineMetadata = true, CancellationToken cancellationToken = default) => Task.FromResult(video);
        public Task<string?> DownloadThumbnailAsync(string thumbnailUrl, string outputPath, CancellationToken cancellationToken = default) => Task.FromResult<string?>(null);
        public Task<List<ImvdbMetadata>> GetTopMatchesAsync(string artist, string title, int maxResults = 5, CancellationToken cancellationToken = default) => Task.FromResult(new List<ImvdbMetadata>());
        public Task<MetadataEnrichmentResult> EnrichVideoMetadataWithResultAsync(Video video, bool fetchOnlineMetadata = true, CancellationToken cancellationToken = default) => Task.FromResult(new MetadataEnrichmentResult { Video = video, MatchConfidence = 1.0 });
        public Task<Video> UpdateVideoFromImvdbMetadataAsync(Video video, ImvdbMetadata metadata, CancellationToken cancellationToken = default) => Task.FromResult(video);
        public Task<string?> EnsureThumbnailAsync(Video video, string? videoFilePath = null, CancellationToken cancellationToken = default) => Task.FromResult<string?>(null);
    }

    private sealed class TestConfigurationPathService : IConfigurationPathService
    {
        private readonly string _workspace;

        public TestConfigurationPathService(string workspace)
        {
            _workspace = workspace;
        }

        public string GetConfigDirectory() => _workspace;
        public string GetDataDirectory() => Path.Combine(_workspace, "data");
        public string GetBackupDirectory() => Path.Combine(_workspace, "backups");
        public string GetLogsDirectory() => Path.Combine(_workspace, "logs");
        public string GetDatabasePath() => Path.Combine(_workspace, "data", "fuzzbin.db");
        public string GetDefaultLibraryPath() => Path.Combine(_workspace, "Library");
        public string GetDefaultDownloadsPath() => Path.Combine(_workspace, "Downloads");
        public string GetThumbnailDirectory() => Path.Combine(_workspace, "thumbnails");
        public void EnsureDirectoryExists(string path) => Directory.CreateDirectory(path);
    }
}

/// <summary>
/// Tests for enhanced filename parsing with featured artist extraction
/// </summary>
public class LibraryImportServiceEnhancedFilenameParsingTests
{
    [Theory]
    [InlineData("Taylor Swift feat. Ed Sheeran - End Game (2017).mp4", "Taylor Swift", "End Game", 2017, "Ed Sheeran")]
    [InlineData("Taylor Swift ft. Ed Sheeran - End Game.mp4", "Taylor Swift", "End Game", null, "Ed Sheeran")]
    [InlineData("Taylor Swift featuring Ed Sheeran - End Game.mp4", "Taylor Swift", "End Game", null, "Ed Sheeran")]
    [InlineData("Taylor Swift with Ed Sheeran - End Game.mp4", "Taylor Swift", "End Game", null, "Ed Sheeran")]
    [InlineData("Taylor Swift x Ed Sheeran - End Game.mp4", "Taylor Swift", "End Game", null, "Ed Sheeran")]
    public async Task EnhancedParser_ShouldExtractFeaturedArtistFromArtistField(
        string filename, string expectedArtist, string expectedTitle, int? expectedYear, string expectedFeatured)
    {
        // Arrange
        var options = CreateOptions();
        await using var context = new ApplicationDbContext(options);
        var (service, unitOfWork) = CreateService(context);
        var rootPath = Path.Combine(Path.GetTempPath(), $"fz-test-{Guid.NewGuid():N}");

        try
        {
            Directory.CreateDirectory(rootPath);
            var filePath = Path.Combine(rootPath, filename);
            await File.WriteAllTextAsync(filePath, "test-content");

            var request = new LibraryImportRequest
            {
                RootPath = rootPath,
                ComputeHashes = false,
                RefreshMetadata = false
            };

            // Act
            var session = await service.StartImportAsync(request);

            // Assert
            var item = Assert.Single(session.Items);
            Assert.Equal(expectedArtist, item.Artist);
            Assert.Equal(expectedTitle, item.Title);
            Assert.Equal(expectedYear, item.Year);
            Assert.NotNull(item.FeaturedArtistsJson);
            
            var featured = JsonSerializer.Deserialize<List<string>>(item.FeaturedArtistsJson);
            Assert.NotNull(featured);
            Assert.Contains(expectedFeatured, featured);
        }
        finally
        {
            if (Directory.Exists(rootPath))
            {
                try { Directory.Delete(rootPath, true); } catch { }
            }
        }
    }

    [Theory]
    [InlineData("Taylor Swift - End Game (feat. Ed Sheeran).mp4", "Taylor Swift", "End Game", "Ed Sheeran")]
    [InlineData("Taylor Swift - End Game [feat. Ed Sheeran].mp4", "Taylor Swift", "End Game", "Ed Sheeran")]
    [InlineData("Taylor Swift - End Game (ft. Ed Sheeran).mp4", "Taylor Swift", "End Game", "Ed Sheeran")]
    [InlineData("Taylor Swift - End Game (featuring Ed Sheeran).mp4", "Taylor Swift", "End Game", "Ed Sheeran")]
    public async Task EnhancedParser_ShouldExtractFeaturedArtistFromTitleField(
        string filename, string expectedArtist, string expectedTitle, string expectedFeatured)
    {
        // Arrange
        var options = CreateOptions();
        await using var context = new ApplicationDbContext(options);
        var (service, unitOfWork) = CreateService(context);
        var rootPath = Path.Combine(Path.GetTempPath(), $"fz-test-{Guid.NewGuid():N}");

        try
        {
            Directory.CreateDirectory(rootPath);
            var filePath = Path.Combine(rootPath, filename);
            await File.WriteAllTextAsync(filePath, "test-content");

            var request = new LibraryImportRequest
            {
                RootPath = rootPath,
                ComputeHashes = false,
                RefreshMetadata = false
            };

            // Act
            var session = await service.StartImportAsync(request);

            // Assert
            var item = Assert.Single(session.Items);
            Assert.Equal(expectedArtist, item.Artist);
            Assert.Equal(expectedTitle, item.Title);
            Assert.NotNull(item.FeaturedArtistsJson);
            
            var featured = JsonSerializer.Deserialize<List<string>>(item.FeaturedArtistsJson);
            Assert.NotNull(featured);
            Assert.Contains(expectedFeatured, featured);
        }
        finally
        {
            if (Directory.Exists(rootPath))
            {
                try { Directory.Delete(rootPath, true); } catch { }
            }
        }
    }

    [Theory]
    [InlineData("Artist - Title (Official Video).mp4", "Artist", "Title")]
    [InlineData("Artist - Title (Official Music Video).mp4", "Artist", "Title")]
    [InlineData("Artist - Title [Official Video].mp4", "Artist", "Title")]
    [InlineData("Artist - Title [HD].mp4", "Artist", "Title")]
    [InlineData("Artist - Title [4K].mp4", "Artist", "Title")]
    [InlineData("Artist - Title (Explicit).mp4", "Artist", "Title")]
    public async Task EnhancedParser_ShouldRemoveCommonSuffixes(
        string filename, string expectedArtist, string expectedTitle)
    {
        // Arrange
        var options = CreateOptions();
        await using var context = new ApplicationDbContext(options);
        var (service, unitOfWork) = CreateService(context);
        var rootPath = Path.Combine(Path.GetTempPath(), $"fz-test-{Guid.NewGuid():N}");

        try
        {
            Directory.CreateDirectory(rootPath);
            var filePath = Path.Combine(rootPath, filename);
            await File.WriteAllTextAsync(filePath, "test-content");

            var request = new LibraryImportRequest
            {
                RootPath = rootPath,
                ComputeHashes = false,
                RefreshMetadata = false
            };

            // Act
            var session = await service.StartImportAsync(request);

            // Assert
            var item = Assert.Single(session.Items);
            Assert.Equal(expectedArtist, item.Artist);
            Assert.Equal(expectedTitle, item.Title);
        }
        finally
        {
            if (Directory.Exists(rootPath))
            {
                try { Directory.Delete(rootPath, true); } catch { }
            }
        }
    }

    [Theory]
    [InlineData("Artist - Title (2020).mp4", "Artist", "Title", 2020)]
    [InlineData("Artist - Title [2020].mp4", "Artist", "Title", 2020)]
    [InlineData("Artist - Title 2020.mp4", "Artist", "Title", 2020)]
    public async Task EnhancedParser_ShouldExtractYearFromVariousFormats(
        string filename, string expectedArtist, string expectedTitle, int expectedYear)
    {
        // Arrange
        var options = CreateOptions();
        await using var context = new ApplicationDbContext(options);
        var (service, unitOfWork) = CreateService(context);
        var rootPath = Path.Combine(Path.GetTempPath(), $"fz-test-{Guid.NewGuid():N}");

        try
        {
            Directory.CreateDirectory(rootPath);
            var filePath = Path.Combine(rootPath, filename);
            await File.WriteAllTextAsync(filePath, "test-content");

            var request = new LibraryImportRequest
            {
                RootPath = rootPath,
                ComputeHashes = false,
                RefreshMetadata = false
            };

            // Act
            var session = await service.StartImportAsync(request);

            // Assert
            var item = Assert.Single(session.Items);
            Assert.Equal(expectedArtist, item.Artist);
            Assert.Equal(expectedTitle, item.Title);
            Assert.Equal(expectedYear, item.Year);
        }
        finally
        {
            if (Directory.Exists(rootPath))
            {
                try { Directory.Delete(rootPath, true); } catch { }
            }
        }
    }

    [Theory]
    [InlineData("Artist feat. Ed Sheeran & Taylor Swift - Title.mp4", "Ed Sheeran", "Taylor Swift")]
    [InlineData("Artist feat. Ed Sheeran and Taylor Swift - Title.mp4", "Ed Sheeran", "Taylor Swift")]
    [InlineData("Artist feat. Ed Sheeran + Taylor Swift - Title.mp4", "Ed Sheeran", "Taylor Swift")]
    [InlineData("Artist feat. Ed Sheeran, Taylor Swift - Title.mp4", "Ed Sheeran", "Taylor Swift")]
    public async Task EnhancedParser_ShouldHandleMultipleFeaturedArtists(
        string filename, string expectedFeatured1, string expectedFeatured2)
    {
        // Arrange
        var options = CreateOptions();
        await using var context = new ApplicationDbContext(options);
        var (service, unitOfWork) = CreateService(context);
        var rootPath = Path.Combine(Path.GetTempPath(), $"fz-test-{Guid.NewGuid():N}");

        try
        {
            Directory.CreateDirectory(rootPath);
            var filePath = Path.Combine(rootPath, filename);
            await File.WriteAllTextAsync(filePath, "test-content");

            var request = new LibraryImportRequest
            {
                RootPath = rootPath,
                ComputeHashes = false,
                RefreshMetadata = false
            };

            // Act
            var session = await service.StartImportAsync(request);

            // Assert
            var item = Assert.Single(session.Items);
            Assert.NotNull(item.FeaturedArtistsJson);
            
            var featured = JsonSerializer.Deserialize<List<string>>(item.FeaturedArtistsJson);
            Assert.NotNull(featured);
            Assert.Contains(expectedFeatured1, featured);
            Assert.Contains(expectedFeatured2, featured);
        }
        finally
        {
            if (Directory.Exists(rootPath))
            {
                try { Directory.Delete(rootPath, true); } catch { }
            }
        }
    }

    [Theory]
    [InlineData("Artist_-_Title.mp4", "Artist", "Title")]
    [InlineData("Artist - Title.mp4", "Artist", "Title")]
    [InlineData("Artist – Title.mp4", "Artist", "Title")]
    [InlineData("Artist — Title.mp4", "Artist", "Title")]
    [InlineData("Artist | Title.mp4", "Artist", "Title")]
    public async Task EnhancedParser_ShouldHandleVariousSeparators(
        string filename, string expectedArtist, string expectedTitle)
    {
        // Arrange
        var options = CreateOptions();
        await using var context = new ApplicationDbContext(options);
        var (service, unitOfWork) = CreateService(context);
        var rootPath = Path.Combine(Path.GetTempPath(), $"fz-test-{Guid.NewGuid():N}");

        try
        {
            Directory.CreateDirectory(rootPath);
            var filePath = Path.Combine(rootPath, filename);
            await File.WriteAllTextAsync(filePath, "test-content");

            var request = new LibraryImportRequest
            {
                RootPath = rootPath,
                ComputeHashes = false,
                RefreshMetadata = false
            };

            // Act
            var session = await service.StartImportAsync(request);

            // Assert
            var item = Assert.Single(session.Items);
            Assert.Equal(expectedArtist, item.Artist);
            Assert.Equal(expectedTitle, item.Title);
        }
        finally
        {
            if (Directory.Exists(rootPath))
            {
                try { Directory.Delete(rootPath, true); } catch { }
            }
        }
    }

    private DbContextOptions<ApplicationDbContext> CreateOptions(string? databaseName = null)
    {
        var builder = new DbContextOptionsBuilder<ApplicationDbContext>();
        builder.UseInMemoryDatabase(databaseName ?? Guid.NewGuid().ToString());
        return builder.Options;
    }

    private (LibraryImportService Service, IUnitOfWork UnitOfWork) CreateService(ApplicationDbContext context)
    {
        var unitOfWork = new UnitOfWork(context);
        var sessionRepository = new Repository<LibraryImportSession>(context);
        var itemRepository = new Repository<LibraryImportItem>(context);
        var videoRepository = new Repository<Video>(context);
        var metadataService = new TestMetadataService();
        var metadataCacheService = new TestMetadataCacheService();
        var tempRoot = Path.Combine(Path.GetTempPath(), $"fz-tests-{Guid.NewGuid():N}");
        var configPathService = new TestConfigurationPathService(tempRoot);
        var pathManager = new LibraryPathManager(unitOfWork, configPathService, NullLogger<LibraryPathManager>.Instance);

        var service = new LibraryImportService(
            NullLogger<LibraryImportService>.Instance,
            sessionRepository,
            itemRepository,
            videoRepository,
            unitOfWork,
            metadataService,
            pathManager,
            metadataCacheService);

        return (service, unitOfWork);
    }

    private sealed class TestMetadataCacheService : IMetadataCacheService
    {
        public Task<MetadataCacheResult> SearchAsync(string artist, string title, int? knownDurationSeconds = null, CancellationToken cancellationToken = default)
        {
            return Task.FromResult(new MetadataCacheResult { Found = false });
        }

        public Task<List<AggregatedCandidate>> GetCandidatesAsync(string artist, string title, int maxResults = 10, CancellationToken cancellationToken = default)
        {
            return Task.FromResult(new List<AggregatedCandidate>());
        }

        public Task<Video> ApplyMetadataAsync(Video video, AggregatedCandidate candidate, CancellationToken cancellationToken = default)
        {
            return Task.FromResult(video);
        }

        public Task<bool> IsCachedAsync(string artist, string title, CancellationToken cancellationToken = default)
        {
            return Task.FromResult(false);
        }

        public Task ClearCacheAsync(CancellationToken cancellationToken = default)
        {
            return Task.CompletedTask;
        }

        public Task<CacheStatistics> GetStatisticsAsync(CancellationToken cancellationToken = default)
        {
            return Task.FromResult(new CacheStatistics());
        }
    }

    private sealed class TestMetadataService : IMetadataService
    {
        public Task<VideoMetadata> ExtractMetadataAsync(string filePath, CancellationToken cancellationToken = default)
        {
            return Task.FromResult<VideoMetadata>(null!);
        }

        public Task<ImvdbMetadata?> GetImvdbMetadataAsync(string artist, string title, CancellationToken cancellationToken = default) => Task.FromResult<ImvdbMetadata?>(null);
        public Task<MusicBrainzMetadata?> GetMusicBrainzMetadataAsync(string artist, string title, CancellationToken cancellationToken = default) => Task.FromResult<MusicBrainzMetadata?>(null);
        public Task<string> GenerateNfoAsync(Video video, string outputPath, CancellationToken cancellationToken = default) => Task.FromResult(string.Empty);
        public Task<NfoData?> ReadNfoAsync(string nfoPath, CancellationToken cancellationToken = default) => Task.FromResult<NfoData?>(null);
        public Task<Video> EnrichVideoMetadataAsync(Video video, bool fetchOnlineMetadata = true, CancellationToken cancellationToken = default) => Task.FromResult(video);
        public Task<string?> DownloadThumbnailAsync(string thumbnailUrl, string outputPath, CancellationToken cancellationToken = default) => Task.FromResult<string?>(null);
        public Task<List<ImvdbMetadata>> GetTopMatchesAsync(string artist, string title, int maxResults = 5, CancellationToken cancellationToken = default) => Task.FromResult(new List<ImvdbMetadata>());
        public Task<MetadataEnrichmentResult> EnrichVideoMetadataWithResultAsync(Video video, bool fetchOnlineMetadata = true, CancellationToken cancellationToken = default) => Task.FromResult(new MetadataEnrichmentResult { Video = video, MatchConfidence = 1.0 });
        public Task<Video> UpdateVideoFromImvdbMetadataAsync(Video video, ImvdbMetadata metadata, CancellationToken cancellationToken = default) => Task.FromResult(video);
        public Task<string?> EnsureThumbnailAsync(Video video, string? videoFilePath = null, CancellationToken cancellationToken = default) => Task.FromResult<string?>(null);
    }

    private sealed class TestConfigurationPathService : IConfigurationPathService
    {
        private readonly string _workspace;

        public TestConfigurationPathService(string workspace)
        {
            _workspace = workspace;
        }

        public string GetConfigDirectory() => _workspace;
        public string GetDataDirectory() => Path.Combine(_workspace, "data");
        public string GetBackupDirectory() => Path.Combine(_workspace, "backups");
        public string GetLogsDirectory() => Path.Combine(_workspace, "logs");
        public string GetDatabasePath() => Path.Combine(_workspace, "data", "fuzzbin.db");
        public string GetDefaultLibraryPath() => Path.Combine(_workspace, "Library");
        public string GetDefaultDownloadsPath() => Path.Combine(_workspace, "Downloads");
        public string GetThumbnailDirectory() => Path.Combine(_workspace, "thumbnails");
        public void EnsureDirectoryExists(string path) => Directory.CreateDirectory(path);
    }
}
