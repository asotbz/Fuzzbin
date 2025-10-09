using System.Collections.Generic;

namespace Fuzzbin.Services.Models;

public sealed class MetadataImportResult
{
    public int VideosUpdated { get; set; }
    public int VideosSkipped { get; set; }
    public List<string> Warnings { get; } = new();
    public List<string> Errors { get; } = new();
}
