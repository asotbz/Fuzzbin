using System;
using Xunit;
using Fuzzbin.Services.Metadata;

namespace Fuzzbin.Tests.Services;

/// <summary>
/// Unit tests for QueryNormalizer
/// Tests various normalization scenarios including Unicode handling, featured artist removal, and edge cases.
/// Validates compliance with docs/cache/normalizer.md specification.
/// </summary>
public class QueryNormalizerTests
{
    #region NormalizeTitle Tests

    [Fact]
    public void NormalizeTitle_BasicString_ReturnsLowercaseWithoutPunctuation()
    {
        // Arrange
        var input = "Still Fly";

        // Act
        var result = QueryNormalizer.NormalizeTitle(input);

        // Assert
        Assert.Equal("still fly", result);
    }

    [Fact]
    public void NormalizeTitle_RemovesFeaturedArtistsFromEnd()
    {
        // Arrange
        var input = "Still Fly (feat. Mannie Fresh)";

        // Act
        var result = QueryNormalizer.NormalizeTitle(input);

        // Assert
        Assert.Equal("still fly", result);
    }

    [Fact]
    public void NormalizeTitle_RemovesFtVariant()
    {
        // Arrange
        var input = "Song Title ft. Artist Name";

        // Act
        var result = QueryNormalizer.NormalizeTitle(input);

        // Assert
        Assert.Equal("song title", result);
    }

    [Fact]
    public void NormalizeTitle_RemovesFeaturingVariant()
    {
        // Arrange
        var input = "Song Title featuring Artist Name";

        // Act
        var result = QueryNormalizer.NormalizeTitle(input);

        // Assert
        Assert.Equal("song title", result);
    }

    [Fact]
    public void NormalizeTitle_RemovesPunctuation()
    {
        // Arrange
        var input = "What's My Age Again?";

        // Act
        var result = QueryNormalizer.NormalizeTitle(input);

        // Assert
        Assert.Equal("what s my age again", result);
    }

    [Fact]
    public void NormalizeTitle_RemovesUnicodeAccents()
    {
        // Arrange
        var input = "Café Noir";

        // Act
        var result = QueryNormalizer.NormalizeTitle(input);

        // Assert
        Assert.Equal("cafe noir", result);
    }

    [Fact]
    public void NormalizeTitle_RemovesSingleLetterStopWord()
    {
        // Arrange
        var input = "A Song Title";

        // Act
        var result = QueryNormalizer.NormalizeTitle(input);

        // Assert
        Assert.Equal("song title", result);
    }

    [Fact]
    public void NormalizeTitle_PreservesTwoLetterWords()
    {
        // Arrange
        var input = "In Da Club";

        // Act
        var result = QueryNormalizer.NormalizeTitle(input);

        // Assert
        Assert.Contains("in", result);
        Assert.Contains("da", result);
    }

    [Fact]
    public void NormalizeTitle_CollapsesMultipleSpaces()
    {
        // Arrange
        var input = "Title   With    Spaces";

        // Act
        var result = QueryNormalizer.NormalizeTitle(input);

        // Assert
        Assert.Equal("title with spaces", result);
        Assert.DoesNotContain("  ", result); // No double spaces
    }

    [Fact]
    public void NormalizeTitle_EmptyString_ReturnsEmpty()
    {
        // Arrange
        var input = "";

        // Act
        var result = QueryNormalizer.NormalizeTitle(input);

        // Assert
        Assert.Equal("", result);
    }

    [Fact]
    public void NormalizeTitle_NullString_ReturnsEmpty()
    {
        // Arrange
        string? input = null;

        // Act
        var result = QueryNormalizer.NormalizeTitle(input!);

        // Assert
        Assert.Equal("", result);
    }

    [Fact]
    public void NormalizeTitle_WhitespaceOnly_ReturnsEmpty()
    {
        // Arrange
        var input = "   ";

        // Act
        var result = QueryNormalizer.NormalizeTitle(input);

        // Assert
        Assert.Equal("", result);
    }

