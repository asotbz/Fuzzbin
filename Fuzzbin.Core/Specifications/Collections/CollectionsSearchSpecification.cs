using System;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Specifications.Collections;

public sealed class CollectionsSearchSpecification : BaseSpecification<Collection>
{
    public CollectionsSearchSpecification(string searchTerm, bool includeVideos = false)
    {
        if (string.IsNullOrWhiteSpace(searchTerm))
        {
            ApplyCriteria(c => c.IsActive);
        }
        else
        {
            var lowered = searchTerm.Trim().ToLowerInvariant();
            ApplyCriteria(c => c.IsActive &&
                (c.Name.ToLower().Contains(lowered) ||
                 (c.Description != null && c.Description.ToLower().Contains(lowered))));
        }

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
