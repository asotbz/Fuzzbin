using System.Diagnostics;
using System.Threading;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.Interfaces;

namespace Fuzzbin.Services;

public class ThumbnailService : IThumbnailService
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILogger<ThumbnailService> _logger;
    private readonly IConfiguration _configuration;
    private readonly IDownloadSettingsProvider _settingsProvider;
    private readonly IImageOptimizationService _imageOptimizationService;
    private readonly string _thumbnailDirectory;
    private readonly string _webRootPath;

    public ThumbnailService(
        IUnitOfWork unitOfWork,
        ILogger<ThumbnailService> logger,
        IConfiguration configuration,
        IDownloadSettingsProvider settingsProvider,
        IImageOptimizationService imageOptimizationService)
    {
        _unitOfWork = unitOfWork;
        _logger = logger;
        _configuration = configuration;
        _settingsProvider = settingsProvider;
        _imageOptimizationService = imageOptimizationService;
        
        _webRootPath = configuration["WebRootPath"] ?? Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "wwwroot");
        _thumbnailDirectory = Path.Combine(_webRootPath, "thumbnails");
        
        // Ensure thumbnail directory exists
        if (!Directory.Exists(_thumbnailDirectory))
        {
            Directory.CreateDirectory(_thumbnailDirectory);
            _logger.LogInformation("Created thumbnail directory: {ThumbnailDirectory}", _thumbnailDirectory);
        }
    }

    public async Task<bool> GenerateThumbnailAsync(string videoPath, string outputPath, double? timePosition = null, CancellationToken cancellationToken = default)
    {
        if (!File.Exists(videoPath))
        {
            _logger.LogWarning("Video file not found: {VideoPath}", videoPath);
            return false;
        }

        try
        {
            cancellationToken.ThrowIfCancellationRequested();

            // Ensure output directory exists
            var outputDir = Path.GetDirectoryName(outputPath);
            if (!string.IsNullOrEmpty(outputDir) && !Directory.Exists(outputDir))
            {
                Directory.CreateDirectory(outputDir);
            }

            // If time position not specified, get video duration and use 10%
            if (!timePosition.HasValue)
            {
                var duration = await GetVideoDurationAsync(videoPath);
                timePosition = duration * 0.1; // 10% of the video
            }

            // Use FFmpeg to generate thumbnail
            var ffmpegPath = _settingsProvider.GetFfmpegPath();
            var arguments = $"-i \"{videoPath}\" -ss {timePosition:F2} -vframes 1 -vf \"scale=320:-1\" -y \"{outputPath}\"";

            using var process = new Process
            {
                StartInfo = new ProcessStartInfo
                {
                    FileName = ffmpegPath,
                    Arguments = arguments,
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true
                }
            };

            _logger.LogDebug("Executing FFmpeg: {Command} {Arguments}", ffmpegPath, arguments);

            process.Start();
            
            // Read output asynchronously
            var outputTask = process.StandardOutput.ReadToEndAsync();
            var errorTask = process.StandardError.ReadToEndAsync();

            var completed = await Task.Run(() => process.WaitForExit(30000), cancellationToken); // 30 second timeout
            
            if (!completed)
            {
                process.Kill();
                _logger.LogError("FFmpeg process timed out for video: {VideoPath}", videoPath);
                return false;
            }

            var output = await outputTask;
            var error = await errorTask;

            if (process.ExitCode != 0)
            {
                _logger.LogError("FFmpeg failed with exit code {ExitCode}. Error: {Error}", process.ExitCode, error);
                return false;
            }

            await _imageOptimizationService.OptimizeInPlaceAsync(outputPath, cancellationToken).ConfigureAwait(false);

            _logger.LogInformation("Generated thumbnail for {VideoPath} at {OutputPath}", videoPath, outputPath);
            return File.Exists(outputPath);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error generating thumbnail for {VideoPath}", videoPath);
            return false;
        }
    }

    public async Task<int> GenerateMissingThumbnailsAsync(
        IProgress<(int current, int total, string currentVideo)>? progress = null, 
        CancellationToken cancellationToken = default)
    {
        var videos = await _unitOfWork.Videos.GetAllAsync();
        var videosNeedingThumbnails = videos.Where(v => !HasThumbnail(v) && !string.IsNullOrEmpty(v.FilePath)).ToList();
        var total = videosNeedingThumbnails.Count;
        var generated = 0;

        _logger.LogInformation("Found {Count} videos needing thumbnails", total);

        for (int i = 0; i < videosNeedingThumbnails.Count; i++)
        {
            if (cancellationToken.IsCancellationRequested)
            {
                _logger.LogInformation("Thumbnail generation cancelled after {Generated} thumbnails", generated);
                break;
            }

            var video = videosNeedingThumbnails[i];
            progress?.Report((i + 1, total, video.Title));

            if (!File.Exists(video.FilePath))
            {
                _logger.LogWarning("Video file not found for {VideoId}: {FilePath}", video.Id, video.FilePath);
                continue;
            }

            var thumbnailPath = GetThumbnailPath(video);
            var success = await GenerateThumbnailAsync(video.FilePath, thumbnailPath, cancellationToken: cancellationToken);

            if (success)
            {
                generated++;
                
                // Update video entity with thumbnail path
                video.ThumbnailPath = Path.GetRelativePath(_webRootPath, thumbnailPath);
                await _unitOfWork.Videos.UpdateAsync(video);
            }
        }

        await _unitOfWork.SaveChangesAsync();
        _logger.LogInformation("Generated {Generated} of {Total} thumbnails", generated, total);

        return generated;
    }

    public string GetThumbnailPath(Video video)
    {
        var safeFileName = $"{video.Id}.jpg";
        return Path.Combine(_thumbnailDirectory, safeFileName);
    }

    public bool HasThumbnail(Video video)
    {
        if (!string.IsNullOrEmpty(video.ThumbnailPath))
        {
            var fullPath = Path.Combine(_webRootPath, video.ThumbnailPath);
            return File.Exists(fullPath);
        }

        // Check default location
        var defaultPath = GetThumbnailPath(video);
        return File.Exists(defaultPath);
    }

    public async Task<bool> DeleteThumbnailAsync(Video video)
    {
        try
        {
            var thumbnailPath = GetThumbnailPath(video);
            if (File.Exists(thumbnailPath))
            {
                File.Delete(thumbnailPath);
                _logger.LogInformation("Deleted thumbnail for video {VideoId}", video.Id);
            }

            // Clear thumbnail path in video entity
            if (!string.IsNullOrEmpty(video.ThumbnailPath))
            {
                video.ThumbnailPath = null;
                await _unitOfWork.Videos.UpdateAsync(video);
                await _unitOfWork.SaveChangesAsync();
            }

            return true;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error deleting thumbnail for video {VideoId}", video.Id);
            return false;
        }
    }

    public string GetThumbnailUrl(Video video)
    {
        // First check if video has YouTube ID - use YouTube thumbnail
        if (!string.IsNullOrEmpty(video.YouTubeId))
        {
            return $"https://img.youtube.com/vi/{video.YouTubeId}/mqdefault.jpg";
        }

        // Check if video has a custom thumbnail path
        if (!string.IsNullOrEmpty(video.ThumbnailPath))
        {
            return $"/{video.ThumbnailPath.Replace('\\', '/')}";
        }

        // Check if thumbnail exists in default location
        if (HasThumbnail(video))
        {
            return $"/thumbnails/{video.Id}.jpg";
        }

        // Return placeholder
        return "/images/video-placeholder.svg";
    }

    private async Task<double> GetVideoDurationAsync(string videoPath)
    {
        try
        {
            var ffprobePath = _settingsProvider.GetFfprobePath();
            var arguments = $"-v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 \"{videoPath}\"";

            using var process = new Process
            {
                StartInfo = new ProcessStartInfo
                {
                    FileName = ffprobePath,
                    Arguments = arguments,
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true
                }
            };

            process.Start();
            var output = await process.StandardOutput.ReadToEndAsync();
            await process.WaitForExitAsync();

            if (double.TryParse(output.Trim(), out var duration))
            {
                return duration;
            }

            _logger.LogWarning("Could not parse duration from ffprobe output: {Output}", output);
            return 30.0; // Default to 30 seconds if we can't get duration
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error getting video duration for {VideoPath}", videoPath);
            return 30.0; // Default to 30 seconds on error
        }
    }
}
