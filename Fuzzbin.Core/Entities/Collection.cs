using System;
using System.Collections.Generic;

namespace Fuzzbin.Core.Entities
{
    public class Collection : BaseEntity
    {
        public string Name { get; set; } = string.Empty;
        public string? Description { get; set; }
        public string? ThumbnailPath { get; set; }
        public CollectionType Type { get; set; } = CollectionType.Manual;
        public string? SmartCriteria { get; set; } // JSON for smart collection rules
        public int SortOrder { get; set; }
        public bool IsPublic { get; set; } = true;
        public bool IsFavorite { get; set; }
        public int VideoCount { get; set; }
        public TimeSpan TotalDuration { get; set; }
        
        // Navigation properties
        public ICollection<CollectionVideo> CollectionVideos { get; set; } = new List<CollectionVideo>();
    }

    public enum CollectionType
    {
        Manual,
        Smart,
        Playlist,
        Series,
        Album
    }
}