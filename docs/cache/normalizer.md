# C# Normalizer (search/caching keys - unified: MusicBrainz, IMVDb, yt-dlp/search)

Goals: Unicode-safe, diacritic-stripping, punctuation-light, stable tokenization, light heuristics for “feat.”/“ft.”, and a consistent combo key.

```csharp
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;

public static class QueryNormalizer
{
    // Compile once
    private static readonly Regex MultiSpace = new Regex(@"\s+", RegexOptions.Compiled);
    private static readonly Regex PunctToSpace = new Regex(@"[^\p{L}\p{Nd}]+", RegexOptions.Compiled); // keep letters/digits, space others
    private static readonly Regex FeatRegex = new Regex(@"\b(feat\.?|ft\.?|featuring)\b", RegexOptions.IgnoreCase | RegexOptions.Compiled);
    private static readonly Regex TrimFeatTrail = new Regex(@"\b(feat\.?|ft\.?|featuring)\b.*$", RegexOptions.IgnoreCase | RegexOptions.Compiled);
    private static readonly HashSet<string> StopSingles = new HashSet<string>(StringComparer.OrdinalIgnoreCase) {
        "a" // keep “the” to avoid breaking artists like “The The”
    };

    public static string NormalizeTitle(string input)
        => NormalizeCore(input, removeTrailingFeat: true);

    public static string NormalizeArtist(string input)
        => NormalizeCore(input, removeTrailingFeat: false);

    public static (string NormTitle, string NormArtist, string ComboKey) NormalizePair(string title, string artist)
    {
        var nt = NormalizeTitle(title ?? string.Empty);
        var na = NormalizeArtist(artist ?? string.Empty);
        var combo = $"{na}||{nt}";
        return (nt, na, combo);
    }

    private static string NormalizeCore(string input, bool removeTrailingFeat)
    {
        if (string.IsNullOrWhiteSpace(input)) return string.Empty;

        // Unicode → NFKD, strip diacritics
        string nfkd = input.Normalize(NormalizationForm.FormD);
        var sb = new StringBuilder(nfkd.Length);
        foreach (var ch in nfkd)
        {
            var uc = CharUnicodeInfo.GetUnicodeCategory(ch);
            if (uc != UnicodeCategory.NonSpacingMark && uc != UnicodeCategory.EnclosingMark)
                sb.Append(ch);
        }
        string noDiacritics = sb.ToString().Normalize(NormalizationForm.FormC);

        // Normalize “feat/ft/featuring”
        string s = FeatRegex.Replace(noDiacritics, " feat ");

        // Optionally trim anything after trailing "feat ..."
        if (removeTrailingFeat)
        {
            s = TrimFeatTrail.Replace(s, string.Empty);
        }

        // Collapse punctuation to spaces, lowercase
        s = PunctToSpace.Replace(s, " ").ToLowerInvariant();

        // Tokenize, drop singleton stopwords (lightly), sort for stability?:
        // We DO NOT sort for artists (order matters for credits), but we DO NOT sort for titles either
        // to avoid changing “still fly” semantics. Keep order; just trim.
        var tokens = MultiSpace.Split(s).Where(t => t.Length > 0).ToList();
        if (tokens.Count == 0) return string.Empty;

        // Remove trivial single-letter "a" only (NOT "the")
        tokens = tokens.Where(t => !(t.Length == 1 && StopSingles.Contains(t))).ToList();

        // Rejoin
        s = string.Join(" ", tokens);

        return s.Trim();
    }
}
```

**Notes**

* Title: trims trailing “feat …” to make track identity stable. Artist: preserves featured artists (order still matters for MB artist-credit alignment).
* You now have a single `ComboKey = "{normArtist}||{normTitle}"` that you can safely use as a uniqueness handle in `query.norm_combo_key`.


## Small upsert helpers (SQLite)

Use `INSERT ... ON CONFLICT DO UPDATE` to keep rows fresh, e.g.:

```sql
INSERT INTO yt_video(video_id, title, channel_id, channel_name, duration_seconds, view_count, last_seen_at)
VALUES ($id,$title,$chId,$chName,$dur,$views,datetime('now'))
ON CONFLICT(video_id) DO UPDATE SET
  title=excluded.title,
  channel_id=excluded.channel_id,
  channel_name=excluded.channel_name,
  duration_seconds=excluded.duration_seconds,
  view_count=excluded.view_count,
  last_seen_at=excluded.last_seen_at;
```

---

## Practical mapping notes

* **Overlaps** (“Big Tymers” vs “Big Tymers Still Fly”): both queries get their own `query` row, but candidates are cached per query; repeated searches will hit the cache and you’ll avoid extra API calls.
* **Director**: IMVDb → `imvdb_video.director_credit`. If you later resolve a specific person object, you can add a `imvdb_person` table; the DDL above keeps it simple.
* **Genres**: Store MB tags/genres in `mb_tag`. If you want a single “specific” vs “generalized” genre, compute and materialize later via a small mapping table or view.
* **Thumbnails**: You store the **URL** and a **local path** to the saved file; this lets you re-render UIs offline.
