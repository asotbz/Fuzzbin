using System;
using System.Collections.Generic;
using System.Linq.Expressions;

namespace Fuzzbin.Core.Specifications;

/// <summary>
/// Base implementation for creating query specifications.
/// </summary>
/// <typeparam name="T">Entity type</typeparam>
public abstract class BaseSpecification<T> : ISpecification<T>
{
    protected BaseSpecification()
    {
    }

    protected BaseSpecification(Expression<Func<T, bool>> criteria)
    {
        Criteria = criteria ?? throw new ArgumentNullException(nameof(criteria));
    }

    public Expression<Func<T, bool>>? Criteria { get; protected set; }

    private readonly List<Expression<Func<T, object>>> _includes = new();
    public IReadOnlyCollection<Expression<Func<T, object>>> Includes => _includes;

    private readonly List<string> _includeStrings = new();
    public IReadOnlyCollection<string> IncludeStrings => _includeStrings;

    private readonly List<OrderExpression<T>> _orderExpressions = new();
    public IReadOnlyCollection<OrderExpression<T>> OrderExpressions => _orderExpressions;

    public int? Skip { get; private set; }
    public int? Take { get; private set; }
    public bool IsPagingEnabled { get; private set; }
    public bool AsNoTracking { get; private set; } = true;
    public bool AsSplitQuery { get; private set; }

    /// <summary>
    /// Adds an include expression to the specification.
    /// </summary>
    protected void AddInclude(Expression<Func<T, object>> includeExpression)
    {
        if (includeExpression == null)
        {
            throw new ArgumentNullException(nameof(includeExpression));
        }
        _includes.Add(includeExpression);
    }

    /// <summary>
    /// Adds a string-based include path.
    /// </summary>
    protected void AddInclude(string includeString)
    {
        if (string.IsNullOrWhiteSpace(includeString))
        {
            throw new ArgumentException("Include string cannot be null or whitespace", nameof(includeString));
        }
        _includeStrings.Add(includeString);
    }

    /// <summary>
    /// Adds an additional filter predicate to the specification.
    /// </summary>
    protected void ApplyCriteria(Expression<Func<T, bool>> criteria)
    {
        if (criteria == null)
        {
            throw new ArgumentNullException(nameof(criteria));
        }

        Criteria = Criteria == null
            ? criteria
            : AndAlso(Criteria, criteria);
    }

    /// <summary>
    /// Configures paging.
    /// </summary>
    protected void ApplyPaging(int skip, int take)
    {
        Skip = skip;
        Take = take;
        IsPagingEnabled = true;
    }

    /// <summary>
    /// Adds an ascending order expression.
    /// </summary>
    protected void AddOrderBy(Expression<Func<T, object>> orderExpression)
    {
        if (orderExpression == null)
        {
            throw new ArgumentNullException(nameof(orderExpression));
        }
        _orderExpressions.Add(new OrderExpression<T>(orderExpression, SortDirection.Ascending));
    }

    /// <summary>
    /// Adds a descending order expression.
    /// </summary>
    protected void AddOrderByDescending(Expression<Func<T, object>> orderExpression)
    {
        if (orderExpression == null)
        {
            throw new ArgumentNullException(nameof(orderExpression));
        }
        _orderExpressions.Add(new OrderExpression<T>(orderExpression, SortDirection.Descending));
    }

    /// <summary>
    /// Switch to tracked queries when updates are expected.
    /// </summary>
    protected void EnableTracking()
    {
        AsNoTracking = false;
    }

    /// <summary>
    /// Enables split query execution for complex include graphs.
    /// </summary>
    protected void EnableSplitQuery()
    {
        AsSplitQuery = true;
    }

    private static Expression<Func<T, bool>> AndAlso(Expression<Func<T, bool>> left, Expression<Func<T, bool>> right)
    {
        var parameter = Expression.Parameter(typeof(T), "x");

        var leftVisitor = new ReplaceParameterVisitor(left.Parameters[0], parameter);
        var leftBody = leftVisitor.Visit(left.Body);

        var rightVisitor = new ReplaceParameterVisitor(right.Parameters[0], parameter);
        var rightBody = rightVisitor.Visit(right.Body);

        return Expression.Lambda<Func<T, bool>>(Expression.AndAlso(leftBody!, rightBody!), parameter);
    }

    private sealed class ReplaceParameterVisitor : ExpressionVisitor
    {
        private readonly ParameterExpression _source;
        private readonly ParameterExpression _replacement;

        public ReplaceParameterVisitor(ParameterExpression source, ParameterExpression replacement)
        {
            _source = source;
            _replacement = replacement;
        }

        protected override Expression VisitParameter(ParameterExpression node)
        {
            return ReferenceEquals(node, _source) ? _replacement : base.VisitParameter(node);
        }
    }
}
