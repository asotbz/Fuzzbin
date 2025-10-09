using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.Interfaces;

namespace Fuzzbin.Services;

public class ThumbnailBackgroundService : BackgroundService
{
    private readonly IServiceProvider _serviceProvider;
    private readonly ILogger<ThumbnailBackgroundService> _logger;
    private readonly TimeSpan _checkInterval = TimeSpan.FromMinutes(5); // Check every 5 minutes
    
    public ThumbnailBackgroundService(
        IServiceProvider serviceProvider,
        ILogger<ThumbnailBackgroundService> logger)
    {
        _serviceProvider = serviceProvider;
        _logger = logger;
    }
    
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("Thumbnail background service started");
        
        // Initial delay to let the application start
        await Task.Delay(TimeSpan.FromSeconds(30), stoppingToken);
        
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await CheckAndGenerateThumbnails(stoppingToken);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error in thumbnail background service");
            }
            
            await Task.Delay(_checkInterval, stoppingToken);
        }
        
        _logger.LogInformation("Thumbnail background service stopped");
    }
    
    private async Task CheckAndGenerateThumbnails(CancellationToken cancellationToken)
    {
        using var scope = _serviceProvider.CreateScope();
        var unitOfWork = scope.ServiceProvider.GetRequiredService<IUnitOfWork>();
        var thumbnailService = scope.ServiceProvider.GetRequiredService<IThumbnailService>();
        
        // Get videos without thumbnails
        var videos = await unitOfWork.Videos.GetAllAsync();
        var videosNeedingThumbnails = videos
            .Where(v => !thumbnailService.HasThumbnail(v) && !string.IsNullOrEmpty(v.FilePath))
            .Take(10) // Process up to 10 videos at a time
            .ToList();
        
        if (!videosNeedingThumbnails.Any())
        {
            return;
        }
        
        _logger.LogInformation("Found {Count} videos needing thumbnails", videosNeedingThumbnails.Count);
        
        foreach (var video in videosNeedingThumbnails)
        {
            if (cancellationToken.IsCancellationRequested)
            {
                break;
            }
            
            try
            {
                if (!System.IO.File.Exists(video.FilePath))
                {
                    _logger.LogWarning("Video file not found for {VideoId}: {FilePath}", video.Id, video.FilePath);
                    continue;
                }
                
                var thumbnailPath = thumbnailService.GetThumbnailPath(video);
                var success = await thumbnailService.GenerateThumbnailAsync(video.FilePath, thumbnailPath, cancellationToken: cancellationToken);
                
                if (success)
                {
                    // Update video entity with thumbnail path
                    video.ThumbnailPath = System.IO.Path.GetRelativePath(
                        System.IO.Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "wwwroot"),
                        thumbnailPath
                    );
                    await unitOfWork.Videos.UpdateAsync(video);
                    await unitOfWork.SaveChangesAsync();
                    
                    _logger.LogInformation("Generated thumbnail for video {VideoId}: {Title}", video.Id, video.Title);
                }
                else
                {
                    _logger.LogWarning("Failed to generate thumbnail for video {VideoId}: {Title}", video.Id, video.Title);
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error generating thumbnail for video {VideoId}", video.Id);
            }
            
            // Small delay between thumbnails to avoid overwhelming the system
            await Task.Delay(TimeSpan.FromSeconds(2), cancellationToken);
        }
    }
}
