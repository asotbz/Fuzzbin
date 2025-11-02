using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using Fuzzbin.Services.Http;
using Microsoft.Extensions.Logging;
using Moq;
using Moq.Protected;
using Xunit;

namespace Fuzzbin.Tests.Http;

/// <summary>
/// Integration tests for MusicBrainzHttpMessageHandler
/// Verifies rate limiting integration with HTTP pipeline
/// </summary>
public class MusicBrainzHttpMessageHandlerTests : IDisposable
{
    private readonly MusicBrainzRateLimiter _rateLimiter;
    private readonly Mock<ILogger<MusicBrainzHttpMessageHandler>> _mockLogger;
    
    public MusicBrainzHttpMessageHandlerTests()
    {
        _rateLimiter = new MusicBrainzRateLimiter();
        _mockLogger = new Mock<ILogger<MusicBrainzHttpMessageHandler>>();
    }
    
    [Fact]
    public async Task SendAsync_FirstRequest_SendsImmediately()
    {
        // Arrange
        var mockInnerHandler = new Mock<HttpMessageHandler>();
        mockInnerHandler
            .Protected()
            .Setup<Task<HttpResponseMessage>>(
                "SendAsync",
                ItExpr.IsAny<HttpRequestMessage>(),
                ItExpr.IsAny<CancellationToken>())
            .ReturnsAsync(new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent("Success")
            });
        
        var handler = new MusicBrainzHttpMessageHandler(_rateLimiter, _mockLogger.Object)
        {
            InnerHandler = mockInnerHandler.Object
        };
        
        var client = new HttpClient(handler)
        {
            BaseAddress = new Uri("https://musicbrainz.org/ws/2/")
        };
        
        var stopwatch = Stopwatch.StartNew();
        
        // Act
        var response = await client.GetAsync("recording/test");
        stopwatch.Stop();
        
        // Assert
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.True(stopwatch.ElapsedMilliseconds < 100, 
            $"Expected immediate send, but took {stopwatch.ElapsedMilliseconds}ms");
        
