using System;

namespace Fuzzbin.Services.Models;

public class ImvdbOptions
{
    /// <summary>
    /// Base URL for IMVDb API requests.
    /// </summary>
    public string BaseUrl { get; set; } = "https://imvdb.com/api/v1";

    /// <summary>
    /// Optional API key supplied via configuration/environment; database value overrides when present.
    /// </summary>
    public string? ApiKey { get; set; }

    /// <summary>
    /// Sliding cache duration for IMVDb responses.
    /// </summary>
    public TimeSpan CacheDuration { get; set; } = TimeSpan.FromHours(24);

    /// <summary>
    /// Maximum retries for transient HTTP failures.
    /// </summary>
    public int RetryCount { get; set; } = 3;

    /// <summary>
    /// Circuit breaker failure threshold before halting outbound calls.
    /// </summary>
    public int CircuitBreakerFailures { get; set; } = 5;

    /// <summary>
    /// Duration the circuit breaker remains open after tripping.
    /// </summary>
    public TimeSpan CircuitBreakerDuration { get; set; } = TimeSpan.FromSeconds(30);

    /// <summary>
    /// Maximum number of outbound calls permitted within a given rate limit window.
    /// </summary>
    public int RateLimitRequests { get; set; } = 5;

    /// <summary>
    /// Window for rate limiting calculations.
    /// </summary>
    public TimeSpan RateLimitWindow { get; set; } = TimeSpan.FromSeconds(1);
}
