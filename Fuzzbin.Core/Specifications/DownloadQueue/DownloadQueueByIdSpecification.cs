using System;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Specifications.DownloadQueue;

public sealed class DownloadQueueByIdSpecification : BaseSpecification<DownloadQueueItem>
{
    public DownloadQueueByIdSpecification(Guid id, bool track = false)
        : base(item => item.Id == id && !item.IsDeleted)
    {
        if (track)
        {
            EnableTracking();
        }
    }
}
