using System.Collections.Generic;

namespace Fuzzbin.Core.Entities
{
    /// <summary>
    /// Represents a tag for categorizing videos
    /// </summary>
    public class Tag : BaseEntity
    {
        /// <summary>
        /// Tag name
        /// </summary>
        public string Name { get; set; } = string.Empty;

        /// <summary>
        /// Tag color for UI display (hex format)
        /// </summary>
        public string? Color { get; set; }

        /// <summary>
        /// Videos with this tag
        /// </summary>
        public virtual ICollection<Video> Videos { get; set; } = new List<Video>();
    }
}