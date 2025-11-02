using System;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;

namespace Fuzzbin.Services.Http;

/// <summary>
/// HTTP message handler that enforces rate limiting for MusicBrainz API requests
/// </summary>
public class MusicBrainzHttpMessageHandler : DelegatingHandler
{
    private readonly MusicBrainzRateLimiter _rateLimiter;
    private readonly ILogger<MusicBrainzHttpMessageHandler> _logger;
    
    public MusicBrainzHttpMessageHandler(
        MusicBrainzRateLimiter rateLimiter,
        ILogger<MusicBrainzHttpMessageHandler> logger)
    {
        _rateLimiter = rateLimiter ?? throw new ArgumentNullException(nameof(rateLimiter));
        _logger = logger ?? throw new ArgumentNullException(nameof(logger));
    }
    
    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        // Acquire rate limit lease before making request
        using var lease = await _rateLimiter.AcquireAsync(cancellationToken);
        
        if (!lease.IsAcquired)
        {
            _logger.LogWarning("Rate limit exceeded for MusicBrainz request to {Uri}", request.RequestUri);
            throw new HttpRequestException("Rate limit exceeded for MusicBrainz API");
        }
        
        _logger.LogDebug("MusicBrainz rate limit acquired, making request to {Uri}", request.RequestUri);
        
        try
        {
            var response = await base.SendAsync(request, cancellationToken);
            
            // Log rate limit information if available in response headers
            if (response.Headers.Contains("X-RateLimit-Remaining"))
            {
                var remaining = response.Headers.GetValues("X-RateLimit-Remaining");
                _logger.LogDebug("MusicBrainz rate limit remaining: {Remaining}", string.Join(", ", remaining));
            }
            
            return response;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error making MusicBrainz request to {Uri}", request.RequestUri);
            throw;
        }
    }
}