namespace Fuzzbin.Services.Models;

public sealed class MetadataExportOptions
{
    public string? OutputDirectory { get; init; }
    public bool IncludeArtwork { get; init; } = true;
    public bool IncludeVideoFile { get; init; }
    public bool IncludeArtistMetadata { get; init; } = true;
    public bool OverwriteExisting { get; init; }
    public bool CreateArchive { get; init; }

    public static MetadataExportOptions Default => new();
}
