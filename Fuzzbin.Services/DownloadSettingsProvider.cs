using System;
using System.Globalization;
using System.IO;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.DependencyInjection;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;

namespace Fuzzbin.Services;

public sealed class DownloadSettingsProvider : IDownloadSettingsProvider
{
    private const string OptionsCacheKey = "Fuzzbin.DownloadWorkerOptions";
    private const string ToolCacheKey = "Fuzzbin.DownloadTools";
    private static readonly TimeSpan CacheDuration = TimeSpan.FromMinutes(5);

    private readonly IServiceScopeFactory _scopeFactory;
    private readonly IMemoryCache _cache;
    private readonly ILogger<DownloadSettingsProvider> _logger;
    private readonly object _syncRoot = new();

    public DownloadSettingsProvider(
        IServiceScopeFactory scopeFactory,
        IMemoryCache cache,
        ILogger<DownloadSettingsProvider> logger)
    {
        _scopeFactory = scopeFactory;
        _cache = cache;
        _logger = logger;
    }

    public DownloadWorkerOptions GetOptions()
    {
        return _cache.GetOrCreate(OptionsCacheKey, entry =>
        {
            entry.AbsoluteExpirationRelativeToNow = CacheDuration;
            return LoadOptions();
        })!;
    }

    public string GetFfmpegPath()
    {
        return GetToolPaths().ffmpeg;
    }

    public string GetFfprobePath()
    {
        return GetToolPaths().ffprobe;
    }

    public void Invalidate()
    {
        _cache.Remove(OptionsCacheKey);
        _cache.Remove(ToolCacheKey);
    }

    private (string ffmpeg, string ffprobe) GetToolPaths()
    {
        return _cache.GetOrCreate(ToolCacheKey, entry =>
        {
            entry.AbsoluteExpirationRelativeToNow = CacheDuration;
            return LoadToolPaths();
        })!;
    }

    private DownloadWorkerOptions LoadOptions()
    {
        try
        {
            using var scope = _scopeFactory.CreateScope();
            var unitOfWork = scope.ServiceProvider.GetRequiredService<IUnitOfWork>();

            var outputDirectory = GetString(unitOfWork, "Downloads", "OutputDirectory", "downloads", "Default output directory for downloaded media",
                ("Storage", "DownloadsPath"));
            var tempDirectory = GetString(unitOfWork, "Downloads", "TempDirectory", Path.Combine(outputDirectory, "tmp"), "Temporary download staging directory");
            var format = GetString(unitOfWork, "Downloads", "Format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best", "Default yt-dlp format selector",
                ("Download", "DefaultVideoFormat"));
            var bandwidthLimit = GetString(unitOfWork, "Downloads", "BandwidthLimit", string.Empty, "Optional bandwidth limit for downloads");

            var maxConcurrentDownloads = GetInt(unitOfWork, "Downloads", "MaxConcurrentDownloads", 3, "Maximum number of concurrent downloads",
                ("Download", "MaxConcurrentDownloads"));
            var maxRetryCount = GetInt(unitOfWork, "Downloads", "MaxRetryCount", 3, "Maximum retry attempts for failed downloads",
                ("Download", "DownloadRetries"));
            var progressStep = GetDouble(unitOfWork, "Downloads", "ProgressPercentageStep", 1.0, "Minimum percentage change before reporting progress");
            var retryBackoffSeconds = GetDouble(unitOfWork, "Downloads", "RetryBackoffSeconds", 15.0, "Delay (seconds) before retrying a failed download");

            var options = new DownloadWorkerOptions
            {
                OutputDirectory = string.IsNullOrWhiteSpace(outputDirectory) ? "downloads" : outputDirectory,
                TempDirectory = string.IsNullOrWhiteSpace(tempDirectory) ? Path.Combine(outputDirectory, "tmp") : tempDirectory,
                Format = string.IsNullOrWhiteSpace(format) ? "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" : format,
                BandwidthLimit = string.IsNullOrWhiteSpace(bandwidthLimit) ? null : bandwidthLimit,
                MaxConcurrentDownloads = Math.Max(1, maxConcurrentDownloads),
                MaxRetryCount = Math.Max(0, maxRetryCount),
                ProgressPercentageStep = Math.Clamp(progressStep, 0.1, 10.0),
                RetryBackoffSeconds = Math.Max(0.0, retryBackoffSeconds)
            };

            return options;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to load download worker options; falling back to defaults");
            return new DownloadWorkerOptions();
        }
    }

