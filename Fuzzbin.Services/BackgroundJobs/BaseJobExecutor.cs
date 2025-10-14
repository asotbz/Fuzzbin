using System;
using System.Threading;
using System.Threading.Tasks;
using System.Linq;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.Interfaces;

namespace Fuzzbin.Services.BackgroundJobs
{
    /// <summary>
    /// Base helper for background job executors handling common progress & cancellation logic.
    /// </summary>
    public abstract class BaseJobExecutor
    {
        protected readonly IUnitOfWork _unitOfWork;
        protected readonly IJobProgressNotifier _notifier;
        protected readonly ILogger _logger;

        protected BaseJobExecutor(
            IUnitOfWork unitOfWork,
            IJobProgressNotifier notifier,
            ILogger logger)
        {
            _unitOfWork = unitOfWork;
            _notifier = notifier;
            _logger = logger;
        }

        protected async Task InitializeJobAsync(BackgroundJob job, BackgroundJobType type, int totalItems, CancellationToken ct)
        {
            job.TotalItems = totalItems;
            job.ProcessedItems = 0;
            job.FailedItems = 0;
            job.Progress = 0;
            job.StatusMessage = "Starting...";
            await _unitOfWork.SaveChangesAsync();
            await _notifier.NotifyJobStartedAsync(job.Id, type, ct);
        }

        protected async Task<bool> UpdateProgressAsync(BackgroundJob job, string? status, CancellationToken ct)
        {
            if (job.CancellationRequested)
            {
                job.StatusMessage = "Cancellation requested";
                await _unitOfWork.SaveChangesAsync();
                return false;
            }
            if (status != null)
            {
                job.StatusMessage = status;
            }
            if (job.TotalItems > 0)
            {
                job.Progress = (int)((job.ProcessedItems / (double)job.TotalItems) * 100);
            }
            await _unitOfWork.SaveChangesAsync();
            await _notifier.NotifyJobProgressAsync(job.Id, job.Progress, job.StatusMessage, ct);
            return true;
        }

        protected async Task CompleteAsync(BackgroundJob job, string summary, CancellationToken ct)
        {
            job.Progress = job.Progress < 100 ? 100 : job.Progress;
            job.StatusMessage = summary;
            var result = BackgroundJobResult.Create(job, summary);
            job.ResultJson = System.Text.Json.JsonSerializer.Serialize(result);
            await _unitOfWork.SaveChangesAsync();
            await _notifier.NotifyJobCompletedAsync(job.Id, summary, ct);
        }
    }

    /// <summary>
    /// Stub executor for ExportNfo (library-wide) until full implementation integrated.
    /// </summary>
    public class ExportNfoJobExecutor : BaseJobExecutor
    {
        private readonly INfoExportService _nfoExport;

        public ExportNfoJobExecutor(
            IUnitOfWork unitOfWork,
            IJobProgressNotifier notifier,
            INfoExportService nfoExport,
            ILogger<ExportNfoJobExecutor> logger)
            : base(unitOfWork, notifier, logger)
        {
            _nfoExport = nfoExport;
        }

        public async Task ExecuteAsync(BackgroundJob job, CancellationToken ct)
        {
            await InitializeJobAsync(job, BackgroundJobType.ExportNfo, 0, ct);
            // TODO: Enumerate all videos and export; for now stub immediate success.
            await UpdateProgressAsync(job, "Exporting NFO metadata (stub)...", ct);
            await CompleteAsync(job, "NFO export stub completed (no-op).", ct);
        }
    }

    /// <summary>
    /// Stub executor for Backup job - currently no real backup performed.
    /// </summary>
    public class BackupJobExecutor : BaseJobExecutor
    {
        private readonly IBackupService _backupService;

        public BackupJobExecutor(
            IUnitOfWork unitOfWork,
            IJobProgressNotifier notifier,
            IBackupService backupService,
            ILogger<BackupJobExecutor> logger)
            : base(unitOfWork, notifier, logger)
        {
            _backupService = backupService;
        }

        public async Task ExecuteAsync(BackgroundJob job, CancellationToken ct)
        {
            await InitializeJobAsync(job, BackgroundJobType.Backup, 0, ct);
            await UpdateProgressAsync(job, "Running backup (stub)...", ct);
            // TODO: Implement real backup pipeline (metadata + media manifest) in future milestone.
            await CompleteAsync(job, "Backup stub completed (no-op).", ct);
        }
    }

    /// <summary>
    /// Executor for regenerating all thumbnails (placeholder).
    /// </summary>
    public class RegenerateThumbnailsJobExecutor : BaseJobExecutor
    {
        private readonly IThumbnailService _thumbnailService;

        public RegenerateThumbnailsJobExecutor(
            IUnitOfWork unitOfWork,
            IJobProgressNotifier notifier,
            IThumbnailService thumbnailService,
            ILogger<RegenerateThumbnailsJobExecutor> logger)
            : base(unitOfWork, notifier, logger)
        {
            _thumbnailService = thumbnailService;
        }

        public async Task ExecuteAsync(BackgroundJob job, CancellationToken ct)
        {
            // Determine total videos for progress
            var videos = await _unitOfWork.Videos.GetAllAsync();
            var list = videos.ToList();
            await InitializeJobAsync(job, BackgroundJobType.RegenerateAllThumbnails, list.Count, ct);
            int index = 0;
            foreach (var v in list)
            {
                if (!await UpdateProgressAsync(job, $"Processing {index + 1}/{list.Count}", ct))
                {
                    return; // cancellation
                }
                // TODO: await _thumbnailService.RegenerateAsync(v);
                index++;
                job.ProcessedItems = index;
                if (index % 10 == 0)
                {
                    await UpdateProgressAsync(job, null, ct);
                }
            }
            await UpdateProgressAsync(job, "Finalizing...", ct);
            await CompleteAsync(job, "Thumbnail regeneration stub completed.", ct);
        }
    }
}