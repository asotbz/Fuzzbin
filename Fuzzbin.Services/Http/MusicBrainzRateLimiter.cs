using System;
using System.Threading;
using System.Threading.RateLimiting;
using System.Threading.Tasks;

namespace Fuzzbin.Services.Http;

/// <summary>
/// Rate limiter for MusicBrainz API requests
/// Enforces 1 request per second as per MusicBrainz API guidelines
/// </summary>
public sealed class MusicBrainzRateLimiter : IDisposable
{
    private readonly RateLimiter _rateLimiter;
    
    public MusicBrainzRateLimiter()
    {
        // 1 request per second for MusicBrainz API
        _rateLimiter = new SlidingWindowRateLimiter(new SlidingWindowRateLimiterOptions
        {
            Window = TimeSpan.FromSeconds(1),
            PermitLimit = 1,
            SegmentsPerWindow = 1,
            QueueProcessingOrder = QueueProcessingOrder.OldestFirst,
            QueueLimit = 10
        });
    }
    
    /// <summary>
    /// Acquires a rate limit lease for making a request
    /// </summary>
    /// <param name="cancellationToken">Cancellation token</param>
    /// <returns>Rate limit lease that must be disposed after use</returns>
    public async Task<RateLimitLease> AcquireAsync(CancellationToken cancellationToken = default)
    {
        return await _rateLimiter.AcquireAsync(permitCount: 1, cancellationToken);
    }
    
    /// <summary>
    /// Attempts to acquire a rate limit lease without waiting
    /// </summary>
    /// <returns>Rate limit lease if successful, null otherwise</returns>
    public RateLimitLease? TryAcquire()
    {
        var lease = _rateLimiter.AttemptAcquire(permitCount: 1);
        return lease.IsAcquired ? lease : null;
    }
    
    public void Dispose()
    {
        _rateLimiter.Dispose();
    }
}