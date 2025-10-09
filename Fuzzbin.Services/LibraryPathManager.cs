using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Interfaces;

namespace Fuzzbin.Services;

public class LibraryPathManager : ILibraryPathManager, IDisposable
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILogger<LibraryPathManager> _logger;
    private readonly SemaphoreSlim _initializationLock = new(1, 1);

    private bool _disposed;
    private bool _initialized;
    private string _libraryRoot = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
        "Fuzzbin",
        "Library");
    private string _videoRoot = string.Empty;
    private string _metadataRoot = string.Empty;
    private string _artworkRoot = string.Empty;

    private static readonly char[] InvalidDirectoryChars = Path.GetInvalidPathChars()
        .Concat(new[] { ':', '*', '?', '"', '<', '>', '|', '\\', '/' })
        .Distinct()
        .ToArray();

    private static readonly char[] InvalidFileChars = Path.GetInvalidFileNameChars();

    private const string LibraryConfigKey = "LibraryPath";
    private const string LibraryConfigCategory = "Storage";

    public LibraryPathManager(IUnitOfWork unitOfWork, ILogger<LibraryPathManager> logger)
    {
        _unitOfWork = unitOfWork;
        _logger = logger;
    }

    public async Task<string> GetLibraryRootAsync(CancellationToken cancellationToken = default)
    {
        await EnsureInitializedAsync(cancellationToken).ConfigureAwait(false);
        return _libraryRoot;
    }

    public async Task<string> GetVideoRootAsync(CancellationToken cancellationToken = default)
    {
        await EnsureInitializedAsync(cancellationToken).ConfigureAwait(false);
        return _videoRoot;
    }

    public async Task<string> GetMetadataRootAsync(CancellationToken cancellationToken = default)
    {
        await EnsureInitializedAsync(cancellationToken).ConfigureAwait(false);
        return _metadataRoot;
    }

    public async Task<string> GetArtworkRootAsync(CancellationToken cancellationToken = default)
    {
        await EnsureInitializedAsync(cancellationToken).ConfigureAwait(false);
        return _artworkRoot;
    }

    public string SanitizeFileName(string value, string? extension = null)
    {
        var sanitized = SanitizeSegmentInternal(value, InvalidFileChars, "untitled");
        sanitized = RemoveDuplicateCharacters(sanitized, '_');
        sanitized = sanitized.Trim('_', ' ', '.');

        if (string.IsNullOrWhiteSpace(sanitized))
        {
            sanitized = "untitled";
        }

        if (!string.IsNullOrWhiteSpace(extension))
        {
            extension = extension!.StartsWith('.') ? extension : $".{extension}";
            sanitized = Path.ChangeExtension(sanitized, extension);
        }

        return sanitized;
    }

    public string SanitizeDirectoryName(string value)
    {
        var sanitized = SanitizeSegmentInternal(value, InvalidDirectoryChars, "unknown");
        sanitized = RemoveDuplicateCharacters(sanitized, '_');
        sanitized = sanitized.Trim('_', ' ');
        return string.IsNullOrWhiteSpace(sanitized) ? "unknown" : sanitized;
    }

    public string NormalizePath(string? path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return string.Empty;
        }

        return path.Replace('\\', '/').Trim();
    }

    public void EnsureDirectoryExists(string path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return;
        }

        Directory.CreateDirectory(path);
    }

    private async Task EnsureInitializedAsync(CancellationToken cancellationToken)
    {
        if (_initialized)
        {
            return;
        }

        await _initializationLock.WaitAsync(cancellationToken).ConfigureAwait(false);
        try
        {
            if (_initialized)
            {
                return;
            }

            var config = await _unitOfWork.Configurations
                .FirstOrDefaultAsync(c => c.Key == LibraryConfigKey && c.Category == LibraryConfigCategory)
                .ConfigureAwait(false);

            if (!string.IsNullOrWhiteSpace(config?.Value))
            {
                _libraryRoot = Environment.ExpandEnvironmentVariables(config.Value);
            }

            _videoRoot = Path.Combine(_libraryRoot, "videos");
            _metadataRoot = Path.Combine(_libraryRoot, "metadata");
            _artworkRoot = Path.Combine(_libraryRoot, "artwork");

            Directory.CreateDirectory(_libraryRoot);
            Directory.CreateDirectory(_videoRoot);
            Directory.CreateDirectory(_metadataRoot);
            Directory.CreateDirectory(_artworkRoot);

            _logger.LogDebug(
                "Initialized library paths. Root: {Root}, Video: {VideoRoot}, Metadata: {MetadataRoot}, Artwork: {ArtworkRoot}",
                _libraryRoot,
                _videoRoot,
                _metadataRoot,
                _artworkRoot);

            _initialized = true;
        }
        finally
        {
            _initializationLock.Release();
        }
    }

    private static string SanitizeSegmentInternal(string value, IReadOnlyCollection<char> invalidChars, string fallback)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            value = fallback;
        }

        var builder = new StringBuilder(value.Length);
        foreach (var c in value)
        {
            builder.Append(invalidChars.Contains(c) ? '_' : c);
        }

        return builder.ToString();
    }

    private static string RemoveDuplicateCharacters(string value, char character)
    {
        if (string.IsNullOrEmpty(value))
        {
            return value;
        }

        var builder = new StringBuilder(value.Length);
        char previous = '\0';
        foreach (var c in value)
        {
            if (c == character && previous == character)
            {
                continue;
            }

            builder.Append(c);
            previous = c;
        }

        return builder.ToString();
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _initializationLock.Dispose();
        _disposed = true;
    }
}
