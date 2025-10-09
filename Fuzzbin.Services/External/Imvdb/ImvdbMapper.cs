using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using DomainImvdbCredit = Fuzzbin.Core.Interfaces.ImvdbCredit;

namespace Fuzzbin.Services.External.Imvdb;

public static class ImvdbMapper
{
    public static string BuildCacheKey(string artist, string title)
    {
        return $"imvdb:metadata:{NormalizeKey(artist)}:{NormalizeKey(title)}";
    }

    public static ImvdbVideoSummary? FindBestMatch(IEnumerable<ImvdbVideoSummary> results, string artist, string title)
    {
        var normalizedArtistKey = NormalizeKey(artist);
        var normalizedTitleKey = NormalizeKey(title);
        var normalizedArtist = NormalizeSimple(artist);
        var normalizedTitle = NormalizeSimple(title);

        ImvdbVideoSummary? exact = null;
        ImvdbVideoSummary? partial = null;

        foreach (var result in results)
        {
            var resultArtist = result.Artist ?? string.Empty;
            var resultTitle = result.SongTitle ?? result.Title ?? string.Empty;

            var resultArtistKey = NormalizeKey(resultArtist);
            var resultTitleKey = NormalizeKey(resultTitle);

            if (resultArtistKey == normalizedArtistKey && resultTitleKey == normalizedTitleKey)
            {
                exact = result;
                break;
            }

            if (partial == null)
            {
                var resultArtistSimple = NormalizeSimple(resultArtist);
                var resultTitleSimple = NormalizeSimple(resultTitle);

                if (!string.IsNullOrEmpty(resultArtistSimple) &&
                    !string.IsNullOrEmpty(resultTitleSimple) &&
                    resultArtistSimple.Contains(normalizedArtist) &&
                    resultTitleSimple.Contains(normalizedTitle))
                {
                    partial = result;
                }
            }
        }

        return exact ?? partial ?? results.FirstOrDefault();
    }

    public static ImvdbMetadata MapToMetadata(ImvdbVideoResponse video, ImvdbVideoSummary summary)
    {
        var metadata = new ImvdbMetadata
        {
            ImvdbId = video.Id,
            Title = FirstNonEmpty(video.SongTitle, video.Title, summary.SongTitle, summary.Title),
            Artist = FirstNonEmpty(video.Artist, summary.Artist),
            Description = video.Description,
            ImageUrl = FirstNonEmpty(video.ThumbnailUrl, summary.ImageUrl),
            VideoUrl = FirstNonEmpty(video.ImvdbUrl, summary.Url),
            IsExplicit = video.IsExplicit ?? false,
            IsUnofficial = video.IsUnofficial ?? false
        };

        if (!string.IsNullOrWhiteSpace(video.ReleaseDate))
        {
            if (DateTime.TryParse(video.ReleaseDate, CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal, out var releaseDate) ||
                DateTime.TryParse(video.ReleaseDate, out releaseDate))
            {
                metadata.ReleaseDate = releaseDate;
                metadata.Year = releaseDate.Year;
            }
            else if (video.ReleaseDate.Length >= 4 && int.TryParse(video.ReleaseDate[..4], out var yearOnly))
            {
                metadata.Year = yearOnly;
            }
        }

        var genres = (video.Genres ?? Enumerable.Empty<ImvdbGenre>())
            .Select(g => g.Name)
            .Where(name => !string.IsNullOrWhiteSpace(name))
            .Select(name => name!)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();

        if (genres.Count > 0)
        {
            metadata.Genres = genres;
        }

        var credits = video.Credits
            .Where(c => !string.IsNullOrWhiteSpace(c.Role) && !string.IsNullOrWhiteSpace(c.Person?.Name))
            .Select(c => new DomainImvdbCredit
            {
                Role = c.Role,
                Name = c.Person!.Name
            })
            .ToList();

        metadata.Credits = credits;
        metadata.Director = FindCreditName(credits, "Director");
        metadata.ProductionCompany = FindCreditName(credits, "Production Company") ?? FindCreditName(credits, "Production");
        metadata.RecordLabel = FindCreditName(credits, "Record Label") ?? FindCreditName(credits, "Label");

        var featured = credits
            .Where(c => string.Equals(c.Role, "Featured Artist", StringComparison.OrdinalIgnoreCase) ||
                        string.Equals(c.Role, "Featuring", StringComparison.OrdinalIgnoreCase))
            .Select(c => c.Name)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();

        if (featured.Count > 0)
        {
            metadata.FeaturedArtists = string.Join(", ", featured);
        }

        return metadata;
    }

    public static string NormalizeKey(string value)
    {
        var builder = new StringBuilder(value.Length);
        foreach (var character in value)
        {
            if (char.IsLetterOrDigit(character))
            {
                builder.Append(char.ToLowerInvariant(character));
            }
        }

        return builder.ToString();
    }

    public static string NormalizeSimple(string value)
    {
        return value.ToLowerInvariant().Trim();
    }

    public static string? FirstNonEmpty(params string?[] values)
    {
        foreach (var value in values)
        {
            if (!string.IsNullOrWhiteSpace(value))
            {
                return value;
            }
        }

        return null;
    }

    private static string? FindCreditName(IEnumerable<DomainImvdbCredit> credits, string role)
    {
        return credits.FirstOrDefault(c => string.Equals(c.Role, role, StringComparison.OrdinalIgnoreCase))?.Name;
    }
}
