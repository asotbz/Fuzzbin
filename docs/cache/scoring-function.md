```csharp
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;

namespace MediaLinking
{
    public sealed class ScoreBreakdown
    {
        public double TextScore { get; init; }          // 0..1
        public double DurationScore { get; init; }      // 0..1
        public double YearScore { get; init; }          // 0..1
        public double ChannelBonus { get; init; }       // -1..+1 (typ. 0..+0.3)
        public double SourceBonus { get; init; }        // -1..+1 (typ. 0..+0.2)
        public double Penalty { get; init; }            // 0..1 (deducted)
        public double Overall { get; init; }            // final weighted 0..1
    }

    public sealed class ScoringWeights
    {
        // Core weights (should sum to <= 1; bonuses/penalties applied after)
        public double WText { get; init; } = 0.60;
        public double WDuration { get; init; } = 0.20;
        public double WYear { get; init; } = 0.20;

        // Bonuses (additive)
        public double MaxChannelBonus { get; init; } = 0.25; // e.g., official channel / VEVO
        public double MaxSourceBonus  { get; init; } = 0.20; // e.g., IMVDb has official source

        // Penalties (subtractive)
        public double MaxPenalty { get; init; } = 0.35; // cap on total penalty subtraction

        // Duration/Year tolerance for scoring curves
        public int DurationToleranceSeconds { get; init; } = 8;  // ≤8s diff ≈ full credit
        public int DurationSoftCapSeconds   { get; init; } = 40; // ≥40s diff → near zero

        public int YearPerfectDelta { get; init; } = 0;  // 0 year diff = full credit
        public int YearSoftCap      { get; init; } = 5;  // ≥5 years diff → near zero
    }

    public static class CandidateScorer
    {
        // Terms that commonly mark NOT the official MV (penalize if present)
        private static readonly string[] NegativeHints = new[]
        {
            "audio", "lyrics", "lyric", "visualizer", "teaser", "live",
            "cover", "remix", "reaction", "sped up", "slowed", "8d",
            "fan made", "dance practice", "concert", "instrumental",
            "parody", "mashup", "edit", "tiktok"
        };

        // Terms that often indicate officialness (light bonus if in title)
        private static readonly string[] PositiveHints = new[]
        {
            "official video", "official music video", "vevo"
        };

        private static readonly Regex Splitter = new Regex(@"[^\p{L}\p{Nd}]+", RegexOptions.Compiled | RegexOptions.CultureInvariant);

        /// <summary>
        /// Compute final score given normalized query + candidate fields.
        /// Title/artist inputs should already be normalized (your QueryNormalizer).
        /// </summary>
        public static ScoreBreakdown Score(
            string normQueryTitle,
            string normQueryArtist,
            string candidateTitleNorm,
            string candidateArtistNorm,
            int? candidateDurationSec,
            int? mbReferenceDurationSec,      // optional reference (from MB); improves duration score
            int? candidateYear,               // publication/release year for the video or track
            int? mbEarliestYear,              // optional reference (from MB)
            bool hasOfficialSourceFromImvdb,  // IMVDb sources present
            string? youtubeChannelName = null,
            string? youtubeChannelId = null,
            string? rawDisplayTitle = null    // unnormalized display title for hint checks
        )
        {
            var weights = new ScoringWeights(); // or inject a configured instance

            // 1) Text score (0..1)
            double textScore = ComputeTextScore(normQueryTitle, normQueryArtist, candidateTitleNorm, candidateArtistNorm);

            // 2) Duration score (0..1)
            double durationScore = ComputeDurationScore(candidateDurationSec, mbReferenceDurationSec, weights);

            // 3) Year score (0..1)
            double yearScore = ComputeYearScore(candidateYear, mbEarliestYear, weights);

            // 4) Bonuses
            double channelBonus = ComputeChannelBonus(youtubeChannelName, youtubeChannelId, rawDisplayTitle, weights);
            double sourceBonus  = hasOfficialSourceFromImvdb ? weights.MaxSourceBonus : 0.0;

            // 5) Penalties
            double penalty = ComputePenalty(rawDisplayTitle, weights);

            // 6) Weighted sum + bonuses − penalties, clamped 0..1
            double core = (weights.WText * textScore) + (weights.WDuration * durationScore) + (weights.WYear * yearScore);
            double overall = core + channelBonus + sourceBonus - penalty;
            overall = Math.Max(0.0, Math.Min(1.0, overall));

            return new ScoreBreakdown
            {
                TextScore = textScore,
                DurationScore = durationScore,
                YearScore = yearScore,
                ChannelBonus = channelBonus,
                SourceBonus = sourceBonus,
                Penalty = penalty,
                Overall = overall
            };
        }

        // -------------------------
        // Feature scores & helpers
        // -------------------------

        // Token-based Set/Jaccard + ordered n-gram signal blended for robustness.
        private static double ComputeTextScore(string qTitle, string qArtist, string cTitle, string cArtist)
        {
            // Title similarity
            double titleScore = BlendTokenAndNgram(qTitle, cTitle);

            // Artist similarity
            double artistScore = BlendTokenAndNgram(qArtist, cArtist);

            // Strong emphasis on title, but artist matters a lot too.
            return (0.6 * titleScore) + (0.4 * artistScore);
        }

        private static double BlendTokenAndNgram(string a, string b)
        {
            var setSim = JaccardTokenSet(a, b);
            var ngram  = NormalizedNgramSim(a, b, n: 3); // trigrams
            // Weight token set higher; ngram helps for ordering/near-duplicates.
            return (0.7 * setSim) + (0.3 * ngram);
        }

        private static HashSet<string> ToTokenSet(string s)
        {
            if (string.IsNullOrWhiteSpace(s)) return new HashSet<string>();
            var tokens = Splitter.Split(s).Where(t => t.Length > 0);
            return new HashSet<string>(tokens);
        }

        private static double JaccardTokenSet(string a, string b)
        {
            var A = ToTokenSet(a);
            var B = ToTokenSet(b);
            if (A.Count == 0 && B.Count == 0) return 1.0;
            if (A.Count == 0 || B.Count == 0) return 0.0;

            int inter = A.Intersect(B).Count();
            int union = A.Union(B).Count();
            return union == 0 ? 0.0 : (double)inter / union;
        }

        private static IEnumerable<string> Ngrams(string s, int n)
        {
            if (string.IsNullOrEmpty(s)) yield break;
            var compact = string.Concat(Splitter.Split(s)); // remove spaces/punct for ngrams
            if (compact.Length < n) yield break;
            for (int i = 0; i <= compact.Length - n; i++)
                yield return compact.Substring(i, n);
        }

        private static double NormalizedNgramSim(string a, string b, int n)
        {
            var A = new HashSet<string>(Ngrams(a, n));
            var B = new HashSet<string>(Ngrams(b, n));
            if (A.Count == 0 && B.Count == 0) return 1.0;
            if (A.Count == 0 || B.Count == 0) return 0.0;
            int inter = A.Intersect(B).Count();
            int union = A.Union(B).Count();
            return union == 0 ? 0.0 : (double)inter / union;
        }

        private static double ComputeDurationScore(int? candidateSec, int? referenceSec, ScoringWeights w)
        {
            if (candidateSec is null || referenceSec is null) return 0.5; // unknowns → neutral-ish
            int diff = Math.Abs(candidateSec.Value - referenceSec.Value);

            if (diff <= w.DurationToleranceSeconds) return 1.0;
            if (diff >= w.DurationSoftCapSeconds)   return 0.0;

            // Smooth decay from tolerance to soft-cap
            double span = w.DurationSoftCapSeconds - w.DurationToleranceSeconds;
            return 1.0 - ((diff - w.DurationToleranceSeconds) / span);
        }

        private static double ComputeYearScore(int? candidateYear, int? refYear, ScoringWeights w)
        {
            if (candidateYear is null || refYear is null) return 0.5; // unknown → neutral-ish
            int delta = Math.Abs(candidateYear.Value - refYear.Value);

            if (delta <= w.YearPerfectDelta) return 1.0;
            if (delta >= w.YearSoftCap)      return 0.0;

            double span = w.YearSoftCap - w.YearPerfectDelta;
            return 1.0 - (delta / span);
        }

        private static double ComputeChannelBonus(string? channelName, string? channelId, string? rawTitle, ScoringWeights w)
        {
            if (string.IsNullOrWhiteSpace(channelName)) return 0.0;

            string cn = channelName.Trim().ToLowerInvariant();

            // Heuristics: VEVO, official artist channel (contains artist, “official”),
            // major label channels, etc. Keep conservative.
            bool looksVevo = cn.EndsWith("vevo");
            bool saysOfficial = cn.Contains("official");
            bool hasLabelHint = cn.Contains("warner") || cn.Contains("atlantic") || cn.Contains("umg") ||
                                cn.Contains("universal") || cn.Contains("sony") || cn.Contains("columbia") ||
                                cn.Contains("rca") || cn.Contains("republic") || cn.Contains("interscope") ||
                                cn.Contains("island") || cn.Contains("def jam");

            double score = 0.0;
            if (looksVevo)     score += w.MaxChannelBonus * 0.80;
            if (saysOfficial)  score += w.MaxChannelBonus * 0.60;
            if (hasLabelHint)  score += w.MaxChannelBonus * 0.50;

            // Light positive hint if title explicitly says official
            if (!string.IsNullOrWhiteSpace(rawTitle))
            {
                var rt = rawTitle.ToLowerInvariant();
                if (PositiveHints.Any(h => rt.Contains(h))) score += w.MaxChannelBonus * 0.40;
            }

            return Math.Min(w.MaxChannelBonus, score);
        }

        private static double ComputePenalty(string? rawTitle, ScoringWeights w)
        {
            if (string.IsNullOrWhiteSpace(rawTitle)) return 0.0;

            string t = rawTitle.ToLowerInvariant();
            double p = 0.0;

            // Each hit adds a small penalty; cap at MaxPenalty
            foreach (var hint in NegativeHints)
            {
                if (t.Contains(hint))
                    p += w.MaxPenalty * 0.12; // ~8 hits → capped
            }

            // Extra penalty when clearly marked non-MV
            if (t.Contains("audio only") || t.Contains("full album"))
                p += w.MaxPenalty * 0.35;

            return Math.Min(w.MaxPenalty, p);
        }
    }
}
```

