using System;
using System.Diagnostics;
using System.Net;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using Fuzzbin.Services.Http;
using Microsoft.Extensions.Logging;
using Moq;
using Moq.Protected;
using Polly;
using Xunit;

namespace Fuzzbin.Tests.Http;

/// <summary>
/// Integration tests for RetryPolicyFactory
/// Verifies retry behavior, delays, and error handling
/// </summary>
public class RetryPolicyFactoryTests
{
    [Fact]
    public async Task RetryPolicy_RetriesOnTransientHttpError_WithCorrectDelays()
    {
        // Arrange
        var attemptCount = 0;
        var delays = new List<TimeSpan>();
        var stopwatch = Stopwatch.StartNew();
        var attemptTimes = new List<long>();
        
        var mockHandler = new Mock<HttpMessageHandler>();
        mockHandler
            .Protected()
            .Setup<Task<HttpResponseMessage>>(
                "SendAsync",
                ItExpr.IsAny<HttpRequestMessage>(),
                ItExpr.IsAny<CancellationToken>())
            .ReturnsAsync(() =>
            {
                attemptCount++;
                attemptTimes.Add(stopwatch.ElapsedMilliseconds);
                
                // First 3 attempts fail with 503, 4th succeeds
                if (attemptCount <= 3)
                {
                    return new HttpResponseMessage(HttpStatusCode.ServiceUnavailable);
                }
                
                return new HttpResponseMessage(HttpStatusCode.OK)
                {
                    Content = new StringContent("Success")
                };
            });
        
        var httpClient = new HttpClient(mockHandler.Object)
        {
            BaseAddress = new Uri("https://test.example.com")
        };
        
        var policy = RetryPolicyFactory.CreateExternalApiRetryPolicy();
        
        // Act
        var response = await policy.ExecuteAsync(() => 
            httpClient.GetAsync("/test"));
        
        // Assert
        Assert.Equal(4, attemptCount); // Initial + 3 retries
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        
        // Calculate delays between attempts
        for (int i = 1; i < attemptTimes.Count; i++)
        {
            delays.Add(TimeSpan.FromMilliseconds(attemptTimes[i] - attemptTimes[i - 1]));
        }
        
        // Verify retry delays (with 500ms tolerance for test timing)
        Assert.Equal(3, delays.Count);
        Assert.InRange(delays[0].TotalSeconds, 1.5, 2.5); // ~2 seconds
        Assert.InRange(delays[1].TotalSeconds, 3.5, 4.5); // ~4 seconds
        Assert.InRange(delays[2].TotalSeconds, 7.5, 8.5); // ~8 seconds
    }
    
    [Theory]
    [InlineData(HttpStatusCode.ServiceUnavailable)] // 503
    [InlineData(HttpStatusCode.BadGateway)] // 502
    [InlineData(HttpStatusCode.GatewayTimeout)] // 504
    [InlineData(HttpStatusCode.RequestTimeout)] // 408
    public async Task RetryPolicy_RetriesOnTransientHttpStatusCodes(HttpStatusCode statusCode)
    {
        // Arrange
        var attemptCount = 0;
        
        var mockHandler = new Mock<HttpMessageHandler>();
        mockHandler
            .Protected()
            .Setup<Task<HttpResponseMessage>>(
                "SendAsync",
                ItExpr.IsAny<HttpRequestMessage>(),
                ItExpr.IsAny<CancellationToken>())
            .ReturnsAsync(() =>
            {
                attemptCount++;
                
                // Fail twice, then succeed
                if (attemptCount <= 2)
                {
                    return new HttpResponseMessage(statusCode);
                }
                
                return new HttpResponseMessage(HttpStatusCode.OK);
            });
        
        var httpClient = new HttpClient(mockHandler.Object)
        {
            BaseAddress = new Uri("https://test.example.com")
        };
        
        var policy = RetryPolicyFactory.CreateExternalApiRetryPolicy();
        
        // Act
        var response = await policy.ExecuteAsync(() => 
            httpClient.GetAsync("/test"));
        
        // Assert
        Assert.Equal(3, attemptCount); // Initial + 2 retries
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }
    
