using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Fuzzbin.Services.Http;
using Xunit;

namespace Fuzzbin.Tests.Http;

/// <summary>
/// Integration tests for MusicBrainzRateLimiter
/// Verifies rate limiting behavior and queue management
/// </summary>
public class MusicBrainzRateLimiterTests : IDisposable
{
    private readonly MusicBrainzRateLimiter _rateLimiter;
    
    public MusicBrainzRateLimiterTests()
    {
        _rateLimiter = new MusicBrainzRateLimiter();
    }
    
    [Fact]
    public async Task AcquireAsync_FirstRequest_AcquiresImmediately()
    {
        // Arrange
        var stopwatch = Stopwatch.StartNew();
        
        // Act
        using var lease = await _rateLimiter.AcquireAsync();
        stopwatch.Stop();
        
        // Assert
        Assert.True(lease.IsAcquired);
        Assert.True(stopwatch.ElapsedMilliseconds < 100, 
            $"Expected immediate acquisition, but took {stopwatch.ElapsedMilliseconds}ms");
    }
    
    [Fact]
    public async Task AcquireAsync_TwoSequentialRequests_SecondWaitsOneSecond()
    {
        // Arrange
        using var lease1 = await _rateLimiter.AcquireAsync();
        Assert.True(lease1.IsAcquired);
        
        var stopwatch = Stopwatch.StartNew();
        
        // Act
        using var lease2 = await _rateLimiter.AcquireAsync();
        stopwatch.Stop();
        
        // Assert
        Assert.True(lease2.IsAcquired);
        Assert.InRange(stopwatch.ElapsedMilliseconds, 900, 1200); // ~1 second with tolerance
    }
    
    [Fact]
    public async Task AcquireAsync_ThreeSequentialRequests_EnforcesOnePerSecond()
    {
        // Arrange
        var acquisitionTimes = new List<long>();
        var overallStopwatch = Stopwatch.StartNew();
        
        // Act
        for (int i = 0; i < 3; i++)
        {
            using var lease = await _rateLimiter.AcquireAsync();
            Assert.True(lease.IsAcquired);
            acquisitionTimes.Add(overallStopwatch.ElapsedMilliseconds);
        }
        
        overallStopwatch.Stop();
        
        // Assert
        // First request should be immediate (~0ms)
        Assert.InRange(acquisitionTimes[0], 0, 100);
        
        // Second request should be ~1000ms
        Assert.InRange(acquisitionTimes[1], 900, 1200);
        
        // Third request should be ~2000ms
        Assert.InRange(acquisitionTimes[2], 1900, 2200);
        
        // Total time should be ~2 seconds
        Assert.InRange(overallStopwatch.ElapsedMilliseconds, 1900, 2300);
    }
    
    [Fact]
    public async Task AcquireAsync_ConcurrentRequests_ProcessedSequentially()
    {
        // Arrange
        var concurrentRequests = 5;
        var acquisitionTimes = new List<long>();
        var timesLock = new object();
        var overallStopwatch = Stopwatch.StartNew();
        
        // Act
        var tasks = Enumerable.Range(0, concurrentRequests)
            .Select(async i =>
            {
                using var lease = await _rateLimiter.AcquireAsync();
                
                lock (timesLock)
                {
                    acquisitionTimes.Add(overallStopwatch.ElapsedMilliseconds);
                }
                
                return lease.IsAcquired;
            })
            .ToList();
        
        var results = await Task.WhenAll(tasks);
        overallStopwatch.Stop();
        
        // Assert
        Assert.All(results, acquired => Assert.True(acquired));
        Assert.Equal(concurrentRequests, acquisitionTimes.Count);
        
        // Verify requests were spaced ~1 second apart
        lock (timesLock)
        {
            acquisitionTimes.Sort();
            
            for (int i = 1; i < acquisitionTimes.Count; i++)
            {
                var timeBetween = acquisitionTimes[i] - acquisitionTimes[i - 1];
                Assert.InRange(timeBetween, 800, 1300); // ~1 second with tolerance
            }
        }
        
        // Total time should be ~4 seconds (5 requests at 1 req/sec)
        Assert.InRange(overallStopwatch.ElapsedMilliseconds, 3800, 4500);
    }
    
    [Fact]
    public void TryAcquire_FirstRequest_SucceedsImmediately()
    {
        // Act
        var lease = _rateLimiter.TryAcquire();
        
        // Assert
        Assert.NotNull(lease);
        Assert.True(lease.IsAcquired);
        
        lease?.Dispose();
    }
    