    private (string ffmpeg, string ffprobe) LoadToolPaths()
    {
        try
        {
            using var scope = _scopeFactory.CreateScope();
            var unitOfWork = scope.ServiceProvider.GetRequiredService<IUnitOfWork>();

            var ffmpeg = GetString(unitOfWork, "System", "FfmpegPath", "ffmpeg", "Path to the ffmpeg executable");
            var ffprobe = GetString(unitOfWork, "System", "FfprobePath", "ffprobe", "Path to the ffprobe executable");

            return (string.IsNullOrWhiteSpace(ffmpeg) ? "ffmpeg" : ffmpeg,
                    string.IsNullOrWhiteSpace(ffprobe) ? "ffprobe" : ffprobe);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to load tool paths; using defaults");
            return ("ffmpeg", "ffprobe");
        }
    }

    private string GetString(
        IUnitOfWork unitOfWork,
        string category,
        string key,
        string defaultValue,
        string? description = null,
        params (string Category, string Key)[] legacyKeys)
    {
        try
        {
            lock (_syncRoot)
            {
                var configuration = FindConfiguration(unitOfWork, category, key, out var isLegacy, legacyKeys);

                if (configuration != null && isLegacy)
                {
                    configuration = EnsurePrimaryConfiguration(unitOfWork, configuration, category, key, defaultValue, description);
                }

                if (configuration == null)
                {
                    configuration = new Configuration
                    {
                        Category = category,
                        Key = key,
                        Value = defaultValue,
                        Description = description,
                        IsSystem = false
                    };

                    unitOfWork.Configurations.AddAsync(configuration).GetAwaiter().GetResult();
                    unitOfWork.SaveChangesAsync().GetAwaiter().GetResult();
                    return defaultValue;
                }

                if (string.IsNullOrWhiteSpace(configuration.Value))
                {
                    configuration.Value = defaultValue;
                    configuration.UpdatedAt = DateTime.UtcNow;
                    unitOfWork.Configurations.UpdateAsync(configuration).GetAwaiter().GetResult();
                    unitOfWork.SaveChangesAsync().GetAwaiter().GetResult();
                    return defaultValue;
                }

                return configuration.Value;
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error retrieving configuration value for {Category}/{Key}", category, key);
            return defaultValue;
        }
    }

    private int GetInt(
        IUnitOfWork unitOfWork,
        string category,
        string key,
        int defaultValue,
        string? description = null,
        params (string Category, string Key)[] legacyKeys)
    {
        var raw = GetString(unitOfWork, category, key, defaultValue.ToString(CultureInfo.InvariantCulture), description, legacyKeys);
        return int.TryParse(raw, NumberStyles.Integer, CultureInfo.InvariantCulture, out var value) ? value : defaultValue;
    }

    private double GetDouble(
        IUnitOfWork unitOfWork,
        string category,
        string key,
        double defaultValue,
        string? description = null,
        params (string Category, string Key)[] legacyKeys)
    {
        var raw = GetString(unitOfWork, category, key, defaultValue.ToString(CultureInfo.InvariantCulture), description, legacyKeys);
        return double.TryParse(raw, NumberStyles.Float, CultureInfo.InvariantCulture, out var value) ? value : defaultValue;
    }

    private Configuration? FindConfiguration(
        IUnitOfWork unitOfWork,
        string category,
        string key,
        out bool isLegacy,
        params (string Category, string Key)[] legacyKeys)
    {
        var configuration = unitOfWork.Configurations
            .FirstOrDefaultAsync(c => c.Category == category && c.Key == key)
            .GetAwaiter()
            .GetResult();

        if (configuration != null)
        {
            isLegacy = false;
            return configuration;
        }

        foreach (var (legacyCategory, legacyKey) in legacyKeys)
        {
            if (string.IsNullOrWhiteSpace(legacyCategory) || string.IsNullOrWhiteSpace(legacyKey))
            {
                continue;
            }

            configuration = unitOfWork.Configurations
                .FirstOrDefaultAsync(c => c.Category == legacyCategory && c.Key == legacyKey)
                .GetAwaiter()
                .GetResult();

            if (configuration != null)
            {
                isLegacy = true;
                return configuration;
            }
        }

        isLegacy = false;
        return null;
    }

    private Configuration EnsurePrimaryConfiguration(
        IUnitOfWork unitOfWork,
        Configuration source,
        string category,
        string key,
        string defaultValue,
        string? description)
    {
        if (string.Equals(source.Category, category, StringComparison.OrdinalIgnoreCase))
        {
            return source;
        }

        var existing = unitOfWork.Configurations
            .FirstOrDefaultAsync(c => c.Category == category && c.Key == key)
            .GetAwaiter()
            .GetResult();

        if (existing != null)
        {
            return existing;
        }

        var valueToUse = string.IsNullOrWhiteSpace(source.Value) ? defaultValue : source.Value;

        var cloned = new Configuration
        {
            Category = category,
            Key = key,
            Value = valueToUse,
            Description = description,
            IsSystem = source.IsSystem
        };

        unitOfWork.Configurations.AddAsync(cloned).GetAwaiter().GetResult();
        unitOfWork.SaveChangesAsync().GetAwaiter().GetResult();
        return cloned;
    }
}
