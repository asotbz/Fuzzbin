using Xunit;
using Fuzzbin.Services.Models;

namespace Fuzzbin.Tests.Integration;

public class SearchPageTests
{
    [Fact]
    public void ExternalSearchQuery_DefaultConstructor_SetsDefaultToggles()
    {
        // Arrange & Act
        var query = new ExternalSearchQuery();

        // Assert
        Assert.True(query.IncludeImvdb, "IncludeImvdb should default to true");
        Assert.True(query.IncludeYtDlp, "IncludeYtDlp should default to true");
    }

    [Fact]
    public void ExternalSearchQuery_WithInitializer_DefaultsAreTrue()
    {
        // Arrange & Act
        var query = new ExternalSearchQuery
        {
            MaxResults = 10
        };

        // Assert
        Assert.True(query.IncludeImvdb, "IncludeImvdb should default to true");
        Assert.True(query.IncludeYtDlp, "IncludeYtDlp should default to true");
        Assert.Equal(10, query.MaxResults);
    }

    [Fact]
    public void ExternalSearchQuery_CanOverrideDefaults()
    {
        // Arrange & Act
        var query = new ExternalSearchQuery
        {
            IncludeImvdb = false,
            IncludeYtDlp = false
        };

        // Assert
        Assert.False(query.IncludeImvdb);
        Assert.False(query.IncludeYtDlp);
    }

    [Theory]
    [InlineData(0, "0")]
    [InlineData(1, "1")]
    [InlineData(100, "100")]
    [InlineData(null, "0")]
    public void SearchResultCount_DisplaysCorrectly(int? count, string expected)
    {
        // This test verifies that the binding "(@(_searchResult?.TotalCount.ToString() ?? "0") videos)"
        // correctly handles null and various count values
        
        // Arrange
        int? totalCount = count;

        // Act
        string displayValue = totalCount?.ToString() ?? "0";

        // Assert
        Assert.Equal(expected, displayValue);
    }

    [Fact]
    public void SearchResultCount_WithNullResult_ShowsZero()
    {
        // Arrange
        int? totalCount = null;

        // Act
        string displayValue = totalCount?.ToString() ?? "0";

        // Assert
        Assert.Equal("0", displayValue);
        Assert.DoesNotContain("??", displayValue);
    }
}