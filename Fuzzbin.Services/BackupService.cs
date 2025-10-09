using System.Collections.Immutable;
using System.Data.Common;
using System.IO.Compression;
using System.Text.Json;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Data.Context;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;

namespace Fuzzbin.Services;

/// <summary>
/// Provides backup and restore functionality for the Fuzzbin SQLite database.
/// </summary>
public sealed class BackupService : IBackupService
{
    private const string DatabaseEntryName = "database.db";
    private const string ConfigurationEntryName = "configurations.json";
    private const string ManifestEntryName = "manifest.json";

    private readonly ApplicationDbContext _context;
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILogger<BackupService> _logger;
    private readonly JsonSerializerOptions _serializerOptions = new()
    {
        WriteIndented = true
    };

    public BackupService(
        ApplicationDbContext context,
        IUnitOfWork unitOfWork,
        ILogger<BackupService> logger)
    {
        _context = context;
        _unitOfWork = unitOfWork;
        _logger = logger;
    }

    public async Task<BackupResult> CreateBackupAsync(CancellationToken cancellationToken = default)
    {
        var databasePath = GetDatabasePath();
        var backupDirectory = EnsureBackupDirectoryExists(databasePath);
        var timestamp = DateTimeOffset.UtcNow;
        var backupFileName = $"fuzzbin-backup-{timestamp:yyyyMMddHHmmss}.zip";
        var backupFilePath = Path.Combine(backupDirectory, backupFileName);

        _logger.LogInformation("Creating database backup at {BackupFilePath}", backupFilePath);

        await using var fileStream = new FileStream(backupFilePath, FileMode.Create, FileAccess.Write, FileShare.None);
        using (var archive = new ZipArchive(fileStream, ZipArchiveMode.Create, leaveOpen: true))
        {
            await WriteDatabaseAsync(databasePath, archive, cancellationToken).ConfigureAwait(false);
            await WriteConfigurationSnapshotAsync(archive, cancellationToken).ConfigureAwait(false);
            await WriteSidecarFilesAsync(databasePath, archive, cancellationToken).ConfigureAwait(false);
            await WriteManifestAsync(databasePath, archive, timestamp, cancellationToken).ConfigureAwait(false);
        }

        await fileStream.FlushAsync(cancellationToken).ConfigureAwait(false);

        var info = new FileInfo(backupFilePath);
        _logger.LogInformation("Database backup completed. Size: {BackupSize} bytes", info.Length);

        return new BackupResult(backupFilePath, info.Length, timestamp);
    }

    public async Task RestoreBackupAsync(Stream backupStream, CancellationToken cancellationToken = default)
    {
        if (backupStream is null)
        {
            throw new ArgumentNullException(nameof(backupStream));
        }

        if (backupStream.CanSeek)
        {
            backupStream.Seek(0, SeekOrigin.Begin);
        }

        var databasePath = GetDatabasePath();
        var databaseDirectory = Path.GetDirectoryName(databasePath) ?? throw new InvalidOperationException("Unable to determine database directory");
        var tempRestoreDirectory = Path.Combine(databaseDirectory, $".fuzzbin-restore-{Guid.NewGuid():N}");
        Directory.CreateDirectory(tempRestoreDirectory);
        var tempDatabasePath = Path.Combine(tempRestoreDirectory, Path.GetFileName(databasePath));
        var sidecarRestoreItems = new List<(SidecarInfo Info, string? TempPath, bool HasEntry)>();

        using (var archive = new ZipArchive(backupStream, ZipArchiveMode.Read, leaveOpen: true))
        {
            var databaseEntry = archive.GetEntry(DatabaseEntryName) ?? throw new InvalidOperationException($"Backup archive is missing required entry '{DatabaseEntryName}'");

            await using (var entryStream = databaseEntry.Open())
            await using (var fileStream = new FileStream(tempDatabasePath, FileMode.Create, FileAccess.Write, FileShare.None))
            {
                await entryStream.CopyToAsync(fileStream, cancellationToken).ConfigureAwait(false);
            }

            foreach (var sidecar in EnumerateSidecarFiles(databasePath))
            {
                var entry = archive.GetEntry(sidecar.EntryName);
                if (entry == null)
                {
                    sidecarRestoreItems.Add((sidecar, null, false));
                    continue;
                }

                var tempSidecarPath = Path.Combine(tempRestoreDirectory, Path.GetFileName(sidecar.Path));
                await using var entryStream = entry.Open();
                await using var fileStream = new FileStream(tempSidecarPath, FileMode.Create, FileAccess.Write, FileShare.None);
                await entryStream.CopyToAsync(fileStream, cancellationToken).ConfigureAwait(false);

                sidecarRestoreItems.Add((sidecar, tempSidecarPath, true));
            }
        }

        try
        {
            await _context.Database.CloseConnectionAsync();
            _context.ChangeTracker.Clear();
            SqliteConnection.ClearAllPools();

            var safetyBackupPath = $"{databasePath}.{DateTimeOffset.UtcNow:yyyyMMddHHmmss}.bak";
            if (File.Exists(databasePath))
            {
                File.Copy(databasePath, safetyBackupPath, overwrite: true);
                _logger.LogInformation("Created safety backup at {SafetyBackupPath}", safetyBackupPath);
            }

            File.Copy(tempDatabasePath, databasePath, overwrite: true);
            _logger.LogInformation("Database restored from backup to {DatabasePath}", databasePath);

            foreach (var sidecar in sidecarRestoreItems)
            {
                if (sidecar.HasEntry && sidecar.TempPath is not null)
                {
                    File.Copy(sidecar.TempPath, sidecar.Info.Path, overwrite: true);
                    _logger.LogInformation("Restored sidecar file {SidecarPath}", sidecar.Info.Path);
                }
                else if (File.Exists(sidecar.Info.Path))
                {
                    File.Delete(sidecar.Info.Path);
                    _logger.LogInformation("Removed leftover sidecar file {SidecarPath}", sidecar.Info.Path);
                }
            }
        }
        finally
        {
            if (Directory.Exists(tempRestoreDirectory))
            {
                try
                {
                    Directory.Delete(tempRestoreDirectory, recursive: true);
                }
                catch
                {
                    // Ignored; temp directory cleanup best-effort
                }
            }
        }
    }

