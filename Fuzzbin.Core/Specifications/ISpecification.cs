using System;
using System.Collections.Generic;
using System.Linq.Expressions;

namespace Fuzzbin.Core.Specifications;

/// <summary>
/// Contract describing a query specification for an entity type.
/// </summary>
/// <typeparam name="T">Entity type</typeparam>
public interface ISpecification<T>
{
    /// <summary>
    /// Primary filtering criteria.
    /// </summary>
    Expression<Func<T, bool>>? Criteria { get; }

    /// <summary>
    /// Collection of expressions describing related entities to include.
    /// </summary>
    IReadOnlyCollection<Expression<Func<T, object>>> Includes { get; }

    /// <summary>
    /// Collection of string-based include paths (for navigations not representable via expressions).
    /// </summary>
    IReadOnlyCollection<string> IncludeStrings { get; }

    /// <summary>
    /// Ordered list of sort projections.
    /// </summary>
    IReadOnlyCollection<OrderExpression<T>> OrderExpressions { get; }

    /// <summary>
    /// Number of items to skip (for paging).
    /// </summary>
    int? Skip { get; }

    /// <summary>
    /// Number of items to take (for paging).
    /// </summary>
    int? Take { get; }

    /// <summary>
    /// Indicates whether paging should be applied.
    /// </summary>
    bool IsPagingEnabled { get; }

    /// <summary>
    /// Use AsNoTracking when executing the query.
    /// </summary>
    bool AsNoTracking { get; }

    /// <summary>
    /// Use split query semantics when supported.
    /// </summary>
    bool AsSplitQuery { get; }
}
