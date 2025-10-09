using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Interfaces;

public interface IMetadataService
{
    /// <summary>
    /// Extracts metadata from a video file
    /// </summary>
    Task<VideoMetadata> ExtractMetadataAsync(string filePath, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Fetches metadata from IMVDb for a music video
    /// </summary>
    Task<ImvdbMetadata?> GetImvdbMetadataAsync(string artist, string title, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Fetches metadata from MusicBrainz for audio information
    /// </summary>
    Task<MusicBrainzMetadata?> GetMusicBrainzMetadataAsync(string artist, string title, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Generates an NFO file for a video
    /// </summary>
    Task<string> GenerateNfoAsync(Video video, string outputPath, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Reads NFO file and returns video metadata
    /// </summary>
    Task<NfoData?> ReadNfoAsync(string nfoPath, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Updates video entity with metadata from various sources
    /// </summary>
    Task<Video> EnrichVideoMetadataAsync(Video video, bool fetchOnlineMetadata = true, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Downloads thumbnail for a video
    /// </summary>
    Task<string?> DownloadThumbnailAsync(string thumbnailUrl, string outputPath, CancellationToken cancellationToken = default);
}

public class VideoMetadata
{
    public string? Title { get; set; }
    public string? Artist { get; set; }
    public string? Album { get; set; }
    public DateTime? ReleaseDate { get; set; }
    public TimeSpan? Duration { get; set; }
    public int? Width { get; set; }
    public int? Height { get; set; }
    public double? FrameRate { get; set; }
    public string? VideoCodec { get; set; }
    public long? VideoBitrate { get; set; }
    public string? AudioCodec { get; set; }
    public long? AudioBitrate { get; set; }
    public int? AudioSampleRate { get; set; }
    public string? Container { get; set; }
    public long FileSize { get; set; }
    public Dictionary<string, string> Tags { get; set; } = new();
}

public class ImvdbMetadata  
{
    public int? ImvdbId { get; set; }
    public string? Title { get; set; }
    public string? Artist { get; set; }
    public string? FeaturedArtists { get; set; }
    public string? Director { get; set; }
    public string? ProductionCompany { get; set; }
    public string? RecordLabel { get; set; }
    public DateTime? ReleaseDate { get; set; }
    public List<string> Genres { get; set; } = new();
    public string? ImageUrl { get; set; }
    public string? VideoUrl { get; set; }
    public int? Year { get; set; }
    public bool IsExplicit { get; set; }
    public bool IsUnofficial { get; set; }
    public string? Description { get; set; }
    public List<ImvdbCredit> Credits { get; set; } = new();
}

public class ImvdbCredit
{
    public string? Name { get; set; }
    public string? Role { get; set; }
}

public class MusicBrainzMetadata
{
    public string? RecordingId { get; set; }
    public string? ReleaseId { get; set; }
    public string? ArtistId { get; set; }
    public string? Title { get; set; }
    public string? Artist { get; set; }
    public string? ArtistSort { get; set; }
    public string? Album { get; set; }
    public int? TrackNumber { get; set; }
    public int? TotalTracks { get; set; }
    public DateTime? ReleaseDate { get; set; }
    public List<string> Genres { get; set; } = new();
    public List<string> Tags { get; set; } = new();
    public string? RecordLabel { get; set; }
    public string? ISRC { get; set; }
    public int? Duration { get; set; } // in milliseconds
}

public class NfoData
{
    public string? Title { get; set; }
    public string? Artist { get; set; }
    public string? Album { get; set; }
    public DateTime? ReleaseDate { get; set; }
    public string? Plot { get; set; }
    public string? Director { get; set; }
    public List<string> Genres { get; set; } = new();
    public List<string> Tags { get; set; } = new();
    public string? Studio { get; set; }
    public string? RecordLabel { get; set; }
    public int? Runtime { get; set; } // in seconds
    public int? Year { get; set; }
    public string? ImvdbId { get; set; }
    public string? MusicBrainzId { get; set; }
    public string? Thumb { get; set; }
    public string? FanArt { get; set; }
    public VideoStreamInfo? VideoStream { get; set; }
    public AudioStreamInfo? AudioStream { get; set; }
    public Dictionary<string, string> CustomFields { get; set; } = new();
}

public class VideoStreamInfo
{
    public string? Codec { get; set; }
    public int? Width { get; set; }
    public int? Height { get; set; }
    public double? AspectRatio { get; set; }
    public double? FrameRate { get; set; }
    public long? Bitrate { get; set; }
    public string? ScanType { get; set; }
}

public class AudioStreamInfo  
{
    public string? Codec { get; set; }
    public int? Channels { get; set; }
    public int? SampleRate { get; set; }
    public long? Bitrate { get; set; }
    public string? Language { get; set; }
}