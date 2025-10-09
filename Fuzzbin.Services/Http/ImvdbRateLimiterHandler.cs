using System;
using System.Net.Http;
using System.Threading;
using System.Threading.RateLimiting;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Fuzzbin.Services.Models;

namespace Fuzzbin.Services.Http;

/// <summary>
/// Limits outbound IMVDb API requests to avoid quota exhaustion.
/// </summary>
public class ImvdbRateLimiterHandler : DelegatingHandler
{
    private readonly RateLimiter _rateLimiter;
    private readonly ILogger<ImvdbRateLimiterHandler> _logger;

    public ImvdbRateLimiterHandler(IOptions<ImvdbOptions> options, ILogger<ImvdbRateLimiterHandler> logger)
    {
        _logger = logger;
        var opts = options.Value;

        var permitLimit = Math.Max(1, opts.RateLimitRequests);
        var window = opts.RateLimitWindow <= TimeSpan.Zero
            ? TimeSpan.FromSeconds(1)
            : opts.RateLimitWindow;

        _rateLimiter = new FixedWindowRateLimiter(new FixedWindowRateLimiterOptions
        {
            AutoReplenishment = true,
            PermitLimit = permitLimit,
            QueueLimit = permitLimit,
            Window = window,
            QueueProcessingOrder = QueueProcessingOrder.OldestFirst
        });
    }

    protected override async Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
    {
        using var lease = await _rateLimiter.AcquireAsync(1, cancellationToken).ConfigureAwait(false);
        if (!lease.IsAcquired)
        {
            _logger.LogWarning("Failed to acquire IMVDb rate limit permit");
            throw new InvalidOperationException("IMVDb rate limit exceeded");
        }

        return await base.SendAsync(request, cancellationToken).ConfigureAwait(false);
    }
}
