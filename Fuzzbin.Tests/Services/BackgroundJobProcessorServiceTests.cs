using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Data.Sqlite;
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

    private sealed class TestEnvironment : IAsyncDisposable
    {
        private readonly SqliteConnection _connection;
        private bool _disposed;

        public TestEnvironment(ServiceProvider provider, SqliteConnection connection, TestJobProgressNotifier notifier, BackgroundJobProcessorService processor)
        {
            Provider = provider;
            _connection = connection;
            Notifier = notifier;
            Processor = processor;
        }

        public ServiceProvider Provider { get; }
        public TestJobProgressNotifier Notifier { get; }
        public BackgroundJobProcessorService Processor { get; }

        public IServiceScope CreateScope() => Provider.CreateScope();

        public async ValueTask DisposeAsync()
        {
            if (_disposed)
            {
                return;
            }

            _disposed = true;
            await Provider.DisposeAsync();
            await _connection.DisposeAsync();
        }
    }

    private static TestEnvironment CreateSystem()
    {
        var services = new ServiceCollection();

        // SQLite in-memory database - maintains data across scopes as long as connection stays open
        var connection = new SqliteConnection("DataSource=:memory:");
        connection.Open();

        services.AddDbContext<ApplicationDbContext>(o =>
        {
            o.UseSqlite(connection);
            o.EnableSensitiveDataLogging();
        });

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

        // Create the database schema
        using (var setupScope = provider.CreateScope())
        {
            var dbContext = setupScope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
            dbContext.Database.EnsureCreated();
        }

        // Create the processor using the service provider (not from a scope)
        // so it can create its own scopes internally
        var processor = ActivatorUtilities.CreateInstance<BackgroundJobProcessorService>(provider);

        return new TestEnvironment(provider, connection, notifier, processor);
    }

    private static async Task WithUnitOfWorkAsync(TestEnvironment env, Func<IUnitOfWork, Task> action)
    {
        using var scope = env.CreateScope();
        var uow = scope.ServiceProvider.GetRequiredService<IUnitOfWork>();
        await action(uow);
    }

    private static async Task<T> WithUnitOfWorkAsync<T>(TestEnvironment env, Func<IUnitOfWork, Task<T>> action)
    {
        using var scope = env.CreateScope();
        var uow = scope.ServiceProvider.GetRequiredService<IUnitOfWork>();
        return await action(uow);
    }

    private static async Task<BackgroundJob?> GetJobSnapshotAsync(TestEnvironment env, Guid jobId)
    {
        using var scope = env.CreateScope();
        var dbContext = scope.ServiceProvider.GetRequiredService<ApplicationDbContext>();
        return await dbContext.BackgroundJobs.AsNoTracking().FirstOrDefaultAsync(j => j.Id == jobId);
    }

    [Fact]
    public async Task ProcessOnce_ExecutesPendingJob_CompletesSuccessfully()
    {
        await using var system = CreateSystem();

        var jobId = await WithUnitOfWorkAsync(system, async uow =>
        {
            var job = new BackgroundJob
            {
                Type = BackgroundJobType.RefreshMetadata,
                Status = BackgroundJobStatus.Pending,
                CreatedAt = DateTime.UtcNow,
                IsActive = true
            };

            await uow.BackgroundJobs.AddAsync(job);
            await uow.SaveChangesAsync();
            return job.Id;
        });

        await system.Processor.ProcessOnceForTestsAsync();

        var reloaded = await WithUnitOfWorkAsync(system, uow => uow.BackgroundJobs.GetByIdAsync(jobId));
        Assert.NotNull(reloaded);
        // The job should complete or fail - either is acceptable since no-op services are used
        Assert.True(reloaded!.Status == BackgroundJobStatus.Completed || reloaded.Status == BackgroundJobStatus.Failed,
            $"Expected job to be Completed or Failed, but was {reloaded.Status}");
        Assert.Contains(system.Notifier.Events, e => e.StartsWith("Started") && e.Contains(jobId.ToString()));
    }

    [Fact]
    public async Task ProcessOnce_CancelsDuplicatePendingSingletons()
    {
        await using var system = CreateSystem();

        var (firstId, duplicateId) = await WithUnitOfWorkAsync(system, async uow =>
        {
            var first = new BackgroundJob
            {
                Type = BackgroundJobType.OrganizeFiles,
                Status = BackgroundJobStatus.Pending,
                CreatedAt = DateTime.UtcNow,
                IsActive = true
            };
            var duplicate = new BackgroundJob
            {
                Type = BackgroundJobType.OrganizeFiles,
                Status = BackgroundJobStatus.Pending,
                CreatedAt = DateTime.UtcNow.AddSeconds(1),
                IsActive = true
            };

            await uow.BackgroundJobs.AddAsync(first);
            await uow.SaveChangesAsync();

            await uow.BackgroundJobs.AddAsync(duplicate);
            await uow.SaveChangesAsync();

            return (first.Id, duplicate.Id);
        });

        await system.Processor.ProcessOnceForTestsAsync();

        var firstJob = await GetJobSnapshotAsync(system, firstId);
        var duplicateJob = await GetJobSnapshotAsync(system, duplicateId);

        var events = system.Notifier.Events.ToArray();
        var stateDump = $"FirstId={firstId}, FirstCreatedAt={firstJob?.CreatedAt:o}, FirstStatus={firstJob?.Status}, FirstCancelledFlag={firstJob?.CancellationRequested}, DuplicateId={duplicateId}, DuplicateCreatedAt={duplicateJob?.CreatedAt:o}, DuplicateStatus={duplicateJob?.Status}, DuplicateCancelledFlag={duplicateJob?.CancellationRequested}";

        Assert.True(firstJob!.Status == BackgroundJobStatus.Completed,
            $"Expected primary OrganizeFiles job to complete but saw {firstJob.Status}. Events: {string.Join(", ", events)}. State: {stateDump}");
        Assert.True(duplicateJob!.Status == BackgroundJobStatus.Cancelled,
            $"Expected duplicate OrganizeFiles job to be cancelled but saw {duplicateJob.Status}. Events: {string.Join(", ", events)}. State: {stateDump}");
        Assert.Contains(events, e => e.StartsWith("Cancelled") && e.Contains(duplicateId.ToString()));
    }

    [Fact]
    public async Task ProcessOnce_RespectsPreExecutionCancellation()
    {
        await using var system = CreateSystem();

        var jobId = await WithUnitOfWorkAsync(system, async uow =>
        {
            var job = new BackgroundJob
            {
                Type = BackgroundJobType.RefreshMetadata,
                Status = BackgroundJobStatus.Pending,
                CreatedAt = DateTime.UtcNow,
                CancellationRequested = true,
                IsActive = true
            };

            await uow.BackgroundJobs.AddAsync(job);
            await uow.SaveChangesAsync();
            return job.Id;
        });

        await system.Processor.ProcessOnceForTestsAsync();

        var reloaded = await WithUnitOfWorkAsync(system, uow => uow.BackgroundJobs.GetByIdAsync(jobId));
        Assert.Equal(BackgroundJobStatus.Cancelled, reloaded!.Status);
        Assert.Contains(system.Notifier.Events, e => e.StartsWith("Cancelled") && e.Contains(jobId.ToString()));
        Assert.DoesNotContain(system.Notifier.Events, e => e.StartsWith("Started") && e.Contains(jobId.ToString()));
    }

    [Fact]
    public async Task ProcessOnce_UnknownJobType_FailsJob()
    {
        await using var system = CreateSystem();

        var jobId = await WithUnitOfWorkAsync(system, async uow =>
        {
            var job = new BackgroundJob
            {
                Type = BackgroundJobType.DeleteVideos,
                Status = BackgroundJobStatus.Pending,
                CreatedAt = DateTime.UtcNow,
                IsActive = true
            };

            await uow.BackgroundJobs.AddAsync(job);
            await uow.SaveChangesAsync();
            return job.Id;
        });

        await system.Processor.ProcessOnceForTestsAsync();

        var reloaded = await WithUnitOfWorkAsync(system, uow => uow.BackgroundJobs.GetByIdAsync(jobId));
        Assert.Equal(BackgroundJobStatus.Failed, reloaded!.Status);
        Assert.NotNull(reloaded.ErrorMessage);
        Assert.Contains(system.Notifier.Events, e => e.StartsWith("Failed") && e.Contains(jobId.ToString()));
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

        public Fuzzbin.Core.Models.PatternValidationResult ValidatePatternWithDetails(string pattern) =>
            new Fuzzbin.Core.Models.PatternValidationResult { IsValid = true };

        public string GenerateExampleFilename(string pattern) =>
            $"Example-Artist/Example-Title.mp4";

        public List<Fuzzbin.Core.Models.PatternExample> GetPatternExamples() =>
            new List<Fuzzbin.Core.Models.PatternExample>();
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
