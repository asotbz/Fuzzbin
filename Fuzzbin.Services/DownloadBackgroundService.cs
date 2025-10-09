using System;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;
using DownloadStatusEnum = Fuzzbin.Core.Entities.DownloadStatus;
using ServicesDownloadQueueService = Fuzzbin.Services.Interfaces.IDownloadQueueService;

namespace Fuzzbin.Services
{
    public class DownloadBackgroundService : BackgroundService
    {
        private readonly IServiceScopeFactory _scopeFactory;
        private readonly ILogger<DownloadBackgroundService> _logger;
        private readonly IDownloadTaskQueue _taskQueue;
        private readonly IDownloadSettingsProvider _settingsProvider;
        private readonly DownloadWorkerOptions _options;
        private readonly SemaphoreSlim _downloadSemaphore;
        private static readonly string[] CleanupPatterns = { "*.part", "*.tmp", "*.ytdl", "*.aria2", "*.info.json" };

        public DownloadBackgroundService(
            IServiceScopeFactory scopeFactory,
            ILogger<DownloadBackgroundService> logger,
            IDownloadTaskQueue taskQueue,
            IDownloadSettingsProvider settingsProvider)
        {
            _scopeFactory = scopeFactory;
            _logger = logger;
            _taskQueue = taskQueue;
            _settingsProvider = settingsProvider;
            _options = _settingsProvider.GetOptions();
            var maxConcurrent = Math.Max(1, _options.MaxConcurrentDownloads);
            _downloadSemaphore = new SemaphoreSlim(maxConcurrent, maxConcurrent);
        }

        protected override async Task ExecuteAsync(CancellationToken stoppingToken)
        {
            _logger.LogInformation("Download Background Service started with concurrency {Concurrency}", _downloadSemaphore.CurrentCount);

            await SeedPendingDownloadsAsync(stoppingToken);

            await foreach (var queueId in _taskQueue.DequeueAsync(stoppingToken))
            {
                await _downloadSemaphore.WaitAsync(stoppingToken);

                _ = Task.Run(async () =>
                {
                    try
                    {
                        await ProcessQueueItemAsync(queueId, stoppingToken);
                    }
                    catch (OperationCanceledException)
                    {
                        // Ignore cancellation as service is shutting down
                    }
                    catch (Exception ex)
                    {
                        _logger.LogError(ex, "Unexpected error while processing queue item {QueueId}", queueId);
                    }
                    finally
                    {
                        _downloadSemaphore.Release();
                    }
                }, CancellationToken.None);
            }

            _logger.LogInformation("Download Background Service stopping");
        }

        private async Task SeedPendingDownloadsAsync(CancellationToken cancellationToken)
        {
            using var scope = _scopeFactory.CreateScope();
            var queueService = scope.ServiceProvider.GetRequiredService<ServicesDownloadQueueService>();
            var pending = await queueService.GetPendingDownloadsAsync();

            foreach (var item in pending.Where(p => p.Status == DownloadStatusEnum.Queued && !p.IsDeleted))
            {
                await _taskQueue.QueueAsync(item.Id, cancellationToken);
            }
        }

