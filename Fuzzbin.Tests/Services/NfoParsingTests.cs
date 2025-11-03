using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net.Http;
using System.Reflection;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using FluentAssertions;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using Moq;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services;
using Fuzzbin.Services.Interfaces;
using Xunit;

namespace Fuzzbin.Tests.Services;

public class NfoParsingTests
{
    private readonly string _fixturesPath;
    private readonly Mock<IMetadataService> _metadataServiceMock;
    private readonly Mock<ILogger<LibraryImportService>> _loggerMock;

    public NfoParsingTests()
    {
        // Get the test fixtures directory
        var assemblyPath = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        _fixturesPath = Path.Combine(assemblyPath!, "..", "..", "..", "Fixtures", "Nfo");
        
        _metadataServiceMock = new Mock<IMetadataService>();
        _loggerMock = new Mock<ILogger<LibraryImportService>>();
    }

    [Fact]
    public async Task ReadNfoAsync_ParsesSourceUrls_WhenSourcesElementPresent()
    {
        // Arrange
        var nfoPath = Path.Combine(_fixturesPath, "complete.nfo");
        var metadataService = CreateRealMetadataService();

        // Act
        var nfoData = await metadataService.ReadNfoAsync(nfoPath, CancellationToken.None);

        // Assert
        nfoData.Should().NotBeNull();
        nfoData!.SourceUrls.Should().HaveCount(2);
        nfoData.SourceUrls.Should().Contain("https://www.youtube.com/watch?v=sOnqjkJTMaA");
        nfoData.SourceUrls.Should().Contain("https://musicbrainz.org/recording/12345");
    }

    [Fact]
    public async Task ReadNfoAsync_FiltersInvalidUrls_FromSourcesElement()
    {
        // Arrange
        var nfoPath = Path.Combine(_fixturesPath, "invalid-sources.nfo");
        var metadataService = CreateRealMetadataService();

        // Act
        var nfoData = await metadataService.ReadNfoAsync(nfoPath, CancellationToken.None);

        // Assert
        nfoData.Should().NotBeNull();
        nfoData!.SourceUrls.Should().HaveCount(1);
        nfoData.SourceUrls.Should().Contain("https://valid-url.com");
        nfoData.SourceUrls.Should().NotContain("not-a-valid-url");
    }

    [Fact]
    public async Task ReadNfoAsync_ReturnsEmptySourceUrls_WhenNoSourcesElement()
    {
        // Arrange
        var nfoPath = Path.Combine(_fixturesPath, "no-sources.nfo");
        var metadataService = CreateRealMetadataService();

        // Act
        var nfoData = await metadataService.ReadNfoAsync(nfoPath, CancellationToken.None);

        // Assert
        nfoData.Should().NotBeNull();
        nfoData!.SourceUrls.Should().BeEmpty();
    }

    [Theory]
    [InlineData("Mark Ronson feat. Bruno Mars", "Bruno Mars")]
    [InlineData("Artist ft. Featured", "Featured")]
    [InlineData("Main featuring Special Guest", "Special Guest")]
    [InlineData("Artist with Collaborator", "Collaborator")]
    [InlineData("Artist x Another Artist", "Another Artist")]
    public void ExtractFeaturedArtists_FindsFeaturedArtist_FromArtistField(string artistField, string expectedFeatured)
    {
        // Act
        var result = InvokePrivateStaticMethod<List<string>>(
            "ExtractFeaturedArtists",
            new object[] { artistField });

        // Assert
        result.Should().Contain(expectedFeatured);
    }

    [Theory]
    [InlineData("Song Title (feat. Featured Artist)", "Featured Artist")]
    [InlineData("Song (ft. Special Guest)", "Special Guest")]
    [InlineData("Track [featuring Collaborator]", "Collaborator")]
    [InlineData("Song [feat. Another]", "Another")]
    public void ExtractFeaturedFromTitle_FindsFeaturedArtist_FromTitleField(string titleField, string expectedFeatured)
    {
        // Act
        var result = InvokePrivateStaticMethod<List<string>>(
            "ExtractFeaturedFromTitle",
            new object[] { titleField });

        // Assert
        result.Should().Contain(expectedFeatured);
    }

    [Fact]
    public void ExtractFeaturedArtists_HandlesMultipleFeatures()
    {
        // Arrange
        var artistField = "David Guetta x Bebe Rexha featuring DJ Snake";

        // Act
        var result = InvokePrivateStaticMethod<List<string>>(
            "ExtractFeaturedArtists",
            new object[] { artistField });

        // Assert
        result.Should().HaveCountGreaterThan(0);
        result.Should().Contain("Bebe Rexha");
        result.Should().Contain("DJ Snake");
    }

