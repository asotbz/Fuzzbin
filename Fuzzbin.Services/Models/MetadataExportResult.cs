using System.Collections.Generic;

namespace Fuzzbin.Services.Models;

public sealed class MetadataExportResult
{
    public MetadataExportResult(bool success, string targetDirectory)
    {
        Success = success;
        TargetDirectory = targetDirectory;
    }

    public bool Success { get; set; }
    public string TargetDirectory { get; }
    public string? ArchivePath { get; set; }
    public List<string> Files { get; } = new();
    public List<string> Warnings { get; } = new();
}
