using System;
using System.Collections.Generic;

namespace Fuzzbin.Core.Entities
{
    /// <summary>
    /// Represents a music video in the system
    /// </summary>
    public class Video : BaseEntity
    {
        /// <summary>
        /// Title of the video
        /// </summary>
        public string Title { get; set; } = string.Empty;

        /// <summary>
        /// Artist name
        /// </summary>
        public string Artist { get; set; } = string.Empty;

        /// <summary>
        /// Album name (if applicable)
        /// </summary>
        public string? Album { get; set; }

        /// <summary>
        /// Release year
        /// </summary>
        public int? Year { get; set; }

        /// <summary>
        /// Video duration in seconds
        /// </summary>
        public int? Duration { get; set; }

        /// <summary>
        /// File path relative to the media directory
        /// </summary>
        public string? FilePath { get; set; }

        /// <summary>
        /// Hash of the file contents, used to detect duplicates
        /// </summary>
        public string? FileHash { get; set; }

        /// <summary>
        /// File size in bytes
        /// </summary>
        public long? FileSize { get; set; }

        /// <summary>
        /// Video codec (e.g., h264, h265)
        /// </summary>
        public string? VideoCodec { get; set; }

        /// <summary>
        /// Audio codec (e.g., aac, mp3)
        /// </summary>
        public string? AudioCodec { get; set; }

        /// <summary>
        /// Video resolution (e.g., 1920x1080)
        /// </summary>
        public string? Resolution { get; set; }

        /// <summary>
        /// Video format/container (e.g., mp4, mkv, webm)
        /// </summary>
        public string? Format { get; set; }

        /// <summary>
        /// Frame rate
        /// </summary>
        public double? FrameRate { get; set; }

        /// <summary>
        /// Bitrate in kbps
        /// </summary>
        public int? Bitrate { get; set; }

        /// <summary>
        /// IMVDb ID for video metadata
        /// </summary>
        public string? ImvdbId { get; set; }

        /// <summary>
        /// MusicBrainz Recording ID for audio metadata
        /// </summary>
        public string? MusicBrainzRecordingId { get; set; }

        /// <summary>
        /// YouTube video ID (if sourced from YouTube)
        /// </summary>
        public string? YouTubeId { get; set; }

        /// <summary>
        /// Video description
        /// </summary>
        public string? Description { get; set; }

        /// <summary>
        /// Director name
        /// </summary>
        public string? Director { get; set; }

        /// <summary>
        /// Production company
        /// </summary>
        public string? ProductionCompany { get; set; }

        /// <summary>
        /// Publisher/Label
        /// </summary>
        public string? Publisher { get; set; }

        /// <summary>
        /// Thumbnail image path
        /// </summary>
        public string? ThumbnailPath { get; set; }

        /// <summary>
        /// NFO file path
        /// </summary>
        public string? NfoPath { get; set; }

        /// <summary>
        /// Import date
        /// </summary>
        public DateTime? ImportedAt { get; set; }

        /// <summary>
        /// Last played date
        /// </summary>
        public DateTime? LastPlayedAt { get; set; }

        /// <summary>
        /// Play count
        /// </summary>
        public int PlayCount { get; set; } = 0;

        /// <summary>
        /// User rating (1-5)
        /// </summary>
        public int? Rating { get; set; }

        /// <summary>
        /// Collection of genres
        /// </summary>
        public virtual ICollection<Genre> Genres { get; set; } = new List<Genre>();

        /// <summary>
        /// Collection of tags
        /// </summary>
        public virtual ICollection<Tag> Tags { get; set; } = new List<Tag>();

        /// <summary>
        /// Collection of featured artists
        /// </summary>
        public virtual ICollection<FeaturedArtist> FeaturedArtists { get; set; } = new List<FeaturedArtist>();

        /// <summary>
        /// Collections this video belongs to
        /// </summary>
        public virtual ICollection<CollectionVideo> CollectionVideos { get; set; } = new List<CollectionVideo>();
    }
}
