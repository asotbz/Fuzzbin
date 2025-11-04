namespace Fuzzbin.Core.Interfaces
{
    /// <summary>
    /// Provides centralized configuration path resolution with environment variable support
    /// </summary>
    public interface IConfigurationPathService
    {
        /// <summary>
        /// Gets the root configuration directory
        /// Default: $HOME/Fuzzbin (non-Docker) or /config (Docker)
        /// Overridable via FUZZBIN_CONFIG_DIR environment variable
        /// </summary>
        string GetConfigDirectory();

        /// <summary>
        /// Gets the data directory (contains database and keys)
        /// Path: FUZZBIN_CONFIG_DIR/data
        /// </summary>
        string GetDataDirectory();

        /// <summary>
        /// Gets the backup directory
        /// Path: FUZZBIN_CONFIG_DIR/backups
        /// </summary>
        string GetBackupDirectory();

        /// <summary>
        /// Gets the logs directory
        /// Path: FUZZBIN_CONFIG_DIR/logs
        /// </summary>
        string GetLogsDirectory();

        /// <summary>
        /// Gets the full database file path
        /// Path: FUZZBIN_CONFIG_DIR/data/fuzzbin.db
        /// </summary>
        string GetDatabasePath();

        /// <summary>
        /// Gets the default library path (user-configurable in UI)
        /// Default: FUZZBIN_CONFIG_DIR/Library
        /// </summary>
        string GetDefaultLibraryPath();

        /// <summary>
        /// Gets the default downloads path (user-configurable in UI)
        /// Default: FUZZBIN_CONFIG_DIR/Downloads
        /// </summary>
        string GetDefaultDownloadsPath();

        /// <summary>
        /// Gets the thumbnail storage directory
        /// Path: FUZZBIN_CONFIG_DIR/thumbnails
        /// </summary>
        string GetThumbnailDirectory();

        /// <summary>
        /// Ensures a directory exists, creating it if necessary
        /// </summary>
        void EnsureDirectoryExists(string path);
    }
}