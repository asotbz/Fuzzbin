using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Xml.Linq;
using Fuzzbin.Core.Entities;
using Fuzzbin.Services.Models;

namespace Fuzzbin.Services.Templates;

internal static class NfoTemplateBuilder
{
    public static XDocument BuildVideoDocument(
        Video video,
        IEnumerable<string>? overrideGenres = null,
        IEnumerable<string>? additionalTags = null,
        NfoArtistMode artistMode = NfoArtistMode.CombinedArtistField,
        bool includeCollectionsAsTags = false)
    {
        ArgumentNullException.ThrowIfNull(video);

        var elements = new List<object>();
        var duration = video.Duration.HasValue
            ? TimeSpan.FromSeconds(Math.Max(0, video.Duration.Value))
            : (TimeSpan?)null;
        var (width, height) = ParseResolution(video.Resolution);

        var featuredNames = video.FeaturedArtists?
            .Select(f => f?.Name)
            .Where(name => !string.IsNullOrWhiteSpace(name))
            .Select(name => name!.Trim())
            .Where(name => !string.IsNullOrWhiteSpace(name))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList() ?? new List<string>();

        // Apply artist mode logic
        var (effectiveTitle, artistElements) = ApplyArtistMode(video.Title, video.Artist, featuredNames, artistMode);

        AddElement(elements, "title", effectiveTitle);
        
        // Add artist elements based on mode
        foreach (var artistName in artistElements)
        {
            AddElement(elements, "artist", artistName);
        }

        AddElement(elements, "album", video.Album);
        AddElement(elements, "year", video.Year?.ToString("0000", CultureInfo.InvariantCulture));
        AddElement(elements, "premiered", BuildPremieredDate(video));
        AddElement(elements, "releasedate", BuildPremieredDate(video));

        if (duration.HasValue)
        {
            AddElement(elements, "runtime", Math.Round(duration.Value.TotalMinutes).ToString(CultureInfo.InvariantCulture));
            AddElement(elements, "durationinseconds", ((int)Math.Round(duration.Value.TotalSeconds)).ToString(CultureInfo.InvariantCulture));
        }

        var resolvedGenres = ResolveGenresForVideo(video, overrideGenres);
        if (resolvedGenres.Count > 0)
        {
            AddElement(elements, "genre", resolvedGenres[0]);
            if (resolvedGenres.Count > 1)
            {
                AddRepeatedElements(elements, "genre", resolvedGenres.Skip(1));
            }
        }
        var resolvedTags = ResolveTagsForVideo(video, additionalTags, includeCollectionsAsTags);
        AddRepeatedElements(elements, "tag", resolvedTags);

        AddElement(elements, "studio", video.ProductionCompany);
        AddElement(elements, "director", video.Director);
        AddElement(elements, "publisher", video.Publisher);
        AddElement(elements, "plot", video.Description);
        AddElement(elements, "outline", video.Description);
        AddElement(elements, "format", video.Format);
        AddElement(elements, "videocodec", video.VideoCodec);
        AddElement(elements, "audiocodec", video.AudioCodec);
        AddElement(elements, "resolution", video.Resolution);
        AddElement(elements, "framerate", video.FrameRate?.ToString("F2", CultureInfo.InvariantCulture));
        AddElement(elements, "filesize", video.FileSize?.ToString(CultureInfo.InvariantCulture));
        AddElement(elements, "bitrate", video.Bitrate?.ToString(CultureInfo.InvariantCulture));

        if (video.Rating.HasValue)
        {
            var rating = new XElement("rating");
            AddElement(rating, "value", (video.Rating.Value * 2).ToString("F1", CultureInfo.InvariantCulture));
            AddElement(rating, "max", "10");
            elements.Add(rating);
            AddElement(elements, "userrating", video.Rating.Value.ToString(CultureInfo.InvariantCulture));
        }

        var uniqueIds = BuildUniqueIdElements(video);
        elements.AddRange(uniqueIds);

        if (!string.IsNullOrWhiteSpace(video.ThumbnailPath))
        {
            var normalized = NormalizePath(video.ThumbnailPath);
            AddElement(elements, "thumb", normalized);
            AddElement(elements, "poster", normalized);
            AddElement(elements, "fanart", normalized);
        }

        var actorElements = BuildActorElements(video);
        if (actorElements.Count > 0)
        {
            elements.AddRange(actorElements);
        }

        var videoStream = new XElement("video");
        AddElement(videoStream, "codec", video.VideoCodec);
        AddElement(videoStream, "micodec", video.VideoCodec);
        AddElement(videoStream, "duration", duration?.TotalSeconds.ToString(CultureInfo.InvariantCulture));

        if (width.HasValue)
        {
            AddElement(videoStream, "width", width.Value.ToString(CultureInfo.InvariantCulture));
        }

        if (height.HasValue)
        {
            AddElement(videoStream, "height", height.Value.ToString(CultureInfo.InvariantCulture));
        }

        var aspectRatio = BuildAspectRatio(width, height);
        AddElement(videoStream, "aspect", aspectRatio);
        AddElement(videoStream, "resolution", BuildResolutionLabel(height));
        AddElement(videoStream, "framerate", video.FrameRate?.ToString("F2", CultureInfo.InvariantCulture));

        var audioStream = new XElement("audio");
        AddElement(audioStream, "codec", video.AudioCodec);
        AddElement(audioStream, "bitrate", video.Bitrate?.ToString(CultureInfo.InvariantCulture));

        if (!string.IsNullOrWhiteSpace(video.AudioCodec))
        {
            AddElement(audioStream, "micodec", video.AudioCodec);
        }

        if (audioStream.HasElements || videoStream.HasElements)
        {
            var streamDetails = new XElement("streamdetails");
            if (videoStream.HasElements)
            {
                streamDetails.Add(videoStream);
            }

            if (audioStream.HasElements)
            {
                streamDetails.Add(audioStream);
            }

            if (streamDetails.HasElements)
            {
                elements.Add(new XElement("fileinfo", streamDetails));
            }
        }

        // Add source URLs if available
        if (video.SourceVerifications?.Any() == true)
        {
            foreach (var source in video.SourceVerifications
                .OrderByDescending(sv => sv.Status == VideoSourceVerificationStatus.Verified)
                .ThenBy(sv => sv.SourceUrl))
            {
                if (!string.IsNullOrWhiteSpace(source.SourceUrl))
                {
                    var sourceElement = new XElement("source");
                    sourceElement.SetAttributeValue("verified", (source.Status == VideoSourceVerificationStatus.Verified).ToString().ToLowerInvariant());
                    sourceElement.SetAttributeValue("status", source.Status.ToString());
                    if (source.VerifiedAt.HasValue)
                    {
                        sourceElement.SetAttributeValue("lastverified", source.VerifiedAt.Value.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture));
                    }
                    sourceElement.Value = source.SourceUrl;
                    elements.Add(sourceElement);
                }
            }
        }

