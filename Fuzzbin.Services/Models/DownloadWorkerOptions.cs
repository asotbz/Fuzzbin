namespace Fuzzbin.Services.Models;

public sealed class DownloadWorkerOptions
{
    public int MaxConcurrentDownloads { get; set; } = 3;
    public int MaxRetryCount { get; set; } = 3;
    public string OutputDirectory { get; set; } = "downloads";
    public string TempDirectory { get; set; } = "downloads/tmp";
    public string Format { get; set; } = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best";
    public string? BandwidthLimit { get; set; }
    public double ProgressPercentageStep { get; set; } = 1;
    public double RetryBackoffSeconds { get; set; } = 15;
}
