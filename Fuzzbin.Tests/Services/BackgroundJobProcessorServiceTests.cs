using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Data.Context;
using Fuzzbin.Data.Repositories;
using Fuzzbin.Services;
using Fuzzbin.Services.Interfaces;
using Xunit;

namespace Fuzzbin.Tests.Services;

public class BackgroundJobProcessorServiceTests
{
    private sealed class TestJobProgressNotifier : IJobProgressNotifier
    {
        public readonly List<string> Events = new();

        public Task NotifyJobStartedAsync(Guid jobId, BackgroundJobType type, CancellationToken cancellationToken = default)
        {
            Events.Add($"Started:{jobId}:{type}");
            return Task.CompletedTask;
        }

        public Task NotifyJobProgressAsync(Guid jobId, int progress, string? statusMessage = null, CancellationToken cancellationToken = default)
        {
            Events.Add($"Progress:{jobId}:{progress}:{statusMessage}");
            return Task.CompletedTask;
        }

        public Task NotifyJobCompletedAsync(Guid jobId, string? resultSummary = null, CancellationToken cancellationToken = default)
        {
            Events.Add($"Completed:{jobId}:{resultSummary}");
            return Task.CompletedTask;
        }

        public Task NotifyJobFailedAsync(Guid jobId, string errorMessage, CancellationToken cancellationToken = default)
        {
            Events.Add($"Failed:{jobId}:{errorMessage}");
            return Task.CompletedTask;
        }

        public Task NotifyJobCancelledAsync(Guid jobId, CancellationToken cancellationToken = default)
        {
            Events.Add($"Cancelled:{jobId}");
            return Task.CompletedTask;
        }
    }

    private static (ServiceProvider Provider,
        ApplicationDbContext Db,
        IUnitOfWork Uow,
        TestJobProgressNotifier Notifier,
        BackgroundJobProcessorService Processor) CreateSystem()
    {
        var services = new ServiceCollection();

        // EF Core InMemory
        services.AddDbContext<ApplicationDbContext>(o =>
            o.UseInMemoryDatabase(Guid.NewGuid().ToString()));

        // Logging
        services.AddLogging(b => b.AddConsole().SetMinimumLevel(LogLevel.Debug));

        // Register UnitOfWork & repositories/services needed by executors
        services.AddScoped<IUnitOfWork, UnitOfWork>();

        // Minimal stub services required by executors
        services.AddScoped<IMetadataService, NoOpMetadataService>();
        services.AddScoped<IFileOrganizationService, NoOpFileOrganizationService>();
        services.AddScoped<ISourceVerificationService, NoOpSourceVerificationService>();

        var notifier = new TestJobProgressNotifier();
        services.AddSingleton<IJobProgressNotifier>(notifier);

        services.AddScoped<IBackgroundJobService, BackgroundJobService>();

        services.AddScoped<BackgroundJobProcessorService>();

        var provider = services.BuildServiceProvider();
        var scope = provider.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        var uow = scope.ServiceProvider.GetRequiredService<IUnitOfWork>();
        var processor = scope.ServiceProvider.GetRequiredService<BackgroundJobProcessorService>();

        return (provider, db, uow, notifier, processor);
    }

    [Fact]
    public async Task ProcessOnce_ExecutesPendingJob_CompletesSuccessfully()
    {
        var (_, _, uow, notifier, processor) = CreateSystem();

        // Arrange: create one pending RefreshMetadata job
        var job = new BackgroundJob
        {
            Type = BackgroundJobType.RefreshMetadata,
            Status = BackgroundJobStatus.Pending,
            CreatedAt = DateTime.UtcNow
        };
        await uow.BackgroundJobs.AddAsync(job);
        await uow.SaveChangesAsync();

        // Act
        await processor.ProcessOnceForTestsAsync();

        // Assert
        var reloaded = await uow.BackgroundJobs.GetByIdAsync(job.Id);
        Assert.NotNull(reloaded);
        Assert.Equal(BackgroundJobStatus.Completed, reloaded!.Status);
        Assert.Equal(100, reloaded.Progress);
        Assert.Contains(notifier.Events, e => e.StartsWith("Started"));
        Assert.Contains(notifier.Events, e => e.StartsWith("Completed"));
    }

