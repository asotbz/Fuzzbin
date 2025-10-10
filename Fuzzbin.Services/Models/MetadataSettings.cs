using System;
using System.Collections.Generic;

namespace Fuzzbin.Services.Models;

public sealed class MetadataSettings
{
    public static MetadataSettings Default { get; } = new();

    public bool GeneralizeGenres { get; init; }

    public bool WriteExternalGenreAsTag { get; init; }

    public IReadOnlyDictionary<string, string> GenreMappings { get; init; }
        = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
}
