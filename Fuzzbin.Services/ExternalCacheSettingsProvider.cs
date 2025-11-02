using System;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;

namespace Fuzzbin.Services;

/// <summary>
/// Provides cached access to external metadata cache configuration settings
/// Settings are cached in memory for 5 minutes to reduce database load
/// </summary>
public sealed class ExternalCacheSettingsProvider : IExternalCacheSettingsProvider
{
    private const string CacheKey = "Fuzzbin.ExternalCacheSettings";
    private static readonly TimeSpan CacheDuration = TimeSpan.FromMinutes(5);
    
    private readonly IServiceScopeFactory _scopeFactory;
    private readonly IMemoryCache _cache;
    private readonly ILogger<ExternalCacheSettingsProvider> _logger;
    
    public ExternalCacheSettingsProvider(
        IServiceScopeFactory scopeFactory,
        IMemoryCache cache,
        ILogger<ExternalCacheSettingsProvider> logger)
    {
        _scopeFactory = scopeFactory ?? throw new ArgumentNullException(nameof(scopeFactory));
        _cache = cache ?? throw new ArgumentNullException(nameof(cache));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }
    
    /// <summary>
    /// Gets the current external cache settings from cache or database
    /// </summary>
    public ExternalCacheOptions GetSettings()
    {
        return _cache.GetOrCreate(CacheKey, entry =>
        {
            entry.AbsoluteExpirationRelativeToNow = CacheDuration;
            return LoadSettings();
        }) ?? new ExternalCacheOptions();
    }
    
    /// <summary>
    /// Invalidates the cached settings, forcing a reload on next access
    /// </summary>
    public void Invalidate()
    {
        _cache.Remove(CacheKey);
        _logger.LogInformation("External cache settings invalidated");
    }
    
    /// <summary>
    /// Loads settings from the database
    /// </summary>
    private ExternalCacheOptions LoadSettings()
    {
        try
        {
            using var scope = _scopeFactory.CreateScope();
            var unitOfWork = scope.ServiceProvider.GetRequiredService<IUnitOfWork>();
            
            var ttlHours = ReadInt(unitOfWork, "ExternalCache", "CacheTtlHours", 336);
            var userAgent = ReadString(unitOfWork, "ExternalCache", "MusicBrainzUserAgent", 
                "Fuzzbin/1.0 (https://github.com/fuzzbin)");
            var enablePurge = ReadBool(unitOfWork, "ExternalCache", "EnableAutomaticPurge", true);
            var maintenanceInterval = ReadInt(unitOfWork, "ExternalCache", "MaintenanceIntervalHours", 8);
            
            var options = new ExternalCacheOptions
            {
                CacheTtlHours = ttlHours,
                MusicBrainzUserAgent = userAgent,
                EnableAutomaticPurge = enablePurge,
                MaintenanceIntervalHours = maintenanceInterval
            };
            
            _logger.LogDebug(
                "Loaded external cache settings: TTL={TtlHours}h, AutoPurge={AutoPurge}, Maintenance={MaintenanceHours}h",
                options.CacheTtlHours,
                options.EnableAutomaticPurge,
                options.MaintenanceIntervalHours);
            
            return options;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to load external cache settings, using defaults");
            return new ExternalCacheOptions();
        }
    }
    
    /// <summary>
    /// Reads an integer configuration value from the database
    /// </summary>
    private int ReadInt(IUnitOfWork unitOfWork, string category, string key, int defaultValue)
    {
        try
        {
            var config = unitOfWork.Configurations
                .FirstOrDefaultAsync(c => c.Category == category && c.Key == key && c.IsActive)
                .GetAwaiter()
                .GetResult();
            
            if (config?.Value != null && int.TryParse(config.Value, out var value))
            {
                return value;
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to read config {Category}.{Key}", category, key);
        }
        
        return defaultValue;
    }
    
    /// <summary>
    /// Reads a string configuration value from the database
    /// </summary>
    private string ReadString(IUnitOfWork unitOfWork, string category, string key, string defaultValue)
    {
        try
        {
            var config = unitOfWork.Configurations
                .FirstOrDefaultAsync(c => c.Category == category && c.Key == key && c.IsActive)
                .GetAwaiter()
                .GetResult();
            
            return config?.Value ?? defaultValue;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to read config {Category}.{Key}", category, key);
            return defaultValue;
        }
    }
    
    /// <summary>
    /// Reads a boolean configuration value from the database
    /// </summary>
    private bool ReadBool(IUnitOfWork unitOfWork, string category, string key, bool defaultValue)
    {
        try
        {
            var config = unitOfWork.Configurations
                .FirstOrDefaultAsync(c => c.Category == category && c.Key == key && c.IsActive)
                .GetAwaiter()
                .GetResult();
            
            if (config?.Value != null && bool.TryParse(config.Value, out var value))
            {
                return value;
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to read config {Category}.{Key}", category, key);
        }
        
        return defaultValue;
    }
}