        // Verify inner handler was called
        mockInnerHandler
            .Protected()
            .Verify(
                "SendAsync",
                Times.Once(),
                ItExpr.IsAny<HttpRequestMessage>(),
                ItExpr.IsAny<CancellationToken>());
    }
    
    [Fact]
    public async Task SendAsync_TwoSequentialRequests_SecondWaitsForRateLimit()
    {
        // Arrange
        var mockInnerHandler = new Mock<HttpMessageHandler>();
        mockInnerHandler
            .Protected()
            .Setup<Task<HttpResponseMessage>>(
                "SendAsync",
                ItExpr.IsAny<HttpRequestMessage>(),
                ItExpr.IsAny<CancellationToken>())
            .ReturnsAsync(new HttpResponseMessage(HttpStatusCode.OK));
        
        var handler = new MusicBrainzHttpMessageHandler(_rateLimiter, _mockLogger.Object)
        {
            InnerHandler = mockInnerHandler.Object
        };
        
        var client = new HttpClient(handler)
        {
            BaseAddress = new Uri("https://musicbrainz.org/ws/2/")
        };
        
        // Act
        var response1 = await client.GetAsync("recording/1");
        
        var stopwatch = Stopwatch.StartNew();
        var response2 = await client.GetAsync("recording/2");
        stopwatch.Stop();
        
        // Assert
        Assert.Equal(HttpStatusCode.OK, response1.StatusCode);
        Assert.Equal(HttpStatusCode.OK, response2.StatusCode);
        Assert.InRange(stopwatch.ElapsedMilliseconds, 900, 1200); // ~1 second delay
    }
    
    [Fact]
    public async Task SendAsync_ConcurrentRequests_ProcessedSequentially()
    {
        // Arrange
        var requestCount = 0;
        var requestLock = new object();
        
        var mockInnerHandler = new Mock<HttpMessageHandler>();
        mockInnerHandler
            .Protected()
            .Setup<Task<HttpResponseMessage>>(
                "SendAsync",
                ItExpr.IsAny<HttpRequestMessage>(),
                ItExpr.IsAny<CancellationToken>())
            .ReturnsAsync(() =>
            {
                lock (requestLock)
                {
                    requestCount++;
                }
                return new HttpResponseMessage(HttpStatusCode.OK);
            });
        
        var handler = new MusicBrainzHttpMessageHandler(_rateLimiter, _mockLogger.Object)
        {
            InnerHandler = mockInnerHandler.Object
        };
        
        var client = new HttpClient(handler)
        {
            BaseAddress = new Uri("https://musicbrainz.org/ws/2/")
        };
        
        var stopwatch = Stopwatch.StartNew();
        
        // Act - Fire off 5 concurrent requests
        var tasks = Enumerable.Range(0, 5)
            .Select(i => client.GetAsync($"recording/{i}"))
            .ToList();
        
        var responses = await Task.WhenAll(tasks);
        stopwatch.Stop();
        
        // Assert
        Assert.All(responses, r => Assert.Equal(HttpStatusCode.OK, r.StatusCode));
        Assert.Equal(5, requestCount);
        
        // Should take ~4 seconds (5 requests at 1/sec)
        Assert.InRange(stopwatch.ElapsedMilliseconds, 3800, 4500);
    }
    
    [Fact]
    public async Task SendAsync_LogsDebugMessages()
    {
        // Arrange
        var mockInnerHandler = new Mock<HttpMessageHandler>();
        mockInnerHandler
            .Protected()
            .Setup<Task<HttpResponseMessage>>(
                "SendAsync",
                ItExpr.IsAny<HttpRequestMessage>(),
                ItExpr.IsAny<CancellationToken>())
            .ReturnsAsync(new HttpResponseMessage(HttpStatusCode.OK));
        
        var handler = new MusicBrainzHttpMessageHandler(_rateLimiter, _mockLogger.Object)
        {
            InnerHandler = mockInnerHandler.Object
        };
        
        var client = new HttpClient(handler)
        {
            BaseAddress = new Uri("https://musicbrainz.org/ws/2/")
        };
        
        // Act
        await client.GetAsync("recording/test");
        
        // Assert - Verify debug logging occurred
        _mockLogger.Verify(
            l => l.Log(
                LogLevel.Debug,
                It.IsAny<EventId>(),
                It.Is<It.IsAnyType>((v, t) => v.ToString()!.Contains("rate limit acquired")),
                It.IsAny<Exception>(),
                It.IsAny<Func<It.IsAnyType, Exception?, string>>()),
            Times.Once);
    }
    
    [Fact]
    public async Task SendAsync_WithRateLimitHeader_LogsRemainingRequests()
    {
        // Arrange
        var mockInnerHandler = new Mock<HttpMessageHandler>();
        mockInnerHandler
            .Protected()
            .Setup<Task<HttpResponseMessage>>(
                "SendAsync",
                ItExpr.IsAny<HttpRequestMessage>(),
                ItExpr.IsAny<CancellationToken>())
            .ReturnsAsync(() =>
            {
                var response = new HttpResponseMessage(HttpStatusCode.OK);
                response.Headers.Add("X-RateLimit-Remaining", "42");
                return response;
            });
        
        var handler = new MusicBrainzHttpMessageHandler(_rateLimiter, _mockLogger.Object)
        {
            InnerHandler = mockInnerHandler.Object
        };
        
        var client = new HttpClient(handler)
        {
            BaseAddress = new Uri("https://musicbrainz.org/ws/2/")
        };
        
        // Act
        await client.GetAsync("recording/test");
        
        // Assert - Verify rate limit logging
        _mockLogger.Verify(
            l => l.Log(
                LogLevel.Debug,
                It.IsAny<EventId>(),
                It.Is<It.IsAnyType>((v, t) => v.ToString()!.Contains("rate limit remaining")),
                It.IsAny<Exception>(),
                It.IsAny<Func<It.IsAnyType, Exception?, string>>()),
            Times.Once);
    }
    
    [Fact]
    public async Task SendAsync_WhenInnerHandlerThrows_LogsError()
    {
        // Arrange
        var expectedException = new HttpRequestException("Network error");
        
        var mockInnerHandler = new Mock<HttpMessageHandler>();
        mockInnerHandler
            .Protected()
            .Setup<Task<HttpResponseMessage>>(
                "SendAsync",
                ItExpr.IsAny<HttpRequestMessage>(),
                ItExpr.IsAny<CancellationToken>())
            .ThrowsAsync(expectedException);
        
        var handler = new MusicBrainzHttpMessageHandler(_rateLimiter, _mockLogger.Object)
        {
            InnerHandler = mockInnerHandler.Object
        };
        
        var client = new HttpClient(handler)
        {
            BaseAddress = new Uri("https://musicbrainz.org/ws/2/")
        };
        
        // Act & Assert
        var exception = await Assert.ThrowsAsync<HttpRequestException>(
            () => client.GetAsync("recording/test"));
        
        Assert.Equal(expectedException, exception);
        
        // Verify error logging
        _mockLogger.Verify(
            l => l.Log(
                LogLevel.Error,
                It.IsAny<EventId>(),
                It.Is<It.IsAnyType>((v, t) => v.ToString()!.Contains("Error making MusicBrainz request")),
                It.Is<Exception>(ex => ex == expectedException),
                It.IsAny<Func<It.IsAnyType, Exception?, string>>()),
            Times.Once);
    }
    
    [Fact]
    public async Task SendAsync_WithCancellation_RespectsCancellationToken()
    {
        // Arrange
        var mockInnerHandler = new Mock<HttpMessageHandler>();
        mockInnerHandler
            .Protected()
            .Setup<Task<HttpResponseMessage>>(
                "SendAsync",
                ItExpr.IsAny<HttpRequestMessage>(),
                ItExpr.IsAny<CancellationToken>())
            .ReturnsAsync(new HttpResponseMessage(HttpStatusCode.OK));
        
        var handler = new MusicBrainzHttpMessageHandler(_rateLimiter, _mockLogger.Object)
        {
            InnerHandler = mockInnerHandler.Object
        };
        
        var client = new HttpClient(handler)
        {
            BaseAddress = new Uri("https://musicbrainz.org/ws/2/")
        };
        
        using var cts = new CancellationTokenSource();
        
        // Make first request to consume rate limit
        await client.GetAsync("recording/1", cts.Token);
        
        // Cancel before second request can acquire rate limit
        cts.CancelAfter(100);
        
        // Act & Assert
        await Assert.ThrowsAnyAsync<OperationCanceledException>(
            () => client.GetAsync("recording/2", cts.Token));
    }
    
    [Fact]
    public async Task SendAsync_IntegrationWithRetryPolicy_WorksTogether()
    {
        // Arrange
        var attemptCount = 0;
        
        var mockInnerHandler = new Mock<HttpMessageHandler>();
        mockInnerHandler
            .Protected()
            .Setup<Task<HttpResponseMessage>>(
                "SendAsync",
                ItExpr.IsAny<HttpRequestMessage>(),
                ItExpr.IsAny<CancellationToken>())
            .ReturnsAsync(() =>
            {
                attemptCount++;
                
                // Fail first attempt, succeed second
                if (attemptCount == 1)
                {
                    return new HttpResponseMessage(HttpStatusCode.ServiceUnavailable);
                }
                
                return new HttpResponseMessage(HttpStatusCode.OK);
            });
        
        var handler = new MusicBrainzHttpMessageHandler(_rateLimiter, _mockLogger.Object)
        {
            InnerHandler = mockInnerHandler.Object
        };
        
        var client = new HttpClient(handler)
        {
            BaseAddress = new Uri("https://musicbrainz.org/ws/2/")
        };
        
        var policy = RetryPolicyFactory.CreateExternalApiRetryPolicy();
        
        // Act
        var response = await policy.ExecuteAsync(() => 
            client.GetAsync("recording/test"));
        
        // Assert
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Equal(2, attemptCount); // Initial + 1 retry
    }
    
    [Fact]
    public async Task SendAsync_MaintainsRateLimitAcrossRetries()
    {
        // Arrange
        var attemptCount = 0;
        var requestTimes = new List<long>();
        var stopwatch = Stopwatch.StartNew();
        
        var mockInnerHandler = new Mock<HttpMessageHandler>();
        mockInnerHandler
            .Protected()
            .Setup<Task<HttpResponseMessage>>(
                "SendAsync",
                ItExpr.IsAny<HttpRequestMessage>(),
                ItExpr.IsAny<CancellationToken>())
            .ReturnsAsync(() =>
            {
                attemptCount++;
                requestTimes.Add(stopwatch.ElapsedMilliseconds);
                
                // Fail twice, succeed on third
                if (attemptCount <= 2)
                {
                    return new HttpResponseMessage(HttpStatusCode.ServiceUnavailable);
                }
                
                return new HttpResponseMessage(HttpStatusCode.OK);
            });
        
        var handler = new MusicBrainzHttpMessageHandler(_rateLimiter, _mockLogger.Object)
        {
            InnerHandler = mockInnerHandler.Object
        };
        
        var client = new HttpClient(handler)
        {
            BaseAddress = new Uri("https://musicbrainz.org/ws/2/")
        };
        
        var policy = RetryPolicyFactory.CreateExternalApiRetryPolicy();
        
        // Act
        var response = await policy.ExecuteAsync(() => 
            client.GetAsync("recording/test"));
        
        stopwatch.Stop();
        
        // Assert
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Equal(3, attemptCount);
        Assert.Equal(3, requestTimes.Count);
        
        // Each attempt should respect rate limit
        // Request 1: immediate
        // Request 2: ~2 seconds later (1s rate limit + 2s retry delay)
        // Request 3: ~4 seconds later (1s rate limit + 4s retry delay from previous)
        Assert.InRange(requestTimes[0], 0, 100);
        Assert.True(requestTimes[1] >= 2000); // At least 2 seconds (retry delay)
        Assert.True(requestTimes[2] >= 5000); // At least 5 seconds cumulative
    }
    
    public void Dispose()
    {
        _rateLimiter?.Dispose();
    }
}