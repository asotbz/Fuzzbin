using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;
using Fuzzbin.Services.Models;

namespace Fuzzbin.Services.Interfaces
{
    public interface ISourceVerificationService
    {
        Task<VideoSourceVerification> VerifyVideoAsync(Video video, SourceVerificationRequest request, CancellationToken cancellationToken = default);
        Task<IReadOnlyList<VideoSourceVerification>> VerifyVideosAsync(IEnumerable<Video> videos, SourceVerificationRequest request, CancellationToken cancellationToken = default);
        Task<VideoSourceVerification?> GetLatestAsync(Guid videoId, CancellationToken cancellationToken = default);
        Task<VideoSourceVerification> OverrideAsync(Guid verificationId, SourceVerificationOverride overrideRequest, CancellationToken cancellationToken = default);
    }
}
