using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;

namespace Fuzzbin.Services.BackgroundJobs
{
    /// <summary>
    /// Source verification executor refactored to use BaseJobExecutor for unified progress & result handling.
    /// Still exposes Guid-based ExecuteAsync signature for compatibility with existing processor call.
    /// </summary>
    public class SourceVerificationJobExecutor : BaseJobExecutor
    {
        private readonly IBackgroundJobService _jobService;
        private readonly ISourceVerificationService _verificationService;

        public SourceVerificationJobExecutor(
            IBackgroundJobService jobService,
            ISourceVerificationService verificationService,
            IUnitOfWork unitOfWork,
            IJobProgressNotifier notifier,
            ILogger<SourceVerificationJobExecutor> logger)
            : base(unitOfWork, notifier, logger)
        {
            _jobService = jobService;
            _verificationService = verificationService;
        }

        /// <summary>
        /// Execute verification for provided video IDs (must be provided; no implicit enumeration).
        /// </summary>
        public async Task ExecuteAsync(Guid jobId, List<Guid> videoIds, CancellationToken ct = default)
        {
            var job = await _unitOfWork.BackgroundJobs.GetByIdAsync(jobId);
            if (job == null)
            {
                _logger.LogWarning("Cannot execute source verification - job {JobId} not found", jobId);
                return;
            }

            try
            {
                // Processor already set status Running; initialize counts + notify started.
                var videos = new List<Video>();
                foreach (var vid in videoIds)
                {
                    var video = await _unitOfWork.Videos.GetByIdAsync(vid);
                    if (video != null) videos.Add(video);
                }

                await InitializeJobAsync(job, BackgroundJobType.VerifySourceUrls, videos.Count, ct);
                _logger.LogInformation("Source verification job {JobId} starting for {Count} videos", job.Id, videos.Count);

                int processed = 0;
                int failed = 0;

                foreach (var video in videos)
                {
                    if (job.CancellationRequested)
                    {
                        _logger.LogInformation("Source verification job {JobId} cancellation detected mid-loop", job.Id);
                        return;
                    }

                    try
                    {
                        var request = new SourceVerificationRequest();
                        var verification = await _verificationService.VerifyVideoAsync(video, request, ct);

                        if (verification.Status == VideoSourceVerificationStatus.Failed ||
                            verification.Status == VideoSourceVerificationStatus.SourceMissing)
                        {
                            failed++;
                        }
                    }
                    catch (Exception ex)
                    {
                        _logger.LogError(ex, "Error verifying source for video {VideoId}", video.Id);
                        failed++;
                    }

                    processed++;
                    job.ProcessedItems = processed;
                    job.FailedItems = failed;

                    if (processed % 5 == 0 || processed == videos.Count)
                    {
                        await UpdateProgressAsync(job, $"Verified {processed}/{videos.Count} videos", ct);
                    }
                }

                var summary = $"Verified {processed} videos, {failed} failed";
                await CompleteAsync(job, summary, ct);
                _logger.LogInformation("Source verification job {JobId} completed. {Summary}", job.Id, summary);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Source verification job {JobId} failed", job.Id);
                // Allow processor to mark Failed and serialize failure result.
                throw;
            }
        }
    }
}