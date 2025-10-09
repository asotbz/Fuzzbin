using System;
using System.IO;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Data.Context;
using Fuzzbin.Data.Repositories;
using Fuzzbin.Services;
using Fuzzbin.Services.Models;
using Fuzzbin.Services.Interfaces;
using Xunit;
using DownloadStatusEnum = Fuzzbin.Core.Entities.DownloadStatus;

namespace Fuzzbin.Tests.Services;

public class DownloadQueueServiceTests
{
    private static (ApplicationDbContext Context, IUnitOfWork UnitOfWork, DownloadQueueService Service) CreateService()
    {
        var options = new DbContextOptionsBuilder<ApplicationDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .Options;

        var context = new ApplicationDbContext(options);
        var unitOfWork = new UnitOfWork(context);
        var taskQueue = new DownloadTaskQueue();
        var settingsProvider = new TestDownloadSettingsProvider();
        var service = new DownloadQueueService(
            unitOfWork,
            NullLogger<DownloadQueueService>.Instance,
            taskQueue,
            settingsProvider);
        return (context, unitOfWork, service);
    }

    [Fact]
    public async Task RetryFailedDownloadAsync_ResetsStatusAndIncrementsRetries()
    {
        var (context, unitOfWork, service) = CreateService();
        await using var _ = context;

        var queued = await service.AddToQueueAsync("https://example.com/test", "downloads", null, 1);
        await unitOfWork.SaveChangesAsync();

        await service.UpdateStatusAsync(queued.Id, DownloadStatusEnum.Failed, "error");
        var retryResult = await service.RetryDownloadAsync(queued.Id);

        Assert.True(retryResult);

        var updated = await service.GetByIdAsync(queued.Id);
        Assert.NotNull(updated);
        Assert.Equal(DownloadStatusEnum.Queued, updated!.Status);
        Assert.Equal(1, updated.RetryCount);
    }

    [Fact]
    public async Task GetQueuePositionAsync_UsesPriorityOrdering()
    {
        var (context, unitOfWork, service) = CreateService();
        await using var _ = context;

        var highPriority = await service.AddToQueueAsync("https://example.com/high", "downloads", null, priority: 10);
        var lowPriority = await service.AddToQueueAsync("https://example.com/low", "downloads", null, priority: 1);
        await unitOfWork.SaveChangesAsync();

        var positionHigh = await service.GetQueuePositionAsync(highPriority.Id);
        var positionLow = await service.GetQueuePositionAsync(lowPriority.Id);

        Assert.Equal(1, positionHigh);
        Assert.Equal(2, positionLow);
    }

    [Fact]
    public async Task GetPendingDownloadsAsync_ReturnsQueuedAndFailed()
    {
        var (context, unitOfWork, service) = CreateService();
        await using var _ = context;

        var queued = await service.AddToQueueAsync("https://example.com/queued", "downloads", null, priority: 1);
        var failed = await service.AddToQueueAsync("https://example.com/failed", "downloads", null, priority: 2);
        await unitOfWork.SaveChangesAsync();

        await service.UpdateStatusAsync(failed.Id, DownloadStatusEnum.Failed, "error");

        var pending = await service.GetPendingDownloadsAsync();

        Assert.Contains(pending, item => item.Id == queued.Id);
        Assert.Contains(pending, item => item.Id == failed.Id);
    }
}

internal sealed class TestDownloadSettingsProvider : IDownloadSettingsProvider
{
    private readonly DownloadWorkerOptions _options = new()
    {
        OutputDirectory = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString()),
        TempDirectory = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString(), "tmp"),
        MaxConcurrentDownloads = 2,
        MaxRetryCount = 3,
        Format = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        ProgressPercentageStep = 1,
        RetryBackoffSeconds = 15
    };

    public DownloadWorkerOptions GetOptions() => _options;

    public string GetFfmpegPath() => "ffmpeg";

    public string GetFfprobePath() => "ffprobe";

    public void Invalidate()
    {
        // No-op for tests
    }
}
