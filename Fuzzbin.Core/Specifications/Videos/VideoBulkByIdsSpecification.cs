using System;
using System.Collections.Generic;
using System.Linq;
using System.Linq.Expressions;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Specifications.Videos;

public sealed class VideoBulkByIdsSpecification : BaseSpecification<Video>
{
    public VideoBulkByIdsSpecification(IEnumerable<Guid> ids, bool includeRelations = false, bool trackForUpdate = false)
    {
        if (ids == null)
        {
            throw new ArgumentNullException(nameof(ids));
        }

        var idList = ids.Distinct().ToList();
        if (idList.Count == 0)
        {
            ApplyCriteria(_ => false);
            return;
        }

        ApplyCriteria(v => idList.Contains(v.Id));

        if (includeRelations)
        {
            AddInclude(v => v.Genres);
            AddInclude(v => v.Tags);
            AddInclude(v => v.FeaturedArtists);
            AddInclude(v => v.CollectionVideos);
            AddInclude($"{nameof(Video.CollectionVideos)}.{nameof(CollectionVideo.Collection)}");
            EnableSplitQuery();
        }

        if (trackForUpdate)
        {
            EnableTracking();
        }

        AddOrderBy(BuildOrderingExpression(idList));
    }

    private static Expression<Func<Video, object>> BuildOrderingExpression(IReadOnlyList<Guid> ids)
    {
        var parameter = Expression.Parameter(typeof(Video), "v");
        var idProperty = Expression.Property(parameter, nameof(Video.Id));

        Expression body = Expression.Constant(int.MaxValue);
        var currentIndex = ids.Count - 1;

        while (currentIndex >= 0)
        {
            var indexValue = Expression.Constant(currentIndex);
            var guidValue = Expression.Constant(ids[currentIndex]);
            var equals = Expression.Equal(idProperty, guidValue);
            body = Expression.Condition(equals, indexValue, body);
            currentIndex--;
        }

        var boxedBody = Expression.Convert(body, typeof(object));
        return Expression.Lambda<Func<Video, object>>(boxedBody, parameter);
    }
}
