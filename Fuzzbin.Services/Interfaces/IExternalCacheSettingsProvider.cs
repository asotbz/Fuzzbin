using Fuzzbin.Services.Models;

namespace Fuzzbin.Services.Interfaces;

/// <summary>
/// Provides cached access to external metadata cache configuration settings
/// </summary>
public interface IExternalCacheSettingsProvider
{
    /// <summary>
    /// Gets the current external cache settings
    /// Settings are cached in memory for 5 minutes to reduce database queries
    /// </summary>
    /// <returns>Current cache configuration options</returns>
    ExternalCacheOptions GetSettings();
    
    /// <summary>
    /// Invalidates the cached settings, forcing a reload on next access
    /// Call this after updating cache configuration in the database
    /// </summary>
    void Invalidate();
}