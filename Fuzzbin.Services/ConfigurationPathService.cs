using System;
using System.IO;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Interfaces;

namespace Fuzzbin.Services;

/// <summary>
/// Provides centralized configuration path resolution with environment variable support
/// </summary>
public sealed class ConfigurationPathService : IConfigurationPathService
{
    private const string ConfigDirEnvVar = "FUZZBIN_CONFIG_DIR";
    private const string ContainerEnvVar = "DOTNET_RUNNING_IN_CONTAINER";
    private const string DatabaseFileName = "fuzzbin.db";

    private readonly ILogger<ConfigurationPathService> _logger;
    private readonly Lazy<string> _configDirectory;
    private readonly Lazy<string> _dataDirectory;
    private readonly Lazy<string> _backupDirectory;
    private readonly Lazy<string> _logsDirectory;
    private readonly Lazy<string> _databasePath;
    private readonly Lazy<string> _defaultLibraryPath;
    private readonly Lazy<string> _defaultDownloadsPath;
    private readonly Lazy<string> _thumbnailDirectory;

    public ConfigurationPathService(ILogger<ConfigurationPathService> logger)
    {
        _logger = logger;

        // Initialize all paths lazily for performance
        _configDirectory = new Lazy<string>(ResolveConfigDirectory);
        _dataDirectory = new Lazy<string>(() => Path.Combine(_configDirectory.Value, "data"));
        _backupDirectory = new Lazy<string>(() => Path.Combine(_configDirectory.Value, "backups"));
        _logsDirectory = new Lazy<string>(() => Path.Combine(_configDirectory.Value, "logs"));
        _databasePath = new Lazy<string>(() => Path.Combine(_dataDirectory.Value, DatabaseFileName));
        _defaultLibraryPath = new Lazy<string>(() => Path.Combine(_configDirectory.Value, "Library"));
        _defaultDownloadsPath = new Lazy<string>(() => Path.Combine(_configDirectory.Value, "Downloads"));
        _thumbnailDirectory = new Lazy<string>(() => Path.Combine(_configDirectory.Value, "thumbnails"));
    }

    public string GetConfigDirectory()
    {
        return _configDirectory.Value;
    }

    public string GetDataDirectory()
    {
        EnsureDirectoryExists(_dataDirectory.Value);
        return _dataDirectory.Value;
    }

    public string GetBackupDirectory()
    {
        EnsureDirectoryExists(_backupDirectory.Value);
        return _backupDirectory.Value;
    }

    public string GetLogsDirectory()
    {
        EnsureDirectoryExists(_logsDirectory.Value);
        return _logsDirectory.Value;
    }

    public string GetDatabasePath()
    {
        // Ensure parent directory exists
        EnsureDirectoryExists(_dataDirectory.Value);
        return _databasePath.Value;
    }

    public string GetDefaultLibraryPath()
    {
        return _defaultLibraryPath.Value;
    }

    public string GetDefaultDownloadsPath()
    {
        return _defaultDownloadsPath.Value;
    }

    public string GetThumbnailDirectory()
    {
        EnsureDirectoryExists(_thumbnailDirectory.Value);
        return _thumbnailDirectory.Value;
    }

    public void EnsureDirectoryExists(string path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return;
        }

        try
        {
            if (!Directory.Exists(path))
            {
                Directory.CreateDirectory(path);
                _logger.LogDebug("Created directory: {Path}", path);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to create directory: {Path}", path);
            throw;
        }
    }

    private string ResolveConfigDirectory()
    {
        // Priority 1: Environment variable override
        var envOverride = Environment.GetEnvironmentVariable(ConfigDirEnvVar);
        if (!string.IsNullOrWhiteSpace(envOverride))
        {
            var expandedPath = Environment.ExpandEnvironmentVariables(envOverride);
            _logger.LogInformation(
                "Using configuration directory from {EnvVar}: {Path}",
                ConfigDirEnvVar,
                expandedPath);
            EnsureDirectoryExists(expandedPath);
            return expandedPath;
        }

        // Priority 2: Docker container - use /config
        var isContainer = Environment.GetEnvironmentVariable(ContainerEnvVar);
        if (!string.IsNullOrWhiteSpace(isContainer) &&
            (isContainer.Equals("true", StringComparison.OrdinalIgnoreCase) ||
             isContainer.Equals("1", StringComparison.OrdinalIgnoreCase)))
        {
            const string dockerPath = "/config";
            _logger.LogInformation("Running in container, using configuration directory: {Path}", dockerPath);
            EnsureDirectoryExists(dockerPath);
            return dockerPath;
        }

        // Priority 3: Default to $HOME/Fuzzbin
        var homePath = Environment.GetFolderPath(
            Environment.SpecialFolder.UserProfile,
            Environment.SpecialFolderOption.DoNotVerify);

        if (string.IsNullOrWhiteSpace(homePath))
        {
            // Fallback for systems where UserProfile might not be set
            homePath = Environment.GetFolderPath(Environment.SpecialFolder.Personal);
        }

        if (string.IsNullOrWhiteSpace(homePath))
        {
            // Last resort fallback
            var tempPath = Path.GetTempPath();
            _logger.LogWarning(
                "Unable to determine user home directory, using temp directory: {Path}",
                tempPath);
            homePath = tempPath;
        }

        var defaultPath = Path.Combine(homePath, "Fuzzbin");
        _logger.LogInformation("Using default configuration directory: {Path}", defaultPath);
        EnsureDirectoryExists(defaultPath);
        return defaultPath;
    }
}