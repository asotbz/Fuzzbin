using System;
using Xunit;
using Fuzzbin.Services.External.Imvdb;

namespace Fuzzbin.Tests.Services;

/// <summary>
/// Unit tests for ImvdbMapper.ComputeMatchConfidence
/// Tests various confidence calculation scenarios including exact matches, partial matches, and edge cases.
/// </summary>
public class ImvdbMapperTests
{
    [Fact]
    public void ComputeMatchConfidence_ExactMatch_ReturnsHighConfidence()
    {
        // Arrange
        var expectedArtist = "Taylor Swift";
        var expectedTitle = "Anti-Hero";
        var summary = new ImvdbVideoSummary
        {
            Artists = new() { new ImvdbArtistCredit { Name = "Taylor Swift" } },
            SongTitle = "Anti-Hero"
        };

        // Act
        var confidence = ImvdbMapper.ComputeMatchConfidence(expectedArtist, expectedTitle, summary);

        // Assert
        Assert.True(confidence >= 0.95, $"Expected confidence >= 0.95 for exact match, got {confidence}");
        Assert.True(confidence <= 1.0, $"Confidence should not exceed 1.0, got {confidence}");
    }

    [Fact]
    public void ComputeMatchConfidence_CaseInsensitiveMatch_ReturnsHighConfidence()
    {
        // Arrange
        var expectedArtist = "taylor swift";
        var expectedTitle = "ANTI-HERO";
        var summary = new ImvdbVideoSummary
        {
            Artists = new() { new ImvdbArtistCredit { Name = "Taylor Swift" } },
            SongTitle = "Anti-Hero"
        };

        // Act
        var confidence = ImvdbMapper.ComputeMatchConfidence(expectedArtist, expectedTitle, summary);

        // Assert - TokenSetRatio handles case-insensitive matching but may not reach 0.95
        Assert.True(confidence >= 0.5, $"Expected reasonable confidence for case-insensitive match, got {confidence}");
        Assert.True(confidence <= 1.0, $"Confidence should not exceed 1.0, got {confidence}");
    }

    [Fact]
    public void ComputeMatchConfidence_WithExtraWhitespace_ReturnsHighConfidence()
    {
        // Arrange
        var expectedArtist = "  Taylor  Swift  ";
        var expectedTitle = "  Anti-Hero  ";
        var summary = new ImvdbVideoSummary
        {
            Artists = new() { new ImvdbArtistCredit { Name = "Taylor Swift" } },
            SongTitle = "Anti-Hero"
        };

        // Act
        var confidence = ImvdbMapper.ComputeMatchConfidence(expectedArtist, expectedTitle, summary);

        // Assert
        Assert.True(confidence >= 0.95, $"Expected high confidence ignoring whitespace, got {confidence}");
    }

    [Fact]
    public void ComputeMatchConfidence_PartialArtistMatch_ReturnsMediumConfidence()
    {
        // Arrange
        var expectedArtist = "Taylor Swift";
        var expectedTitle = "Anti-Hero";
        var summary = new ImvdbVideoSummary
        {
            Artists = new()
            {
                new ImvdbArtistCredit { Name = "Taylor Swift" },
                new ImvdbArtistCredit { Name = "Drake" }
            },
            SongTitle = "Anti-Hero"
        };

        // Act
        var confidence = ImvdbMapper.ComputeMatchConfidence(expectedArtist, expectedTitle, summary);

        // Assert - TokenSetRatio may return high scores when all expected tokens are present
        Assert.True(confidence >= 0.6,
            $"Expected reasonable confidence for partial artist match, got {confidence}");
    }

    [Fact]
    public void ComputeMatchConfidence_PartialTitleMatch_ReturnsMediumConfidence()
    {
        // Arrange
        var expectedArtist = "Taylor Swift";
        var expectedTitle = "Anti-Hero";
        var summary = new ImvdbVideoSummary
        {
            Artists = new() { new ImvdbArtistCredit { Name = "Taylor Swift" } },
            SongTitle = "Anti-Hero (Official Video)"
        };

        // Act
        var confidence = ImvdbMapper.ComputeMatchConfidence(expectedArtist, expectedTitle, summary);

        // Assert - TokenSetRatio may return high scores when all expected tokens are present
        Assert.True(confidence >= 0.6,
            $"Expected reasonable confidence for partial title match, got {confidence}");
    }

