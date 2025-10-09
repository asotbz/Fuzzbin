using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Specifications.Collections;

public sealed class CollectionsPublicSpecification : BaseSpecification<Collection>
{
    public CollectionsPublicSpecification(bool includeVideos = false)
    {
        ApplyCriteria(c => c.IsPublic && c.IsActive);
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
