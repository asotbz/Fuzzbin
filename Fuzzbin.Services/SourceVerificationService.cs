using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;

namespace Fuzzbin.Services
{
    public class SourceVerificationService : ISourceVerificationService
    {
        private readonly ILogger<SourceVerificationService> _logger;
        private readonly IRepository<VideoSourceVerification> _verificationRepository;
        private readonly IRepository<Video> _videoRepository;
        private readonly IYtDlpService _ytDlpService;
        private readonly IUnitOfWork _unitOfWork;

        public SourceVerificationService(
            ILogger<SourceVerificationService> logger,
            IRepository<VideoSourceVerification> verificationRepository,
            IRepository<Video> videoRepository,
            IYtDlpService ytDlpService,
            IUnitOfWork unitOfWork)
        {
            _logger = logger;
            _verificationRepository = verificationRepository;
            _videoRepository = videoRepository;
            _ytDlpService = ytDlpService;
            _unitOfWork = unitOfWork;
        }

        public async Task<VideoSourceVerification> VerifyVideoAsync(Video video, SourceVerificationRequest request, CancellationToken cancellationToken = default)
        {
            if (video == null)
            {
                throw new ArgumentNullException(nameof(video));
            }

            request ??= new SourceVerificationRequest();

            var sourceUrl = ResolveSourceUrl(video, request);
            if (string.IsNullOrWhiteSpace(sourceUrl))
            {
                return await PersistResultAsync(video, request, null, null, VideoSourceVerificationStatus.SourceMissing, 0, cancellationToken)
                    .ConfigureAwait(false);
            }

            try
            {
                var metadata = await _ytDlpService.GetVideoMetadataAsync(sourceUrl, cancellationToken).ConfigureAwait(false);
                var comparison = BuildComparison(video, metadata);
                var confidence = ComputeConfidence(video, metadata, request, comparison);
                var status = confidence >= request.ConfidenceThreshold
                    ? VideoSourceVerificationStatus.Verified
                    : VideoSourceVerificationStatus.Mismatch;

                return await PersistResultAsync(video, request, comparison, sourceUrl, status, confidence, cancellationToken)
                    .ConfigureAwait(false);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "Source verification failed for video {VideoId}", video.Id);
                return await PersistResultAsync(video, request, null, sourceUrl, VideoSourceVerificationStatus.Failed, 0, cancellationToken)
                    .ConfigureAwait(false);
            }
        }

        public async Task<IReadOnlyList<VideoSourceVerification>> VerifyVideosAsync(IEnumerable<Video> videos, SourceVerificationRequest request, CancellationToken cancellationToken = default)
        {
            var results = new List<VideoSourceVerification>();
            foreach (var video in videos)
            {
                cancellationToken.ThrowIfCancellationRequested();
                var result = await VerifyVideoAsync(video, request.Clone(), cancellationToken).ConfigureAwait(false);
                results.Add(result);
            }

            return results;
        }

        public async Task<VideoSourceVerification?> GetLatestAsync(Guid videoId, CancellationToken cancellationToken = default)
        {
            var records = await _verificationRepository.GetAsync(r => r.VideoId == videoId).ConfigureAwait(false);
            return records
                .OrderByDescending(r => r.VerifiedAt ?? r.CreatedAt)
                .FirstOrDefault();
        }

        public async Task<VideoSourceVerification> OverrideAsync(Guid verificationId, SourceVerificationOverride overrideRequest, CancellationToken cancellationToken = default)
        {
            if (overrideRequest == null)
            {
                throw new ArgumentNullException(nameof(overrideRequest));
            }

            var record = await _verificationRepository.GetByIdAsync(verificationId).ConfigureAwait(false);
            if (record == null)
            {
                throw new InvalidOperationException("Verification record not found.");
            }

            record.IsManualOverride = true;
            record.Status = overrideRequest.MarkAsVerified
                ? VideoSourceVerificationStatus.Verified
                : VideoSourceVerificationStatus.Mismatch;
            record.Confidence = overrideRequest.Confidence ?? record.Confidence;
            record.Notes = overrideRequest.Notes;
            record.VerifiedAt = DateTime.UtcNow;

            await _verificationRepository.UpdateAsync(record).ConfigureAwait(false);
            await _unitOfWork.SaveChangesAsync().ConfigureAwait(false);

            return record;
        }

        private string? ResolveSourceUrl(Video video, SourceVerificationRequest request)
        {
            if (!string.IsNullOrWhiteSpace(request.SourceUrl))
            {
                return request.SourceUrl;
            }

            if (!string.IsNullOrWhiteSpace(video.YouTubeId))
            {
                return $"https://www.youtube.com/watch?v={video.YouTubeId}";
            }

            if (!string.IsNullOrWhiteSpace(video.ImvdbId))
            {
                return video.ImvdbId;
            }

            return null;
        }