    [Fact]
    public void IsMetadataComplete_ReturnsTrue_WhenAllRequiredFieldsPresent()
    {
        // Arrange
        var nfoData = new NfoData
        {
            Artist = "Test Artist",
            Title = "Test Title",
            Year = 2023,
            Genres = new List<string> { "Pop" }
        };

        // Act
        var result = InvokePrivateStaticMethod<bool>(
            "IsMetadataComplete",
            new object[] { nfoData });

        // Assert
        result.Should().BeTrue();
    }

    [Theory]
    [InlineData(null, "Title", 2023, true)]  // Missing artist
    [InlineData("Artist", null, 2023, true)]  // Missing title
    [InlineData("Artist", "Title", null, true)]  // Missing year
    [InlineData("Artist", "Title", 2023, false)]  // Missing genres
    public void IsMetadataComplete_ReturnsFalse_WhenRequiredFieldsMissing(
        string? artist, string? title, int? year, bool hasGenre)
    {
        // Arrange
        var nfoData = new NfoData
        {
            Artist = artist,
            Title = title,
            Year = year,
            Genres = hasGenre ? new List<string> { "Pop" } : new List<string>()
        };

        // Act
        var result = InvokePrivateStaticMethod<bool>(
            "IsMetadataComplete",
            new object[] { nfoData });

        // Assert
        result.Should().BeFalse();
    }

    [Fact]
    public async Task FindNfoFileAsync_FindsSameBasename_First()
    {
        // Arrange
        var tempDir = Path.Combine(Path.GetTempPath(), $"nfo-test-{Guid.NewGuid():N}");
        Directory.CreateDirectory(tempDir);
        
        try
        {
            var videoPath = Path.Combine(tempDir, "video.mp4");
            var nfoPath = Path.Combine(tempDir, "video.nfo");
            
            await File.WriteAllTextAsync(videoPath, "video content");
            await File.WriteAllTextAsync(nfoPath, "<?xml version=\"1.0\"?><musicvideo></musicvideo>");

            var service = CreateLibraryImportServiceWithMocks();

            // Act
            var result = await InvokePrivateMethodAsync<string?>(
                service,
                "FindNfoFileAsync",
                new object[] { videoPath, CancellationToken.None });

            // Assert
            result.Should().Be(nfoPath);
        }
        finally
        {
            if (Directory.Exists(tempDir))
            {
                Directory.Delete(tempDir, true);
            }
        }
    }

    [Fact]
    public async Task FindNfoFileAsync_FindsKodiPattern_WhenSameBasenameNotPresent()
    {
        // Arrange
        var tempDir = Path.Combine(Path.GetTempPath(), $"nfo-test-{Guid.NewGuid():N}");
        Directory.CreateDirectory(tempDir);
        
        try
        {
            var videoPath = Path.Combine(tempDir, "video.mp4");
            var kodiNfoPath = Path.Combine(tempDir, "video-nfo.nfo");
            
            await File.WriteAllTextAsync(videoPath, "video content");
            await File.WriteAllTextAsync(kodiNfoPath, "<?xml version=\"1.0\"?><musicvideo></musicvideo>");

            var service = CreateLibraryImportServiceWithMocks();

            // Act
            var result = await InvokePrivateMethodAsync<string?>(
                service,
                "FindNfoFileAsync",
                new object[] { videoPath, CancellationToken.None });

            // Assert
            result.Should().Be(kodiNfoPath);
        }
        finally
        {
            if (Directory.Exists(tempDir))
            {
                Directory.Delete(tempDir, true);
            }
        }
    }

    [Fact]
    public async Task FindNfoFileAsync_FindsDirectoryLevel_WhenOthersNotPresent()
    {
        // Arrange
        var tempDir = Path.Combine(Path.GetTempPath(), $"nfo-test-{Guid.NewGuid():N}");
        Directory.CreateDirectory(tempDir);
        
        try
        {
            var videoPath = Path.Combine(tempDir, "video.mp4");
            var movieNfoPath = Path.Combine(tempDir, "movie.nfo");
            
            await File.WriteAllTextAsync(videoPath, "video content");
            await File.WriteAllTextAsync(movieNfoPath, "<?xml version=\"1.0\"?><musicvideo></musicvideo>");

            var service = CreateLibraryImportServiceWithMocks();

            // Act
            var result = await InvokePrivateMethodAsync<string?>(
                service,
                "FindNfoFileAsync",
                new object[] { videoPath, CancellationToken.None });

            // Assert
            result.Should().Be(movieNfoPath);
        }
        finally
        {
            if (Directory.Exists(tempDir))
            {
                Directory.Delete(tempDir, true);
            }
        }
    }

