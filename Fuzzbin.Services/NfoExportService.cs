using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Xml;
using System.Xml.Linq;
using Fuzzbin.Core.Entities;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Templates;

namespace Fuzzbin.Services;

public class NfoExportService : INfoExportService
{
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
        var document = NfoTemplateBuilder.BuildVideoDocument(video);
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
        var document = NfoTemplateBuilder.BuildArtistDocument(artist, videoList);
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
}
