using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Specifications.DownloadQueue;

public sealed class DownloadQueuePendingSpecification : BaseSpecification<DownloadQueueItem>
{
    public DownloadQueuePendingSpecification(bool includeFailed = true)
    {
        ApplyCriteria(item => !item.IsDeleted);

        if (includeFailed)
        {
            ApplyCriteria(item =>
                item.Status == DownloadStatus.Queued ||
                item.Status == DownloadStatus.Failed);
        }
        else
        {
            ApplyCriteria(item => item.Status == DownloadStatus.Queued);
        }

        AddOrderByDescending(item => item.Priority);
        AddOrderBy(item => item.AddedDate);
    }
}
