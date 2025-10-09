using System;
using System.Collections.Generic;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using YtSearchResult = Fuzzbin.Core.Interfaces.SearchResult;

namespace Fuzzbin.Services.Models;

public class ExternalSearchQuery
{
    public string SearchText { get; set; } = string.Empty;
    public string? Artist { get; set; }
    public string? Title { get; set; }
    public int MaxResults { get; set; } = 10;
    public bool IncludeImvdb { get; set; } = true;
    public bool IncludeYtDlp { get; set; } = true;
}

public class ExternalSearchResult
{
    public List<ExternalSearchItem> Items { get; set; } = new();
    public List<string> Warnings { get; set; } = new();
    public bool ImvdbEnabled { get; set; }
    public bool YtDlpEnabled { get; set; }
    public DateTime RetrievedAtUtc { get; set; } = DateTime.UtcNow;
}

public enum ExternalSearchSource
{
    Imvdb,
    YtDlp,
    Combined
}

public class ExternalSearchItem
{
    public string Title { get; set; } = string.Empty;
    public string Artist { get; set; } = string.Empty;
    public ExternalSearchSource Source { get; set; }
    public ImvdbMetadata? Imvdb { get; set; }
    public YtSearchResult? YtDlp { get; set; }
    public double Confidence { get; set; }
    public string? Description { get; set; }
    public string? ArtworkUrl { get; set; }

    public bool HasImvdb => Imvdb != null;
    public bool HasYtDlp => YtDlp != null;
}