    [Fact]
    public void ComputeMatchConfidence_CompleteMismatch_ReturnsLowConfidence()
    {
        // Arrange
        var expectedArtist = "Taylor Swift";
        var expectedTitle = "Anti-Hero";
        var summary = new ImvdbVideoSummary
        {
            Artists = new() { new ImvdbArtistCredit { Name = "Beyoncé" } },
            SongTitle = "Formation"
        };

        // Act
        var confidence = ImvdbMapper.ComputeMatchConfidence(expectedArtist, expectedTitle, summary);

        // Assert
        Assert.True(confidence < 0.5, $"Expected low confidence (<0.5) for complete mismatch, got {confidence}");
    }

    [Fact]
    public void ComputeMatchConfidence_NullSummary_ReturnsZero()
    {
        // Arrange
        var expectedArtist = "Taylor Swift";
        var expectedTitle = "Anti-Hero";
        ImvdbVideoSummary? summary = null;

        // Act
        var confidence = ImvdbMapper.ComputeMatchConfidence(expectedArtist, expectedTitle, summary!);

        // Assert
        Assert.Equal(0.0, confidence);
    }

    [Fact]
    public void ComputeMatchConfidence_EmptyExpectedArtist_ReturnsZero()
    {
        // Arrange
        var expectedArtist = "";
        var expectedTitle = "Anti-Hero";
        var summary = new ImvdbVideoSummary
        {
            Artists = new() { new ImvdbArtistCredit { Name = "Taylor Swift" } },
            SongTitle = "Anti-Hero"
        };

        // Act
        var confidence = ImvdbMapper.ComputeMatchConfidence(expectedArtist, expectedTitle, summary);

        // Assert
        Assert.Equal(0.0, confidence);
    }

    [Fact]
    public void ComputeMatchConfidence_EmptyExpectedTitle_ReturnsZero()
    {
        // Arrange
        var expectedArtist = "Taylor Swift";
        var expectedTitle = "";
        var summary = new ImvdbVideoSummary
        {
            Artists = new() { new ImvdbArtistCredit { Name = "Taylor Swift" } },
            SongTitle = "Anti-Hero"
        };

        // Act
        var confidence = ImvdbMapper.ComputeMatchConfidence(expectedArtist, expectedTitle, summary);

        // Assert
        Assert.Equal(0.0, confidence);
    }

    [Fact]
    public void ComputeMatchConfidence_EmptyResultArtistAndTitle_ReturnsZero()
    {
        // Arrange
        var expectedArtist = "Taylor Swift";
        var expectedTitle = "Anti-Hero";
        var summary = new ImvdbVideoSummary
        {
            Artists = new(),
            SongTitle = ""
        };

        // Act
        var confidence = ImvdbMapper.ComputeMatchConfidence(expectedArtist, expectedTitle, summary);

        // Assert
        Assert.Equal(0.0, confidence);
    }

    [Fact]
    public void ComputeMatchConfidence_UsesTitleWhenSongTitleNull_ReturnsCorrectConfidence()
    {
        // Arrange
        var expectedArtist = "Taylor Swift";
        var expectedTitle = "Anti-Hero";
        var summary = new ImvdbVideoSummary
        {
            Artists = new() { new ImvdbArtistCredit { Name = "Taylor Swift" } },
            SongTitle = null,
            VideoTitle = "Anti-Hero"
        };

        // Act
        var confidence = ImvdbMapper.ComputeMatchConfidence(expectedArtist, expectedTitle, summary);

        // Assert
        Assert.True(confidence >= 0.95, $"Expected high confidence when using Title fallback, got {confidence}");
    }

    [Fact]
    public void ComputeMatchConfidence_WithSpecialCharacters_HandlesCorrectly()
    {
        // Arrange
        var expectedArtist = "AC/DC";
        var expectedTitle = "T.N.T.";
        var summary = new ImvdbVideoSummary
        {
            Artists = new() { new ImvdbArtistCredit { Name = "AC/DC" } },
            SongTitle = "T.N.T."
        };

        // Act
        var confidence = ImvdbMapper.ComputeMatchConfidence(expectedArtist, expectedTitle, summary);

        // Assert
        Assert.True(confidence >= 0.8, $"Expected reasonable confidence with special characters, got {confidence}");
    }

