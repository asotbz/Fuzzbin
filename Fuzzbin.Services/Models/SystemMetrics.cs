using System;

namespace Fuzzbin.Services.Models;

public sealed class SystemMetrics
{
    public double CpuUsagePercent { get; init; }
    public double WorkingSetMb { get; init; }
    public double ManagedMemoryMb { get; init; }
    public int ThreadCount { get; init; }
    public int HandleCount { get; init; }
    public TimeSpan Uptime { get; init; }
    public int ActiveDownloads { get; init; }
    public int PendingDownloads { get; init; }
    public int LibrarySize { get; init; }
    public DateTime CapturedAtUtc { get; init; }
}
