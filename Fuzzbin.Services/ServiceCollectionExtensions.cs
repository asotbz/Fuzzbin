using System;
using System.Net;
using System.Net.Http;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Polly;
using Polly.Extensions.Http;
using Refit;
using Fuzzbin.Services.External.Imvdb;
using Fuzzbin.Services.Http;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;

namespace Fuzzbin.Services;

public static class ServiceCollectionExtensions
{
    public static IServiceCollection AddImvdbIntegration(this IServiceCollection services)
    {
        services.AddSingleton<IImvdbApiKeyProvider, ImvdbApiKeyProvider>();
        services.AddTransient<ImvdbAuthenticationHandler>();
        services.AddTransient<ImvdbRateLimiterHandler>();

        services.AddRefitClient<IImvdbApi>()
            .ConfigureHttpClient((sp, client) =>
            {
                var options = sp.GetRequiredService<IOptions<ImvdbOptions>>().Value;
                client.BaseAddress = new Uri(options.BaseUrl);
                client.Timeout = TimeSpan.FromSeconds(30);
            })
            .AddHttpMessageHandler<ImvdbAuthenticationHandler>()
            .AddHttpMessageHandler<ImvdbRateLimiterHandler>()
            .AddPolicyHandler((sp, _) => CreateRetryPolicy(sp))
            .AddPolicyHandler((sp, _) => CreateCircuitBreakerPolicy(sp));

        return services;
    }

    private static IAsyncPolicy<HttpResponseMessage> CreateRetryPolicy(IServiceProvider sp)
    {
        var options = sp.GetRequiredService<IOptions<ImvdbOptions>>().Value;
        var logger = sp.GetRequiredService<ILoggerFactory>().CreateLogger("ImvdbHttpRetry");

        if (options.RetryCount <= 0)
        {
            return Policy.NoOpAsync<HttpResponseMessage>();
        }

        return HttpPolicyExtensions
            .HandleTransientHttpError()
            .OrResult(response => response.StatusCode == HttpStatusCode.TooManyRequests)
            .WaitAndRetryAsync(options.RetryCount, retryAttempt =>
                TimeSpan.FromSeconds(Math.Pow(2, retryAttempt)),
                (outcome, timespan, retryAttempt, context) =>
                {
                    var reason = outcome.Exception?.Message
                        ?? outcome.Result?.StatusCode.ToString();
                    logger.LogWarning(
                        "Retrying IMVDb request (attempt {RetryAttempt}) due to {Reason}",
                        retryAttempt,
                        reason);
                });
    }

    private static IAsyncPolicy<HttpResponseMessage> CreateCircuitBreakerPolicy(IServiceProvider sp)
    {
        var options = sp.GetRequiredService<IOptions<ImvdbOptions>>().Value;
        var logger = sp.GetRequiredService<ILoggerFactory>().CreateLogger("ImvdbHttpCircuitBreaker");

        if (options.CircuitBreakerFailures <= 0)
        {
            return Policy.NoOpAsync<HttpResponseMessage>();
        }

        return HttpPolicyExtensions
            .HandleTransientHttpError()
            .CircuitBreakerAsync(
                handledEventsAllowedBeforeBreaking: options.CircuitBreakerFailures,
                durationOfBreak: options.CircuitBreakerDuration <= TimeSpan.Zero
                    ? TimeSpan.FromSeconds(30)
                    : options.CircuitBreakerDuration,
                onBreak: (outcome, breakDelay) =>
                {
                    var reason = outcome.Exception?.Message
                        ?? outcome.Result?.StatusCode.ToString();
                    logger.LogWarning(
                        "IMVDb circuit breaker open for {BreakDelay}. Reason: {Reason}",
                        breakDelay,
                        reason);
                },
                onReset: () => logger.LogInformation("IMVDb circuit breaker reset"));
    }
}