## How to use it (examples)

```csharp
// Inputs you already have:
var qTitle  = QueryNormalizer.NormalizeTitle("Still Fly");
var qArtist = QueryNormalizer.NormalizeArtist("Big Tymers");

// Example: YouTube candidate
var ytScore = CandidateScorer.Score(
    normQueryTitle: qTitle,
    normQueryArtist: qArtist,
    candidateTitleNorm: QueryNormalizer.NormalizeTitle("Big Tymers - Still Fly (Official Music Video)"),
    candidateArtistNorm: QueryNormalizer.NormalizeArtist("Big Tymers"),
    candidateDurationSec: 226,
    mbReferenceDurationSec: 224,      // from MB if known; else null
    candidateYear: 2002,               // from upload/MB/IMVDb if known
    mbEarliestYear: 2002,              // MB Release Group earliest year
    hasOfficialSourceFromImvdb: false, // this is a YT-only path
    youtubeChannelName: "BigTymersVEVO",
    youtubeChannelId: "UCxxxxx",
    rawDisplayTitle: "Big Tymers - Still Fly (Official Music Video)"
);
// ytScore.Overall → sort descending across candidates

// Example: IMVDb candidate with official sources
var imvdbScore = CandidateScorer.Score(
    normQueryTitle: qTitle,
    normQueryArtist: qArtist,
    candidateTitleNorm: QueryNormalizer.NormalizeTitle("Still Fly"),
    candidateArtistNorm: QueryNormalizer.NormalizeArtist("Big Tymers"),
    candidateDurationSec: null,        // IMVDb duration unknown
    mbReferenceDurationSec: 224,
    candidateYear: 2002,
    mbEarliestYear: 2002,
    hasOfficialSourceFromImvdb: true,  // boosts confidence
    youtubeChannelName: null,
    youtubeChannelId: null,
    rawDisplayTitle: "Big Tymers – Still Fly"
);
```

### Implementation notes

* Feed `candidateDurationSec` from yt-dlp (seconds) and `mbReferenceDurationSec` from MusicBrainz `length_ms / 1000`.
* Feed `candidateYear` from YouTube upload year or IMVDb/MB dates; `mbEarliestYear` from MB release-group earliest date.
* For **IMVDb candidates with sources**, pass `hasOfficialSourceFromImvdb = true` to get a positive bump.
* Persist the entire `ScoreBreakdown` alongside each `*_candidate` row so you can audit/adjust weights later without losing explainability.
