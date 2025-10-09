using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text.RegularExpressions;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;

namespace Fuzzbin.Services;

public class FileOrganizationService : IFileOrganizationService
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILogger<FileOrganizationService> _logger;
    private readonly ILibraryPathManager _libraryPathManager;

    private static readonly Regex _variablePattern = new(@"\{([^}]+)\}", RegexOptions.Compiled);

    public FileOrganizationService(
        IUnitOfWork unitOfWork,
        ILogger<FileOrganizationService> logger,
        ILibraryPathManager libraryPathManager)
    {
        _unitOfWork = unitOfWork;
        _logger = logger;
        _libraryPathManager = libraryPathManager;
    }

    public async Task<string> OrganizeVideoFileAsync(
        Video video,
        string sourceFilePath,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(video);
        ArgumentException.ThrowIfNullOrWhiteSpace(sourceFilePath);

        try
        {
            var pattern = await ResolveNamingPatternAsync(cancellationToken).ConfigureAwait(false);
            var libraryRoot = await _libraryPathManager.GetVideoRootAsync(cancellationToken).ConfigureAwait(false);

            var relativePath = GenerateFilePath(video, pattern);
            var fullPath = Path.Combine(libraryRoot, relativePath);

            _libraryPathManager.EnsureDirectoryExists(Path.GetDirectoryName(fullPath)!);

            if (!File.Exists(sourceFilePath))
            {
                throw new FileNotFoundException("Source file not found", sourceFilePath);
            }

            var destinationPath = ResolveDuplicate(fullPath);

            await Task.Run(() => File.Move(sourceFilePath, destinationPath), cancellationToken).ConfigureAwait(false);
            _logger.LogInformation(
                "Organized video file from {Source} to {Destination}",
                sourceFilePath,
                destinationPath);

            video.FilePath = destinationPath;
            video.UpdatedAt = DateTime.UtcNow;
            await _unitOfWork.Videos.UpdateAsync(video).ConfigureAwait(false);
            await _unitOfWork.SaveChangesAsync().ConfigureAwait(false);

            return destinationPath;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error organizing video file {FilePath}", sourceFilePath);
            throw;
        }
    }

    public string GenerateFilePath(Video video, string pattern)
    {
        ArgumentNullException.ThrowIfNull(video);
        ArgumentException.ThrowIfNullOrWhiteSpace(pattern);

        var replaced = _variablePattern.Replace(pattern, match =>
        {
            var variable = match.Groups[1].Value;
            return GetVariableValue(video, variable);
        });

        replaced = Regex.Replace(replaced, @"[/\\]+", Path.DirectorySeparatorChar.ToString());
        replaced = replaced.Trim();

        return SanitizeRelativePath(replaced);
    }

    public bool ValidatePattern(string pattern)
    {
        if (string.IsNullOrWhiteSpace(pattern))
        {
            return false;
        }

        if (!_variablePattern.IsMatch(pattern))
        {
            return false;
        }

        var withoutVariables = _variablePattern.Replace(pattern, string.Empty);
        var invalidPathChars = Path.GetInvalidPathChars()
            .Where(c => c != Path.DirectorySeparatorChar && c != Path.AltDirectorySeparatorChar);

        return !invalidPathChars.Any(c => withoutVariables.Contains(c, StringComparison.Ordinal));
    }

    public Dictionary<string, string> GetAvailablePatternVariables()
    {
        return new Dictionary<string, string>(FileOrganizationPatternVariables.Variables);
    }

    public string PreviewOrganizedPath(Video video, string pattern)
    {
        var sanitizedRelative = GenerateFilePath(video, pattern);
        var libraryRoot = _libraryPathManager.GetVideoRootAsync().GetAwaiter().GetResult();
        return Path.Combine(libraryRoot, sanitizedRelative);
    }

    public async Task<ReorganizeResult> ReorganizeLibraryAsync(
        string newPattern,
        IProgress<ReorganizeProgress>? progress = null,
        CancellationToken cancellationToken = default)
    {
        var result = new ReorganizeResult();
        var startTime = DateTime.UtcNow;

        if (!ValidatePattern(newPattern))
        {
            result.Errors.Add("Invalid naming pattern");
            return result;
        }

        try
        {
            var videos = await _unitOfWork.Videos.GetAllAsync().ConfigureAwait(false);
            var libraryRoot = await _libraryPathManager.GetVideoRootAsync(cancellationToken).ConfigureAwait(false);

            result.TotalVideos = videos.Count();
            var currentIndex = 0;

            foreach (var video in videos)
            {
                cancellationToken.ThrowIfCancellationRequested();
                currentIndex++;

                progress?.Report(new ReorganizeProgress
                {
                    Current = currentIndex,
                    Total = result.TotalVideos,
                    CurrentFile = video.Title ?? "Unknown"
                });

                try
                {
                    var newRelativePath = GenerateFilePath(video, newPattern);
                    var newFullPath = Path.Combine(libraryRoot, newRelativePath);

                    if (string.Equals(video.FilePath, newFullPath, StringComparison.OrdinalIgnoreCase))
                    {
                        result.SuccessfulMoves++;
                        continue;
                    }

                    if (await MoveVideoFileAsync(video, newFullPath, cancellationToken).ConfigureAwait(false))
                    {
                        result.SuccessfulMoves++;
                    }
                    else
                    {
                        result.FailedMoves++;
                        result.Errors.Add($"Failed to move: {video.Title}");
                    }
                }
                catch (Exception ex)
                {
                    result.FailedMoves++;
                    result.Errors.Add($"Error with {video.Title}: {ex.Message}");
                    _logger.LogError(ex, "Error reorganizing video {VideoId}", video.Id);
                }
            }

            await PersistPatternAsync(newPattern).ConfigureAwait(false);

            result.Duration = DateTime.UtcNow - startTime;
            return result;
        }
        catch (OperationCanceledException)
        {
            result.Errors.Add("Operation cancelled");
            result.Duration = DateTime.UtcNow - startTime;
            return result;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error reorganizing library");
            result.Errors.Add($"Fatal error: {ex.Message}");
            result.Duration = DateTime.UtcNow - startTime;
            return result;
        }
    }

    public async Task<bool> MoveVideoFileAsync(
        Video video,
        string newPath,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(video);
        ArgumentException.ThrowIfNullOrWhiteSpace(newPath);

        try
        {
            if (string.IsNullOrWhiteSpace(video.FilePath) || !File.Exists(video.FilePath))
            {
                _logger.LogWarning(
                    "Source file not found for video {VideoId}: {FilePath}",
                    video.Id,
                    video.FilePath);
                return false;
            }

            var originalPath = video.FilePath!;
            var sanitizedFullPath = SanitizeFullPath(newPath);
            _libraryPathManager.EnsureDirectoryExists(Path.GetDirectoryName(sanitizedFullPath)!);

            var destination = ResolveDuplicate(sanitizedFullPath);

            await Task.Run(() => File.Move(originalPath, destination, true), cancellationToken).ConfigureAwait(false);

            video.FilePath = destination;
            video.UpdatedAt = DateTime.UtcNow;
            await _unitOfWork.Videos.UpdateAsync(video).ConfigureAwait(false);
            await _unitOfWork.SaveChangesAsync().ConfigureAwait(false);

            _logger.LogInformation(
                "Moved video file from {OldPath} to {NewPath}",
                originalPath,
                destination);

            return true;
        }
        catch (Exception ex)
        {
            _logger.LogError(
                ex,
                "Error moving video file from {OldPath} to {NewPath}",
                video.FilePath,
                newPath);
            return false;
        }
    }

    public void EnsureDirectoryExists(string filePath)
    {
        var directory = Path.GetDirectoryName(filePath);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            _libraryPathManager.EnsureDirectoryExists(directory);
        }
    }

    private async Task PersistPatternAsync(string newPattern)
    {
        var patternConfig = await _unitOfWork.Configurations
            .FirstOrDefaultAsync(c => c.Key == "NamingPattern" && c.Category == "Organization")
            .ConfigureAwait(false);

        if (patternConfig != null)
        {
            patternConfig.Value = newPattern;
            patternConfig.UpdatedAt = DateTime.UtcNow;
            await _unitOfWork.Configurations.UpdateAsync(patternConfig).ConfigureAwait(false);
        }
        else
        {
            await _unitOfWork.Configurations.AddAsync(new Configuration
            {
                Key = "NamingPattern",
                Value = newPattern,
                Category = "Organization",
                Description = "File naming pattern for organized videos"
            }).ConfigureAwait(false);
        }

        await _unitOfWork.SaveChangesAsync().ConfigureAwait(false);
    }

    private async Task<string> ResolveNamingPatternAsync(CancellationToken cancellationToken)
    {
        var patternConfig = await _unitOfWork.Configurations
            .FirstOrDefaultAsync(c => c.Key == "NamingPattern" && c.Category == "Organization")
            .ConfigureAwait(false);

        return patternConfig?.Value ?? "{artist_safe}/{year} - {title_safe}.{format}";
    }

    private string SanitizeRelativePath(string relativePath)
    {
        if (string.IsNullOrWhiteSpace(relativePath))
        {
            return _libraryPathManager.SanitizeFileName("untitled");
        }

        var segments = relativePath.Split(
            new[] { Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar },
            StringSplitOptions.RemoveEmptyEntries);

        if (segments.Length == 0)
        {
            return _libraryPathManager.SanitizeFileName("untitled");
        }

        var sanitizedSegments = new List<string>(segments.Length);

        for (var index = 0; index < segments.Length; index++)
        {
            var segment = segments[index];
            var isLast = index == segments.Length - 1;

            if (isLast)
            {
                var extension = Path.GetExtension(segment);
                var nameWithoutExtension = Path.GetFileNameWithoutExtension(segment);
                var sanitized = _libraryPathManager.SanitizeFileName(
                    string.IsNullOrWhiteSpace(nameWithoutExtension) ? segment : nameWithoutExtension,
                    string.IsNullOrWhiteSpace(extension) ? null : extension.TrimStart('.'));
                sanitizedSegments.Add(sanitized);
            }
            else
            {
                sanitizedSegments.Add(_libraryPathManager.SanitizeDirectoryName(segment));
            }
        }

        return Path.Combine(sanitizedSegments.ToArray());
    }

    private string SanitizeFullPath(string fullPath)
    {
        if (string.IsNullOrWhiteSpace(fullPath))
        {
            return fullPath;
        }

        var root = Path.GetPathRoot(fullPath) ?? string.Empty;
        var relative = string.IsNullOrEmpty(root)
            ? fullPath
            : fullPath[root.Length..];

        relative = relative.TrimStart(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        var sanitizedRelative = SanitizeRelativePath(relative);

        return string.IsNullOrEmpty(root)
            ? sanitizedRelative
            : Path.Combine(root, sanitizedRelative);
    }

    private string ResolveDuplicate(string targetPath)
    {
        if (!File.Exists(targetPath))
        {
            return targetPath;
        }

        var directory = Path.GetDirectoryName(targetPath)!;
        var baseName = Path.GetFileNameWithoutExtension(targetPath);
        var extension = Path.GetExtension(targetPath);
        var counter = 1;

        string candidate;
        do
        {
            candidate = Path.Combine(directory, $"{baseName}_{counter}{extension}");
            counter++;
        } while (File.Exists(candidate));

        return candidate;
    }

    private string GetVariableValue(Video video, string variable)
    {
        return variable.ToLowerInvariant() switch
        {
            "artist" => video.Artist ?? "Unknown Artist",
            "artist_safe" => _libraryPathManager.SanitizeDirectoryName(video.Artist ?? "Unknown Artist"),
            "artist_sort" => video.Artist ?? "Unknown Artist",

            "title" => video.Title ?? "Unknown Title",
            "title_safe" => _libraryPathManager.SanitizeFileName(video.Title ?? "Unknown Title"),

            "year" => video.Year?.ToString("0000", CultureInfo.InvariantCulture) ?? "0000",
            "year2" => (video.Year % 100)?.ToString("00", CultureInfo.InvariantCulture) ?? "00",
            "month" => "00",
            "month_name" => "Unknown",
            "day" => "00",
            "date" => video.Year != null ? $"{video.Year:0000}-01-01" : "0000-00-00",

            "genre" => video.Genres?.FirstOrDefault()?.Name ?? "Unknown",
            "genres" => string.Join(", ", video.Genres?.Select(g => g.Name) ?? Enumerable.Empty<string>()),

            "label" => video.Publisher ?? "Unknown Label",
            "label_safe" => _libraryPathManager.SanitizeDirectoryName(video.Publisher ?? "Unknown Label"),

            "resolution" => GetResolutionString(ParseHeight(video.Resolution)),
            "width" => ParseWidth(video.Resolution)?.ToString(CultureInfo.InvariantCulture) ?? "0",
            "height" => ParseHeight(video.Resolution)?.ToString(CultureInfo.InvariantCulture) ?? "0",
            "codec" => video.VideoCodec ?? "unknown",
            "format" => ResolveFormat(video),
            "bitrate" => video.Bitrate?.ToString(CultureInfo.InvariantCulture) ?? "0",
            "fps" => video.FrameRate?.ToString("F2", CultureInfo.InvariantCulture) ?? "0",

            "imvdb_id" => video.ImvdbId ?? string.Empty,
            "director" => video.Director ?? "Unknown",
            "production" => video.ProductionCompany ?? "Unknown",
            "featured_artists" => string.Join(", ", video.FeaturedArtists?.Select(fa => fa.Name) ?? Enumerable.Empty<string>()),

            "mb_artist_id" => string.Empty,
            "mb_recording_id" => video.MusicBrainzRecordingId ?? string.Empty,
            "album" => video.Album ?? "Unknown Album",
            "track_number" => string.Empty,

            "tags" => string.Join(", ", video.Tags?.Select(t => t.Name) ?? Enumerable.Empty<string>()),
            "collection" => string.Empty,
            "custom1" => string.Empty,
            "custom2" => string.Empty,
            "custom3" => string.Empty,

            _ => $"{{{variable}}}"
        };
    }

    private static string ResolveFormat(Video video)
    {
        if (!string.IsNullOrWhiteSpace(video.Format))
        {
            return video.Format;
        }

        var extension = Path.GetExtension(video.FilePath);
        return string.IsNullOrWhiteSpace(extension)
            ? "mp4"
            : extension.TrimStart('.');
    }

    private static string GetResolutionString(int? height)
    {
        return height switch
        {
            >= 2160 => "4K",
            >= 1440 => "1440p",
            >= 1080 => "1080p",
            >= 720 => "720p",
            >= 480 => "480p",
            >= 360 => "360p",
            >= 240 => "240p",
            _ => "SD"
        };
    }

    private static int? ParseHeight(string? resolution)
    {
        if (string.IsNullOrEmpty(resolution))
        {
            return null;
        }

        var parts = resolution.Split('x');
        return parts.Length == 2 && int.TryParse(parts[1], out var height) ? height : null;
    }

    private static int? ParseWidth(string? resolution)
    {
        if (string.IsNullOrEmpty(resolution))
        {
            return null;
        }

        var parts = resolution.Split('x');
        return parts.Length == 2 && int.TryParse(parts[0], out var width) ? width : null;
    }
}
