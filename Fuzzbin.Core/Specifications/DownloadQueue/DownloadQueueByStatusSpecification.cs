using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Specifications.DownloadQueue;

public sealed class DownloadQueueByStatusSpecification : BaseSpecification<DownloadQueueItem>
{
    public DownloadQueueByStatusSpecification(DownloadStatus status, bool includeVideo = false)
        : base(item => item.Status == status && !item.IsDeleted)
    {
        AddOrderBy(item => item.Priority);
        AddOrderBy(item => item.CreatedAt);

        if (includeVideo)
        {
            AddInclude(item => item.Video!);
        }
    }
}
