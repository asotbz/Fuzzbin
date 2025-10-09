using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Interfaces
{
    public interface IYtDlpService
    {
        /// <summary>
        /// Downloads a video from the specified URL
        /// </summary>
        Task<DownloadResult> DownloadVideoAsync(string url, string outputPath, IProgress<DownloadProgress>? progress = null, CancellationToken cancellationToken = default);
        
        /// <summary>
        /// Searches for videos using yt-dlp's ytsearch functionality
        /// </summary>
        Task<List<SearchResult>> SearchVideosAsync(string query, int maxResults = 10, CancellationToken cancellationToken = default);
        
        /// <summary>
        /// Extracts metadata from a URL without downloading
        /// </summary>
        Task<YtDlpVideoMetadata> GetVideoMetadataAsync(string url, CancellationToken cancellationToken = default);
        
        /// <summary>
        /// Validates if yt-dlp is properly installed and accessible
        /// </summary>
        Task<bool> ValidateInstallationAsync();
        
        /// <summary>
        /// Gets the current version of yt-dlp
        /// </summary>
        Task<string> GetVersionAsync();
    }
    
    public class DownloadResult
    {
        public bool Success { get; set; }
        public string? FilePath { get; set; }
        public string? ErrorMessage { get; set; }
        public YtDlpVideoMetadata? Metadata { get; set; }
        public TimeSpan Duration { get; set; }
    }
    
    public class DownloadProgress
    {
        public string Status { get; set; } = string.Empty;
        public double Percentage { get; set; }
        public string? DownloadSpeed { get; set; }
        public string? ETA { get; set; }
        public long? TotalBytes { get; set; }
        public long? DownloadedBytes { get; set; }
    }
    
    public class SearchResult
    {
        public string Id { get; set; } = string.Empty;
        public string Title { get; set; } = string.Empty;
        public string? Channel { get; set; }
        public string? ThumbnailUrl { get; set; }
        public TimeSpan? Duration { get; set; }
        public string Url { get; set; } = string.Empty;
        public DateTime? UploadDate { get; set; }
        public long? ViewCount { get; set; }
    }
    
    public class YtDlpVideoMetadata
    {
        public string Id { get; set; } = string.Empty;
        public string Title { get; set; } = string.Empty;
        public string? Artist { get; set; }
        public string? Channel { get; set; }
        public string? Description { get; set; }
        public TimeSpan? Duration { get; set; }
        public DateTime? UploadDate { get; set; }
        public List<string> Tags { get; set; } = new();
        public string? ThumbnailUrl { get; set; }
        public long? ViewCount { get; set; }
        public long? LikeCount { get; set; }
        public int? Width { get; set; }
        public int? Height { get; set; }
        public double? Fps { get; set; }
        public string? VideoCodec { get; set; }
        public string? AudioCodec { get; set; }
        public long? FileSize { get; set; }
    }
}