    #endregion

    #region NormalizeArtist Tests

    [Fact]
    public void NormalizeArtist_BasicString_ReturnsLowercaseWithoutPunctuation()
    {
        // Arrange
        var input = "Big Tymers";

        // Act
        var result = QueryNormalizer.NormalizeArtist(input);

        // Assert
        Assert.Equal("big tymers", result);
    }

    [Fact]
    public void NormalizeArtist_PreservesFeaturedArtists()
    {
        // Arrange
        var input = "Drake feat. The Weeknd";

        // Act
        var result = QueryNormalizer.NormalizeArtist(input);

        // Assert
        Assert.Contains("drake", result);
        Assert.Contains("feat", result);
        Assert.Contains("weeknd", result);
    }

    [Fact]
    public void NormalizeArtist_NormalizesFeatVariants()
    {
        // Arrange
        var input = "Artist ft. Other";

        // Act
        var result = QueryNormalizer.NormalizeArtist(input);

        // Assert
        Assert.Contains("feat", result); // All variants normalized to "feat"
    }

    [Fact]
    public void NormalizeArtist_RemovesPunctuation()
    {
        // Arrange
        var input = "AC/DC";

        // Act
        var result = QueryNormalizer.NormalizeArtist(input);

        // Assert
        Assert.Equal("ac dc", result);
    }

    [Fact]
    public void NormalizeArtist_HandlesUnicodeCharacters()
    {
        // Arrange
        var input = "Beyoncé";

        // Act
        var result = QueryNormalizer.NormalizeArtist(input);

        // Assert
        Assert.Equal("beyonce", result);
    }

    #endregion

    #region NormalizePair Tests

    [Fact]
    public void NormalizePair_ReturnsCorrectTuple()
    {
        // Arrange
        var title = "Still Fly";
        var artist = "Big Tymers";

        // Act
        var (normTitle, normArtist, comboKey) = QueryNormalizer.NormalizePair(title, artist);

        // Assert
        Assert.Equal("still fly", normTitle);
        Assert.Equal("big tymers", normArtist);
        Assert.Equal("big tymers||still fly", comboKey);
    }

    [Fact]
    public void NormalizePair_ComboKeyFormat_ArtistPipeTitleFormat()
    {
        // Arrange
        var title = "Test Title";
        var artist = "Test Artist";

        // Act
        var (_, _, comboKey) = QueryNormalizer.NormalizePair(title, artist);

        // Assert
        Assert.Contains("||", comboKey);
        Assert.StartsWith("test artist||", comboKey);
        Assert.EndsWith("||test title", comboKey);
    }

    [Fact]
    public void NormalizePair_TitleRemovesFeaturedArtists()
    {
        // Arrange
        var title = "Song feat. Someone";
        var artist = "Main Artist";

        // Act
        var (normTitle, _, _) = QueryNormalizer.NormalizePair(title, artist);

        // Assert
        Assert.Equal("song", normTitle);
        Assert.DoesNotContain("feat", normTitle);
    }

    [Fact]
    public void NormalizePair_ArtistPreservesFeaturedArtists()
    {
        // Arrange
        var title = "Song Title";
        var artist = "Main feat. Featured";

        // Act
        var (_, normArtist, _) = QueryNormalizer.NormalizePair(title, artist);

        // Assert
        Assert.Contains("feat", normArtist);
    }

    [Fact]
    public void NormalizePair_HandlesNullInputs()
    {
        // Arrange
        string? title = null;
        string? artist = null;

        // Act
        var (normTitle, normArtist, comboKey) = QueryNormalizer.NormalizePair(title!, artist!);

        // Assert
        Assert.Equal("", normTitle);
        Assert.Equal("", normArtist);
        Assert.Equal("||", comboKey);
    }

    #endregion

    #region Unicode and Special Character Tests

