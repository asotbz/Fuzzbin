using System;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Specifications.Videos;

public sealed class VideoMostPlayedSpecification : BaseSpecification<Video>
{
    public VideoMostPlayedSpecification(int take = 40, DateTime? since = null)
    {
        if (take <= 0)
        {
            take = 40;
        }

        ApplyCriteria(v => v.IsActive && v.PlayCount > 0);

        if (since.HasValue)
        {
            var sinceValue = since.Value;
            ApplyCriteria(v => v.LastPlayedAt.HasValue && v.LastPlayedAt.Value >= sinceValue);
        }

        AddOrderByDescending(v => v.PlayCount);
        AddOrderByDescending(v => v.LastPlayedAt ?? DateTime.MinValue);
        ApplyPaging(0, take);
    }
}
