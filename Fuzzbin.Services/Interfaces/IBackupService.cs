using Fuzzbin.Services.Models;

namespace Fuzzbin.Services.Interfaces;

public interface IBackupService
{
    /// <summary>
    /// Create a backup archive of the application database and related metadata.
    /// </summary>
    /// <param name="cancellationToken">Optional cancellation token.</param>
    /// <returns>Information about the created backup archive.</returns>
    Task<BackupResult> CreateBackupAsync(CancellationToken cancellationToken = default);

    /// <summary>
    /// Restore the application database from a previously created backup archive.
    /// </summary>
    /// <param name="backupStream">Stream containing the backup archive.</param>
    /// <param name="cancellationToken">Optional cancellation token.</param>
    Task RestoreBackupAsync(Stream backupStream, CancellationToken cancellationToken = default);
}