    [Fact]
    public async Task RetryPolicy_RetriesOnRateLimitResponse_429()
    {
        // Arrange
        var attemptCount = 0;
        
        var mockHandler = new Mock<HttpMessageHandler>();
        mockHandler
            .Protected()
            .Setup<Task<HttpResponseMessage>>(
                "SendAsync",
                ItExpr.IsAny<HttpRequestMessage>(),
                ItExpr.IsAny<CancellationToken>())
            .ReturnsAsync(() =>
            {
                attemptCount++;
                
                // Return 429 once, then succeed
                if (attemptCount == 1)
                {
                    return new HttpResponseMessage((HttpStatusCode)429)
                    {
                        ReasonPhrase = "Too Many Requests"
                    };
                }
                
                return new HttpResponseMessage(HttpStatusCode.OK);
            });
        
        var httpClient = new HttpClient(mockHandler.Object)
        {
            BaseAddress = new Uri("https://test.example.com")
        };
        
        var policy = RetryPolicyFactory.CreateExternalApiRetryPolicy();
        
        // Act
        var response = await policy.ExecuteAsync(() => 
            httpClient.GetAsync("/test"));
        
        // Assert
        Assert.Equal(2, attemptCount); // Initial + 1 retry
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }
    
    [Fact]
    public async Task RetryPolicy_DoesNotRetryOnClientError_400()
    {
        // Arrange
        var attemptCount = 0;
        
        var mockHandler = new Mock<HttpMessageHandler>();
        mockHandler
            .Protected()
            .Setup<Task<HttpResponseMessage>>(
                "SendAsync",
                ItExpr.IsAny<HttpRequestMessage>(),
                ItExpr.IsAny<CancellationToken>())
            .ReturnsAsync(() =>
            {
                attemptCount++;
                return new HttpResponseMessage(HttpStatusCode.BadRequest);
            });
        
        var httpClient = new HttpClient(mockHandler.Object)
        {
            BaseAddress = new Uri("https://test.example.com")
        };
        
        var policy = RetryPolicyFactory.CreateExternalApiRetryPolicy();
        
        // Act
        var response = await policy.ExecuteAsync(() => 
            httpClient.GetAsync("/test"));
        
        // Assert
        Assert.Equal(1, attemptCount); // No retries
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
    }
    
    [Fact]
    public async Task RetryPolicy_DoesNotRetryOnSuccess_200()
    {
        // Arrange
        var attemptCount = 0;
        
        var mockHandler = new Mock<HttpMessageHandler>();
        mockHandler
            .Protected()
            .Setup<Task<HttpResponseMessage>>(
                "SendAsync",
                ItExpr.IsAny<HttpRequestMessage>(),
                ItExpr.IsAny<CancellationToken>())
            .ReturnsAsync(() =>
            {
                attemptCount++;
                return new HttpResponseMessage(HttpStatusCode.OK)
                {
                    Content = new StringContent("Success")
                };
            });
        
        var httpClient = new HttpClient(mockHandler.Object)
        {
            BaseAddress = new Uri("https://test.example.com")
        };
        
        var policy = RetryPolicyFactory.CreateExternalApiRetryPolicy();
        
        // Act
        var response = await policy.ExecuteAsync(() => 
            httpClient.GetAsync("/test"));
        
        // Assert
        Assert.Equal(1, attemptCount); // No retries needed
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }
    
