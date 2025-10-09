using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Specifications.Collections;

public sealed class CollectionsFavoritesSpecification : BaseSpecification<Collection>
{
    public CollectionsFavoritesSpecification(bool includeVideos = false)
    {
        ApplyCriteria(c => c.IsFavorite && c.IsActive);
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
