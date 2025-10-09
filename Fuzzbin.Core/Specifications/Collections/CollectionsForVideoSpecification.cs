using System;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Specifications.Collections;

public sealed class CollectionsForVideoSpecification : BaseSpecification<Collection>
{
    public CollectionsForVideoSpecification(Guid videoId)
    {
        ApplyCriteria(c => c.IsActive);
        ApplyCriteria(c => c.CollectionVideos.Any(cv => cv.VideoId == videoId));

        AddInclude(c => c.CollectionVideos);
        AddInclude($"{nameof(Collection.CollectionVideos)}.{nameof(CollectionVideo.Video)}");
        AddOrderBy(c => c.Name);
        EnableSplitQuery();
    }
}
