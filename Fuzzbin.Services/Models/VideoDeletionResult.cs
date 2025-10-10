using System;
using System.Collections.Generic;

namespace Fuzzbin.Services.Models;

public sealed class VideoDeletionResult
{
    public int RequestedCount { get; init; }
    public int DeletedCount { get; set; }
    public List<VideoDeletionFailure> Failures { get; } = new();

    public bool HasFailures => Failures.Count > 0;

    public sealed class VideoDeletionFailure
    {
        public Guid VideoId { get; init; }
        public string Title { get; init; } = string.Empty;
        public string Error { get; init; } = string.Empty;
    }
}
