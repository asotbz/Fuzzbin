using System;
using System.Net.Http;
using Microsoft.Extensions.Logging;
using Polly;
using Polly.Extensions.Http;

namespace Fuzzbin.Services.Http;

/// <summary>
/// Factory for creating Polly retry policies for HTTP requests to external APIs
/// </summary>
public static class RetryPolicyFactory
{
    /// <summary>
    /// Creates a retry policy for external API calls with exponential backoff
    /// Retries on transient HTTP errors and rate limit responses (429)
    /// - Retry 1: 2 seconds delay
    /// - Retry 2: 4 seconds delay
    /// - Retry 3: 8 seconds delay
    /// </summary>
    public static IAsyncPolicy<HttpResponseMessage> CreateExternalApiRetryPolicy()
    {
        return HttpPolicyExtensions
            .HandleTransientHttpError()
            .OrResult(msg => (int)msg.StatusCode == 429) // Rate limit
            .WaitAndRetryAsync(
                retryCount: 3,
                sleepDurationProvider: retryAttempt => retryAttempt switch
                {
                    1 => TimeSpan.FromSeconds(2),
                    2 => TimeSpan.FromSeconds(4),
                    _ => TimeSpan.FromSeconds(8)
                },
                onRetry: (outcome, timespan, retryCount, context) =>
                {
                    var logger = context.GetLogger();
                    if (logger != null)
                    {
                        var reason = outcome.Exception?.Message ?? 
                                   outcome.Result?.ReasonPhrase ?? 
                                   "unknown";
                        var statusCode = outcome.Result?.StatusCode.ToString() ?? "N/A";
                        
                        logger.LogWarning(
                            "Retry {RetryCount} after {Delay}s due to {Reason} (Status: {StatusCode})",
                            retryCount,
                            timespan.TotalSeconds,
                            reason,
                            statusCode);
                    }
                });
    }
    
    /// <summary>
    /// Extension method to get ILogger from Polly context
    /// </summary>
    private static ILogger? GetLogger(this Context context)
    {
        if (context.TryGetValue("Logger", out var logger) && logger is ILogger log)
        {
            return log;
        }
        return null;
    }
}