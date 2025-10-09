using System;
using System.Collections.Generic;

namespace Fuzzbin.Core.Specifications.Queries;

public sealed class PagedResult<T>
{
    public PagedResult(IReadOnlyList<T> items, int totalCount, int page, int pageSize)
    {
        if (pageSize <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(pageSize));
        }

        Items = items ?? throw new ArgumentNullException(nameof(items));
        TotalCount = totalCount < 0 ? 0 : totalCount;
        Page = page < 1 ? 1 : page;
        PageSize = pageSize;
        TotalPages = (int)Math.Ceiling(TotalCount / (double)PageSize);
    }

    public IReadOnlyList<T> Items { get; }
    public int TotalCount { get; }
    public int Page { get; }
    public int PageSize { get; }
    public int TotalPages { get; }
}