    [Fact]
    public async Task ProcessOnce_CancelsDuplicatePendingSingletons()
    {
        var (_, _, uow, notifier, processor) = CreateSystem();

        var first = new BackgroundJob
        {
            Type = BackgroundJobType.OrganizeFiles,
            Status = BackgroundJobStatus.Pending,
            CreatedAt = DateTime.UtcNow
        };
        var duplicate = new BackgroundJob
        {
            Type = BackgroundJobType.OrganizeFiles,
            Status = BackgroundJobStatus.Pending,
            CreatedAt = DateTime.UtcNow.AddSeconds(1)
        };
        await uow.BackgroundJobs.AddAsync(first);
        await uow.BackgroundJobs.AddAsync(duplicate);
        await uow.SaveChangesAsync();

        await processor.ProcessOnceForTestsAsync();

        var j1 = await uow.BackgroundJobs.GetByIdAsync(first.Id);
        var j2 = await uow.BackgroundJobs.GetByIdAsync(duplicate.Id);

        Assert.Equal(BackgroundJobStatus.Completed, j1!.Status);
        Assert.Equal(BackgroundJobStatus.Cancelled, j2!.Status);
        Assert.Contains(notifier.Events, e => e.StartsWith("Cancelled") && e.Contains(j2.Id.ToString()));
    }

    [Fact]
    public async Task ProcessOnce_RespectsPreExecutionCancellation()
    {
        var (_, _, uow, notifier, processor) = CreateSystem();

        var job = new BackgroundJob
        {
            Type = BackgroundJobType.RefreshMetadata,
            Status = BackgroundJobStatus.Pending,
            CreatedAt = DateTime.UtcNow,
            CancellationRequested = true
        };
        await uow.BackgroundJobs.AddAsync(job);
        await uow.SaveChangesAsync();

        await processor.ProcessOnceForTestsAsync();

        var reloaded = await uow.BackgroundJobs.GetByIdAsync(job.Id);
        Assert.Equal(BackgroundJobStatus.Cancelled, reloaded!.Status);
        Assert.Contains(notifier.Events, e => e.StartsWith("Cancelled") && e.Contains(job.Id.ToString()));
        Assert.DoesNotContain(notifier.Events, e => e.StartsWith("Started") && e.Contains(job.Id.ToString()));
    }

    [Fact]
    public async Task ProcessOnce_UnknownJobType_FailsJob()
    {
        var (_, _, uow, notifier, processor) = CreateSystem();

        // Use a job type not currently implemented in ExecuteJobAsync switch: DeleteVideos
        var job = new BackgroundJob
        {
            Type = BackgroundJobType.DeleteVideos,
            Status = BackgroundJobStatus.Pending,
            CreatedAt = DateTime.UtcNow
        };
        await uow.BackgroundJobs.AddAsync(job);
        await uow.SaveChangesAsync();

        await processor.ProcessOnceForTestsAsync();

        var reloaded = await uow.BackgroundJobs.GetByIdAsync(job.Id);
        Assert.Equal(BackgroundJobStatus.Failed, reloaded!.Status);
        Assert.NotNull(reloaded.ErrorMessage);
        Assert.Contains(notifier.Events, e => e.StartsWith("Failed") && e.Contains(job.Id.ToString()));
    }

    // --- No-op service implementations for executor dependencies ---

    private sealed class NoOpMetadataService : IMetadataService
    {
        public Task<VideoMetadata> ExtractMetadataAsync(string filePath, CancellationToken cancellationToken = default) =>
            Task.FromResult(new VideoMetadata());

        public Task<ImvdbMetadata?> GetImvdbMetadataAsync(string artist, string title, CancellationToken cancellationToken = default) =>
            Task.FromResult<ImvdbMetadata?>(null);

        public Task<List<ImvdbMetadata>> GetTopMatchesAsync(string artist, string title, int maxResults = 5, CancellationToken cancellationToken = default) =>
            Task.FromResult(new List<ImvdbMetadata>());

        public Task<MusicBrainzMetadata?> GetMusicBrainzMetadataAsync(string artist, string title, CancellationToken cancellationToken = default) =>
            Task.FromResult<MusicBrainzMetadata?>(null);

