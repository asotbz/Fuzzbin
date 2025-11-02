using System;

namespace Fuzzbin.Services.Models;

/// <summary>
/// Configuration options for external metadata cache system
/// </summary>
public class ExternalCacheOptions
{
    /// <summary>
    /// Cache time-to-live in hours. Default: 336 (14 days)
    /// </summary>
    public int CacheTtlHours { get; set; } = 336;
    
    /// <summary>
    /// Maximum allowed cache TTL in hours. Default: 720 (30 days)
    /// </summary>
    public int MaxCacheTtlHours { get; set; } = 720;
    
    /// <summary>
    /// Minimum allowed cache TTL in hours. 0 = cache disabled
    /// </summary>
    public int MinCacheTtlHours { get; set; } = 0;
    
    /// <summary>
    /// User-Agent string for MusicBrainz API requests (required by MusicBrainz)
    /// </summary>
    public string MusicBrainzUserAgent { get; set; } = "Fuzzbin/1.0";
    
    /// <summary>
    /// Number of retry attempts for failed requests. Default: 3
    /// </summary>
    public int RetryCount { get; set; } = 3;
    
    /// <summary>
    /// Delay in seconds for first retry attempt. Default: 2
    /// </summary>
    public int RetryDelaySeconds1 { get; set; } = 2;
    
    /// <summary>
    /// Delay in seconds for second retry attempt. Default: 4
    /// </summary>
    public int RetryDelaySeconds2 { get; set; } = 4;
    
    /// <summary>
    /// Enable automatic cache purging. Default: true
    /// </summary>
    public bool EnableAutomaticPurge { get; set; } = true;
    
    /// <summary>
    /// Interval in hours between maintenance runs. Default: 8
    /// </summary>
    public int MaintenanceIntervalHours { get; set; } = 8;
    
    /// <summary>
    /// Gets the cache duration as a TimeSpan, clamped to min/max values
    /// </summary>
    /// <returns>Cache duration, or TimeSpan.Zero if cache is disabled</returns>
    public TimeSpan GetCacheDuration()
    {
        var clamped = Math.Clamp(CacheTtlHours, MinCacheTtlHours, MaxCacheTtlHours);
        return clamped == 0 ? TimeSpan.Zero : TimeSpan.FromHours(clamped);
    }
    
    /// <summary>
    /// Gets the maintenance interval as a TimeSpan
    /// </summary>
    /// <returns>Maintenance interval (minimum 1 hour)</returns>
    public TimeSpan GetMaintenanceInterval()
    {
        return TimeSpan.FromHours(Math.Max(1, MaintenanceIntervalHours));
    }
    
    /// <summary>
    /// Checks if caching is enabled
    /// </summary>
    /// <returns>True if cache TTL is greater than 0</returns>
    public bool IsCacheEnabled() => CacheTtlHours > 0;
}