        var metadataElement = BuildFuzzbinMetadata(video);
        if (metadataElement is not null)
        {
            elements.Add(metadataElement);
        }

        return new XDocument(
            new XDeclaration("1.0", "UTF-8", "yes"),
            new XElement("musicvideo", elements));
    }

    private static (string EffectiveTitle, List<string> ArtistElements) ApplyArtistMode(
        string? title,
        string? primaryArtist,
        List<string> featuredArtists,
        NfoArtistMode mode)
    {
        var effectiveTitle = title ?? string.Empty;
        var artistElements = new List<string>();

        switch (mode)
        {
            case NfoArtistMode.PrimaryOnly:
                // Write primary artist to NFO only. Ignore any featured artists.
                if (!string.IsNullOrWhiteSpace(primaryArtist))
                {
                    artistElements.Add(primaryArtist);
                }
                break;

            case NfoArtistMode.SeparateFields:
                // Write primary artist and any additional featured artists as individual artist fields.
                if (!string.IsNullOrWhiteSpace(primaryArtist))
                {
                    artistElements.Add(primaryArtist);
                }
                artistElements.AddRange(featuredArtists);
                break;

            case NfoArtistMode.CombinedArtistField:
                // Write primary artist, "feat.", and any featured artists to a singular artist field (default behavior).
                if (!string.IsNullOrWhiteSpace(primaryArtist))
                {
                    if (featuredArtists.Count > 0)
                    {
                        artistElements.Add($"{primaryArtist} feat. {string.Join(", ", featuredArtists)}");
                    }
                    else
                    {
                        artistElements.Add(primaryArtist);
                    }
                }
                break;

            case NfoArtistMode.FeaturedInTitle:
                // Write primary artist to singular artist element. Write any featured artists to the title element.
                if (!string.IsNullOrWhiteSpace(primaryArtist))
                {
                    artistElements.Add(primaryArtist);
                }
                if (featuredArtists.Count > 0)
                {
                    effectiveTitle = string.IsNullOrWhiteSpace(effectiveTitle)
                        ? $"feat. {string.Join(", ", featuredArtists)}"
                        : $"{effectiveTitle} (feat. {string.Join(", ", featuredArtists)})";
                }
                break;

            default:
                // Fallback to CombinedArtistField behavior
                if (!string.IsNullOrWhiteSpace(primaryArtist))
                {
                    if (featuredArtists.Count > 0)
                    {
                        artistElements.Add($"{primaryArtist} feat. {string.Join(", ", featuredArtists)}");
                    }
                    else
                    {
                        artistElements.Add(primaryArtist);
                    }
                }
                break;
        }

        return (effectiveTitle, artistElements);
    }

    public static XDocument BuildArtistDocument(FeaturedArtist artist, IEnumerable<Video> videos, Func<Video, IEnumerable<string>?>? genreSelector = null)
    {
        ArgumentNullException.ThrowIfNull(artist);

        var associatedVideos = videos?.ToList() ?? new List<Video>();
        var elements = new List<object>();

        AddElement(elements, "name", artist.Name);
        AddElement(elements, "sortname", artist.Name);
        AddElement(elements, "biography", artist.Biography);

        if (!string.IsNullOrWhiteSpace(artist.ImagePath))
        {
            var normalized = NormalizePath(artist.ImagePath);
            AddElement(elements, "thumb", normalized);
            AddElement(elements, "fanart", normalized);
        }

        var uniqueIds = BuildUniqueIdElements(artist);
        elements.AddRange(uniqueIds);

        var artistGenres = ResolveGenresForArtist(associatedVideos, genreSelector);
        AddRepeatedElements(elements, "genre", artistGenres);

        var tags = associatedVideos
            .Where(v => v.Tags?.Any() == true)
            .SelectMany(v => v.Tags!)
            .Select(t => t.Name)
            .Where(name => !string.IsNullOrWhiteSpace(name))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();

        AddRepeatedElements(elements, "style", tags);

        var earliestYear = associatedVideos
            .Where(v => v.Year.HasValue && v.Year.Value > 0)
            .Select(v => v.Year!.Value)
            .DefaultIfEmpty()
            .Min();

        if (earliestYear > 0)
        {
            AddElement(elements, "formed", earliestYear.ToString("0000", CultureInfo.InvariantCulture));
        }

        if (associatedVideos.Count > 0)
        {
            var musicVideosElement = new XElement("musicvideos");
            foreach (var video in associatedVideos)
            {
                var item = new XElement("musicvideo");
                AddElement(item, "title", video.Title);
                AddElement(item, "year", video.Year?.ToString("0000", CultureInfo.InvariantCulture));
                AddElement(item, "runtime", video.Duration?.ToString(CultureInfo.InvariantCulture));
                AddElement(item, "path", NormalizePath(video.FilePath));
                musicVideosElement.Add(item);
            }

            elements.Add(musicVideosElement);
        }

        AddElement(elements, "musicvideoscount", associatedVideos.Count.ToString(CultureInfo.InvariantCulture));

        return new XDocument(
            new XDeclaration("1.0", "UTF-8", "yes"),
            new XElement("artist", elements));
    }

    private static IReadOnlyList<string> ResolveGenresForVideo(Video video, IEnumerable<string>? overrideGenres)
    {
        var normalizedOverride = NormalizeGenres(overrideGenres);
        if (normalizedOverride.Count > 0)
        {
            return normalizedOverride;
        }

        return NormalizeGenres(video.Genres?.Select(g => g.Name));
    }

    private static IReadOnlyList<string> ResolveTagsForVideo(
        Video video,
        IEnumerable<string>? additionalTags,
        bool includeCollectionsAsTags)
    {
        var result = new List<string>();
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        void AddRange(IEnumerable<string?>? source)
        {
            if (source is null)
            {
                return;
            }

            foreach (var entry in source)
            {
                if (string.IsNullOrWhiteSpace(entry))
                {
                    continue;
                }

                var normalized = entry.Trim();
                if (seen.Add(normalized))
                {
                    result.Add(normalized);
                }
            }
        }

        AddRange(video.Tags?.Select(t => t.Name));
        AddRange(additionalTags);
        if (includeCollectionsAsTags)
        {
            AddRange(video.CollectionVideos?
                .Select(cv => cv?.Collection?.Name));
        }

        return result;
    }

    private static IReadOnlyList<string> ResolveGenresForArtist(IEnumerable<Video> videos, Func<Video, IEnumerable<string>?>? genreSelector)
    {
        var result = new List<string>();
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        foreach (var video in videos)
        {
            var genres = ResolveGenresForVideo(video, genreSelector?.Invoke(video));
            foreach (var genre in genres)
            {
                if (seen.Add(genre))
                {
                    result.Add(genre);
                }
            }
        }

        return result;
    }

    private static IReadOnlyList<string> NormalizeGenres(IEnumerable<string?>? source)
    {
        if (source is null)
        {
            return Array.Empty<string>();
        }

        var result = new List<string>();
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        foreach (var entry in source)
        {
            if (string.IsNullOrWhiteSpace(entry))
            {
                continue;
            }

            var normalized = entry.Trim();
            if (seen.Add(normalized))
            {
                result.Add(normalized);
            }
        }

        return result;
    }

    private static XElement? BuildFuzzbinMetadata(Video video)
    {
        var metadata = new XElement("fuzzbin");
        AddElement(metadata, "dateadded", video.CreatedAt.ToString("yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture));
        AddElement(metadata, "dateimported", video.ImportedAt?.ToString("yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture));
        AddElement(metadata, "lastplayed", video.LastPlayedAt?.ToString("yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture));
        AddElement(metadata, "playcount", video.PlayCount.ToString(CultureInfo.InvariantCulture));
        AddElement(metadata, "filepath", NormalizePath(video.FilePath));
        AddElement(metadata, "thumbnailpath", NormalizePath(video.ThumbnailPath));
        AddElement(metadata, "nfopath", NormalizePath(video.NfoPath));

        // Add source URLs (note: VideoSourceVerification needs to be loaded separately)
        // This is a placeholder for when the Video entity includes navigation properties
        // In practice, you would load these via repository with includes
        
        // Add collections the video belongs to
        if (video.CollectionVideos?.Any() == true)
        {
            var collectionsElement = new XElement("collections");
            foreach (var collectionVideo in video.CollectionVideos.OrderBy(cv => cv.AddedToCollectionDate))
            {
                if (collectionVideo.Collection != null)
                {
                    var collElement = new XElement("collection");
                    AddElement(collElement, "name", collectionVideo.Collection.Name);
                    AddElement(collElement, "type", collectionVideo.Collection.Type.ToString());
                    AddElement(collElement, "dateadded", collectionVideo.AddedToCollectionDate.ToString("yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture));
                    if (collectionVideo.Position > 0)
                    {
                        AddElement(collElement, "position", collectionVideo.Position.ToString(CultureInfo.InvariantCulture));
                    }
                    if (!string.IsNullOrWhiteSpace(collectionVideo.Notes))
                    {
                        AddElement(collElement, "notes", collectionVideo.Notes);
                    }
                    collectionsElement.Add(collElement);
                }
            }
            if (collectionsElement.HasElements)
            {
                metadata.Add(collectionsElement);
            }
        }

        return metadata.HasElements ? metadata : null;
    }

    private static IEnumerable<XElement> BuildUniqueIdElements(Video video)
    {
        var elements = new List<XElement>();

        var primaryId = CreateUniqueId("imvdb", video.ImvdbId, isDefault: !string.IsNullOrWhiteSpace(video.ImvdbId));
        if (primaryId is not null)
        {
            elements.Add(primaryId);
        }

        var youtubeId = CreateUniqueId("youtube", video.YouTubeId, isDefault: string.IsNullOrWhiteSpace(video.ImvdbId));
        if (youtubeId is not null)
        {
            elements.Add(youtubeId);
        }

        var musicBrainzId = CreateUniqueId("musicbrainz", video.MusicBrainzRecordingId);
        if (musicBrainzId is not null)
        {
            elements.Add(musicBrainzId);
        }

        return elements;
    }

    private static IEnumerable<XElement> BuildUniqueIdElements(FeaturedArtist artist)
    {
        var elements = new List<XElement>();

        var imvdbId = CreateUniqueId("imvdb", artist.ImvdbArtistId, isDefault: !string.IsNullOrWhiteSpace(artist.ImvdbArtistId));
        if (imvdbId is not null)
        {
            elements.Add(imvdbId);
        }

        var musicBrainzId = CreateUniqueId("musicbrainz", artist.MusicBrainzArtistId, isDefault: string.IsNullOrWhiteSpace(artist.ImvdbArtistId));
        if (musicBrainzId is not null)
        {
            elements.Add(musicBrainzId);
        }

        return elements;
    }

    private static List<XElement> BuildActorElements(Video video)
    {
        var actors = new List<XElement>();

        if (video.FeaturedArtists?.Any() != true)
        {
            return actors;
        }

        foreach (var artist in video.FeaturedArtists)
        {
            if (string.IsNullOrWhiteSpace(artist.Name))
            {
                continue;
            }

            var actor = new XElement("actor");
            AddElement(actor, "name", artist.Name);
            AddElement(actor, "role", "Featured Artist");
            AddElement(actor, "type", "FeaturedArtist");

            if (!string.IsNullOrWhiteSpace(artist.ImvdbArtistId))
            {
                AddElement(actor, "imvdbartistid", artist.ImvdbArtistId);
            }

            if (!string.IsNullOrWhiteSpace(artist.MusicBrainzArtistId))
            {
                AddElement(actor, "mbartistid", artist.MusicBrainzArtistId);
            }

            actors.Add(actor);
        }

        return actors;
    }

    private static string? BuildPremieredDate(Video video)
    {
        if (video.Year.HasValue && video.Year.Value > 0)
        {
            return $"{video.Year.Value:0000}-01-01";
        }

        if (video.ImportedAt.HasValue)
        {
            return video.ImportedAt.Value.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
        }

        return null;
    }

    private static XElement? CreateUniqueId(string type, string? value, bool isDefault = false)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        var element = new XElement("uniqueid", value);
        element.SetAttributeValue("type", type);
        if (isDefault)
        {
            element.SetAttributeValue("default", "true");
        }

        return element;
    }

    private static string? BuildAspectRatio(int? width, int? height)
    {
        if (!width.HasValue || !height.HasValue || width.Value <= 0 || height.Value <= 0)
        {
            return null;
        }

        var gcd = GreatestCommonDivisor(width.Value, height.Value);
        var aspectWidth = width.Value / gcd;
        var aspectHeight = height.Value / gcd;

        return $"{aspectWidth}:{aspectHeight}";
    }

    private static string? BuildResolutionLabel(int? height)
    {
        if (!height.HasValue)
        {
            return null;
        }

        return height.Value switch
        {
            >= 2160 => "2160",
            >= 1440 => "1440",
            >= 1080 => "1080",
            >= 720 => "720",
            >= 480 => "480",
            >= 360 => "360",
            >= 240 => "240",
            _ => height.Value.ToString(CultureInfo.InvariantCulture)
        };
    }

    private static (int? Width, int? Height) ParseResolution(string? resolution)
    {
        if (string.IsNullOrWhiteSpace(resolution))
        {
            return (null, null);
        }

        var parts = resolution.Split('x', 'X');
        if (parts.Length != 2)
        {
            return (null, null);
        }

        if (!int.TryParse(parts[0], NumberStyles.Integer, CultureInfo.InvariantCulture, out var width))
        {
            width = 0;
        }

        if (!int.TryParse(parts[1], NumberStyles.Integer, CultureInfo.InvariantCulture, out var height))
        {
            height = 0;
        }

        return (width > 0 ? width : null, height > 0 ? height : null);
    }

    private static void AddElement(ICollection<object> container, string name, string? value)
    {
        if (!string.IsNullOrWhiteSpace(value))
        {
            container.Add(new XElement(name, value));
        }
    }

    private static void AddElement(XElement parent, string name, string? value)
    {
        if (!string.IsNullOrWhiteSpace(value))
        {
            parent.Add(new XElement(name, value));
        }
    }

    private static void AddRepeatedElements(ICollection<object> container, string name, IEnumerable<string?> values)
    {
        foreach (var value in values)
        {
            if (!string.IsNullOrWhiteSpace(value))
            {
                container.Add(new XElement(name, value));
            }
        }
    }

    private static int GreatestCommonDivisor(int a, int b)
    {
        while (b != 0)
        {
            (a, b) = (b, a % b);
        }

        return Math.Max(1, a);
    }

    private static string? NormalizePath(string? path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return null;
        }

        return path.Replace('\\', '/');
    }
}
