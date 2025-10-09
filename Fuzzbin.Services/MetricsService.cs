using System;
using System.Diagnostics;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;

using DownloadStatus = Fuzzbin.Core.Entities.DownloadStatus;

namespace Fuzzbin.Services;

public sealed class MetricsService : IMetricsService
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILogger<MetricsService> _logger;
    private readonly object _cpuLock = new();
    private DateTime _lastSampleTimeUtc = DateTime.UtcNow;
    private TimeSpan _lastTotalProcessorTime = Process.GetCurrentProcess().TotalProcessorTime;

    public MetricsService(IUnitOfWork unitOfWork, ILogger<MetricsService> logger)
    {
        _unitOfWork = unitOfWork;
        _logger = logger;
    }

    public async Task<SystemMetrics> CaptureAsync(CancellationToken cancellationToken = default)
    {
        var process = Process.GetCurrentProcess();
        var cpuUsage = SampleCpuUsage(process);

        int librarySize = 0;
        int activeDownloads = 0;
        int pendingDownloads = 0;

        try
        {
            librarySize = await _unitOfWork.Videos.CountAsync().ConfigureAwait(false);
            activeDownloads = await _unitOfWork.DownloadQueueItems
                .CountAsync(item => item.Status == DownloadStatus.Downloading).ConfigureAwait(false);
            pendingDownloads = await _unitOfWork.DownloadQueueItems
                .CountAsync(item => item.Status == DownloadStatus.Queued)
                .ConfigureAwait(false);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Failed to gather queue metrics");
        }

        var managedMemoryBytes = GC.GetTotalMemory(forceFullCollection: false);

        return new SystemMetrics
        {
            CpuUsagePercent = Math.Round(cpuUsage, 2),
            WorkingSetMb = Math.Round(process.WorkingSet64 / 1024d / 1024d, 2),
            ManagedMemoryMb = Math.Round(managedMemoryBytes / 1024d / 1024d, 2),
            ThreadCount = process.Threads.Count,
            HandleCount = process.HandleCount,
            Uptime = DateTime.UtcNow - process.StartTime.ToUniversalTime(),
            ActiveDownloads = activeDownloads,
            PendingDownloads = pendingDownloads,
            LibrarySize = librarySize,
            CapturedAtUtc = DateTime.UtcNow
        };
    }

    private double SampleCpuUsage(Process process)
    {
        lock (_cpuLock)
        {
            var now = DateTime.UtcNow;
            var cpuTime = process.TotalProcessorTime;
            var elapsedMs = (now - _lastSampleTimeUtc).TotalMilliseconds;

            double usage = 0;
            if (elapsedMs > 0)
            {
                var cpuTimeDelta = (cpuTime - _lastTotalProcessorTime).TotalMilliseconds;
                usage = (cpuTimeDelta / (Environment.ProcessorCount * elapsedMs)) * 100d;
            }

            _lastSampleTimeUtc = now;
            _lastTotalProcessorTime = cpuTime;
            return Math.Clamp(usage, 0, 100);
        }
    }
}
