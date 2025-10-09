using System.Collections.Generic;

namespace Fuzzbin.Core.Entities
{
    /// <summary>
    /// Represents a featured artist in videos
    /// </summary>
    public class FeaturedArtist : BaseEntity
    {
        /// <summary>
        /// Artist name
        /// </summary>
        public string Name { get; set; } = string.Empty;

        /// <summary>
        /// IMVDb artist ID
        /// </summary>
        public string? ImvdbArtistId { get; set; }

        /// <summary>
        /// MusicBrainz artist ID
        /// </summary>
        public string? MusicBrainzArtistId { get; set; }

        /// <summary>
        /// Artist biography
        /// </summary>
        public string? Biography { get; set; }

        /// <summary>
        /// Artist image URL or path
        /// </summary>
        public string? ImagePath { get; set; }

        /// <summary>
        /// Videos featuring this artist
        /// </summary>
        public virtual ICollection<Video> Videos { get; set; } = new List<Video>();
    }
}