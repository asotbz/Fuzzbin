using System;
using System.Collections.Generic;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using Moq;
using Xunit;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services;

namespace Fuzzbin.Tests.Services;

public class FileOrganizationServiceTests : IDisposable
{
    private readonly Mock<IUnitOfWork> _mockUnitOfWork;
    private readonly Mock<ILogger<FileOrganizationService>> _mockLogger;
    private readonly Mock<ILibraryPathManager> _mockPathManager;
    private readonly FileOrganizationService _service;
    private readonly string _tempDirectory;

    public FileOrganizationServiceTests()
    {
        _mockUnitOfWork = new Mock<IUnitOfWork>();
        _mockLogger = new Mock<ILogger<FileOrganizationService>>();
        _mockPathManager = new Mock<ILibraryPathManager>();
        
        _tempDirectory = Path.Combine(Path.GetTempPath(), "FuzzbinTests", Guid.NewGuid().ToString());
        Directory.CreateDirectory(_tempDirectory);

        _mockPathManager
            .Setup(x => x.SanitizeFileName(It.IsAny<string>(), It.IsAny<string?>()))
            .Returns<string, string?>((name, ext) => 
                string.IsNullOrWhiteSpace(ext) ? name : $"{name}.{ext}");
        
        _mockPathManager
            .Setup(x => x.SanitizeDirectoryName(It.IsAny<string>()))
            .Returns<string>(name => name);

        _service = new FileOrganizationService(_mockUnitOfWork.Object, _mockLogger.Object, _mockPathManager.Object);
    }

    public void Dispose()
    {
        if (Directory.Exists(_tempDirectory))
        {
            Directory.Delete(_tempDirectory, true);
        }
    }

    #region Primary Artist Token Tests

    [Fact]
    public void GenerateFilePath_WithPrimaryArtistToken_StripsFeatToken()
    {
        // Arrange
        var video = new Video
        {
            Artist = "Taylor Swift feat. Ed Sheeran",
            Title = "End Game",
            Format = "mp4"
        };
        var pattern = "{primary_artist}/{title}.{format}";

        // Act
        var result = _service.GenerateFilePath(video, pattern);

        // Assert
        result.Should().Be(Path.Combine("Taylor Swift", "End Game.mp4"));
    }

    [Fact]
    public void GenerateFilePath_WithPrimaryArtistToken_StripsFtToken()
    {
        // Arrange
        var video = new Video
        {
            Artist = "Drake ft. Rihanna",
            Title = "Work",
            Format = "mp4"
        };
        var pattern = "{primary_artist}/{title}.{format}";

        // Act
        var result = _service.GenerateFilePath(video, pattern);

        // Assert
        result.Should().Be(Path.Combine("Drake", "Work.mp4"));
    }

    [Fact]
    public void GenerateFilePath_WithPrimaryArtistToken_StripsFeaturingToken()
    {
        // Arrange
        var video = new Video
        {
            Artist = "Maroon 5 featuring Christina Aguilera",
            Title = "Moves Like Jagger",
            Format = "mp4"
        };
        var pattern = "{primary_artist}/{title}.{format}";

        // Act
        var result = _service.GenerateFilePath(video, pattern);

        // Assert
        result.Should().Be(Path.Combine("Maroon 5", "Moves Like Jagger.mp4"));
    }

    [Fact]
    public void GenerateFilePath_WithPrimaryArtistToken_HandlesMultipleFeaturingFormats()
    {
        // Arrange - test case insensitive matching
        var video = new Video
        {
            Artist = "The Weeknd FEAT. Daft Punk",
            Title = "Starboy",
            Format = "mp4"
        };
        var pattern = "{primary_artist}/{title}.{format}";

        // Act
        var result = _service.GenerateFilePath(video, pattern);

        // Assert
        result.Should().Be(Path.Combine("The Weeknd", "Starboy.mp4"));
    }

    [Fact]
    public void GenerateFilePath_WithPrimaryArtistToken_HandlesNoFeaturingText()
    {
        // Arrange
        var video = new Video
        {
            Artist = "Beyoncé",
            Title = "Halo",
            Format = "mp4"
        };
        var pattern = "{primary_artist}/{title}.{format}";

        // Act
        var result = _service.GenerateFilePath(video, pattern);

        // Assert
        result.Should().Be(Path.Combine("Beyoncé", "Halo.mp4"));
    }

    [Fact]
    public void GenerateFilePath_WithPrimaryArtistToken_HandlesNullArtist()
    {
        // Arrange
        var video = new Video
        {
            Artist = null,
            Title = "Unknown Track",
            Format = "mp4"
        };
        var pattern = "{primary_artist}/{title}.{format}";

        // Act
        var result = _service.GenerateFilePath(video, pattern);

        // Assert
        result.Should().Be(Path.Combine("Unknown Artist", "Unknown Track.mp4"));
    }

    [Fact]
    public void GenerateFilePath_WithPrimaryArtistToken_HandlesEmptyArtist()
    {
        // Arrange
        var video = new Video
        {
            Artist = "",
            Title = "Unknown Track",
            Format = "mp4"
        };
        var pattern = "{primary_artist}/{title}.{format}";

        // Act
        var result = _service.GenerateFilePath(video, pattern);

        // Assert
        result.Should().Be(Path.Combine("Unknown Artist", "Unknown Track.mp4"));
    }

