using Fuzzbin.Services.Models;

namespace Fuzzbin.Services.Interfaces;

public interface IMetadataSettingsProvider
{
    MetadataSettings GetSettings();
    void Invalidate();
}
