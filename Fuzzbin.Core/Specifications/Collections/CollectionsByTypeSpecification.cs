using System;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Specifications.Collections;

public sealed class CollectionsByTypeSpecification : BaseSpecification<Collection>
{
    public CollectionsByTypeSpecification(CollectionType type, bool includeVideos = false)
        : base(c => c.Type == type && c.IsActive)
    {
        AddOrderBy(c => c.SortOrder);
        AddOrderBy(c => c.Name);

        if (includeVideos)
        {
            AddInclude(c => c.CollectionVideos);
            AddInclude($"{nameof(Collection.CollectionVideos)}.{nameof(CollectionVideo.Video)}");
            EnableSplitQuery();
        }
    }
}
