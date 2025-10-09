using System;
using System.Linq.Expressions;

namespace Fuzzbin.Core.Specifications;

/// <summary>
/// Represents an ordered projection for a specification.
/// </summary>
/// <typeparam name="T">Entity type</typeparam>
public sealed class OrderExpression<T>
{
    public OrderExpression(Expression<Func<T, object>> keySelector, SortDirection direction)
    {
        KeySelector = keySelector ?? throw new ArgumentNullException(nameof(keySelector));
        Direction = direction;
    }

    /// <summary>
    /// Sorting key selector expression.
    /// </summary>
    public Expression<Func<T, object>> KeySelector { get; }

    /// <summary>
    /// Sorting direction.
    /// </summary>
    public SortDirection Direction { get; }
}