        private async Task ProcessQueueItemAsync(Guid queueId, CancellationToken stoppingToken)
        {
            using var scope = _scopeFactory.CreateScope();
            var queueService = scope.ServiceProvider.GetRequiredService<ServicesDownloadQueueService>();
            var ytDlpService = scope.ServiceProvider.GetRequiredService<IYtDlpService>();
            var fileService = scope.ServiceProvider.GetRequiredService<IFileOrganizationService>();
            var unitOfWork = scope.ServiceProvider.GetRequiredService<IUnitOfWork>();

            var queueItem = await queueService.GetByIdAsync(queueId);
            if (queueItem == null || queueItem.IsDeleted)
            {
                return;
            }

            if (queueItem.Status != DownloadStatusEnum.Queued)
            {
                _logger.LogDebug("Queue item {QueueId} skipped because status is {Status}", queueId, queueItem.Status);
                return;
            }

            var options = _settingsProvider.GetOptions();

            await queueService.UpdateStatusAsync(queueId, DownloadStatusEnum.Downloading);

            var outputDirectory = ResolveOutputDirectory(queueItem.OutputPath);
            Directory.CreateDirectory(outputDirectory);
            var tempDirectory = ResolveTempDirectory();
            Directory.CreateDirectory(tempDirectory);

            try
            {
                var lastReportedAt = DateTime.MinValue;
                double lastReportedPercent = -1;

                var progress = new Progress<Fuzzbin.Core.Interfaces.DownloadProgress>(p =>
                {
                    var now = DateTime.UtcNow;
                    if (p == null)
                    {
                        return;
                    }

                    var percent = Math.Clamp(p.Percentage, 0, 100);
                    var percentDelta = percent - lastReportedPercent;
                    if (percentDelta < options.ProgressPercentageStep && (now - lastReportedAt) < TimeSpan.FromSeconds(1))
                    {
                        return;
                    }

                    lastReportedPercent = percent;
                    lastReportedAt = now;
                    _ = Task.Run(async () =>
                    {
                        try
                        {
                            await queueService.UpdateProgressAsync(queueId, percent, p.DownloadSpeed, p.ETA);
                        }
                        catch (Exception ex)
                        {
                            _logger.LogDebug(ex, "Failed to update progress for queue item {QueueId}", queueId);
                        }
                    }, CancellationToken.None);
                });

                var downloadResult = await ytDlpService.DownloadVideoAsync(
                    queueItem.Url,
                    outputDirectory,
                    progress,
                    stoppingToken);

                if (downloadResult.Success && !string.IsNullOrWhiteSpace(downloadResult.FilePath))
                {
                    var persistenceResult = await PersistVideoAsync(
                        queueItem,
                        downloadResult,
                        unitOfWork,
                        ytDlpService,
                        fileService,
                        stoppingToken);

                    var finalPath = persistenceResult.FinalFilePath ?? downloadResult.FilePath;
                    var finalDirectory = string.IsNullOrWhiteSpace(finalPath)
                        ? outputDirectory
                        : Path.GetDirectoryName(finalPath) ?? outputDirectory;

                    await queueService.UpdateFilePathAsync(queueId, finalPath, finalDirectory);
                    await queueService.MarkAsCompletedAsync(queueId, persistenceResult.VideoId);
                    _logger.LogInformation("Successfully processed queue item {QueueId}", queueId);
                    return;
                }

                var errorMessage = downloadResult.ErrorMessage ?? "Download failed";
                await queueService.UpdateStatusAsync(queueId, DownloadStatusEnum.Failed, errorMessage);

                var maxRetries = Math.Max(0, options.MaxRetryCount);
                if (queueItem.RetryCount < maxRetries)
                {
                    _logger.LogWarning(
                        "Queue item {QueueId} failed (attempt {Attempt}/{Max}). Retrying in {DelaySeconds}s. Error: {Error}",
                        queueId,
                        queueItem.RetryCount + 1,
                        maxRetries,
                        options.RetryBackoffSeconds,
                        errorMessage);

                    if (options.RetryBackoffSeconds > 0)
                    {
                        try
                        {
                            await Task.Delay(TimeSpan.FromSeconds(options.RetryBackoffSeconds), stoppingToken);
                        }
                        catch (OperationCanceledException)
                        {
                            return;
                        }
                    }

                    await queueService.RetryDownloadAsync(queueId);
                    return;
                }

                _logger.LogError(
                    "Queue item {QueueId} exceeded retry budget. Marking as permanently failed. Error: {Error}",
                    queueId,
                    errorMessage);
            }
            finally
            {
                CleanupDownloadArtifacts(outputDirectory, tempDirectory);
            }
        }

