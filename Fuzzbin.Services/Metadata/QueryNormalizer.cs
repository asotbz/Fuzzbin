using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;

namespace Fuzzbin.Services.Metadata;

/// <summary>
/// Provides query normalization for metadata search and matching.
/// Implements the normalization strategy from docs/cache/normalizer.md
/// </summary>
public static class QueryNormalizer
{
    private static readonly Regex MultiSpace = new(@"\s+", RegexOptions.Compiled);
    private static readonly Regex PunctToSpace = new(@"[^\p{L}\p{Nd}]+", RegexOptions.Compiled);
    private static readonly Regex FeatRegex = new(@"\b(feat\.?|ft\.?|featuring)\b", 
        RegexOptions.IgnoreCase | RegexOptions.Compiled);
    private static readonly Regex TrimFeatTrail = new(@"\b(feat\.?|ft\.?|featuring)\b.*$", 
        RegexOptions.IgnoreCase | RegexOptions.Compiled);
    private static readonly HashSet<string> StopSingles = new(StringComparer.OrdinalIgnoreCase) 
    {
        "a"
    };

    /// <summary>
    /// Normalizes a song title for matching.
    /// Removes trailing featured artist information.
    /// </summary>
    /// <param name="input">Raw title string</param>
    /// <returns>Normalized title string</returns>
    public static string NormalizeTitle(string input)
        => NormalizeCore(input, removeTrailingFeat: true);

    /// <summary>
    /// Normalizes an artist name for matching.
    /// Preserves featured artist information.
    /// </summary>
    /// <param name="input">Raw artist string</param>
    /// <returns>Normalized artist string</returns>
    public static string NormalizeArtist(string input)
        => NormalizeCore(input, removeTrailingFeat: false);

    /// <summary>
    /// Normalizes both title and artist, returning a combined key for uniqueness checks.
    /// </summary>
    /// <param name="title">Raw title string</param>
    /// <param name="artist">Raw artist string</param>
    /// <returns>Tuple of (NormTitle, NormArtist, ComboKey)</returns>
    public static (string NormTitle, string NormArtist, string ComboKey) NormalizePair(string title, string artist)
    {
        var nt = NormalizeTitle(title ?? string.Empty);
        var na = NormalizeArtist(artist ?? string.Empty);
        var combo = $"{na}||{nt}";
        return (nt, na, combo);
    }

    /// <summary>
    /// Core normalization implementation.
    /// </summary>
    /// <param name="input">Input string</param>
    /// <param name="removeTrailingFeat">Whether to remove trailing featured artist markers</param>
    /// <returns>Normalized string</returns>
    private static string NormalizeCore(string input, bool removeTrailingFeat)
    {
        if (string.IsNullOrWhiteSpace(input)) 
            return string.Empty;

        // Step 1: Unicode normalization - NFKD decomposition and strip combining marks
        string nfkd = input.Normalize(NormalizationForm.FormKD);
        var sb = new StringBuilder(nfkd.Length);
        foreach (var ch in nfkd)
        {
            var uc = CharUnicodeInfo.GetUnicodeCategory(ch);
            if (uc != UnicodeCategory.NonSpacingMark && uc != UnicodeCategory.EnclosingMark)
                sb.Append(ch);
        }
        string noDiacritics = sb.ToString().Normalize(NormalizationForm.FormC);

        // Step 2: Normalize featured artist markers to standard form
        string s = FeatRegex.Replace(noDiacritics, " feat ");

        // Step 3: Optionally remove trailing featured artist info (for titles only)
        if (removeTrailingFeat)
        {
            s = TrimFeatTrail.Replace(s, string.Empty);
        }

        // Step 4: Replace all punctuation with spaces and convert to lowercase
        s = PunctToSpace.Replace(s, " ").ToLowerInvariant();

        // Step 5: Split into tokens and remove empty ones
        var tokens = MultiSpace.Split(s).Where(t => t.Length > 0).ToList();
        if (tokens.Count == 0) 
            return string.Empty;

        // Step 6: Remove single-character stop words
        tokens = tokens.Where(t => !(t.Length == 1 && StopSingles.Contains(t))).ToList();

        // Step 7: Join with single spaces
        s = string.Join(" ", tokens);

        return s.Trim();
    }
}