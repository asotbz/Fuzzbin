using System;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Specifications.DownloadQueue;

public sealed class DownloadQueueRetrySpecification : BaseSpecification<DownloadQueueItem>
{
    public DownloadQueueRetrySpecification(TimeSpan retryWindow, int maxRetries, DateTime? currentUtc = null)
    {
        if (retryWindow <= TimeSpan.Zero)
        {
            retryWindow = TimeSpan.FromMinutes(5);
        }

        if (maxRetries <= 0)
        {
            maxRetries = 3;
        }

        var referenceTime = currentUtc ?? DateTime.UtcNow;
        var cutoff = referenceTime.Subtract(retryWindow);

        ApplyCriteria(item => item.Status == DownloadStatus.Failed && !item.IsDeleted);
        ApplyCriteria(item => item.RetryCount < maxRetries);
        ApplyCriteria(item => item.UpdatedAt <= cutoff);

        AddOrderBy(item => item.Priority);
        AddOrderBy(item => item.UpdatedAt);
        EnableTracking();
    }
}
