using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Xml.Linq;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;

namespace Fuzzbin.Services;

public class MetadataExportService : IMetadataExportService
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILibraryPathManager _pathManager;
    private readonly INfoExportService _nfoExportService;
    private readonly ILogger<MetadataExportService> _logger;
    private readonly string _webRootPath;

    public MetadataExportService(
        IUnitOfWork unitOfWork,
        ILibraryPathManager pathManager,
        INfoExportService nfoExportService,
        IConfiguration configuration,
        ILogger<MetadataExportService> logger)
    {
        _unitOfWork = unitOfWork;
        _pathManager = pathManager;
        _nfoExportService = nfoExportService;
        _logger = logger;
        _webRootPath = configuration["WebRootPath"] ?? Path.Combine(AppContext.BaseDirectory, "wwwroot");
    }

    public async Task<MetadataExportResult> ExportVideoAsync(
        Video video,
        MetadataExportOptions options,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(video);
        options ??= MetadataExportOptions.Default;

        var exportRoot = options.OutputDirectory ?? await _pathManager.GetMetadataRootAsync(cancellationToken).ConfigureAwait(false);
        var artistSegment = _pathManager.SanitizeDirectoryName(video.Artist ?? "Unknown Artist");
        var titleSegment = _pathManager.SanitizeDirectoryName(video.Title ?? "Untitled");
        var targetDirectory = Path.Combine(exportRoot, artistSegment, titleSegment);
        _pathManager.EnsureDirectoryExists(targetDirectory);

        var result = new MetadataExportResult(success: true, targetDirectory);

        try
        {
            var nfoFileName = _pathManager.SanitizeFileName(video.Title ?? video.Id.ToString(), "nfo");
            var nfoPath = Path.Combine(targetDirectory, nfoFileName);

            if (!File.Exists(nfoPath) || options.OverwriteExisting)
            {
                var exported = await _nfoExportService.ExportNfoAsync(video, nfoPath, cancellationToken).ConfigureAwait(false);
                if (exported)
                {
                    result.Files.Add(nfoPath);
                    await UpdateVideoNfoReferenceAsync(video, exportRoot, nfoPath).ConfigureAwait(false);
                }
                else
                {
                    result.Success = false;
                    result.Warnings.Add($"Failed to export NFO for {video.Title ?? video.Id.ToString()}");
                }
            }
            else
            {
                result.Warnings.Add($"NFO already exists at {nfoPath}");
            }

            if (options.IncludeArtwork)
            {
                var artworkPath = await CopyArtworkAsync(video, targetDirectory, options.OverwriteExisting, cancellationToken).ConfigureAwait(false);
                if (artworkPath is not null)
                {
                    result.Files.Add(artworkPath);
                }
                else
                {
                    result.Warnings.Add($"No artwork located for {video.Title ?? video.Id.ToString()}");
                }
            }

            if (options.IncludeVideoFile && !string.IsNullOrWhiteSpace(video.FilePath) && File.Exists(video.FilePath))
            {
                var destinationVideoPath = Path.Combine(targetDirectory, Path.GetFileName(video.FilePath));
                if (!File.Exists(destinationVideoPath) || options.OverwriteExisting)
                {
                    await Task.Run(() => File.Copy(video.FilePath!, destinationVideoPath, options.OverwriteExisting), cancellationToken)
                        .ConfigureAwait(false);
                    result.Files.Add(destinationVideoPath);
                }
                else
                {
                    result.Warnings.Add($"Video already exists at {destinationVideoPath}");
                }
            }

            if (options.IncludeArtistMetadata && video.FeaturedArtists?.Any() == true)
            {
                foreach (var featured in video.FeaturedArtists)
                {
                    var artistResult = await ExportArtistAsync(featured, new[] { video }, options, cancellationToken).ConfigureAwait(false);
                    result.Files.AddRange(artistResult.Files);
                    result.Warnings.AddRange(artistResult.Warnings);
                    if (!artistResult.Success)
                    {
                        result.Success = false;
                    }
                }
            }

            if (options.CreateArchive)
            {
                var archivePath = await CreateArchiveAsync(targetDirectory, options, cancellationToken).ConfigureAwait(false);
                if (!string.IsNullOrWhiteSpace(archivePath))
                {
                    result.ArchivePath = archivePath;
                }
            }

            await _unitOfWork.SaveChangesAsync().ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            result.Success = false;
            result.Warnings.Add(ex.Message);
            _logger.LogError(ex, "Failed to export metadata for video {VideoId}", video.Id);
        }

        return result;
    }

    public async Task<IReadOnlyList<MetadataExportResult>> ExportLibraryAsync(
        IEnumerable<Video> videos,
        MetadataExportOptions options,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(videos);
        var results = new List<MetadataExportResult>();

        foreach (var video in videos)
        {
            cancellationToken.ThrowIfCancellationRequested();
            results.Add(await ExportVideoAsync(video, options, cancellationToken).ConfigureAwait(false));
        }

        return results;
    }

    public async Task<MetadataExportResult> ExportArtistAsync(
        FeaturedArtist artist,
        IEnumerable<Video> videos,
        MetadataExportOptions options,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(artist);
        options ??= MetadataExportOptions.Default;

        var exportRoot = options.OutputDirectory ?? await _pathManager.GetMetadataRootAsync(cancellationToken).ConfigureAwait(false);
        var artistSegment = _pathManager.SanitizeDirectoryName(artist.Name ?? "Unknown Artist");
        var targetDirectory = Path.Combine(exportRoot, "artists", artistSegment);
        _pathManager.EnsureDirectoryExists(targetDirectory);

        var result = new MetadataExportResult(true, targetDirectory);
        var videoList = videos?.ToList() ?? new List<Video>();

        try
        {
            var artistNfoPath = Path.Combine(targetDirectory, _pathManager.SanitizeFileName("artist", "nfo"));

            if (!File.Exists(artistNfoPath) || options.OverwriteExisting)
            {
                var exported = await _nfoExportService.ExportArtistNfoAsync(artist, videoList, artistNfoPath, cancellationToken)
                    .ConfigureAwait(false);
                if (exported)
                {
                    result.Files.Add(artistNfoPath);
                }
                else
                {
                    result.Success = false;
                    result.Warnings.Add($"Failed to export artist NFO for {artist.Name}");
                }
            }

            if (options.IncludeArtwork)
            {
                var artworkCopied = await CopyArtistArtworkAsync(artist, targetDirectory, options.OverwriteExisting, cancellationToken)
                    .ConfigureAwait(false);
                if (artworkCopied is not null)
                {
                    result.Files.Add(artworkCopied);
                }
                else
                {
                    result.Warnings.Add($"No artwork located for artist {artist.Name}");
                }
            }

            if (options.CreateArchive)
            {
                var archivePath = await CreateArchiveAsync(targetDirectory, options, cancellationToken).ConfigureAwait(false);
                if (!string.IsNullOrWhiteSpace(archivePath))
                {
                    result.ArchivePath = archivePath;
                }
            }
        }
        catch (Exception ex)
        {
            result.Success = false;
            result.Warnings.Add(ex.Message);
            _logger.LogError(ex, "Failed to export artist metadata for {ArtistId}", artist.Id);
        }

        return result;
    }

    public async Task<MetadataImportResult> ImportAsync(
        string packagePath,
        CancellationToken cancellationToken = default)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(packagePath);

        var result = new MetadataImportResult();

        if (File.Exists(packagePath) && Path.GetExtension(packagePath).Equals(".zip", StringComparison.OrdinalIgnoreCase))
        {
            var tempDirectory = Path.Combine(Path.GetTempPath(), $"fz-import-{Guid.NewGuid():N}");
            Directory.CreateDirectory(tempDirectory);

            try
            {
                ZipFile.ExtractToDirectory(packagePath, tempDirectory, overwriteFiles: true);
                return await ImportFromDirectoryAsync(tempDirectory, cleanup: true, cancellationToken).ConfigureAwait(false);
            }
            catch (Exception ex)
            {
                result.Errors.Add($"Failed to extract package: {ex.Message}");
                _logger.LogError(ex, "Failed to extract metadata package {Package}", packagePath);
                TryDeleteDirectory(tempDirectory);
                return result;
            }
        }

        if (Directory.Exists(packagePath))
        {
            return await ImportFromDirectoryAsync(packagePath, cleanup: false, cancellationToken).ConfigureAwait(false);
        }

        result.Errors.Add($"Package path not found: {packagePath}");
        return result;
    }

    private async Task UpdateVideoNfoReferenceAsync(Video video, string exportRoot, string nfoPath)
    {
        try
        {
            var relative = Path.GetRelativePath(exportRoot, nfoPath);
            video.NfoPath = _pathManager.NormalizePath(relative);
        }
        catch
        {
            video.NfoPath = _pathManager.NormalizePath(nfoPath);
        }

        await _unitOfWork.Videos.UpdateAsync(video).ConfigureAwait(false);
    }

    private async Task<string?> CopyArtworkAsync(
        Video video,
        string targetDirectory,
        bool overwrite,
        CancellationToken cancellationToken)
    {
        var sourcePath = ResolveVideoArtworkSource(video);
        if (sourcePath is null || !File.Exists(sourcePath))
        {
            return null;
        }

        var extension = Path.GetExtension(sourcePath);
        var artworkFileName = _pathManager.SanitizeFileName(video.Title ?? video.Id.ToString(), string.IsNullOrWhiteSpace(extension) ? null : extension.TrimStart('.'));
        var destination = Path.Combine(targetDirectory, artworkFileName);

        if (File.Exists(destination) && !overwrite)
        {
            return destination;
        }

        await Task.Run(() => File.Copy(sourcePath, destination, overwrite), cancellationToken).ConfigureAwait(false);
        return destination;
    }

    private async Task<string?> CopyArtistArtworkAsync(
        FeaturedArtist artist,
        string targetDirectory,
        bool overwrite,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(artist.ImagePath))
        {
            return null;
        }

        var sourcePath = ResolveArtworkPath(artist.ImagePath!);
        if (sourcePath is null || !File.Exists(sourcePath))
        {
            return null;
        }

        var extension = Path.GetExtension(sourcePath);
        var fileName = _pathManager.SanitizeFileName(artist.Name ?? artist.Id.ToString(), string.IsNullOrWhiteSpace(extension) ? null : extension.TrimStart('.'));
        var destination = Path.Combine(targetDirectory, fileName);

        if (File.Exists(destination) && !overwrite)
        {
            return destination;
        }

        await Task.Run(() => File.Copy(sourcePath, destination, overwrite), cancellationToken).ConfigureAwait(false);
        return destination;
    }

    private string? ResolveVideoArtworkSource(Video video)
    {
        if (!string.IsNullOrWhiteSpace(video.ThumbnailPath))
        {
            var candidates = new[]
            {
                video.ThumbnailPath,
                Path.Combine(_webRootPath, video.ThumbnailPath.TrimStart(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)),
                Path.GetFullPath(video.ThumbnailPath)
            };

            foreach (var candidate in candidates)
            {
                if (!string.IsNullOrWhiteSpace(candidate) && File.Exists(candidate))
                {
                    return candidate;
                }
            }
        }

        if (!string.IsNullOrWhiteSpace(video.FilePath))
        {
            var jpgCandidate = Path.ChangeExtension(video.FilePath, ".jpg");
            if (File.Exists(jpgCandidate))
            {
                return jpgCandidate;
            }

            var pngCandidate = Path.ChangeExtension(video.FilePath, ".png");
            if (File.Exists(pngCandidate))
            {
                return pngCandidate;
            }
        }

        var defaultThumbnail = Path.Combine(_webRootPath, "thumbnails", $"{video.Id}.jpg");
        return File.Exists(defaultThumbnail) ? defaultThumbnail : null;
    }

    private string? ResolveArtworkPath(string path)
    {
        if (Path.IsPathRooted(path))
        {
            return File.Exists(path) ? path : null;
        }

        var relativeCandidate = Path.GetFullPath(path, AppContext.BaseDirectory);
        if (File.Exists(relativeCandidate))
        {
            return relativeCandidate;
        }

        var webRootCandidate = Path.Combine(_webRootPath, path.TrimStart(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar));
        return File.Exists(webRootCandidate) ? webRootCandidate : null;
    }

    private async Task<string?> CreateArchiveAsync(
        string targetDirectory,
        MetadataExportOptions options,
        CancellationToken cancellationToken)
    {
        if (!Directory.Exists(targetDirectory))
        {
            return null;
        }

        var parent = Path.GetDirectoryName(targetDirectory) ?? targetDirectory;
        var archiveName = _pathManager.SanitizeFileName(
            $"{Path.GetFileName(parent)}-{Path.GetFileName(targetDirectory)}",
            "zip");
        var archivePath = Path.Combine(parent, archiveName);

        if (File.Exists(archivePath))
        {
            if (!options.OverwriteExisting)
            {
                return archivePath;
            }

            File.Delete(archivePath);
        }

        await Task.Run(() =>
        {
            using var archive = ZipFile.Open(archivePath, ZipArchiveMode.Create);
            foreach (var file in Directory.EnumerateFiles(targetDirectory, "*", SearchOption.TopDirectoryOnly))
            {
                cancellationToken.ThrowIfCancellationRequested();
                archive.CreateEntryFromFile(file, Path.GetFileName(file), CompressionLevel.Optimal);
            }
        }, cancellationToken).ConfigureAwait(false);

        return archivePath;
    }

    private async Task<MetadataImportResult> ImportFromDirectoryAsync(
        string directory,
        bool cleanup,
        CancellationToken cancellationToken)
    {
        var result = new MetadataImportResult();
        var libraryRoot = await _pathManager.GetLibraryRootAsync(cancellationToken).ConfigureAwait(false);
        var libraryRootFull = Path.GetFullPath(libraryRoot);

        try
        {
            foreach (var nfoPath in Directory.EnumerateFiles(directory, "*.nfo", SearchOption.AllDirectories))
            {
                cancellationToken.ThrowIfCancellationRequested();

                try
                {
                    var document = XDocument.Load(nfoPath);
                    if (!string.Equals(document.Root?.Name.LocalName, "musicvideo", StringComparison.OrdinalIgnoreCase))
                    {
                        result.Warnings.Add($"Skipping non-musicvideo NFO: {nfoPath}");
                        continue;
                    }

                    var metadata = ParseVideoMetadata(document, nfoPath);
                    var matchingVideo = await FindMatchingVideoAsync(metadata).ConfigureAwait(false);

                    if (matchingVideo is null)
                    {
                        result.Warnings.Add($"No matching video found for metadata at {nfoPath}");
                        result.VideosSkipped++;
                        continue;
                    }

                    ApplyMetadata(matchingVideo, metadata);

                    var nfoFullPath = Path.GetFullPath(nfoPath);
                    if (nfoFullPath.StartsWith(libraryRootFull, StringComparison.OrdinalIgnoreCase))
                    {
                        var relativeNfo = Path.GetRelativePath(libraryRootFull, nfoFullPath);
                        matchingVideo.NfoPath = _pathManager.NormalizePath(relativeNfo);
                    }
                    else
                    {
                        matchingVideo.NfoPath = _pathManager.NormalizePath(nfoFullPath);
                    }
                    await _unitOfWork.Videos.UpdateAsync(matchingVideo).ConfigureAwait(false);
                    result.VideosUpdated++;
                }
                catch (Exception ex)
                {
                    result.Errors.Add($"Failed to import {nfoPath}: {ex.Message}");
                    _logger.LogError(ex, "Failed to import metadata from {NfoPath}", nfoPath);
                }
            }

            if (result.VideosUpdated > 0)
            {
                await _unitOfWork.SaveChangesAsync().ConfigureAwait(false);
            }

            return result;
        }
        finally
        {
            if (cleanup)
            {
                TryDeleteDirectory(directory);
            }
        }
    }

    private static void ApplyMetadata(Video video, ParsedVideoMetadata metadata)
    {
        if (!string.IsNullOrWhiteSpace(metadata.Title))
        {
            video.Title = metadata.Title;
        }

        if (!string.IsNullOrWhiteSpace(metadata.Artist))
        {
            video.Artist = metadata.Artist;
        }

        if (!string.IsNullOrWhiteSpace(metadata.Album))
        {
            video.Album = metadata.Album;
        }

        if (metadata.Year.HasValue)
        {
            video.Year = metadata.Year;
        }

        if (metadata.DurationSeconds.HasValue)
        {
            video.Duration = metadata.DurationSeconds;
        }

        if (!string.IsNullOrWhiteSpace(metadata.Director))
        {
            video.Director = metadata.Director;
        }

        if (!string.IsNullOrWhiteSpace(metadata.Studio))
        {
            video.ProductionCompany = metadata.Studio;
        }

        if (!string.IsNullOrWhiteSpace(metadata.Publisher))
        {
            video.Publisher = metadata.Publisher;
        }

        if (!string.IsNullOrWhiteSpace(metadata.Description))
        {
            video.Description = metadata.Description;
        }

        if (!string.IsNullOrWhiteSpace(metadata.ImvdbId))
        {
            video.ImvdbId = metadata.ImvdbId;
        }

        if (!string.IsNullOrWhiteSpace(metadata.YouTubeId))
        {
            video.YouTubeId = metadata.YouTubeId;
        }

        if (!string.IsNullOrWhiteSpace(metadata.MusicBrainzId))
        {
            video.MusicBrainzRecordingId = metadata.MusicBrainzId;
        }
    }

    private async Task<Video?> FindMatchingVideoAsync(ParsedVideoMetadata metadata)
    {
        if (!string.IsNullOrWhiteSpace(metadata.ImvdbId))
        {
            var byImvdb = await _unitOfWork.Videos.FirstOrDefaultAsync(v => v.ImvdbId == metadata.ImvdbId).ConfigureAwait(false);
            if (byImvdb != null)
            {
                return byImvdb;
            }
        }

        if (!string.IsNullOrWhiteSpace(metadata.YouTubeId))
        {
            var byYoutube = await _unitOfWork.Videos.FirstOrDefaultAsync(v => v.YouTubeId == metadata.YouTubeId).ConfigureAwait(false);
            if (byYoutube != null)
            {
                return byYoutube;
            }
        }

        if (!string.IsNullOrWhiteSpace(metadata.MusicBrainzId))
        {
            var byMb = await _unitOfWork.Videos.FirstOrDefaultAsync(v => v.MusicBrainzRecordingId == metadata.MusicBrainzId)
                .ConfigureAwait(false);
            if (byMb != null)
            {
                return byMb;
            }
        }

        if (!string.IsNullOrWhiteSpace(metadata.Title) && !string.IsNullOrWhiteSpace(metadata.Artist))
        {
            var matches = await _unitOfWork.Videos.GetAsync(v =>
                v.Title == metadata.Title && v.Artist == metadata.Artist).ConfigureAwait(false);
            return matches.FirstOrDefault();
        }

        return null;
    }

    private static ParsedVideoMetadata ParseVideoMetadata(XDocument document, string nfoPath)
    {
        var root = document.Root ?? throw new InvalidOperationException($"Invalid NFO document: {nfoPath}");

        string? ReadElement(string name) => root.Element(name)?.Value?.Trim();

        var uniqueIds = root.Elements("uniqueid")
            .Where(e => !string.IsNullOrWhiteSpace(e.Value))
            .Select(e => new
            {
                Value = e.Value.Trim(),
                Type = e.Attribute("type")?.Value?.Trim()?.ToLowerInvariant()
            })
            .Where(e => !string.IsNullOrWhiteSpace(e.Type))
            .ToDictionary(e => e.Type!, e => e.Value, StringComparer.OrdinalIgnoreCase);

        int? ParseInt(string? value)
        {
            if (int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var parsed))
            {
                return parsed;
            }
            return null;
        }

        int? ParseDuration(string? value)
        {
            if (string.IsNullOrWhiteSpace(value))
            {
                return null;
            }

            if (int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var seconds))
            {
                return seconds;
            }

            if (double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out var minutes))
            {
                return (int)Math.Round(minutes * 60);
            }

            return null;
        }

        var duration = ParseDuration(ReadElement("durationinseconds")) ?? ParseDuration(ReadElement("runtime"));

        return new ParsedVideoMetadata(
            Title: ReadElement("title"),
            Artist: ReadElement("artist"),
            Album: ReadElement("album"),
            Description: ReadElement("plot") ?? ReadElement("outline"),
            Director: ReadElement("director"),
            Studio: ReadElement("studio"),
            Publisher: ReadElement("publisher"),
            Year: ParseInt(ReadElement("year")),
            DurationSeconds: duration,
            ImvdbId: uniqueIds.TryGetValue("imvdb", out var imvdb) ? imvdb : null,
            MusicBrainzId: uniqueIds.TryGetValue("musicbrainz", out var mbid) ? mbid : null,
            YouTubeId: uniqueIds.TryGetValue("youtube", out var youtube) ? youtube : null);
    }

    private static void TryDeleteDirectory(string directory)
    {
        try
        {
            if (Directory.Exists(directory))
            {
                Directory.Delete(directory, recursive: true);
            }
        }
        catch
        {
            // best effort cleanup
        }
    }

    private sealed record ParsedVideoMetadata(
        string? Title,
        string? Artist,
        string? Album,
        string? Description,
        string? Director,
        string? Studio,
        string? Publisher,
        int? Year,
        int? DurationSeconds,
        string? ImvdbId,
        string? MusicBrainzId,
        string? YouTubeId);
}
