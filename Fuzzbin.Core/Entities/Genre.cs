using System.Collections.Generic;

namespace Fuzzbin.Core.Entities
{
    /// <summary>
    /// Represents a music genre
    /// </summary>
    public class Genre : BaseEntity
    {
        /// <summary>
        /// Genre name
        /// </summary>
        public string Name { get; set; } = string.Empty;

        /// <summary>
        /// Genre description
        /// </summary>
        public string? Description { get; set; }

        /// <summary>
        /// Videos in this genre
        /// </summary>
        public virtual ICollection<Video> Videos { get; set; } = new List<Video>();
    }
}