    [Fact]
    public async Task FindNfoFileAsync_ReturnsNull_WhenNoNfoFound()
    {
        // Arrange
        var tempDir = Path.Combine(Path.GetTempPath(), $"nfo-test-{Guid.NewGuid():N}");
        Directory.CreateDirectory(tempDir);
        
        try
        {
            var videoPath = Path.Combine(tempDir, "video.mp4");
            await File.WriteAllTextAsync(videoPath, "video content");

            var service = CreateLibraryImportServiceWithMocks();

            // Act
            var result = await InvokePrivateMethodAsync<string?>(
                service,
                "FindNfoFileAsync",
                new object[] { videoPath, CancellationToken.None });

            // Assert
            result.Should().BeNull();
        }
        finally
        {
            if (Directory.Exists(tempDir))
            {
                Directory.Delete(tempDir, true);
            }
        }
    }

    [Fact]
    public async Task ApplyNfoMetadataAsync_PopulatesLibraryImportItem_WithNfoData()
    {
        // Arrange
        var nfoPath = Path.Combine(_fixturesPath, "complete.nfo");
        var item = new LibraryImportItem
        {
            FilePath = "/test/video.mp4",
            FileName = "video.mp4"
        };

        var metadataService = CreateRealMetadataService();
        var service = CreateLibraryImportServiceWithRealMetadataService(metadataService);

        // Act
        await InvokePrivateMethodAsync(
            service,
            "ApplyNfoMetadataAsync",
            new object[] { item, nfoPath, CancellationToken.None });

        // Assert
        item.Artist.Should().Be("Michael Jackson");
        item.Title.Should().Be("Thriller");
        item.Year.Should().Be(1983);
        item.Album.Should().Be("Thriller");
        item.MetadataSource.Should().Be("nfo_complete");
        item.NfoMetadataJson.Should().NotBeNullOrWhiteSpace();
        
        var nfoData = JsonSerializer.Deserialize<NfoData>(item.NfoMetadataJson!);
        nfoData.Should().NotBeNull();
        nfoData!.SourceUrls.Should().HaveCount(2);
    }

    [Fact]
    public async Task ApplyNfoMetadataAsync_ExtractsFeaturedArtists_FromArtistField()
    {
        // Arrange
        var nfoPath = Path.Combine(_fixturesPath, "featured-in-artist.nfo");
        var item = new LibraryImportItem
        {
            FilePath = "/test/video.mp4",
            FileName = "video.mp4"
        };

        var metadataService = CreateRealMetadataService();
        var service = CreateLibraryImportServiceWithRealMetadataService(metadataService);

        // Act
        await InvokePrivateMethodAsync(
            service,
            "ApplyNfoMetadataAsync",
            new object[] { item, nfoPath, CancellationToken.None });

        // Assert
        item.FeaturedArtistsJson.Should().NotBeNullOrWhiteSpace();
        var featuredArtists = JsonSerializer.Deserialize<List<string>>(item.FeaturedArtistsJson!);
        featuredArtists.Should().Contain("Bruno Mars");
    }

    [Fact]
    public async Task ApplyNfoMetadataAsync_ExtractsFeaturedArtists_FromTitleField()
    {
        // Arrange
        var nfoPath = Path.Combine(_fixturesPath, "featured-in-title.nfo");
        var item = new LibraryImportItem
        {
            FilePath = "/test/video.mp4",
            FileName = "video.mp4"
        };

        var metadataService = CreateRealMetadataService();
        var service = CreateLibraryImportServiceWithRealMetadataService(metadataService);

        // Act
        await InvokePrivateMethodAsync(
            service,
            "ApplyNfoMetadataAsync",
            new object[] { item, nfoPath, CancellationToken.None });

        // Assert
        item.FeaturedArtistsJson.Should().NotBeNullOrWhiteSpace();
        var featuredArtists = JsonSerializer.Deserialize<List<string>>(item.FeaturedArtistsJson!);
        featuredArtists.Should().Contain("Justin Bieber");
    }