    [Fact]
    public void Normalize_HandlesGermanUmlauts()
    {
        // Arrange
        var input = "Für Elise";

        // Act
        var result = QueryNormalizer.NormalizeTitle(input);

        // Assert
        Assert.Equal("fur elise", result);
    }

    [Fact]
    public void Normalize_HandlesSpanishAccents()
    {
        // Arrange
        var input = "Música";

        // Act
        var result = QueryNormalizer.NormalizeTitle(input);

        // Assert
        Assert.Equal("musica", result);
    }

    [Fact]
    public void Normalize_HandlesFrenchAccents()
    {
        // Arrange
        var input = "Crème Brûlée";

        // Act
        var result = QueryNormalizer.NormalizeTitle(input);

        // Assert
        Assert.Equal("creme brulee", result);
    }

    [Fact]
    public void Normalize_RemovesEmojis()
    {
        // Arrange
        var input = "Song Title 🎵🎶";

        // Act
        var result = QueryNormalizer.NormalizeTitle(input);

        // Assert
        Assert.Equal("song title", result);
    }

    #endregion

    #region Edge Cases

    [Fact]
    public void Normalize_VeryLongString_HandlesCorrectly()
    {
        // Arrange
        var input = string.Concat(Enumerable.Repeat("Word ", 1000));

        // Act
        var result = QueryNormalizer.NormalizeTitle(input);

        // Assert
        Assert.NotNull(result);
        Assert.Contains("word", result);
    }

    [Fact]
    public void Normalize_OnlyPunctuation_ReturnsEmpty()
    {
        // Arrange
        var input = "!!!???...";

        // Act
        var result = QueryNormalizer.NormalizeTitle(input);

        // Assert
        Assert.Equal("", result);
    }

    [Fact]
    public void Normalize_OnlyStopWords_ReturnsEmpty()
    {
        // Arrange
        var input = "a a a";

        // Act
        var result = QueryNormalizer.NormalizeTitle(input);

        // Assert
        Assert.Equal("", result);
    }

    [Fact]
    public void Normalize_MixedCaseWithNumbers_HandlesCorrectly()
    {
        // Arrange
        var input = "Blink-182";

        // Act
        var result = QueryNormalizer.NormalizeArtist(input);

        // Assert
        Assert.Contains("blink", result);
        Assert.Contains("182", result);
    }

    [Fact]
    public void Normalize_ConsistentResults_SameInputProducesSameOutput()
    {
        // Arrange
        var input = "Test Title feat. Artist";

        // Act
        var result1 = QueryNormalizer.NormalizeTitle(input);
        var result2 = QueryNormalizer.NormalizeTitle(input);

        // Assert
        Assert.Equal(result1, result2);
    }

    #endregion

    #region Real-World Examples

    [Fact]
    public void NormalizePair_RealWorldExample_StillFly()
    {
        // Arrange
        var title = "Still Fly (feat. Mannie Fresh)";
        var artist = "Big Tymers";

        // Act
        var (normTitle, normArtist, comboKey) = QueryNormalizer.NormalizePair(title, artist);

        // Assert
        Assert.Equal("still fly", normTitle);
        Assert.Equal("big tymers", normArtist);
        Assert.Equal("big tymers||still fly", comboKey);
    }

    [Fact]
    public void NormalizePair_RealWorldExample_GodsPlain()
    {
        // Arrange
        var title = "God's Plan";
        var artist = "Drake";

        // Act
        var (normTitle, normArtist, _) = QueryNormalizer.NormalizePair(title, artist);

        // Assert
        Assert.Equal("god s plan", normTitle);
        Assert.Equal("drake", normArtist);
    }

    [Fact]
    public void NormalizePair_RealWorldExample_AntiHero()
    {
        // Arrange
        var title = "Anti-Hero";
        var artist = "Taylor Swift";

        // Act
        var (normTitle, normArtist, _) = QueryNormalizer.NormalizePair(title, artist);

        // Assert
        Assert.Equal("anti hero", normTitle);
        Assert.Equal("taylor swift", normArtist);
    }

    #endregion
}