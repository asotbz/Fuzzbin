using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;

namespace Fuzzbin.Services;

public sealed class MetadataSettingsProvider : IMetadataSettingsProvider
{
    private const string CacheKey = "Fuzzbin.MetadataSettings";
    private static readonly TimeSpan CacheDuration = TimeSpan.FromMinutes(5);

    private readonly IServiceScopeFactory _scopeFactory;
    private readonly IMemoryCache _cache;
    private readonly ILogger<MetadataSettingsProvider> _logger;
    private readonly IGenreMappingDefaultsProvider _defaultsProvider;
    private readonly JsonSerializerOptions _jsonOptions = new() { PropertyNameCaseInsensitive = true };

    public MetadataSettingsProvider(
        IServiceScopeFactory scopeFactory,
        IMemoryCache cache,
        ILogger<MetadataSettingsProvider> logger,
        IGenreMappingDefaultsProvider defaultsProvider)
    {
        _scopeFactory = scopeFactory;
        _cache = cache;
        _logger = logger;
        _defaultsProvider = defaultsProvider;
    }

    public MetadataSettings GetSettings()
    {
        return _cache.GetOrCreate(CacheKey, entry =>
        {
            entry.AbsoluteExpirationRelativeToNow = CacheDuration;
            return LoadSettings();
        }) ?? MetadataSettings.Default;
    }

    public void Invalidate() => _cache.Remove(CacheKey);

    private MetadataSettings LoadSettings()
    {
        try
        {
            using var scope = _scopeFactory.CreateScope();
            var unitOfWork = scope.ServiceProvider.GetRequiredService<IUnitOfWork>();

            var generalizeGenres = ReadBool(unitOfWork, "Metadata", "GeneralizeGenres", defaultValue: false);
            var writeExternalGenreAsTag = generalizeGenres
                ? ReadBool(unitOfWork, "Metadata", "WriteExternalGenreAsTag", defaultValue: false)
                : false;
            var genreMappings = generalizeGenres
                ? ReadGenreMappings(unitOfWork)
                : new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            
            // Read new artist mode configuration with backward compatibility
            var artistMode = ReadArtistMode(unitOfWork);
            
            var writeCollectionsAsNfoTags = ReadBool(unitOfWork, "Metadata", "WriteCollectionsAsNfoTags", defaultValue: false);

            return new MetadataSettings
            {
                GeneralizeGenres = generalizeGenres,
                WriteExternalGenreAsTag = writeExternalGenreAsTag,
                ArtistMode = artistMode,
                WriteCollectionsAsNfoTags = writeCollectionsAsNfoTags,
                GenreMappings = genreMappings
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to load metadata settings; falling back to defaults");
            return MetadataSettings.Default;
        }
    }

    private bool ReadBool(IUnitOfWork unitOfWork, string category, string key, bool defaultValue)
    {
        try
        {
            var config = unitOfWork.Configurations
                .FirstOrDefaultAsync(c => c.Category == category && c.Key == key)
                .GetAwaiter()
                .GetResult();

            if (config is null || string.IsNullOrWhiteSpace(config.Value))
            {
                return defaultValue;
            }

            return bool.TryParse(config.Value, out var value) ? value : defaultValue;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to read configuration flag for {Category}/{Key}", category, key);
            return defaultValue;
        }
    }

    private NfoArtistMode ReadArtistMode(IUnitOfWork unitOfWork)
    {
        try
        {
            // First try to read the new ArtistMode configuration
            var config = unitOfWork.Configurations
                .FirstOrDefaultAsync(c => c.Category == "Metadata" && c.Key == "ArtistMode")
                .GetAwaiter()
                .GetResult();

            if (config is not null && !string.IsNullOrWhiteSpace(config.Value))
            {
                if (Enum.TryParse<NfoArtistMode>(config.Value, out var mode))
                {
                    return mode;
                }
            }

            // Backward compatibility: read legacy settings
            var usePrimaryArtistForNfo = ReadBool(unitOfWork, "Metadata", "UsePrimaryArtistForNfo", defaultValue: false);
            var appendFeaturedArtistsToTitle = ReadBool(unitOfWork, "Metadata", "AppendFeaturedArtistsToTitle", defaultValue: false);

            if (usePrimaryArtistForNfo && appendFeaturedArtistsToTitle)
            {
                return NfoArtistMode.FeaturedInTitle;
            }
            else if (usePrimaryArtistForNfo)
            {
                return NfoArtistMode.PrimaryOnly;
            }

            // Default: CombinedArtistField (includes featured artists in artist field)
            return NfoArtistMode.CombinedArtistField;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to read ArtistMode configuration; using default");
            return NfoArtistMode.CombinedArtistField;
        }
    }

    private IReadOnlyDictionary<string, string> ReadGenreMappings(IUnitOfWork unitOfWork)
    {
        try
        {
            var config = unitOfWork.Configurations
                .FirstOrDefaultAsync(c => c.Category == "Metadata" && c.Key == "GenreMappings")
                .GetAwaiter()
                .GetResult();

            if (config is null || string.IsNullOrWhiteSpace(config.Value))
            {
                return BuildDictionaryFromDefaults();
            }

            var mappings = JsonSerializer.Deserialize<List<GenreMappingDto>>(config.Value, _jsonOptions)
                ?? new List<GenreMappingDto>();

            var result = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

            foreach (var mapping in mappings)
            {
                var from = mapping.From?.Trim();
                var to = mapping.To?.Trim();

                if (string.IsNullOrWhiteSpace(from) || string.IsNullOrWhiteSpace(to))
                {
                    continue;
                }

                if (!result.ContainsKey(from))
                {
                    result[from] = to;
                }
            }

            return result.Count > 0
                ? result
                : BuildDictionaryFromDefaults();
        }
        catch (JsonException ex)
        {
            _logger.LogWarning(ex, "Failed to parse GenreMappings configuration; ignoring");
            return BuildDictionaryFromDefaults();
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Unexpected error while reading GenreMappings configuration");
            return BuildDictionaryFromDefaults();
        }
    }

    private sealed record GenreMappingDto(string? From, string? To);

    private IReadOnlyDictionary<string, string> BuildDictionaryFromDefaults()
    {
        var defaults = _defaultsProvider.GetDefaultMappings();
        if (defaults.Count == 0)
        {
            return new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        }

        var result = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        foreach (var entry in defaults)
        {
            var from = entry.SpecificGenre?.Trim();
            var to = entry.GeneralGenre?.Trim();

            if (string.IsNullOrWhiteSpace(from) || string.IsNullOrWhiteSpace(to))
            {
                continue;
            }

            if (!result.ContainsKey(from))
            {
                result[from] = to;
            }
        }

        return result;
    }
}
