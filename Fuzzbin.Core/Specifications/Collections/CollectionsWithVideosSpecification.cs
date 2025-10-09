using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Specifications.Collections;

public sealed class CollectionsWithVideosSpecification : BaseSpecification<Collection>
{
    public CollectionsWithVideosSpecification(bool onlyActive = true)
    {
        if (onlyActive)
        {
            ApplyCriteria(c => c.IsActive);
        }

        AddInclude(c => c.CollectionVideos);
        AddInclude($"{nameof(Collection.CollectionVideos)}.{nameof(CollectionVideo.Video)}");
        AddOrderBy(c => c.SortOrder);
        AddOrderBy(c => c.Name);
        EnableSplitQuery();
    }
}
