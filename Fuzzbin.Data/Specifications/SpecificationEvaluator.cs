using System;
using System.Linq;
using Microsoft.EntityFrameworkCore;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Specifications;

namespace Fuzzbin.Data.Specifications;

/// <summary>
/// Applies an <see cref="ISpecification{T}"/> to an <see cref="IQueryable{T}"/>.
/// </summary>
/// <typeparam name="T">Entity type.</typeparam>
public static class SpecificationEvaluator<T> where T : BaseEntity
{
    public static IQueryable<T> GetQuery(
        IQueryable<T> inputQuery,
        ISpecification<T> specification,
        bool ignoreIncludes = false,
        bool applyOrder = true)
    {
        if (specification == null)
        {
            throw new ArgumentNullException(nameof(specification));
        }

        IQueryable<T> query = inputQuery ?? throw new ArgumentNullException(nameof(inputQuery));

        if (specification.AsNoTracking)
        {
            query = query.AsNoTracking();
        }

        if (specification.Criteria != null)
        {
            query = query.Where(specification.Criteria);
        }

        if (!ignoreIncludes)
        {
            foreach (var include in specification.IncludeStrings)
            {
                query = query.Include(include);
            }

            foreach (var includeExpression in specification.Includes)
            {
                query = query.Include(includeExpression);
            }
        }

        if (applyOrder && specification.OrderExpressions.Count > 0)
        {
            var orderedQuery = ApplyOrdering(query, specification);
            query = orderedQuery ?? query;
        }

        if (specification.IsPagingEnabled)
        {
            if (specification.Skip.HasValue)
            {
                query = query.Skip(specification.Skip.Value);
            }

            if (specification.Take.HasValue)
            {
                query = query.Take(specification.Take.Value);
            }
        }

        if (specification.AsSplitQuery)
        {
            query = query.AsSplitQuery();
        }

        return query;
    }

    private static IOrderedQueryable<T>? ApplyOrdering(IQueryable<T> query, ISpecification<T> specification)
    {
        IOrderedQueryable<T>? orderedQuery = null;
        var index = 0;
        foreach (var order in specification.OrderExpressions)
        {
            if (index == 0)
            {
                orderedQuery = order.Direction == SortDirection.Descending
                    ? query.OrderByDescending(order.KeySelector)
                    : query.OrderBy(order.KeySelector);
            }
            else if (orderedQuery != null)
            {
                orderedQuery = order.Direction == SortDirection.Descending
                    ? orderedQuery.ThenByDescending(order.KeySelector)
                    : orderedQuery.ThenBy(order.KeySelector);
            }
            index++;
        }

        return orderedQuery;
    }
}
