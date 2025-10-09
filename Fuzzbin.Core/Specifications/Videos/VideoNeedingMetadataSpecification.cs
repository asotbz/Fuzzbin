using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Specifications.Videos;

public sealed class VideoNeedingMetadataSpecification : BaseSpecification<Video>
{
    public VideoNeedingMetadataSpecification()
    {
        ApplyCriteria(v => v.IsActive && (
            string.IsNullOrEmpty(v.ImvdbId) ||
            string.IsNullOrEmpty(v.ThumbnailPath) ||
            string.IsNullOrEmpty(v.Description)));

        AddOrderBy(v => v.CreatedAt);
    }
}
