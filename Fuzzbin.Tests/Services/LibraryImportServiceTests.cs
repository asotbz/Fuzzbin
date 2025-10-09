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
        var pathManager = new LibraryPathManager(unitOfWork, NullLogger<LibraryPathManager>.Instance);

        var service = new LibraryImportService(
            NullLogger<LibraryImportService>.Instance,
            sessionRepository,
            itemRepository,
            videoRepository,
            unitOfWork,
            metadataService,
            pathManager);

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
    }
}
