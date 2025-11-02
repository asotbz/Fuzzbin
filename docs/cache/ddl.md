# Consolidated MusicBrainz, IMVDb, yt-dlp (search) DDL

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

/* =========================
   Shared & Query Cache
   ========================= */

-- What the user typed and the normalized forms we key caching on.
CREATE TABLE IF NOT EXISTS query (
  id                    INTEGER PRIMARY KEY,
  raw_title             TEXT,
  raw_artist            TEXT,
  norm_title            TEXT NOT NULL,
  norm_artist           TEXT NOT NULL,
  norm_combo_key        TEXT NOT NULL,  -- e.g., "{artist}||{title}" normalized; unique for dedupe
  created_at            TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(norm_combo_key)
);

CREATE INDEX IF NOT EXISTS idx_query_norm_title  ON query(norm_title);
CREATE INDEX IF NOT EXISTS idx_query_norm_artist ON query(norm_artist);

-- Track whether we’ve already called external sources for a query.
CREATE TABLE IF NOT EXISTS query_source_cache (
  id              INTEGER PRIMARY KEY,
  query_id        INTEGER NOT NULL REFERENCES query(id) ON DELETE CASCADE,
  source          TEXT NOT NULL CHECK (source IN ('musicbrainz','imvdb','youtube')),
  last_checked_at TEXT NOT NULL,
  result_etag     TEXT,               -- hash of normalized result set (for change detection)
  http_status     INTEGER,
  notes           TEXT,
  UNIQUE(query_id, source)
);

/* =========================
   MusicBrainz (mb_*)
   ========================= */

