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
    public class SourceVerificationJobExecutor
    {
        private readonly ILogger<SourceVerificationJobExecutor> _logger;
        private readonly IBackgroundJobService _jobService;
        private readonly ISourceVerificationService _verificationService;
        private readonly IUnitOfWork _unitOfWork;
        private readonly IJobProgressNotifier _progressNotifier;

        public SourceVerificationJobExecutor(
            ILogger<SourceVerificationJobExecutor> logger,
            IBackgroundJobService jobService,
            ISourceVerificationService verificationService,
            IUnitOfWork unitOfWork,
            IJobProgressNotifier progressNotifier)
        {
            _logger = logger;
            _jobService = jobService;
            _verificationService = verificationService;
            _unitOfWork = unitOfWork;
            _progressNotifier = progressNotifier;
        }

        public async Task ExecuteAsync(Guid jobId, List<Guid> videoIds, CancellationToken cancellationToken = default)
        {
            try
            {
                await _jobService.StartJobAsync(jobId, cancellationToken);
                await _progressNotifier.NotifyJobStartedAsync(jobId, BackgroundJobType.VerifySourceUrls, cancellationToken);

                var videos = new List<Video>();
                foreach (var videoId in videoIds)
                {
                    var video = await _unitOfWork.Videos.GetByIdAsync(videoId);
                    if (video != null)
                    {
                        videos.Add(video);
                    }
                }

                await _jobService.UpdateItemCountsAsync(jobId, videos.Count, 0, 0, cancellationToken);

                var processed = 0;
                var failed = 0;

                foreach (var video in videos)
                {
                    if (await _jobService.IsCancellationRequestedAsync(jobId, cancellationToken))
                    {
                        _logger.LogInformation("Source verification job {JobId} cancelled", jobId);
                        await _jobService.FailJobAsync(jobId, "Job was cancelled by user", cancellationToken);
                        await _progressNotifier.NotifyJobCancelledAsync(jobId);
                        return;
                    }

                    try
                    {
                        // Create an empty request (service will use video's existing source URLs)
                        var request = new SourceVerificationRequest();
                        
                        // Verify the video
                        var verification = await _verificationService.VerifyVideoAsync(
                            video,
                            request,
                            cancellationToken);

                        processed++;

                        // Count failures
                        if (verification.Status == VideoSourceVerificationStatus.Failed ||
                            verification.Status == VideoSourceVerificationStatus.SourceMissing)
                        {
                            failed++;
                        }

                        var progress = (int)((processed / (double)videos.Count) * 100);
                        await _jobService.UpdateProgressAsync(
                            jobId,
                            progress,
                            $"Verified {processed} of {videos.Count} videos",
                            cancellationToken);

                        await _progressNotifier.NotifyJobProgressAsync(
                            jobId,
                            progress,
                            $"Verified {processed} of {videos.Count} videos");
                    }
                    catch (Exception ex)
                    {
                        _logger.LogError(ex, "Error verifying source for video {VideoId}", video.Id);
                        failed++;
                        processed++;
                    }
                }

                await _jobService.UpdateItemCountsAsync(jobId, videos.Count, processed, failed, cancellationToken);
                await _jobService.CompleteJobAsync(jobId, cancellationToken: cancellationToken);
                await _progressNotifier.NotifyJobCompletedAsync(jobId, $"Verified {processed} videos, {failed} failed", cancellationToken);

                _logger.LogInformation(
                    "Source verification job {JobId} completed. Verified: {Processed}, Failed: {Failed}",
                    jobId, processed, failed);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error executing source verification job {JobId}", jobId);
                await _jobService.FailJobAsync(jobId, ex.Message, cancellationToken);
                await _progressNotifier.NotifyJobFailedAsync(jobId, ex.Message);
            }
        }
    }
}