    [Fact]
    public void TryAcquire_SecondImmediateRequest_Fails()
    {
        // Arrange
        var lease1 = _rateLimiter.TryAcquire();
        Assert.NotNull(lease1);
        Assert.True(lease1.IsAcquired);
        
        // Act
        var lease2 = _rateLimiter.TryAcquire();
        
        // Assert
        Assert.Null(lease2); // Should fail because rate limit is exceeded
        
        lease1?.Dispose();
    }
    
    [Fact]
    public async Task TryAcquire_AfterOneSecond_SucceedsAgain()
    {
        // Arrange
        var lease1 = _rateLimiter.TryAcquire();
        Assert.NotNull(lease1);
        lease1?.Dispose();
        
        // Wait for rate limit window to reset
        await Task.Delay(TimeSpan.FromSeconds(1.1));
        
        // Act
        var lease2 = _rateLimiter.TryAcquire();
        
        // Assert
        Assert.NotNull(lease2);
        Assert.True(lease2.IsAcquired);
        
        lease2?.Dispose();
    }
    
    [Fact]
    public async Task AcquireAsync_WithCancellation_ThrowsOperationCanceledException()
    {
        // Arrange
        using var cts = new CancellationTokenSource();
        
        // Acquire first lease to force second to wait
        using var lease1 = await _rateLimiter.AcquireAsync();
        
        // Cancel after 100ms
        cts.CancelAfter(100);
        
        // Act & Assert
        await Assert.ThrowsAnyAsync<OperationCanceledException>(async () =>
        {
            using var lease2 = await _rateLimiter.AcquireAsync(cts.Token);
        });
    }
    
    [Fact]
    public async Task AcquireAsync_QueueLimit_AcceptsUpToTenRequests()
    {
        // Arrange
        var queuedRequests = 11; // Queue limit is 10, so 11th should fail or be rejected
        var tasks = new List<Task<bool>>();
        var exceptions = new List<Exception>();
        
        // Act
        // Fire off 11 concurrent requests
        for (int i = 0; i < queuedRequests; i++)
        {
            var task = Task.Run(async () =>
            {
                try
                {
                    using var lease = await _rateLimiter.AcquireAsync();
                    return lease.IsAcquired;
                }
                catch (Exception ex)
                {
                    lock (exceptions)
                    {
                        exceptions.Add(ex);
                    }
                    return false;
                }
            });
            
            tasks.Add(task);
        }
        
        var results = await Task.WhenAll(tasks);
        
        // Assert
        // At least 10 should succeed (within queue limit)
        var successCount = results.Count(r => r);
        Assert.True(successCount >= 10, 
            $"Expected at least 10 successful acquisitions, got {successCount}");
    }
    
    [Fact]
    public async Task AcquireAsync_MultipleLeases_ReleasedProperly()
    {
        // Arrange
        var leaseCount = 3;
        var acquisitionTimes = new List<long>();
        var stopwatch = Stopwatch.StartNew();
        
        // Act
        for (int i = 0; i < leaseCount; i++)
        {
            using (var lease = await _rateLimiter.AcquireAsync())
            {
                Assert.True(lease.IsAcquired);
                acquisitionTimes.Add(stopwatch.ElapsedMilliseconds);
                
                // Lease is automatically disposed here
            }
        }
        
        stopwatch.Stop();
        
        // Assert
        Assert.Equal(leaseCount, acquisitionTimes.Count);
        
        // Verify proper spacing between acquisitions
        for (int i = 1; i < acquisitionTimes.Count; i++)
        {
            var timeBetween = acquisitionTimes[i] - acquisitionTimes[i - 1];
            Assert.InRange(timeBetween, 900, 1200);
        }
    }
    
    [Fact]
    public async Task RateLimiter_UnderLoad_MaintainsOnePerSecondRate()
    {
        // Arrange
        var requestCount = 10;
        var completedRequests = 0;
        var completedLock = new object();
        var stopwatch = Stopwatch.StartNew();
        
        // Act
        var tasks = Enumerable.Range(0, requestCount)
            .Select(async i =>
            {
                using var lease = await _rateLimiter.AcquireAsync();
                
                lock (completedLock)
                {
                    completedRequests++;
                }
                
                return lease.IsAcquired;
            })
            .ToList();
        
        var results = await Task.WhenAll(tasks);
        stopwatch.Stop();
        
        // Assert
        Assert.All(results, acquired => Assert.True(acquired));
        Assert.Equal(requestCount, completedRequests);
        
        // Average rate should be ~1 request per second
        var expectedMinTime = (requestCount - 1) * 900; // Allow 100ms tolerance per request
        var expectedMaxTime = (requestCount - 1) * 1200;
        
        Assert.InRange(stopwatch.ElapsedMilliseconds, expectedMinTime, expectedMaxTime);
    }
    
    public void Dispose()
    {
        _rateLimiter?.Dispose();
    }
}