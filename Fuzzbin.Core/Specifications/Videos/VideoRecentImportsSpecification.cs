using System;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Specifications.Videos;

public sealed class VideoRecentImportsSpecification : BaseSpecification<Video>
{
    public VideoRecentImportsSpecification(int take = 40, TimeSpan? window = null)
    {
        if (take <= 0)
        {
            take = 40;
        }

        var interval = window ?? TimeSpan.FromDays(30);
        var threshold = DateTime.UtcNow.Subtract(interval);

        ApplyCriteria(v => v.CreatedAt >= threshold && v.IsActive);
        AddOrderByDescending(v => v.CreatedAt);
        ApplyPaging(0, take);
    }
}
