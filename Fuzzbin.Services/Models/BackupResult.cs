using System.IO;

namespace Fuzzbin.Services.Models;

/// <summary>
/// Represents the result of a backup operation.
/// </summary>
public sealed record BackupResult(string FilePath, long FileSize, DateTimeOffset CreatedAt)
{
    /// <summary>
    /// Gets the file name of the backup archive.
    /// </summary>
    public string FileName => Path.GetFileName(FilePath);
}
