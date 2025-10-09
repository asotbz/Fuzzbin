using System;
using System.Collections.Generic;
using System.Linq;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Specifications.Lookups;

public sealed class TagLookupSpecification : BaseSpecification<Tag>
{
    public TagLookupSpecification(IEnumerable<Guid> tagIds)
    {
        if (tagIds == null)
        {
            throw new ArgumentNullException(nameof(tagIds));
        }

        var ids = tagIds.Distinct().ToList();
        if (ids.Count == 0)
        {
            ApplyCriteria(_ => false);
            return;
        }

        ApplyCriteria(tag => ids.Contains(tag.Id) && tag.IsActive);
        AddOrderBy(tag => tag.Name);
    }
}
