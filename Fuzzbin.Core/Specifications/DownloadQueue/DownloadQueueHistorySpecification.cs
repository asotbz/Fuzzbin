using System;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Specifications.DownloadQueue;

public sealed class DownloadQueueHistorySpecification : BaseSpecification<DownloadQueueItem>
{
    public DownloadQueueHistorySpecification(DateTime? olderThan = null, int page = 1, int pageSize = 100)
    {
        if (page < 1)
        {
            page = 1;
        }

        if (pageSize <= 0)
        {
            pageSize = 100;
        }

        ApplyCriteria(item =>
            (item.Status == DownloadStatus.Completed ||
             item.Status == DownloadStatus.Cancelled ||
             item.Status == DownloadStatus.Failed) &&
            !item.IsDeleted);

        if (olderThan.HasValue)
        {
            var cutoff = olderThan.Value;
            ApplyCriteria(item => item.UpdatedAt <= cutoff);
        }

        AddOrderByDescending(item => item.UpdatedAt);
        ApplyPaging((page - 1) * pageSize, pageSize);
    }
}