    private static async Task WriteDatabaseAsync(string databasePath, ZipArchive archive, CancellationToken cancellationToken)
    {
        var entry = archive.CreateEntry(DatabaseEntryName, CompressionLevel.Fastest);

        await using var entryStream = entry.Open();
        await using var databaseStream = new FileStream(databasePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
        await databaseStream.CopyToAsync(entryStream, cancellationToken).ConfigureAwait(false);
    }

    private async Task WriteConfigurationSnapshotAsync(ZipArchive archive, CancellationToken cancellationToken)
    {
        var configurations = await _unitOfWork.Configurations.GetAllAsync().ConfigureAwait(false);
        var entry = archive.CreateEntry(ConfigurationEntryName, CompressionLevel.Optimal);

        await using var entryStream = entry.Open();
        await JsonSerializer.SerializeAsync(entryStream, configurations, _serializerOptions, cancellationToken).ConfigureAwait(false);
    }

    private async Task WriteManifestAsync(string databasePath, ZipArchive archive, DateTimeOffset createdAt, CancellationToken cancellationToken)
    {
        var entry = archive.CreateEntry(ManifestEntryName, CompressionLevel.Optimal);
        var manifest = new BackupManifest
        {
            Application = "Fuzzbin",
            CreatedAt = createdAt,
            DatabaseSize = new FileInfo(databasePath).Length,
            ConfigurationCount = await _unitOfWork.Configurations.CountAsync().ConfigureAwait(false),
            RuntimeVersion = Environment.Version.ToString(),
            Assemblies = AppDomain.CurrentDomain.GetAssemblies()
                .Where(a => !a.IsDynamic)
                .Select(a => new AssemblyInfo
                {
                    Name = a.GetName().Name ?? string.Empty,
                    Version = a.GetName().Version?.ToString() ?? "unknown"
                })
                .OrderBy(a => a.Name)
                .ToImmutableArray()
        };

        await using var entryStream = entry.Open();
        await JsonSerializer.SerializeAsync(entryStream, manifest, _serializerOptions, cancellationToken).ConfigureAwait(false);
    }

    private async Task WriteSidecarFilesAsync(string databasePath, ZipArchive archive, CancellationToken cancellationToken)
    {
        foreach (var sidecar in EnumerateSidecarFiles(databasePath))
        {
            if (!File.Exists(sidecar.Path))
            {
                continue;
            }

            var entry = archive.CreateEntry(sidecar.EntryName, CompressionLevel.Fastest);

            await using var entryStream = entry.Open();
            await using var fileStream = new FileStream(sidecar.Path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
            await fileStream.CopyToAsync(entryStream, cancellationToken).ConfigureAwait(false);
        }
    }

    private string EnsureBackupDirectoryExists(string databasePath)
    {
        var databaseDirectory = Path.GetDirectoryName(databasePath) ?? throw new InvalidOperationException("Unable to determine database directory");
        var backupDirectory = Path.Combine(databaseDirectory, "backups");

        if (!Directory.Exists(backupDirectory))
        {
            Directory.CreateDirectory(backupDirectory);
            _logger.LogInformation("Created backup directory at {BackupDirectory}", backupDirectory);
        }

        return backupDirectory;
    }

    private string GetDatabasePath()
    {
        var connectionString = _context.Database.GetDbConnection().ConnectionString;
        if (string.IsNullOrWhiteSpace(connectionString))
        {
            throw new InvalidOperationException("Database connection string is not configured");
        }

        var builder = new DbConnectionStringBuilder
        {
            ConnectionString = connectionString
        };

        var keysToTry = new[] { "Data Source", "DataSource", "Filename" };
        foreach (var key in keysToTry)
        {
            if (builder.TryGetValue(key, out var value) && value is string dataSource && !string.IsNullOrWhiteSpace(dataSource))
            {
                return Path.GetFullPath(dataSource);
            }
        }

        throw new InvalidOperationException("Unable to determine database path from connection string");
    }

    private static IEnumerable<SidecarInfo> EnumerateSidecarFiles(string databasePath)
    {
        yield return new SidecarInfo(databasePath + "-wal", $"{DatabaseEntryName}-wal");
        yield return new SidecarInfo(databasePath + "-shm", $"{DatabaseEntryName}-shm");
    }

    private sealed record BackupManifest
    {
        public string Application { get; init; } = string.Empty;
        public DateTimeOffset CreatedAt { get; init; }
        public long DatabaseSize { get; init; }
        public int ConfigurationCount { get; init; }
        public string RuntimeVersion { get; init; } = string.Empty;
        public ImmutableArray<AssemblyInfo> Assemblies { get; init; } = [];
    }

    private sealed record AssemblyInfo
    {
        public string Name { get; init; } = string.Empty;
        public string Version { get; init; } = string.Empty;
    }

    private readonly record struct SidecarInfo(string Path, string EntryName);
}