        public Task<string> GenerateNfoAsync(Video video, string outputPath, CancellationToken cancellationToken = default) =>
            Task.FromResult(outputPath);

        public Task<NfoData?> ReadNfoAsync(string nfoPath, CancellationToken cancellationToken = default) =>
            Task.FromResult<NfoData?>(null);

        public Task<Video> EnrichVideoMetadataAsync(Video video, bool fetchOnlineMetadata = true, CancellationToken cancellationToken = default) =>
            Task.FromResult(video);

        public Task<MetadataEnrichmentResult> EnrichVideoMetadataWithResultAsync(Video video, bool fetchOnlineMetadata = true, CancellationToken cancellationToken = default) =>
            Task.FromResult(new MetadataEnrichmentResult { Video = video, MatchConfidence = 0, MetadataApplied = false, RequiresManualReview = false });

        public Task<Video> UpdateVideoFromImvdbMetadataAsync(Video video, ImvdbMetadata metadata, CancellationToken cancellationToken = default) =>
            Task.FromResult(video);

        public Task<string?> DownloadThumbnailAsync(string thumbnailUrl, string outputPath, CancellationToken cancellationToken = default) =>
            Task.FromResult<string?>(null);

        public Task<string?> EnsureThumbnailAsync(Video video, string? remoteImageUrl = null, CancellationToken cancellationToken = default) =>
            Task.FromResult<string?>(null);
    }

    private sealed class NoOpFileOrganizationService : IFileOrganizationService
    {
        public Task<string> OrganizeVideoFileAsync(Video video, string sourceFilePath, CancellationToken cancellationToken = default) =>
            Task.FromResult(sourceFilePath);

        public string GenerateFilePath(Video video, string pattern) =>
            $"/organized/{video.Artist}/{video.Title}.mp4";

        public bool ValidatePattern(string pattern) => true;

        public Dictionary<string, string> GetAvailablePatternVariables() =>
            new Dictionary<string, string>();

        public string PreviewOrganizedPath(Video video, string pattern) =>
            $"/preview/{video.Artist}/{video.Title}.mp4";

        public Task<ReorganizeResult> ReorganizeLibraryAsync(string newPattern, IProgress<ReorganizeProgress>? progress = null, CancellationToken cancellationToken = default) =>
            Task.FromResult(new ReorganizeResult { TotalVideos = 0, SuccessfulMoves = 0, FailedMoves = 0 });

        public Task<bool> MoveVideoFileAsync(Video video, string newPath, CancellationToken cancellationToken = default) =>
            Task.FromResult(true);

        public void EnsureDirectoryExists(string filePath) { }
    }

    private sealed class NoOpSourceVerificationService : ISourceVerificationService
    {
        public Task<VideoSourceVerification> VerifyVideoAsync(Video video, Fuzzbin.Services.Models.SourceVerificationRequest request, CancellationToken cancellationToken = default)
        {
            var verification = new VideoSourceVerification
            {
                Id = Guid.NewGuid(),
                VideoId = video.Id,
                Status = VideoSourceVerificationStatus.Verified,
                CreatedAt = DateTime.UtcNow,
                UpdatedAt = DateTime.UtcNow
            };
            return Task.FromResult(verification);
        }

        public Task<IReadOnlyList<VideoSourceVerification>> VerifyVideosAsync(IEnumerable<Video> videos, Fuzzbin.Services.Models.SourceVerificationRequest request, CancellationToken cancellationToken = default) =>
            Task.FromResult<IReadOnlyList<VideoSourceVerification>>(new List<VideoSourceVerification>());

        public Task<VideoSourceVerification?> GetLatestAsync(Guid videoId, CancellationToken cancellationToken = default) =>
            Task.FromResult<VideoSourceVerification?>(null);

        public Task<VideoSourceVerification> OverrideAsync(Guid verificationId, Fuzzbin.Services.Models.SourceVerificationOverride overrideRequest, CancellationToken cancellationToken = default) =>
            Task.FromResult(new VideoSourceVerification
            {
                Id = verificationId,
                Status = VideoSourceVerificationStatus.Verified,
                CreatedAt = DateTime.UtcNow,
                UpdatedAt = DateTime.UtcNow
            });
    }
}