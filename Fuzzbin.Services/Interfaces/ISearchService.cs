using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Services.Interfaces
{
    public interface ISearchService
    {
        Task<SearchResult> SearchAsync(SearchQuery query);
        Task<List<SavedSearch>> GetSavedSearchesAsync();
        Task<SavedSearch> GetSavedSearchAsync(Guid id);
        Task<SavedSearch> SaveSearchAsync(SavedSearch savedSearch);
        Task DeleteSavedSearchAsync(Guid id);
        Task<SearchFacets> GetSearchFacetsAsync();
        void InvalidateFacetsCache();
    }

    public class SearchQuery
    {
        public string? SearchText { get; set; }
        public List<string> Artists { get; set; } = new();
        public List<string> Genres { get; set; } = new();
        public List<string> Formats { get; set; } = new();
        public List<string> Resolutions { get; set; } = new();
        public List<Guid> CollectionIds { get; set; } = new();
        public int? YearFrom { get; set; }
        public int? YearTo { get; set; }
        public int? DurationMin { get; set; }
        public int? DurationMax { get; set; }
        public bool? HasYouTubeId { get; set; }
        public bool? HasImvdbId { get; set; }
        public bool? HasCollections { get; set; }
        public DateTime? AddedAfter { get; set; }
        public DateTime? AddedBefore { get; set; }
        public string SortBy { get; set; } = "Title";
        public bool SortDescending { get; set; }
        public int PageNumber { get; set; } = 1;
        public int PageSize { get; set; } = 20;
    }

    public class SearchResult
    {
        public List<Video> Videos { get; set; } = new();
        public int TotalCount { get; set; }
        public int PageNumber { get; set; }
        public int PageSize { get; set; }
        public int TotalPages => (int)Math.Ceiling(TotalCount / (double)PageSize);
        public SearchFacets? Facets { get; set; }
    }

    public class SearchFacets
    {
        public Dictionary<string, int> Artists { get; set; } = new();
        public Dictionary<string, int> Genres { get; set; } = new();
        public Dictionary<string, int> Formats { get; set; } = new();
        public Dictionary<string, int> Resolutions { get; set; } = new();
        public Dictionary<string, int> Years { get; set; } = new();
        public Dictionary<string, int> Collections { get; set; } = new();
    }
}
