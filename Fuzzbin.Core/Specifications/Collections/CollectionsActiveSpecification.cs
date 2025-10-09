using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Specifications.Collections;

public sealed class CollectionsActiveSpecification : BaseSpecification<Collection>
{
    public CollectionsActiveSpecification(bool includeVideos = false)
    {
        ApplyCriteria(c => c.IsActive);
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