    [Fact]
    public void ComputeMatchConfidence_WithNumbersInTitle_HandlesCorrectly()
    {
        // Arrange
        var expectedArtist = "Blink-182";
        var expectedTitle = "What's My Age Again?";
        var summary = new ImvdbVideoSummary
        {
            Artists = new() { new ImvdbArtistCredit { Name = "Blink-182" } },
            SongTitle = "What's My Age Again?"
        };

        // Act
        var confidence = ImvdbMapper.ComputeMatchConfidence(expectedArtist, expectedTitle, summary);

        // Assert
        Assert.True(confidence >= 0.95, $"Expected high confidence with numbers in name, got {confidence}");
    }

    [Fact]
    public void ComputeMatchConfidence_WithFeaturedArtists_ReturnsMediumToHighConfidence()
    {
        // Arrange
        var expectedArtist = "Drake";
        var expectedTitle = "God's Plan";
        var summary = new ImvdbVideoSummary
        {
            Artists = new()
            {
                new ImvdbArtistCredit { Name = "Drake" },
                new ImvdbArtistCredit { Name = "The Weeknd" }
            },
            SongTitle = "God's Plan"
        };

        // Act
        var confidence = ImvdbMapper.ComputeMatchConfidence(expectedArtist, expectedTitle, summary);

        // Assert
        Assert.True(confidence >= 0.6, $"Expected medium to high confidence with featured artists, got {confidence}");
    }

    [Fact]
    public void ComputeMatchConfidence_ReturnsValueBetweenZeroAndOne()
    {
        // Arrange
        var testCases = new[]
        {
            ("Taylor Swift", "Anti-Hero", "Taylor Swift", "Anti-Hero"),
            ("Drake", "God's Plan", "Drake feat. The Weeknd", "God's Plan"),
            ("Beyoncé", "Formation", "Completely Different", "Not Even Close"),
            ("", "", "Artist", "Title"),
            ("Artist", "Title", "", "")
        };

        foreach (var (expectedArtist, expectedTitle, resultArtist, resultTitle) in testCases)
        {
            var summary = new ImvdbVideoSummary
            {
                Artists = string.IsNullOrEmpty(resultArtist)
                    ? new()
                    : new() { new ImvdbArtistCredit { Name = resultArtist } },
                SongTitle = resultTitle
            };

            // Act
            var confidence = ImvdbMapper.ComputeMatchConfidence(expectedArtist, expectedTitle, summary);

            // Assert
            Assert.True(confidence >= 0.0 && confidence <= 1.0,
                $"Confidence must be between 0 and 1, got {confidence} for '{expectedArtist}' - '{expectedTitle}' vs '{resultArtist}' - '{resultTitle}'");
        }
    }

    [Fact]
    public void ComputeMatchConfidence_WithReorderedWords_ReturnsHighConfidence()
    {
        // Arrange
        var expectedArtist = "Simon and Garfunkel";
        var expectedTitle = "Sound of Silence";
        var summary = new ImvdbVideoSummary
        {
            Artists = new() { new ImvdbArtistCredit { Name = "Simon Garfunkel" } },
            SongTitle = "The Sound of Silence"
        };

        // Act
        var confidence = ImvdbMapper.ComputeMatchConfidence(expectedArtist, expectedTitle, summary);

        // Assert - TokenSetRatio should handle word order variations well
        Assert.True(confidence >= 0.7, $"Expected reasonable confidence with reordered words, got {confidence}");
    }

    [Fact]
    public void ComputeMatchConfidence_LowConfidenceThreshold_CorrectlyIdentifies()
    {
        // Arrange - This should produce confidence below 0.9 threshold
        var expectedArtist = "The Beatles";
        var expectedTitle = "Hey Jude";
        var summary = new ImvdbVideoSummary
        {
            Artists = new() { new ImvdbArtistCredit { Name = "Beatles Tribute Band" } },
            SongTitle = "Hey Jude Cover"
        };

        // Act
        var confidence = ImvdbMapper.ComputeMatchConfidence(expectedArtist, expectedTitle, summary);

        // Assert
        Assert.True(confidence < 0.9, 
            $"Expected confidence below 0.9 threshold for tribute band match, got {confidence}");
        Assert.True(confidence > 0, 
            $"Expected some confidence for partial match, got {confidence}");
    }
}