    [Fact]
    public async Task ApplyNfoMetadataAsync_SetsPartialMetadataSource_WhenIncomplete()
    {
        // Arrange
        var nfoPath = Path.Combine(_fixturesPath, "partial.nfo");
        var item = new LibraryImportItem
        {
            FilePath = "/test/video.mp4",
            FileName = "video.mp4"
        };

        var metadataService = CreateRealMetadataService();
        var service = CreateLibraryImportServiceWithRealMetadataService(metadataService);

        // Act
        await InvokePrivateMethodAsync(
            service,
            "ApplyNfoMetadataAsync",
            new object[] { item, nfoPath, CancellationToken.None });

        // Assert
        item.MetadataSource.Should().Be("nfo_partial");
    }

    // Helper methods for invoking private methods
    private T InvokePrivateStaticMethod<T>(string methodName, object[] parameters)
    {
        var method = typeof(LibraryImportService).GetMethod(
            methodName,
            BindingFlags.NonPublic | BindingFlags.Static);

        if (method == null)
        {
            throw new InvalidOperationException($"Method {methodName} not found");
        }

        var result = method.Invoke(null, parameters);
        return (T)result!;
    }

    private async Task InvokePrivateMethodAsync(object instance, string methodName, object[] parameters)
    {
        var method = typeof(LibraryImportService).GetMethod(
            methodName,
            BindingFlags.NonPublic | BindingFlags.Instance);

        if (method == null)
        {
            throw new InvalidOperationException($"Method {methodName} not found");
        }

        var result = method.Invoke(instance, parameters);
        
        if (result is Task task)
        {
            await task.ConfigureAwait(false);
        }
    }

    private async Task<T> InvokePrivateMethodAsync<T>(object instance, string methodName, object[] parameters)
    {
        var method = typeof(LibraryImportService).GetMethod(
            methodName,
            BindingFlags.NonPublic | BindingFlags.Instance);

        if (method == null)
        {
            throw new InvalidOperationException($"Method {methodName} not found");
        }

        var result = method.Invoke(instance, parameters);
        
        if (result is Task task)
        {
            await task.ConfigureAwait(false);
            
            // Handle Task<TResult>
            var resultProperty = task.GetType().GetProperty("Result");
            return resultProperty != null ? (T)resultProperty.GetValue(task)! : default!;
        }

        return (T)result!;
    }

    private MetadataService CreateRealMetadataService()
    {
        var loggerMock = new Mock<ILogger<MetadataService>>();
        var unitOfWorkMock = new Mock<IUnitOfWork>();
        var httpClientFactoryMock = new Mock<System.Net.Http.IHttpClientFactory>();
        var thumbnailServiceMock = new Mock<IThumbnailService>();
        var metadataCacheServiceMock = new Mock<IMetadataCacheService>();
        
        httpClientFactoryMock.Setup(x => x.CreateClient(It.IsAny<string>()))
            .Returns(new System.Net.Http.HttpClient());
        
        return new MetadataService(
            loggerMock.Object,
            unitOfWorkMock.Object,
            httpClientFactoryMock.Object,
            thumbnailServiceMock.Object,
            metadataCacheServiceMock.Object);
    }

    private LibraryImportService CreateLibraryImportServiceWithMocks()
    {
        var sessionRepoMock = new Mock<IRepository<LibraryImportSession>>();
        var itemRepoMock = new Mock<IRepository<LibraryImportItem>>();
        var videoRepoMock = new Mock<IRepository<Video>>();
        var unitOfWorkMock = new Mock<IUnitOfWork>();
        var libraryPathManagerMock = new Mock<ILibraryPathManager>();
        var metadataCacheServiceMock = new Mock<IMetadataCacheService>();

        return new LibraryImportService(
            _loggerMock.Object,
            sessionRepoMock.Object,
            itemRepoMock.Object,
            videoRepoMock.Object,
            unitOfWorkMock.Object,
            _metadataServiceMock.Object,
            libraryPathManagerMock.Object,
            metadataCacheServiceMock.Object);
    }

    private LibraryImportService CreateLibraryImportServiceWithRealMetadataService(IMetadataService metadataService)
    {
        var sessionRepoMock = new Mock<IRepository<LibraryImportSession>>();
        var itemRepoMock = new Mock<IRepository<LibraryImportItem>>();
        var videoRepoMock = new Mock<IRepository<Video>>();
        var unitOfWorkMock = new Mock<IUnitOfWork>();
        var libraryPathManagerMock = new Mock<ILibraryPathManager>();
        var metadataCacheServiceMock = new Mock<IMetadataCacheService>();

        return new LibraryImportService(
            _loggerMock.Object,
            sessionRepoMock.Object,
            itemRepoMock.Object,
            videoRepoMock.Object,
            unitOfWorkMock.Object,
            metadataService,
            libraryPathManagerMock.Object,
            metadataCacheServiceMock.Object);
    }
}