    [Fact]
    public void GenerateFilePath_WithPrimaryArtistToken_TrimsTrailingPunctuation()
    {
        // Arrange
        var video = new Video
        {
            Artist = "Calvin Harris, feat. Rihanna",
            Title = "This Is What You Came For",
            Format = "mp4"
        };
        var pattern = "{primary_artist}/{title}.{format}";

        // Act
        var result = _service.GenerateFilePath(video, pattern);

        // Assert
        result.Should().Be(Path.Combine("Calvin Harris", "This Is What You Came For.mp4"));
    }

    [Fact]
    public void GenerateFilePath_WithPrimaryArtistToken_HandlesOnlyFeaturingText()
    {
        // Arrange - edge case where artist is only featuring text
        var video = new Video
        {
            Artist = "feat. Someone",
            Title = "Track",
            Format = "mp4"
        };
        var pattern = "{primary_artist}/{title}.{format}";

        // Act
        var result = _service.GenerateFilePath(video, pattern);

        // Assert
        // Should return the original artist trimmed when stripping would result in empty string
        result.Should().Be(Path.Combine("feat. Someone", "Track.mp4"));
    }

    #endregion

    #region Pattern Validation Tests

    [Fact]
    public void ValidatePattern_WithValidPattern_ReturnsTrue()
    {
        // Arrange
        var pattern = "{artist}/{title}.{format}";

        // Act
        var result = _service.ValidatePattern(pattern);

        // Assert
        result.Should().BeTrue();
    }

    [Fact]
    public void ValidatePattern_WithNoVariables_ReturnsFalse()
    {
        // Arrange
        var pattern = "videos/file.mp4";

        // Act
        var result = _service.ValidatePattern(pattern);

        // Assert
        result.Should().BeFalse();
    }

    [Fact]
    public void ValidatePattern_WithEmptyPattern_ReturnsFalse()
    {
        // Arrange
        var pattern = "";

        // Act
        var result = _service.ValidatePattern(pattern);

        // Assert
        result.Should().BeFalse();
    }

    [Fact]
    public void ValidatePattern_WithNullPattern_ReturnsFalse()
    {
        // Arrange
        string? pattern = null;

        // Act
        var result = _service.ValidatePattern(pattern!);

        // Assert
        result.Should().BeFalse();
    }

    #endregion

    #region Available Variables Tests

    [Fact]
    public void GetAvailablePatternVariables_ReturnsVariableDictionary()
    {
        // Act
        var variables = _service.GetAvailablePatternVariables();

        // Assert
        variables.Should().NotBeNull();
        variables.Should().ContainKey("artist");
        variables.Should().ContainKey("title");
        variables.Should().ContainKey("primary_artist");
        variables.Should().ContainKey("year");
        variables.Should().ContainKey("format");
    }

    #endregion

    #region Generate FilePath Tests

    [Fact]
    public void GenerateFilePath_WithMultipleVariables_ReplacesAll()
    {
        // Arrange
        var video = new Video
        {
            Artist = "Test Artist",
            Title = "Test Title",
            Year = 2023,
            Format = "mp4"
        };
        var pattern = "{artist}/{year}/{title}.{format}";

        // Act
        var result = _service.GenerateFilePath(video, pattern);

        // Assert
        result.Should().Be(Path.Combine("Test Artist", "2023", "Test Title.mp4"));
    }

    [Fact]
    public void GenerateFilePath_WithMissingData_UsesFallbacks()
    {
        // Arrange
        var video = new Video
        {
            Artist = null,
            Title = null,
            Year = null,
            Format = null,
            FilePath = "/some/path/video.mp4"
        };
        var pattern = "{artist}/{title}.{format}";

        // Act
        var result = _service.GenerateFilePath(video, pattern);

        // Assert
        result.Should().Be(Path.Combine("Unknown Artist", "Unknown Title.mp4"));
    }

    [Fact]
    public void GenerateFilePath_NormalizesDirectorySeparators()
    {
        // Arrange
        var video = new Video
        {
            Artist = "Artist",
            Title = "Title",
            Format = "mp4"
        };
        var pattern = "{artist}\\{title}.{format}"; // Windows-style separator

        // Act
        var result = _service.GenerateFilePath(video, pattern);

        // Assert
        result.Should().Be(Path.Combine("Artist", "Title.mp4"));
    }

    #endregion

    #region Preview OrganizedPath Tests

    [Fact]
    public async Task PreviewOrganizedPath_ReturnsFullPath()
    {
        // Arrange
        var libraryRoot = "/library/videos";
        _mockPathManager.Setup(x => x.GetVideoRootAsync(It.IsAny<CancellationToken>()))
            .ReturnsAsync(libraryRoot);

        var video = new Video
        {
            Artist = "Artist",
            Title = "Title",
            Format = "mp4"
        };
        var pattern = "{artist}/{title}.{format}";

        // Act
        var result = _service.PreviewOrganizedPath(video, pattern);

        // Assert
        result.Should().Be(Path.Combine(libraryRoot, "Artist", "Title.mp4"));
    }

    #endregion
}