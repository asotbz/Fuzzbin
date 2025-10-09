namespace Fuzzbin.Core.Interfaces;

public interface ILibraryPathManager
{
    Task<string> GetLibraryRootAsync(CancellationToken cancellationToken = default);
    Task<string> GetVideoRootAsync(CancellationToken cancellationToken = default);
    Task<string> GetMetadataRootAsync(CancellationToken cancellationToken = default);
    Task<string> GetArtworkRootAsync(CancellationToken cancellationToken = default);

    string SanitizeFileName(string value, string? extension = null);
    string SanitizeDirectoryName(string value);
    string NormalizePath(string? path);
    void EnsureDirectoryExists(string path);
}
