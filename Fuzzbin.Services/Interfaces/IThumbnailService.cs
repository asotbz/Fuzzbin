using System.Threading;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Services.Interfaces;

public interface IThumbnailService
{
    /// <summary>
    /// Generate a thumbnail for a video file
    /// </summary>
    /// <param name="videoPath">Path to the video file</param>
    /// <param name="outputPath">Path where the thumbnail should be saved</param>
    /// <param name="timePosition">Time position in seconds to capture the thumbnail (default: 10% of duration)</param>
    /// <returns>True if successful, false otherwise</returns>
    Task<bool> GenerateThumbnailAsync(string videoPath, string outputPath, double? timePosition = null, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Generate thumbnails for all videos missing them
    /// </summary>
    /// <param name="progress">Optional progress callback</param>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Number of thumbnails generated</returns>
    Task<int> GenerateMissingThumbnailsAsync(IProgress<(int current, int total, string currentVideo)>? progress = null, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Get the thumbnail path for a video
    /// </summary>
    /// <param name="video">The video entity</param>
    /// <returns>Path to the thumbnail file</returns>
    string GetThumbnailPath(Video video);
    
    /// <summary>
    /// Check if a video has a thumbnail
    /// </summary>
    /// <param name="video">The video entity</param>
    /// <returns>True if thumbnail exists</returns>
    bool HasThumbnail(Video video);
    
    /// <summary>
    /// Delete thumbnail for a video
    /// </summary>
    /// <param name="video">The video entity</param>
    /// <returns>True if successful or no thumbnail existed</returns>
    Task<bool> DeleteThumbnailAsync(Video video);
    
    /// <summary>
    /// Get thumbnail URL for web display
    /// </summary>
    /// <param name="video">The video entity</param>
    /// <returns>URL to the thumbnail</returns>
    string GetThumbnailUrl(Video video);
}
