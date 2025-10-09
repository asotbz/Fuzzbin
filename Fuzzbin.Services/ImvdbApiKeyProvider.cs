using System;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;

namespace Fuzzbin.Services;

public class ImvdbApiKeyProvider : IImvdbApiKeyProvider
{
    private const string CacheKey = "imvdb_api_key";
    private readonly IServiceScopeFactory _scopeFactory;
    private readonly IMemoryCache _cache;
    private readonly IOptions<ImvdbOptions> _options;
    private readonly ILogger<ImvdbApiKeyProvider> _logger;

    public ImvdbApiKeyProvider(
        IServiceScopeFactory scopeFactory,
        IMemoryCache cache,
        IOptions<ImvdbOptions> options,
        ILogger<ImvdbApiKeyProvider> logger)
    {
        _scopeFactory = scopeFactory;
        _cache = cache;
        _options = options;
        _logger = logger;
    }

    public async Task<string?> GetApiKeyAsync(CancellationToken cancellationToken = default)
    {
        if (_cache.TryGetValue<string>(CacheKey, out var cached))
        {
            return cached;
        }

        var optionKey = _options.Value.ApiKey;
        if (!string.IsNullOrWhiteSpace(optionKey))
        {
            CacheKeyValue(optionKey);
            return optionKey;
        }

        using var scope = _scopeFactory.CreateScope();
        var unitOfWork = scope.ServiceProvider.GetRequiredService<IUnitOfWork>();
        var config = await unitOfWork.Configurations
            .FirstOrDefaultAsync(c => c.Key == "ImvdbApiKey" && c.Category == "API");

        var dbKey = config?.Value;
        if (!string.IsNullOrWhiteSpace(dbKey))
        {
            CacheKeyValue(dbKey);
            return dbKey;
        }

        _logger.LogWarning("IMVDb API key not configured; falling back to unauthenticated requests");
        return null;
    }

    private void CacheKeyValue(string key)
    {
        var options = new MemoryCacheEntryOptions
        {
            AbsoluteExpirationRelativeToNow = TimeSpan.FromMinutes(10)
        };
        _cache.Set(CacheKey, key, options);
    }
}