    [Fact]
    public async Task RetryPolicy_ExhaustsRetriesAndReturnsLastFailure()
    {
        // Arrange
        var attemptCount = 0;
        
        var mockHandler = new Mock<HttpMessageHandler>();
        mockHandler
            .Protected()
            .Setup<Task<HttpResponseMessage>>(
                "SendAsync",
                ItExpr.IsAny<HttpRequestMessage>(),
                ItExpr.IsAny<CancellationToken>())
            .ReturnsAsync(() =>
            {
                attemptCount++;
                return new HttpResponseMessage(HttpStatusCode.ServiceUnavailable);
            });
        
        var httpClient = new HttpClient(mockHandler.Object)
        {
            BaseAddress = new Uri("https://test.example.com")
        };
        
        var policy = RetryPolicyFactory.CreateExternalApiRetryPolicy();
        
        // Act
        var response = await policy.ExecuteAsync(() => 
            httpClient.GetAsync("/test"));
        
        // Assert
        Assert.Equal(4, attemptCount); // Initial + 3 retries
        Assert.Equal(HttpStatusCode.ServiceUnavailable, response.StatusCode);
    }
    
    [Fact]
    public async Task RetryPolicy_LogsRetryAttempts_WhenLoggerInContext()
    {
        // Arrange
        var mockLogger = new Mock<ILogger>();
        var logMessages = new List<string>();
        
        mockLogger
            .Setup(l => l.Log(
                It.IsAny<LogLevel>(),
                It.IsAny<EventId>(),
                It.IsAny<It.IsAnyType>(),
                It.IsAny<Exception>(),
                It.IsAny<Func<It.IsAnyType, Exception?, string>>()))
            .Callback((LogLevel level, EventId eventId, object state, Exception exception, Delegate formatter) =>
            {
                logMessages.Add(state.ToString() ?? "");
            });
        
        var attemptCount = 0;
        var mockHandler = new Mock<HttpMessageHandler>();
        mockHandler
            .Protected()
            .Setup<Task<HttpResponseMessage>>(
                "SendAsync",
                ItExpr.IsAny<HttpRequestMessage>(),
                ItExpr.IsAny<CancellationToken>())
            .ReturnsAsync(() =>
            {
                attemptCount++;
                
                if (attemptCount <= 2)
                {
                    return new HttpResponseMessage(HttpStatusCode.ServiceUnavailable);
                }
                
                return new HttpResponseMessage(HttpStatusCode.OK);
            });
        
        var httpClient = new HttpClient(mockHandler.Object)
        {
            BaseAddress = new Uri("https://test.example.com")
        };
        
        var policy = RetryPolicyFactory.CreateExternalApiRetryPolicy();
        var context = new Context();
        context["Logger"] = mockLogger.Object;
        
        // Act
        var response = await policy.ExecuteAsync(ctx => 
            httpClient.GetAsync("/test"), context);
        
        // Assert
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        
        // Verify logging occurred (2 retries logged)
        mockLogger.Verify(
            l => l.Log(
                LogLevel.Warning,
                It.IsAny<EventId>(),
                It.IsAny<It.IsAnyType>(),
                It.IsAny<Exception>(),
                It.IsAny<Func<It.IsAnyType, Exception?, string>>()),
            Times.Exactly(2));
    }
    
    [Fact]
    public async Task RetryPolicy_RetriesOnHttpRequestException()
    {
        // Arrange
        var attemptCount = 0;
        
        var mockHandler = new Mock<HttpMessageHandler>();
        mockHandler
            .Protected()
            .Setup<Task<HttpResponseMessage>>(
                "SendAsync",
                ItExpr.IsAny<HttpRequestMessage>(),
                ItExpr.IsAny<CancellationToken>())
            .ReturnsAsync(() =>
            {
                attemptCount++;
                
                // Throw exception once, then succeed
                if (attemptCount == 1)
                {
                    throw new HttpRequestException("Network error");
                }
                
                return new HttpResponseMessage(HttpStatusCode.OK);
            });
        
        var httpClient = new HttpClient(mockHandler.Object)
        {
            BaseAddress = new Uri("https://test.example.com")
        };
        
        var policy = RetryPolicyFactory.CreateExternalApiRetryPolicy();
        
        // Act
        var response = await policy.ExecuteAsync(() => 
            httpClient.GetAsync("/test"));
        
        // Assert
        Assert.Equal(2, attemptCount); // Initial + 1 retry
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }
}