CREATE TABLE IF NOT EXISTS mb_artist (
  mbid                TEXT PRIMARY KEY,    -- UUID
  name                TEXT NOT NULL,
  sort_name           TEXT,
  disambiguation      TEXT,
  country             TEXT,
  last_seen_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS mb_recording (
  mbid                TEXT PRIMARY KEY,    -- UUID
  title               TEXT NOT NULL,
  length_ms           INTEGER,             -- null if unknown
  last_seen_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS mb_release_group (
  mbid                TEXT PRIMARY KEY,
  title               TEXT NOT NULL,
  primary_type        TEXT,                -- e.g., 'Single','Album'
  first_release_date  TEXT,                -- YYYY or YYYY-MM or YYYY-MM-DD
  last_seen_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS mb_release (
  mbid                TEXT PRIMARY KEY,
  title               TEXT NOT NULL,
  date                TEXT,                -- YYYY or YYYY-MM or YYYY-MM-DD
  country             TEXT,
  barcode             TEXT,
  last_seen_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

-- N:M
CREATE TABLE IF NOT EXISTS mb_recording_artist (
  recording_mbid      TEXT NOT NULL REFERENCES mb_recording(mbid) ON DELETE CASCADE,
  artist_mbid         TEXT NOT NULL REFERENCES mb_artist(mbid)    ON DELETE CASCADE,
  artist_order        INTEGER NOT NULL DEFAULT 0,
  is_join_phrase_feat INTEGER NOT NULL DEFAULT 0,  -- rough flag if joinPhrase looked like 'feat.'
  PRIMARY KEY (recording_mbid, artist_mbid)
);

-- Recording ↔ Release & Release ↔ Release Group
CREATE TABLE IF NOT EXISTS mb_recording_release (
  recording_mbid      TEXT NOT NULL REFERENCES mb_recording(mbid) ON DELETE CASCADE,
  release_mbid        TEXT NOT NULL REFERENCES mb_release(mbid)   ON DELETE CASCADE,
  track_number        INTEGER,
  disc_number         INTEGER,
  PRIMARY KEY (recording_mbid, release_mbid)
);

CREATE TABLE IF NOT EXISTS mb_release_to_group (
  release_mbid        TEXT NOT NULL REFERENCES mb_release(mbid)       ON DELETE CASCADE,
  release_group_mbid  TEXT NOT NULL REFERENCES mb_release_group(mbid) ON DELETE CASCADE,
  PRIMARY KEY (release_mbid, release_group_mbid)
);

-- Tags/genres captured at any entity level (artist or recording or release-group).
CREATE TABLE IF NOT EXISTS mb_tag (
  entity_type         TEXT NOT NULL CHECK (entity_type IN ('artist','recording','release_group')),
  entity_mbid         TEXT NOT NULL,
  tag                 TEXT NOT NULL,
  count               INTEGER,
  PRIMARY KEY (entity_type, entity_mbid, tag)
);

-- Per-query MB candidate matches (for confidence/ranking + dedupe).
CREATE TABLE IF NOT EXISTS mb_recording_candidate (
  id                  INTEGER PRIMARY KEY,
  query_id            INTEGER NOT NULL REFERENCES query(id) ON DELETE CASCADE,
  recording_mbid      TEXT NOT NULL REFERENCES mb_recording(mbid) ON DELETE CASCADE,
  title_norm          TEXT NOT NULL,
  artist_norm         TEXT NOT NULL,
  text_score          REAL NOT NULL,    -- e.g., token-set or exact match weighting
  year_score          REAL,             -- distance from earliest release year (if available)
  duration_score      REAL,             -- distance from known duration
  overall_score       REAL NOT NULL,
  rank                INTEGER NOT NULL, -- 1 = best
  selected            INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_mb_cand_query ON mb_recording_candidate(query_id);

/* =========================
   IMVDb (imvdb_*)
   ========================= */

CREATE TABLE IF NOT EXISTS imvdb_artist (
  id                  INTEGER PRIMARY KEY, -- IMVDb numeric id
  name                TEXT NOT NULL,
  last_seen_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS imvdb_video (
  id                  INTEGER PRIMARY KEY, -- IMVDb numeric id
  song_title          TEXT,                -- IMVDb song title
  video_title         TEXT,                -- sometimes IMVDb has a distinct video title
  release_date        TEXT,                -- yyyy-mm-dd if available
  director_credit     TEXT,                -- free text; IMVDb can return structured people too
  has_sources         INTEGER NOT NULL DEFAULT 0, -- whether IMVDb provided official sources
  last_seen_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS imvdb_video_artist (
  video_id            INTEGER NOT NULL REFERENCES imvdb_video(id)   ON DELETE CASCADE,
  artist_id           INTEGER NOT NULL REFERENCES imvdb_artist(id)  ON DELETE CASCADE,
  role                TEXT NOT NULL CHECK (role IN ('primary','featured')),
  artist_order        INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (video_id, artist_id, role)
);

-- If IMVDb provides external sources (YouTube/Vimeo ids).
CREATE TABLE IF NOT EXISTS imvdb_video_source (
  video_id            INTEGER NOT NULL REFERENCES imvdb_video(id) ON DELETE CASCADE,
  source              TEXT NOT NULL CHECK (source IN ('youtube','vimeo')),
  external_id         TEXT NOT NULL,  -- e.g., YouTube videoId or Vimeo id
  is_official         INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (video_id, source, external_id)
);

-- Per-query IMVDb candidate matches.
CREATE TABLE IF NOT EXISTS imvdb_video_candidate (
  id                  INTEGER PRIMARY KEY,
  query_id            INTEGER NOT NULL REFERENCES query(id) ON DELETE CASCADE,
  video_id            INTEGER NOT NULL REFERENCES imvdb_video(id) ON DELETE CASCADE,
  title_norm          TEXT NOT NULL,
  artist_norm         TEXT NOT NULL,
  text_score          REAL NOT NULL,
  source_bonus        REAL NOT NULL,      -- boost if sources exist
  overall_score       REAL NOT NULL,
  rank                INTEGER NOT NULL,
  selected            INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_imvdb_cand_query ON imvdb_video_candidate(query_id);

/* =========================
   YouTube (yt_* from yt-dlp)
   ========================= */

CREATE TABLE IF NOT EXISTS yt_video (
  video_id            TEXT PRIMARY KEY,   -- YouTube ID
  title               TEXT NOT NULL,
  channel_id          TEXT,
  channel_name        TEXT,
  duration_seconds    INTEGER,
  width               INTEGER,
  height              INTEGER,
  view_count          INTEGER,
  published_at        TEXT,
  thumbnail_url       TEXT,
  thumbnail_path      TEXT,               -- on-disk file you saved
  is_official_channel INTEGER,            -- heuristic you compute later
  last_seen_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS yt_video_candidate (
  id                  INTEGER PRIMARY KEY,
  query_id            INTEGER NOT NULL REFERENCES query(id) ON DELETE CASCADE,
  video_id            TEXT NOT NULL REFERENCES yt_video(video_id) ON DELETE CASCADE,
  title_norm          TEXT NOT NULL,
  artist_norm         TEXT NOT NULL,
  text_score          REAL NOT NULL,
  channel_bonus       REAL,
  duration_score      REAL,
  overall_score       REAL NOT NULL,
  rank                INTEGER NOT NULL,
  selected            INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_yt_cand_query ON yt_video_candidate(query_id);

/* =========================
   Cross-linking & Final Answers
   ========================= */

-- When you’re confident a specific MV exists (from IMVDb) and links to a MB recording and/or YT video.
CREATE TABLE IF NOT EXISTS mv_link (
  id                  INTEGER PRIMARY KEY,
  imvdb_video_id      INTEGER REFERENCES imvdb_video(id)      ON DELETE SET NULL,
  mb_recording_mbid   TEXT    REFERENCES mb_recording(mbid)    ON DELETE SET NULL,
  yt_video_id         TEXT    REFERENCES yt_video(video_id)     ON DELETE SET NULL,
  link_type           TEXT NOT NULL CHECK (link_type IN ('imvdb_to_mb','imvdb_to_yt','mb_to_yt','triad')),
  confidence          REAL NOT NULL,  -- 0..1
  notes               TEXT,
  created_at          TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (imvdb_video_id, mb_recording_mbid, yt_video_id)
);

-- Your final “answer” per query: did a music video exist, and what’s the chosen cross-link?
CREATE TABLE IF NOT EXISTS query_resolution (
  query_id            INTEGER PRIMARY KEY REFERENCES query(id) ON DELETE CASCADE,
  mv_exists           INTEGER NOT NULL, -- 0/1
  chosen_source       TEXT NOT NULL CHECK (chosen_source IN ('imvdb','youtube','none')),
  mv_link_id          INTEGER REFERENCES mv_link(id) ON DELETE SET NULL,
  resolved_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

/* =========================
   Materialized “best candidate per query” (optional views)
   ========================= */

CREATE VIEW IF NOT EXISTS v_best_imvdb AS
SELECT *
FROM (
  SELECT c.*, ROW_NUMBER() OVER (PARTITION BY c.query_id ORDER BY c.overall_score DESC) rn
  FROM imvdb_video_candidate c
)
WHERE rn = 1;

CREATE VIEW IF NOT EXISTS v_best_mb AS
SELECT *
FROM (
  SELECT c.*, ROW_NUMBER() OVER (PARTITION BY c.query_id ORDER BY c.overall_score DESC) rn
  FROM mb_recording_candidate c
)
WHERE rn = 1;

CREATE VIEW IF NOT EXISTS v_best_yt AS
SELECT *
FROM (
  SELECT c.*, ROW_NUMBER() OVER (PARTITION BY c.query_id ORDER BY c.overall_score DESC) rn
  FROM yt_video_candidate c
)
WHERE rn = 1;
```

# Unified MusicBrainz, IMVDb, yt-dlp (search) Normalizer (search/caching keys)

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
