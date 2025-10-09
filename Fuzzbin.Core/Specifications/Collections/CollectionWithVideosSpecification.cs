using System;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Specifications.Collections;

public sealed class CollectionWithVideosSpecification : BaseSpecification<Collection>
{
    public CollectionWithVideosSpecification(Guid collectionId)
        : base(c => c.Id == collectionId && c.IsActive)
    {
        AddInclude(c => c.CollectionVideos);
        AddInclude($"{nameof(Collection.CollectionVideos)}.{nameof(CollectionVideo.Video)}");
        AddOrderBy(c => c.Name);
        EnableSplitQuery();
    }
}