        private SourceVerificationComparison BuildComparison(Video video, YtDlpVideoMetadata metadata)
        {
            var comparison = new SourceVerificationComparison();

            comparison.LocalDurationSeconds = video.Duration;
            comparison.SourceDurationSeconds = metadata.Duration?.TotalSeconds;
            comparison.LocalFrameRate = video.FrameRate;
            comparison.SourceFrameRate = metadata.Fps;

            if (metadata.Duration.HasValue && video.Duration.HasValue)
            {
                comparison.DurationDeltaSeconds = Math.Abs(metadata.Duration.Value.TotalSeconds - video.Duration.Value);
            }

            if (metadata.Fps.HasValue && video.FrameRate.HasValue)
            {
                comparison.FrameRateDelta = Math.Abs(metadata.Fps.Value - video.FrameRate.Value);
            }

            if (metadata.FileSize.HasValue && video.FileSize.HasValue)
            {
                comparison.BitrateDelta = Math.Abs((metadata.FileSize.Value / Math.Max(1, (metadata.Duration?.TotalSeconds ?? 1))) - video.Bitrate.GetValueOrDefault());
            }

            if (metadata.Width.HasValue && metadata.Height.HasValue)
            {
                comparison.SourceResolution = $"{metadata.Width.Value}x{metadata.Height.Value}";
            }

            comparison.Resolution = video.Resolution;
            return comparison;
        }

        private double ComputeConfidence(Video video, YtDlpVideoMetadata metadata, SourceVerificationRequest request, SourceVerificationComparison comparison)
        {
            var confidence = 1.0;

            if (comparison.DurationDeltaSeconds.HasValue)
            {
                var penalty = Math.Min(1.0, comparison.DurationDeltaSeconds.Value / Math.Max(1, request.DurationToleranceSeconds));
                confidence -= penalty * 0.5;
            }

            if (!string.IsNullOrWhiteSpace(comparison.SourceResolution) && !string.IsNullOrWhiteSpace(video.Resolution))
            {
                if (!string.Equals(comparison.SourceResolution, video.Resolution, StringComparison.OrdinalIgnoreCase))
                {
                    confidence -= 0.2;
                }
            }

            if (comparison.FrameRateDelta.HasValue && comparison.FrameRateDelta.Value > 1.0)
            {
                confidence -= 0.1;
            }

            confidence = Math.Clamp(confidence, 0, 1);
            comparison.Confidence = confidence;
            return confidence;
        }

        private async Task<VideoSourceVerification> PersistResultAsync(
            Video video,
            SourceVerificationRequest request,
            SourceVerificationComparison? comparison,
            string? sourceUrl,
            VideoSourceVerificationStatus status,
            double confidence,
            CancellationToken cancellationToken)
        {
            var record = new VideoSourceVerification
            {
                VideoId = video.Id,
                Video = video,
                SourceUrl = sourceUrl,
                SourceProvider = DetectProvider(sourceUrl),
                Status = status,
                Confidence = confidence,
                ComparisonSnapshotJson = comparison != null ? JsonSerializer.Serialize(comparison) : null,
                VerifiedAt = DateTime.UtcNow,
                Notes = BuildAutoNotes(status, comparison)
            };

            await _verificationRepository.AddAsync(record).ConfigureAwait(false);
            await _unitOfWork.SaveChangesAsync().ConfigureAwait(false);

            return record;
        }

        private static string? DetectProvider(string? url)
        {
            if (string.IsNullOrWhiteSpace(url))
            {
                return null;
            }

            if (url.Contains("youtube", StringComparison.OrdinalIgnoreCase))
            {
                return "youtube";
            }

            if (url.Contains("vimeo", StringComparison.OrdinalIgnoreCase))
            {
                return "vimeo";
            }

            return new Uri(url).Host;
        }

        private static string? BuildAutoNotes(VideoSourceVerificationStatus status, SourceVerificationComparison? comparison)
        {
            if (comparison == null)
            {
                return status switch
                {
                    VideoSourceVerificationStatus.SourceMissing => "Source URL missing",
                    VideoSourceVerificationStatus.Failed => "Verification failed",
                    _ => null
                };
            }

            var parts = new List<string>();

            if (comparison.DurationDeltaSeconds.HasValue)
            {
                parts.Add($"Duration Δ {comparison.DurationDeltaSeconds.Value.ToString("0.0", CultureInfo.InvariantCulture)}s");
            }

            if (!string.IsNullOrWhiteSpace(comparison.SourceResolution))
            {
                parts.Add($"Source {comparison.SourceResolution}");
            }

            if (!string.IsNullOrWhiteSpace(comparison.Resolution))
            {
                parts.Add($"Local {comparison.Resolution}");
            }

            return parts.Count == 0 ? null : string.Join(" · ", parts);
        }
    }
}
