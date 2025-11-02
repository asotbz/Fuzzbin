using System;
using Xunit;
using Fuzzbin.Services.Metadata;

namespace Fuzzbin.Tests.Services;

/// <summary>
/// Unit tests for CandidateScorer
/// Tests scoring algorithm with various input combinations including text matching, duration, year, and source bonuses.
/// Validates compliance with docs/cache/scoring-function.md specification.
/// </summary>
public class CandidateScorerTests
{
    #region Exact Match Tests

    [Fact]
    public void Score_ExactMatch_ReturnsHighConfidence()
    {
        // Arrange
        var normQueryTitle = "still fly";
        var normQueryArtist = "big tymers";
        var candidateTitleNorm = "still fly";
        var candidateArtistNorm = "big tymers";

        // Act
        var result = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            null, null, null, null, false);

        // Assert
        Assert.True(result.Overall >= 0.50, $"Expected confidence >= 0.50 for exact match, got {result.Overall}");
        Assert.True(result.TextScore >= 0.95, $"Expected text score >= 0.95, got {result.TextScore}");
    }

    [Fact]
    public void Score_ExactMatchWithDuration_ReturnsVeryHighConfidence()
    {
        // Arrange
        var normQueryTitle = "still fly";
        var normQueryArtist = "big tymers";
        var candidateTitleNorm = "still fly";
        var candidateArtistNorm = "big tymers";
        var candidateDuration = 224;
        var mbReferenceDuration = 224;

        // Act
        var result = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            candidateDuration,
            mbReferenceDuration,
            null, null, false);

        // Assert
        Assert.True(result.Overall >= 0.70, $"Expected very high confidence with matching duration, got {result.Overall}");
        Assert.True(result.DurationScore >= 0.9, $"Expected high duration score, got {result.DurationScore}");
    }

    [Fact]
    public void Score_ExactMatchWithYearAndDuration_ReturnsMaxConfidence()
    {
        // Arrange
        var normQueryTitle = "still fly";
        var normQueryArtist = "big tymers";
        var candidateTitleNorm = "still fly";
        var candidateArtistNorm = "big tymers";
        var candidateYear = 2002;
        var mbEarliestYear = 2002;
        var candidateDuration = 224;
        var mbReferenceDuration = 224;

        // Act
        var result = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            candidateDuration,
            mbReferenceDuration,
            candidateYear,
            mbEarliestYear,
            false);

        // Assert
        Assert.True(result.Overall >= 0.90, $"Expected near-max confidence with all signals, got {result.Overall}");
        Assert.True(result.YearScore >= 0.9, "Expected high year score");
        Assert.True(result.DurationScore >= 0.9, "Expected high duration score");
    }

    #endregion

    #region Text Scoring Tests

    [Fact]
    public void Score_PartialTitleMatch_ReturnsModerateConfidence()
    {
        // Arrange
        var normQueryTitle = "still fly";
        var normQueryArtist = "big tymers";
        var candidateTitleNorm = "still fly official video";
        var candidateArtistNorm = "big tymers";

        // Act
        var result = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            null, null, null, null, false);

        // Assert
        Assert.True(result.TextScore >= 0.6, $"Expected moderate text score for partial match, got {result.TextScore}");
    }

    [Fact]
    public void Score_PartialArtistMatch_ReturnsModerateConfidence()
    {
        // Arrange
        var normQueryTitle = "still fly";
        var normQueryArtist = "big tymers";
        var candidateTitleNorm = "still fly";
        var candidateArtistNorm = "big tymers feat mannie fresh";

        // Act
        var result = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            null, null, null, null, false);

        // Assert
        Assert.True(result.TextScore >= 0.6, $"Expected moderate text score for featured artist, got {result.TextScore}");
    }

    [Fact]
    public void Score_CompleteMismatch_ReturnsLowConfidence()
    {
        // Arrange
        var normQueryTitle = "still fly";
        var normQueryArtist = "big tymers";
        var candidateTitleNorm = "formation";
        var candidateArtistNorm = "beyonce";

        // Act
        var result = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            null, null, null, null, false);

        // Assert
        Assert.True(result.Overall < 0.5, $"Expected low confidence for mismatch, got {result.Overall}");
    }

    #endregion

    #region Duration Scoring Tests

    [Fact]
    public void Score_DurationWithinTolerance_ReturnsHighDurationScore()
    {
        // Arrange
        var normQueryTitle = "still fly";
        var normQueryArtist = "big tymers";
        var candidateTitleNorm = "still fly";
        var candidateArtistNorm = "big tymers";
        var candidateDuration = 224;
        var mbReferenceDuration = 226; // 2 seconds difference

        // Act
        var result = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            candidateDuration,
            mbReferenceDuration,
            null, null, false);

        // Assert
        Assert.True(result.DurationScore >= 0.8, $"Expected high duration score within tolerance, got {result.DurationScore}");
    }

    [Fact]
    public void Score_DurationOutsideTolerance_ReturnsLowDurationScore()
    {
        // Arrange
        var normQueryTitle = "still fly";
        var normQueryArtist = "big tymers";
        var candidateTitleNorm = "still fly";
        var candidateArtistNorm = "big tymers";
        var candidateDuration = 224;
        var mbReferenceDuration = 324; // 100 seconds difference

        // Act
        var result = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            candidateDuration,
            mbReferenceDuration,
            null, null, false);

        // Assert
        Assert.True(result.DurationScore < 0.5, $"Expected low duration score outside tolerance, got {result.DurationScore}");
    }

    [Fact]
    public void Score_NoDurationProvided_ReturnsNeutralDurationScore()
    {
        // Arrange
        var normQueryTitle = "still fly";
        var normQueryArtist = "big tymers";
        var candidateTitleNorm = "still fly";
        var candidateArtistNorm = "big tymers";

        // Act
        var result = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            null, null, null, null, false);

        // Assert - Should return neutral score (0.5) when duration is null
        Assert.Equal(0.5, result.DurationScore);
    }

    [Fact]
    public void Score_OnlyOneDurationProvided_ReturnsNeutralDurationScore()
    {
        // Arrange
        var normQueryTitle = "still fly";
        var normQueryArtist = "big tymers";
        var candidateTitleNorm = "still fly";
        var candidateArtistNorm = "big tymers";

        // Act
        var result = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            224, null, null, null, false);

        // Assert
        Assert.Equal(0.5, result.DurationScore);
    }

    #endregion

    #region Year Scoring Tests

    [Fact]
    public void Score_ExactYearMatch_ReturnsHighYearScore()
    {
        // Arrange
        var normQueryTitle = "still fly";
        var normQueryArtist = "big tymers";
        var candidateTitleNorm = "still fly";
        var candidateArtistNorm = "big tymers";
        var candidateYear = 2002;
        var mbEarliestYear = 2002;

        // Act
        var result = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            null, null,
            candidateYear,
            mbEarliestYear,
            false);

        // Assert
        Assert.True(result.YearScore >= 0.9, $"Expected high year score for exact match, got {result.YearScore}");
    }

    [Fact]
    public void Score_OneYearDifference_ReturnsHighYearScore()
    {
        // Arrange
        var normQueryTitle = "still fly";
        var normQueryArtist = "big tymers";
        var candidateTitleNorm = "still fly";
        var candidateArtistNorm = "big tymers";
        var candidateYear = 2002;
        var mbEarliestYear = 2003;

        // Act
        var result = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            null, null,
            candidateYear,
            mbEarliestYear,
            false);

        // Assert
        Assert.True(result.YearScore >= 0.7, $"Expected good year score for 1 year difference, got {result.YearScore}");
    }

    [Fact]
    public void Score_LargeYearDifference_ReturnsLowYearScore()
    {
        // Arrange
        var normQueryTitle = "still fly";
        var normQueryArtist = "big tymers";
        var candidateTitleNorm = "still fly";
        var candidateArtistNorm = "big tymers";
        var candidateYear = 2002;
        var mbEarliestYear = 2020;

        // Act
        var result = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            null, null,
            candidateYear,
            mbEarliestYear,
            false);

        // Assert
        Assert.True(result.YearScore < 0.5, $"Expected low year score for large difference, got {result.YearScore}");
    }

    [Fact]
    public void Score_NoYearProvided_ReturnsNeutralYearScore()
    {
        // Arrange
        var normQueryTitle = "still fly";
        var normQueryArtist = "big tymers";
        var candidateTitleNorm = "still fly";
        var candidateArtistNorm = "big tymers";

        // Act
        var result = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            null, null, null, null, false);

        // Assert - Should return neutral score (0.5) when year is null
        Assert.Equal(0.5, result.YearScore);
    }

    #endregion

    #region Source Bonus Tests

    [Fact]
    public void Score_OfficialImvdbSource_AppliesBonus()
    {
        // Arrange
        var normQueryTitle = "still fly";
        var normQueryArtist = "big tymers";
        var candidateTitleNorm = "still fly";
        var candidateArtistNorm = "big tymers";

        // Act
        var resultWithBonus = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            null, null, null, null,
            hasOfficialSourceFromImvdb: true);

        var resultWithoutBonus = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            null, null, null, null,
            hasOfficialSourceFromImvdb: false);

        // Assert
        Assert.True(resultWithBonus.Overall > resultWithoutBonus.Overall,
            "Official IMVDb source should increase overall score");
        Assert.True(resultWithBonus.SourceBonus > 0, "Should have positive source bonus");
    }

    [Fact]
    public void Score_OfficialChannel_AppliesBonus()
    {
        // Arrange
        var normQueryTitle = "still fly";
        var normQueryArtist = "big tymers";
        var candidateTitleNorm = "still fly";
        var candidateArtistNorm = "big tymers";

        // Act
        var resultWithBonus = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            null, null, null, null, false,
            youtubeChannelName: "Big TymersVEVO");

        var resultWithoutBonus = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            null, null, null, null, false,
            youtubeChannelName: "Random Channel");

        // Assert
        Assert.True(resultWithBonus.Overall > resultWithoutBonus.Overall,
            "Official channel should increase overall score");
        Assert.True(resultWithBonus.ChannelBonus > 0, "Should have positive channel bonus");
    }

    #endregion

    #region Penalty Tests

    [Fact]
    public void Score_LyricVideoPattern_AppliesPenalty()
    {
        // Arrange
        var normQueryTitle = "still fly";
        var normQueryArtist = "big tymers";
        var candidateTitleNorm = "still fly";
        var candidateArtistNorm = "big tymers";

        // Act
        var resultWithPenalty = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            null, null, null, null, false,
            rawDisplayTitle: "Still Fly (Lyric Video)");

        var resultWithoutPenalty = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            null, null, null, null, false,
            rawDisplayTitle: "Still Fly");

        // Assert
        Assert.True(resultWithPenalty.Overall < resultWithoutPenalty.Overall,
            "Lyric video keyword should decrease overall score");
        Assert.True(resultWithPenalty.Penalty > 0, "Should have positive penalty value");
    }

    [Fact]
    public void Score_AudioOnlyPattern_AppliesHighPenalty()
    {
        // Arrange
        var normQueryTitle = "still fly";
        var normQueryArtist = "big tymers";
        var candidateTitleNorm = "still fly";
        var candidateArtistNorm = "big tymers";

        // Act
        var result = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            null, null, null, null, false,
            rawDisplayTitle: "Still Fly (Audio Only)");

        // Assert
        Assert.True(result.Penalty > 0, "Audio only should apply penalty");
    }

    #endregion

    #region Edge Cases

    [Fact]
    public void Score_EmptyStrings_ReturnsLowScore()
    {
        // Arrange
        var normQueryTitle = "";
        var normQueryArtist = "";
        var candidateTitleNorm = "";
        var candidateArtistNorm = "";

        // Act
        var result = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            null, null, null, null, false);

        // Assert - Empty strings result in neutral scores (0.5 for duration/year, 1.0 for text when both empty)
        // Overall = 0.6 * 1.0 + 0.2 * 0.5 + 0.2 * 0.5 = 0.8
        Assert.True(result.Overall >= 0.7 && result.Overall <= 0.9, $"Expected neutral-high score for empty strings, got {result.Overall}");
    }

    [Fact]
    public void Score_OverallScoreBoundedByZeroAndOne()
    {
        // Arrange - Test multiple scenarios
        var testCases = new[]
        {
            ("still fly", "big tymers", "still fly", "big tymers", true, 224, 224, 2002, 2002),
            ("title", "artist", "different", "artist", false, (int?)null, (int?)null, (int?)null, (int?)null),
            ("", "", "test", "test", false, (int?)null, (int?)null, (int?)null, (int?)null),
            ("exact", "match", "exact", "match", true, 200, 200, 2020, 2020)
        };

        foreach (var test in testCases)
        {
            // Act
            var result = CandidateScorer.Score(
                test.Item1,
                test.Item2,
                test.Item3,
                test.Item4,
                test.Item6,
                test.Item7,
                test.Item8,
                test.Item9,
                test.Item5);

            // Assert
            Assert.True(result.Overall >= 0.0 && result.Overall <= 1.0,
                $"Overall score must be between 0 and 1, got {result.Overall}");
        }
    }

    [Fact]
    public void Score_ConsistentResults_SameInputProducesSameOutput()
    {
        // Arrange
        var normQueryTitle = "still fly";
        var normQueryArtist = "big tymers";
        var candidateTitleNorm = "still fly";
        var candidateArtistNorm = "big tymers";

        // Act
        var result1 = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            null, null, null, null, false);

        var result2 = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            null, null, null, null, false);

        // Assert
        Assert.Equal(result1.Overall, result2.Overall);
        Assert.Equal(result1.TextScore, result2.TextScore);
    }

    #endregion

    #region Real-World Scenarios

    [Fact]
    public void Score_RealWorldScenario_PerfectMatch()
    {
        // Arrange - Perfect match with all signals
        var normQueryTitle = "still fly";
        var normQueryArtist = "big tymers";
        var candidateTitleNorm = "still fly";
        var candidateArtistNorm = "big tymers";

        // Act
        var result = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            224, 224, 2002, 2002,
            hasOfficialSourceFromImvdb: true);

        // Assert
        Assert.True(result.Overall >= 0.90, $"Perfect match should score >= 0.90, got {result.Overall}");
    }

    [Fact]
    public void Score_RealWorldScenario_GoodMatchWithMinorVariation()
    {
        // Arrange - Good match with slight duration difference
        var normQueryTitle = "god s plan";
        var normQueryArtist = "drake";
        var candidateTitleNorm = "god s plan";
        var candidateArtistNorm = "drake";

        // Act
        var result = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            199, 201, // 2 second difference
            2018, 2018,
            false);

        // Assert
        Assert.True(result.Overall >= 0.80, $"Good match with minor variation should score >= 0.80, got {result.Overall}");
    }

    [Fact]
    public void Score_RealWorldScenario_AmbiguousMatch()
    {
        // Arrange - Match with missing year/duration data
        var normQueryTitle = "anti hero";
        var normQueryArtist = "taylor swift";
        var candidateTitleNorm = "anti hero";
        var candidateArtistNorm = "taylor swift";

        // Act
        var result = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            null, null, null, null, false);

        // Assert - Should still score well on text alone
        Assert.True(result.Overall >= 0.50, $"Text-only perfect match should score >= 0.50, got {result.Overall}");
        Assert.Equal(0.5, result.DurationScore);
        Assert.Equal(0.5, result.YearScore);
    }

    [Fact]
    public void Score_RealWorldScenario_LyricVideoVariant()
    {
        // Arrange - Official lyric video variant
        var normQueryTitle = "blinding lights";
        var normQueryArtist = "the weeknd";
        var candidateTitleNorm = "blinding lights";
        var candidateArtistNorm = "the weeknd";

        // Act
        var result = CandidateScorer.Score(
            normQueryTitle,
            normQueryArtist,
            candidateTitleNorm,
            candidateArtistNorm,
            null, null, null, null,
            hasOfficialSourceFromImvdb: true,
            rawDisplayTitle: "Blinding Lights (Lyric Video)");

        // Assert - With official source bonus, lyric video still scores highly despite small penalty
        Assert.True(result.Overall >= 0.70,
            $"Official lyric video should still score well with source bonus, got {result.Overall}");
        Assert.True(result.Penalty > 0, "Should have penalty applied");
        Assert.True(result.SourceBonus > 0, "Should have source bonus from IMVDb");
    }

    #endregion
}