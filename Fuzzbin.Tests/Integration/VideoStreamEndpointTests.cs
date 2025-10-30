using System;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;

namespace Fuzzbin.Tests.Integration;

/// <summary>
/// Integration tests for the /api/videos/stream endpoint.
/// Tests file streaming, path resolution, error handling, and content delivery.
/// </summary>
public class VideoStreamEndpointTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly WebApplicationFactory<Program> _factory;
    private readonly HttpClient _client;

    public VideoStreamEndpointTests(WebApplicationFactory<Program> factory)
    {
        _factory = factory;
        _client = factory.CreateClient(new WebApplicationFactoryClientOptions
        {
            AllowAutoRedirect = false
        });
    }

    [Fact]
    public async Task StreamEndpoint_WithMissingPath_ReturnsBadRequest()
    {
        // Act
        var response = await _client.GetAsync("/api/videos/stream");

        // Assert
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        
        var content = await response.Content.ReadAsStringAsync();
        Assert.Contains("path is required", content, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task StreamEndpoint_WithEmptyPath_ReturnsBadRequest()
    {
        // Act
        var response = await _client.GetAsync("/api/videos/stream?path=");

        // Assert
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        
        var content = await response.Content.ReadAsStringAsync();
        Assert.Contains("path is required", content, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task StreamEndpoint_WithNonexistentFile_ReturnsNotFound()
    {
        // Arrange
        var nonexistentPath = "nonexistent/video/file.mp4";

        // Act
        var response = await _client.GetAsync($"/api/videos/stream?path={Uri.EscapeDataString(nonexistentPath)}");

        // Assert
        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
        
        var content = await response.Content.ReadAsStringAsync();
        Assert.Contains("not found", content, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public async Task StreamEndpoint_WithValidFile_ReturnsOkAndVideoContent()
    {
        // Arrange - Create a temporary test video file
        var testVideoContent = new byte[] { 0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70 }; // Minimal MP4 header
        var tempVideoPath = Path.Combine(Path.GetTempPath(), $"test-video-{Guid.NewGuid()}.mp4");
        
        try
        {
            await File.WriteAllBytesAsync(tempVideoPath, testVideoContent);

            // Act
            var response = await _client.GetAsync($"/api/videos/stream?path={Uri.EscapeDataString(tempVideoPath)}");

            // Assert
            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
            
            // Verify content type
            Assert.NotNull(response.Content.Headers.ContentType);
            Assert.Equal("video/mp4", response.Content.Headers.ContentType.MediaType);
            
            // Verify content length
            Assert.NotNull(response.Content.Headers.ContentLength);
            Assert.Equal(testVideoContent.Length, response.Content.Headers.ContentLength.Value);
            
            // Verify range processing is enabled
            Assert.Contains("bytes", response.Headers.AcceptRanges);
        }
        finally
        {
            // Cleanup
            if (File.Exists(tempVideoPath))
            {
                File.Delete(tempVideoPath);
            }
        }
    }

    [Fact]
    public async Task StreamEndpoint_SupportsRangeRequests()
    {
        // Arrange - Create a test video file with known content
        var testVideoContent = new byte[1024];
        for (int i = 0; i < testVideoContent.Length; i++)
        {
            testVideoContent[i] = (byte)(i % 256);
        }
        
        var tempVideoPath = Path.Combine(Path.GetTempPath(), $"test-video-range-{Guid.NewGuid()}.mp4");
        
        try
        {
            await File.WriteAllBytesAsync(tempVideoPath, testVideoContent);

            // Create request with range header
            var request = new HttpRequestMessage(HttpMethod.Get, 
                $"/api/videos/stream?path={Uri.EscapeDataString(tempVideoPath)}");
            request.Headers.Range = new System.Net.Http.Headers.RangeHeaderValue(0, 511);

            // Act
            var response = await _client.SendAsync(request);

            // Assert
            Assert.Equal(HttpStatusCode.PartialContent, response.StatusCode);
            
            var content = await response.Content.ReadAsByteArrayAsync();
            Assert.Equal(512, content.Length);
            
            // Verify the content matches the requested range
            for (int i = 0; i < 512; i++)
            {
                Assert.Equal(testVideoContent[i], content[i]);
            }
        }
        finally
        {
            if (File.Exists(tempVideoPath))
            {
                File.Delete(tempVideoPath);
            }
        }
    }

    [Fact]
    public async Task StreamEndpoint_WithInvalidPathCharacters_ReturnsNotFound()
    {
        // Arrange
        var invalidPath = "../../../etc/passwd";

        // Act
        var response = await _client.GetAsync($"/api/videos/stream?path={Uri.EscapeDataString(invalidPath)}");

        // Assert
        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
    }

    [Fact]
    public async Task StreamEndpoint_WithUrlEncodedPath_DecodesCorrectly()
    {
        // Arrange - Create a file with special characters in the name
        var fileName = "test video (2024) [HD].mp4";
        var tempVideoPath = Path.Combine(Path.GetTempPath(), fileName);
        var testContent = new byte[] { 0x00, 0x00, 0x00, 0x20 };
        
        try
        {
            await File.WriteAllBytesAsync(tempVideoPath, testContent);

            // Act
            var response = await _client.GetAsync($"/api/videos/stream?path={Uri.EscapeDataString(tempVideoPath)}");

            // Assert
            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        }
        finally
        {
            if (File.Exists(tempVideoPath))
            {
                File.Delete(tempVideoPath);
            }
        }
    }

    [Fact]
    public async Task StreamEndpoint_WithDifferentVideoFormats_ReturnsCorrectContentType()
    {
        // Arrange
        var testCases = new[]
        {
            ("test.mp4", "video/mp4"),
            ("test.mkv", "video/x-matroska"),
            ("test.webm", "video/webm"),
            ("test.avi", "video/x-msvideo")
        };

        foreach (var (fileName, expectedContentType) in testCases)
        {
            var tempPath = Path.Combine(Path.GetTempPath(), fileName);
            
            try
            {
                await File.WriteAllBytesAsync(tempPath, new byte[] { 0x00 });

                // Act
                var response = await _client.GetAsync($"/api/videos/stream?path={Uri.EscapeDataString(tempPath)}");

                // Assert
                Assert.Equal(HttpStatusCode.OK, response.StatusCode);
                Assert.NotNull(response.Content.Headers.ContentType);
                Assert.Equal(expectedContentType, response.Content.Headers.ContentType.MediaType);
            }
            finally
            {
                if (File.Exists(tempPath))
                {
                    File.Delete(tempPath);
                }
            }
        }
    }

    [Fact]
    public async Task StreamEndpoint_WithLargeFile_StreamsSuccessfully()
    {
        // Arrange - Create a larger test file (1MB)
        var testVideoContent = new byte[1024 * 1024];
        new Random().NextBytes(testVideoContent);
        
        var tempVideoPath = Path.Combine(Path.GetTempPath(), $"test-large-video-{Guid.NewGuid()}.mp4");
        
        try
        {
            await File.WriteAllBytesAsync(tempVideoPath, testVideoContent);

            // Act
            var response = await _client.GetAsync($"/api/videos/stream?path={Uri.EscapeDataString(tempVideoPath)}");

            // Assert
            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
            
            var streamedContent = await response.Content.ReadAsByteArrayAsync();
            Assert.Equal(testVideoContent.Length, streamedContent.Length);
        }
        finally
        {
            if (File.Exists(tempVideoPath))
            {
                File.Delete(tempVideoPath);
            }
        }
    }

    [Fact]
    public async Task StreamEndpoint_AllowsAnonymousAccess()
    {
        // Arrange - Create a test file
        var testVideoContent = new byte[] { 0x00, 0x00, 0x00, 0x20 };
        var tempVideoPath = Path.Combine(Path.GetTempPath(), $"test-anonymous-{Guid.NewGuid()}.mp4");
        
        try
        {
            await File.WriteAllBytesAsync(tempVideoPath, testVideoContent);

            // Create a client without authentication
            var anonymousClient = _factory.CreateClient();

            // Act
            var response = await anonymousClient.GetAsync($"/api/videos/stream?path={Uri.EscapeDataString(tempVideoPath)}");

            // Assert
            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        }
        finally
        {
            if (File.Exists(tempVideoPath))
            {
                File.Delete(tempVideoPath);
            }
        }
    }
}