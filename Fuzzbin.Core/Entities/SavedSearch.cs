using System;

namespace Fuzzbin.Core.Entities
{
    public class SavedSearch : BaseEntity
    {
        public string Name { get; set; } = string.Empty;
        public string? Description { get; set; }
        public string Query { get; set; } = string.Empty; // JSON serialized SearchQuery
        public string? Icon { get; set; }
        public string? Color { get; set; }
        public Guid? UserId { get; set; }
        public DateTime LastUsed { get; set; }
        public int UseCount { get; set; }
        public bool IsPublic { get; set; }
    }
}