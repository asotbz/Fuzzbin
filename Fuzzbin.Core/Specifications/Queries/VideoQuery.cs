using System;
using System.Collections.Generic;
using System.Linq;

namespace Fuzzbin.Core.Specifications.Queries;

/// <summary>
/// Represents the filter and paging input for querying videos.
/// </summary>
public class VideoQuery
{
    private const int DefaultPageSize = 50;
    private const int MaxPageSize = 200;

    private int _page = 1;
    private int _pageSize = DefaultPageSize;
    private readonly List<string> _searchTerms = new();

    public string? Search { get; set; }
    public List<Guid> GenreIds { get; set; } = new();
    public List<Guid> TagIds { get; set; } = new();
    public List<Guid> CollectionIds { get; set; } = new();
    public List<string> GenreNames { get; set; } = new();
    public List<string> ArtistNames { get; set; } = new();
    public List<string> Formats { get; set; } = new();
    public List<string> Resolutions { get; set; } = new();
    public List<int> Years { get; set; } = new();
    public int? YearFrom { get; set; }
    public int? YearTo { get; set; }
    public int? DurationFrom { get; set; }
    public int? DurationTo { get; set; }
    public int? MinRating { get; set; }
    public bool? HasFile { get; set; }
    public bool? MissingMetadata { get; set; }
    public bool? HasCollections { get; set; }
    public bool? HasYouTubeId { get; set; }
    public bool? HasImvdbId { get; set; }
    public DateTime? AddedAfter { get; set; }
    public DateTime? AddedBefore { get; set; }
    public bool IncludeInactive { get; set; }
    public VideoSortOption SortBy { get; set; } = VideoSortOption.Title;
    public SortDirection SortDirection { get; set; } = SortDirection.Ascending;

    public int Page
    {
        get => _page;
        set => _page = value < 1 ? 1 : value;
    }

    public int PageSize
    {
        get => _pageSize;
        set
        {
            if (value <= 0)
            {
                _pageSize = DefaultPageSize;
                return;
            }

            _pageSize = Math.Min(value, MaxPageSize);
        }
    }

    /// <summary>
    /// Normalised search terms parsed from <see cref="Search"/>.
    /// </summary>
    public IReadOnlyList<string> SearchTerms => _searchTerms;

    /// <summary>
    /// Normalises the query input and prepares derived values.
    /// </summary>
    public void Normalize()
    {
        Search = string.IsNullOrWhiteSpace(Search) ? null : Search.Trim();

        _searchTerms.Clear();
        if (!string.IsNullOrEmpty(Search))
        {
            var tokens = Search
                .Split(' ', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                .Select(term => term.ToLowerInvariant())
                .Distinct();

            _searchTerms.AddRange(tokens);
        }

        Page = Page; // triggers setter to clamp value
        PageSize = PageSize; // triggers setter to clamp value

        NormalizeStringList(GenreNames);
        NormalizeStringList(ArtistNames);
        NormalizeStringList(Formats);
        NormalizeStringList(Resolutions);

        if (Years.Count > 0)
        {
            Years = Years
                .Where(year => year > 0)
                .Distinct()
                .OrderBy(year => year)
                .ToList();
        }
    }

    public int Skip => (Page - 1) * PageSize;

    private static void NormalizeStringList(List<string> values)
    {
        if (values.Count == 0)
        {
            return;
        }

        var normalized = values
            .Where(v => !string.IsNullOrWhiteSpace(v))
            .Select(v => v.Trim())
            .Where(v => v.Length > 0)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();

        values.Clear();
        values.AddRange(normalized);
    }
}
