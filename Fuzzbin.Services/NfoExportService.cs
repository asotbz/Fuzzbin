using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Xml;
using System.Xml.Linq;
using Fuzzbin.Core.Entities;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;
using Fuzzbin.Services.Templates;

namespace Fuzzbin.Services;

public class NfoExportService : INfoExportService
{
    private readonly IMetadataSettingsProvider _metadataSettingsProvider;

    public NfoExportService(IMetadataSettingsProvider metadataSettingsProvider)
    {
        _metadataSettingsProvider = metadataSettingsProvider;
    }

    public async Task<bool> ExportNfoAsync(
        Video video,
        string outputPath,
        CancellationToken cancellationToken = default)
    {
        try
        {
            ArgumentNullException.ThrowIfNull(video);
            ArgumentException.ThrowIfNullOrWhiteSpace(outputPath);

            var content = GenerateNfoContent(video);
            EnsureDirectoryExists(outputPath);
            await File.WriteAllTextAsync(outputPath, content, Encoding.UTF8, cancellationToken)
                .ConfigureAwait(false);
            return true;
        }
        catch
        {
            return false;
        }
    }

    public async Task<int> BulkExportNfoAsync(
        IEnumerable<Video> videos,
        string outputDirectory,
        bool useVideoPath = false,
        CancellationToken cancellationToken = default)
    {
        ArgumentNullException.ThrowIfNull(videos);
        ArgumentException.ThrowIfNullOrWhiteSpace(outputDirectory);

        if (!useVideoPath)
        {
            Directory.CreateDirectory(outputDirectory);
        }

        var successCount = 0;

        foreach (var video in videos)
        {
            cancellationToken.ThrowIfCancellationRequested();

            var targetPath = ResolveVideoOutputPath(video, outputDirectory, useVideoPath);
            if (await ExportNfoAsync(video, targetPath, cancellationToken).ConfigureAwait(false))
            {
                successCount++;
            }
        }

        return successCount;
    }

    public string GenerateNfoContent(Video video)
    {
        var settings = _metadataSettingsProvider.GetSettings();
        var overrideGenres = settings.GeneralizeGenres
            ? GetGeneralizedGenres(video, settings)
            : null;
        var additionalTags = settings.GeneralizeGenres && settings.WriteExternalGenreAsTag
            ? GetSpecificGenresForTags(video, settings)
            : null;
        var includeCollectionsAsTags = settings.WriteCollectionsAsNfoTags;

        var document = NfoTemplateBuilder.BuildVideoDocument(
            video,
            overrideGenres,
            additionalTags,
            settings.ArtistMode,
            includeCollectionsAsTags);
        return Serialize(document);
    }

    public async Task<bool> ExportArtistNfoAsync(
        FeaturedArtist artist,
        IEnumerable<Video> artistVideos,
        string outputPath,
        CancellationToken cancellationToken = default)
    {
        try
        {
            ArgumentNullException.ThrowIfNull(artist);
            ArgumentNullException.ThrowIfNull(artistVideos);
            ArgumentException.ThrowIfNullOrWhiteSpace(outputPath);

            var content = GenerateArtistNfoContent(artist, artistVideos);
            EnsureDirectoryExists(outputPath);
            await File.WriteAllTextAsync(outputPath, content, Encoding.UTF8, cancellationToken)
                .ConfigureAwait(false);
            return true;
        }
        catch
        {
            return false;
        }
    }

    public string GenerateArtistNfoContent(FeaturedArtist artist, IEnumerable<Video> artistVideos)
    {
        var videoList = artistVideos?.ToList() ?? new List<Video>();
        var settings = _metadataSettingsProvider.GetSettings();
        Func<Video, IEnumerable<string>?>? genreSelector = null;

        if (settings.GeneralizeGenres)
        {
            genreSelector = video => GetGeneralizedGenres(video, settings);
        }

        var document = NfoTemplateBuilder.BuildArtistDocument(artist, videoList, genreSelector);
        return Serialize(document);
    }

    private static string ResolveVideoOutputPath(Video video, string outputDirectory, bool useVideoPath)
    {
        if (useVideoPath && !string.IsNullOrWhiteSpace(video.FilePath))
        {
            return Path.ChangeExtension(video.FilePath, ".nfo") ?? Path.Combine(outputDirectory, BuildVideoFileName(video));
        }

        return Path.Combine(outputDirectory, BuildVideoFileName(video));
    }

    private static string BuildVideoFileName(Video video)
    {
        var artist = string.IsNullOrWhiteSpace(video.Artist) ? "Unknown Artist" : video.Artist;
        var title = string.IsNullOrWhiteSpace(video.Title) ? "Untitled" : video.Title;
        var fileName = $"{artist} - {title}.nfo";
        return SanitizeFileName(fileName);
    }

    private static string Serialize(XDocument document)
    {
        var settings = new XmlWriterSettings
        {
            Indent = true,
            IndentChars = "    ",
            Encoding = Encoding.UTF8,
            NewLineHandling = NewLineHandling.Entitize,
            OmitXmlDeclaration = false
        };

        var builder = new StringBuilder();
        using var writer = XmlWriter.Create(builder, settings);
        document.WriteTo(writer);
        writer.Flush();
        return builder.ToString();
    }

    private static void EnsureDirectoryExists(string filePath)
    {
        var directory = Path.GetDirectoryName(filePath);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }
    }

    private static string SanitizeFileName(string fileName)
    {
        var invalidChars = Path.GetInvalidFileNameChars();
        var builder = new StringBuilder(fileName.Length);

        foreach (var c in fileName)
        {
            builder.Append(invalidChars.Contains(c) ? '_' : c);
        }

        return builder.ToString();
    }

    private static IReadOnlyList<string>? GetGeneralizedGenres(Video video, MetadataSettings settings)
    {
        if (video.Genres?.Any() != true)
        {
            return null;
        }

        var result = new List<string>();
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        foreach (var genre in video.Genres)
        {
            if (string.IsNullOrWhiteSpace(genre?.Name))
            {
                continue;
            }

            var normalized = genre.Name.Trim();
            if (settings.GenreMappings.TryGetValue(normalized, out var mapped) && !string.IsNullOrWhiteSpace(mapped))
            {
                normalized = mapped.Trim();
            }

            if (seen.Add(normalized))
            {
                result.Add(normalized);
            }
        }

        return result.Count > 0 ? result : null;
    }

    private static IReadOnlyList<string>? GetSpecificGenresForTags(Video video, MetadataSettings settings)
    {
        if (video.Genres?.Any() != true)
        {
            return null;
        }

        var result = new List<string>();
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        foreach (var genre in video.Genres)
        {
            if (string.IsNullOrWhiteSpace(genre?.Name))
            {
                continue;
            }

            var original = genre.Name.Trim();
            if (!settings.GenreMappings.TryGetValue(original, out var mapped) ||
                string.IsNullOrWhiteSpace(mapped))
            {
                continue;
            }

            if (string.Equals(original, mapped, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            if (seen.Add(original))
            {
                result.Add(original);
            }
        }

        return result.Count > 0 ? result : null;
    }
}
