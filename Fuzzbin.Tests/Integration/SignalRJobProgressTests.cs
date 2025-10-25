using System;
using System.Collections.Concurrent;
using System.Linq;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.SignalR.Client;
using Microsoft.Extensions.DependencyInjection;
using Xunit;
using System.Text.Json;

namespace Fuzzbin.Tests.Integration
{
    /// <summary>
    /// Smoke integration test validating that SignalR hub emits lifecycle events
    /// for a processed background job and that a subscribed client receives them.
    /// </summary>
    public class SignalRJobProgressTests : IAsyncLifetime
    {
        private readonly WebApplicationFactory<Program> _factory;
        private HubConnection? _connection;
        private HttpClient? _client;

        public SignalRJobProgressTests()
        {
            _factory = new WebApplicationFactory<Program>()
                .WithWebHostBuilder(builder =>
                {
                    builder.ConfigureServices(services =>
                    {
                        // Register BackgroundJobProcessorService for tests
                        services.AddScoped<Fuzzbin.Services.BackgroundJobProcessorService>();
                    });
                });
        }

        public async Task InitializeAsync()
        {
            _client = _factory.CreateClient();
            // Build HubConnection using server's handler so we stay in-memory (no real network).
            _connection = new HubConnectionBuilder()
                .WithUrl(new Uri(_client.BaseAddress!, "hubs/jobprogress"), options =>
                {
                    // Reuse server handler for in-memory transport
                    options.HttpMessageHandlerFactory = _ => _factory.Server.CreateHandler();
                })
                .WithAutomaticReconnect()
                .Build();

            await _connection.StartAsync();
        }

        public async Task DisposeAsync()
        {
            if (_connection is not null)
            {
                await _connection.DisposeAsync();
            }
            _client?.Dispose();
            _factory.Dispose();
        }

        [Fact(Timeout = 15000)]
        public async Task JobLifecycleEvents_AreReceivedBySubscribedClient()
        {
            Assert.NotNull(_connection);

            // Arrange: create a pending RefreshMetadata job
            Guid jobId;
            using (var scope = _factory.Services.CreateScope())
            {
                var jobService = scope.ServiceProvider.GetRequiredService<IBackgroundJobService>();
                var job = await jobService.CreateJobAsync(BackgroundJobType.RefreshMetadata);
                jobId = job.Id;
            }

            // Event capture collections
            var started = new ConcurrentBag<Guid>();
            var completed = new ConcurrentBag<Guid>();
            var failed = new ConcurrentBag<(Guid Id, string Error)>();
            var cancelled = new ConcurrentBag<Guid>();
            var observedEvents = new ConcurrentBag<string>();

            // Register handlers
            _connection!.On<JsonElement>("JobStarted", payload =>
            {
                observedEvents.Add($"Started:{payload}");
                var id = ExtractGuid(payload, "JobId");
                if (id != Guid.Empty) started.Add(id);
            });
            _connection.On<JsonElement>("JobCompleted", payload =>
            {
                observedEvents.Add($"Completed:{payload}");
                var id = ExtractGuid(payload, "JobId");
                if (id != Guid.Empty) completed.Add(id);
            });
            _connection.On<JsonElement>("JobFailed", payload =>
            {
                observedEvents.Add($"Failed:{payload}");
                var id = ExtractGuid(payload, "JobId");
                var err = ExtractString(payload, "ErrorMessage");
                if (id != Guid.Empty) failed.Add((id, err ?? string.Empty));
            });
            _connection.On<JsonElement>("JobCancelled", payload =>
            {
                observedEvents.Add($"Cancelled:{payload}");
                var id = ExtractGuid(payload, "JobId");
                if (id != Guid.Empty) cancelled.Add(id);
            });

            // Subscribe to the specific job group before processing begins
            await _connection.InvokeAsync("SubscribeToJob", jobId);

            // Act: process pending jobs exactly once
            using (var scope = _factory.Services.CreateScope())
            {
                var processor = scope.ServiceProvider.GetRequiredService<Fuzzbin.Services.BackgroundJobProcessorService>();
                await processor.ProcessOnceForTestsAsync();
            }

            // Wait for expected events (Started + Completed OR Failed)
            var sw = System.Diagnostics.Stopwatch.StartNew();
            while (sw.Elapsed < TimeSpan.FromSeconds(5))
            {
                if (started.Contains(jobId) && (completed.Contains(jobId) || failed.Any(f => f.Id == jobId)))
                {
                    break;
                }
                await Task.Delay(50);
            }

            // Assert
            var eventsSnapshot = observedEvents.ToArray();
            Assert.True(started.Contains(jobId), $"Expected JobStarted for {jobId}, observed events: {string.Join(" | ", eventsSnapshot)}");
            Assert.True(completed.Contains(jobId) ^ failed.Any(f => f.Id == jobId), "Job should be either completed or failed, not both.");
            Assert.DoesNotContain(jobId, cancelled);

            // If it failed, ensure error is captured
            if (failed.Any(f => f.Id == jobId))
            {
                var err = failed.First(f => f.Id == jobId).Error;
                Assert.False(string.IsNullOrWhiteSpace(err), "Failure event should include error message.");
            }
        }

        private static Guid ExtractGuid(object payload, string propertyName)
        {
            if (TryGetJsonValue(payload, propertyName, out var value))
            {
                if (value.ValueKind == JsonValueKind.String &&
                    Guid.TryParse(value.GetString(), out var parsed))
                {
                    return parsed;
                }
            }

            var prop = payload.GetType().GetProperty(propertyName);
            if (prop?.GetValue(payload) is Guid g) return g;
            if (prop?.GetValue(payload) is string s && Guid.TryParse(s, out var parsedGuid)) return parsedGuid;
            return Guid.Empty;
        }

        private static string? ExtractString(object payload, string propertyName)
        {
            if (TryGetJsonValue(payload, propertyName, out var value))
            {
                return value.ValueKind switch
                {
                    JsonValueKind.String => value.GetString(),
                    JsonValueKind.Number => value.ToString(),
                    JsonValueKind.True => bool.TrueString,
                    JsonValueKind.False => bool.FalseString,
                    _ => value.ToString()
                };
            }

            var prop = payload.GetType().GetProperty(propertyName);
            return prop?.GetValue(payload)?.ToString();
        }

        private static bool TryGetJsonValue(object payload, string propertyName, out JsonElement value)
        {
            if (payload is JsonElement element && element.ValueKind == JsonValueKind.Object)
            {
                if (element.TryGetProperty(propertyName, out value))
                {
                    return true;
                }

                var camel = char.ToLowerInvariant(propertyName[0]) + propertyName.Substring(1);
                if (element.TryGetProperty(camel, out value))
                {
                    return true;
                }
            }

            value = default;
            return false;
        }
    }
}
