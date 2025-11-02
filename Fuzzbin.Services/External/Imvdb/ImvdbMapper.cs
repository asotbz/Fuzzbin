using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;
using FuzzySharp;
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
            var resultArtist = result.Artists.FirstOrDefault()?.Name ?? string.Empty;
            var resultTitle = result.SongTitle ?? result.VideoTitle ?? string.Empty;

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

    public static ImvdbMetadata MapToMetadata(ImvdbVideoResponse video, ImvdbVideoSummary summary, double confidence = 0)
    {
        var metadata = new ImvdbMetadata
        {
            ImvdbId = (int?)video.Id,
            Title = FirstNonEmpty(video.SongTitle, video.VideoTitle, summary.SongTitle, summary.VideoTitle),
            Artist = FirstNonEmpty(
                video.Artists.FirstOrDefault()?.Name,
                summary.Artists.FirstOrDefault()?.Name),
            Description = null, // Removed legacy field
            ImageUrl = FirstNonEmpty(video.Thumbnail?.Url, summary.Thumbnail?.Url),
            VideoUrl = FirstNonEmpty(video.Url, summary.Url),
            IsExplicit = false, // Removed legacy field
            IsUnofficial = false // Removed legacy field
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

        // Extract genres from structured data (if available in future)
        metadata.Genres = new List<string>();

        // Extract director from Directors array
        metadata.Director = video.Directors.FirstOrDefault()?.Name;
        
        // Note: ProductionCompany and RecordLabel not available in current API structure
        metadata.ProductionCompany = null;
        metadata.RecordLabel = null;

        // Extract featured artists from Artists array with 'featured' role
        var featured = video.Artists
            .Where(a => string.Equals(a.Role, "featured", StringComparison.OrdinalIgnoreCase))
            .Select(a => a.Name)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();

        if (featured.Count > 0)
        {
            metadata.FeaturedArtists = string.Join(", ", featured);
        }

        // Legacy credits structure removed
        metadata.Credits = new List<DomainImvdbCredit>();

        metadata.Confidence = Math.Clamp(confidence, 0, 1);
        return metadata;
    }

    public static double ComputeMatchConfidence(string expectedArtist, string expectedTitle, ImvdbVideoSummary summary)
    {
        if (summary == null)
        {
            return 0;
        }

        var resultArtist = summary.Artists.FirstOrDefault()?.Name ?? string.Empty;
        var resultTitle = FirstNonEmpty(summary.SongTitle, summary.VideoTitle) ?? string.Empty;

        if (string.IsNullOrWhiteSpace(expectedArtist) || string.IsNullOrWhiteSpace(expectedTitle) ||
            (string.IsNullOrWhiteSpace(resultArtist) && string.IsNullOrWhiteSpace(resultTitle)))
        {
            return 0;
        }

        var artistScore = Fuzz.TokenSetRatio(expectedArtist, resultArtist);
        var titleScore = Fuzz.TokenSetRatio(expectedTitle, resultTitle);
        var combinedScore = Fuzz.TokenSetRatio(
            $"{expectedArtist} {expectedTitle}",
            $"{resultArtist} {resultTitle}");

        var weightedScore = (artistScore * 0.4 + titleScore * 0.4 + combinedScore * 0.2) / 100.0;
        return Math.Clamp(Math.Round(weightedScore, 4), 0, 1);
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
