using System;
using System.Collections.Generic;

namespace Fuzzbin.Services.Models;

public sealed class VideoBatchUpdateResult
{
    public int RequestedCount { get; init; }
    public int UpdatedCount { get; set; }
    public List<VideoUpdateFailure> Failures { get; } = new();

    public bool HasFailures => Failures.Count > 0;

    public sealed class VideoUpdateFailure
    {
        public Guid VideoId { get; init; }
        public string Title { get; init; } = string.Empty;
        public string Error { get; init; } = string.Empty;
    }
}
