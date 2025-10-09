using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Specifications.Videos;

public sealed class VideoOrphansSpecification : BaseSpecification<Video>
{
    public VideoOrphansSpecification()
    {
        ApplyCriteria(v => !v.IsActive || v.FilePath == null || !v.FileSize.HasValue || v.FileSize.Value == 0);
        AddOrderBy(v => v.IsActive);
        AddOrderBy(v => v.Title);
    }
}