        private async Task<(Guid? VideoId, string? FinalFilePath)> PersistVideoAsync(
            DownloadQueueItem queueItem,
            DownloadResult downloadResult,
            IUnitOfWork unitOfWork,
            IYtDlpService ytDlpService,
            IFileOrganizationService fileService,
            CancellationToken cancellationToken)
        {
            try
            {
                var metadata = downloadResult.Metadata ?? await ytDlpService.GetVideoMetadataAsync(queueItem.Url, cancellationToken);

                if (metadata == null)
                {
                    _logger.LogWarning("No metadata returned for {Url}", queueItem.Url);
                    return (queueItem.VideoId, downloadResult.FilePath);
                }

                var existingVideo = await unitOfWork.Videos.FirstOrDefaultAsync(v => v.YouTubeId == metadata.Id);

                if (existingVideo == null)
                {
                    var video = new Video
                    {
                        Title = metadata.Title ?? Path.GetFileNameWithoutExtension(downloadResult.FilePath!),
                        Artist = metadata.Artist ?? metadata.Channel ?? "Unknown Artist",
                        FilePath = downloadResult.FilePath!,
                        FileSize = metadata.FileSize,
                        VideoCodec = metadata.VideoCodec,
                        AudioCodec = metadata.AudioCodec,
                        FrameRate = metadata.Fps,
                        Format = Path.GetExtension(downloadResult.FilePath)?.Trim('.'),
                        Duration = metadata.Duration.HasValue ? (int)metadata.Duration.Value.TotalSeconds : null,
                        YouTubeId = metadata.Id,
                        Description = metadata.Description,
                        ImportedAt = DateTime.UtcNow
                    };

                    if (metadata.Width.HasValue && metadata.Height.HasValue)
                    {
                        video.Resolution = $"{metadata.Width}x{metadata.Height}";
                    }

                    await unitOfWork.Videos.AddAsync(video);
                    await unitOfWork.SaveChangesAsync();
                    var finalPath = await fileService.OrganizeVideoFileAsync(video, downloadResult.FilePath!, cancellationToken);
                    return (video.Id, finalPath);
                }

                existingVideo.FilePath = downloadResult.FilePath!;
                existingVideo.ImportedAt = DateTime.UtcNow;
                existingVideo.FileSize = metadata.FileSize ?? existingVideo.FileSize;
                existingVideo.VideoCodec = metadata.VideoCodec ?? existingVideo.VideoCodec;
                existingVideo.AudioCodec = metadata.AudioCodec ?? existingVideo.AudioCodec;
                existingVideo.FrameRate = metadata.Fps ?? existingVideo.FrameRate;
                existingVideo.Format = Path.GetExtension(downloadResult.FilePath)?.Trim('.') ?? existingVideo.Format;

                if (metadata.Duration.HasValue)
                {
                    existingVideo.Duration = (int)metadata.Duration.Value.TotalSeconds;
                }

                existingVideo.Description = metadata.Description ?? existingVideo.Description;

                if (metadata.Width.HasValue && metadata.Height.HasValue)
                {
                    existingVideo.Resolution = $"{metadata.Width}x{metadata.Height}";
                }

                await unitOfWork.Videos.UpdateAsync(existingVideo);
                await unitOfWork.SaveChangesAsync();
                var existingFinalPath = await fileService.OrganizeVideoFileAsync(existingVideo, downloadResult.FilePath!, cancellationToken);
                return (existingVideo.Id, existingFinalPath);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error persisting video entity for queue item {QueueId}", queueItem.Id);
                return (queueItem.VideoId, downloadResult.FilePath);
            }
        }

        private string ResolveOutputDirectory(string? requestedPath)
        {
            var output = !string.IsNullOrWhiteSpace(requestedPath)
                ? requestedPath!
                : _options.OutputDirectory;

            if (!Path.IsPathRooted(output))
            {
                output = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, output);
            }

            return output;
        }

        private string ResolveTempDirectory()
        {
            var tempPath = _options.TempDirectory;

            if (string.IsNullOrWhiteSpace(tempPath))
            {
                tempPath = Path.Combine(_options.OutputDirectory, "tmp");
            }

            if (!Path.IsPathRooted(tempPath))
            {
                tempPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, tempPath);
            }

            return tempPath;
        }

        private void CleanupDownloadArtifacts(params string?[] directories)
        {
            foreach (var directory in directories)
            {
                if (string.IsNullOrWhiteSpace(directory) || !Directory.Exists(directory))
                {
                    continue;
                }

                try
                {
                    foreach (var pattern in CleanupPatterns)
                    {
                        foreach (var file in Directory.EnumerateFiles(directory, pattern))
                        {
                            TryDeleteFile(file);
                        }
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogDebug(ex, "Cleanup skipped for {Directory}", directory);
                }
            }
        }

        private void TryDeleteFile(string filePath)
        {
            try
            {
                if (File.Exists(filePath))
                {
                    File.Delete(filePath);
                }
            }
            catch (Exception ex)
            {
                _logger.LogDebug(ex, "Unable to delete {File}", filePath);
            }
        }

        public override async Task StopAsync(CancellationToken cancellationToken)
        {
            _logger.LogInformation("Download Background Service is stopping");
            await base.StopAsync(cancellationToken);
            _downloadSemaphore.Dispose();
        }
    }
}
