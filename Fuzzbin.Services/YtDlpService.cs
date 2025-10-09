using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;
using YoutubeDLSharp;
using YoutubeDLSharp.Metadata;
using YoutubeDLSharp.Options;
using CoreDownloadProgress = Fuzzbin.Core.Interfaces.DownloadProgress;
using CoreSearchResult = Fuzzbin.Core.Interfaces.SearchResult;

namespace Fuzzbin.Services
{
    public class YtDlpService : IYtDlpService
    {
        private readonly ILogger<YtDlpService> _logger;
        private readonly IDownloadSettingsProvider _settingsProvider;
        private readonly string _ytDlpPath;
        private readonly string _cookiesPath;

        public YtDlpService(
            ILogger<YtDlpService> logger,
            IDownloadSettingsProvider settingsProvider)
        {
            _logger = logger;
            _settingsProvider = settingsProvider;
            _ytDlpPath = GetYtDlpPath();
            _cookiesPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "data", "cookies.txt");
        }

        public async Task<DownloadResult> DownloadVideoAsync(
            string url,
            string outputPath,
            IProgress<CoreDownloadProgress>? progress = null,
            CancellationToken cancellationToken = default)
        {
            var result = new DownloadResult();
            var startTime = DateTime.UtcNow;
            YtDlpVideoMetadata? metadata = null;

            try
            {
                var workerOptions = _settingsProvider.GetOptions();
                var resolvedOutputPath = ResolvePath(outputPath);
                Directory.CreateDirectory(resolvedOutputPath);
                metadata = await TryGetMetadataAsync(url, cancellationToken).ConfigureAwait(false);

                var youtubeDl = CreateClient(resolvedOutputPath, workerOptions);
                var optionSet = BuildDownloadOptionSet(resolvedOutputPath, workerOptions);
                var downloadProgress = new Progress<YoutubeDLSharp.DownloadProgress>(p =>
                {
                    if (p == null)
                    {
                        return;
                    }

                    progress?.Report(new CoreDownloadProgress
                    {
                        Status = p.State.ToString(),
                        Percentage = Math.Clamp(p.Progress * 100, 0, 100),
                        DownloadSpeed = p.DownloadSpeed,
                        ETA = p.ETA,
                        TotalBytes = ParseSizeToBytes(p.TotalDownloadSize),
                        DownloadedBytes = ParseSizeToBytes(p.Data)
                    });
                });

                if (File.Exists(_cookiesPath))
                {
                    optionSet.Cookies = _cookiesPath;
                }

                var mergeFormat = DownloadMergeFormat.Mp4;
                var runResult = await youtubeDl.RunVideoDownload(
                    url,
                    workerOptions.Format,
                    mergeFormat,
                    VideoRecodeFormat.None,
                    cancellationToken,
                    downloadProgress,
                    null,
                    optionSet).ConfigureAwait(false);

                result.Duration = DateTime.UtcNow - startTime;
                result.Metadata = metadata;

                if (!runResult.Success)
                {
                    result.Success = false;
                    result.ErrorMessage = FormatErrorOutput(runResult.ErrorOutput);
                    _logger.LogError("Download failed for {Url}: {Error}", url, result.ErrorMessage);
                    return result;
                }

                var resolvedPath = ResolveDownloadedFilePath(runResult.Data, resolvedOutputPath, metadata);

                if (string.IsNullOrWhiteSpace(resolvedPath) || !File.Exists(resolvedPath))
                {
                    result.Success = false;
                    result.ErrorMessage = "Downloaded file could not be located.";
                    _logger.LogError("Download for {Url} completed but file could not be found", url);
                    return result;
                }

                result.Success = true;
                result.FilePath = resolvedPath;
                _logger.LogInformation("Downloaded video from {Url} to {Path}", url, resolvedPath);
                return result;
            }
            catch (OperationCanceledException)
            {
                _logger.LogWarning("Download cancelled for {Url}", url);
                throw;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error downloading video from {Url}", url);
                return new DownloadResult
                {
                    Success = false,
                    ErrorMessage = ex.Message,
                    Metadata = metadata,
                    Duration = DateTime.UtcNow - startTime
                };
            }
        }

        public async Task<List<CoreSearchResult>> SearchVideosAsync(
            string query,
            int maxResults = 10,
            CancellationToken cancellationToken = default)
        {
            try
            {
                var workerOptions = _settingsProvider.GetOptions();
                var youtubeDl = CreateClient(null, workerOptions);
                var optionSet = BuildBaseOptionSet(workerOptions);
                var searchQuery = $"ytsearch{Math.Max(1, maxResults)}:{query}";
                var runResult = await youtubeDl.RunVideoDataFetch(
                    searchQuery,
                    cancellationToken,
                    flat: false,
                    fetchComments: false,
                    optionSet).ConfigureAwait(false);

                if (!runResult.Success || runResult.Data == null)
                {
                    _logger.LogWarning("Search for {Query} returned no data", query);
                    return new List<CoreSearchResult>();
                }

                var videoEntries = runResult.Data.Entries ?? new[] { runResult.Data };
                return videoEntries
                    .Where(entry => entry != null)
                    .Select(entry => MapSearchResult(entry!))
                    .ToList();
            }
            catch (OperationCanceledException)
            {
                throw;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error searching for videos with query {Query}", query);
                return new List<CoreSearchResult>();
            }
        }

        public async Task<YtDlpVideoMetadata> GetVideoMetadataAsync(
            string url,
            CancellationToken cancellationToken = default)
        {
            var workerOptions = _settingsProvider.GetOptions();
            var youtubeDl = CreateClient(null, workerOptions);
            var optionSet = BuildBaseOptionSet(workerOptions);
            var runResult = await youtubeDl.RunVideoDataFetch(
                url,
                cancellationToken,
                flat: false,
                fetchComments: false,
                optionSet).ConfigureAwait(false);

            if (!runResult.Success || runResult.Data == null)
            {
                var error = FormatErrorOutput(runResult.ErrorOutput);
                throw new InvalidOperationException($"Failed to fetch metadata: {error}");
            }

            return MapMetadata(runResult.Data);
        }

        public async Task<bool> ValidateInstallationAsync()
        {
            try
            {
                var processStartInfo = new ProcessStartInfo
                {
                    FileName = _ytDlpPath,
                    Arguments = "--version",
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true
                };

                using var process = Process.Start(processStartInfo);
                if (process == null)
                {
                    return false;
                }

                await process.WaitForExitAsync().ConfigureAwait(false);
                return process.ExitCode == 0;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error validating yt-dlp installation");
                return false;
            }
        }

        public async Task<string> GetVersionAsync()
        {
            try
            {
                var processStartInfo = new ProcessStartInfo
                {
                    FileName = _ytDlpPath,
                    Arguments = "--version",
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true
                };

                using var process = Process.Start(processStartInfo);
                if (process == null)
                {
                    return "Unknown";
                }

                var version = await process.StandardOutput.ReadToEndAsync().ConfigureAwait(false);
                await process.WaitForExitAsync().ConfigureAwait(false);
                return version.Trim();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting yt-dlp version");
                return "Unknown";
            }
        }

        private YoutubeDL CreateClient(string? outputFolder, DownloadWorkerOptions workerOptions)
        {
            var client = new YoutubeDL
            {
                YoutubeDLPath = _ytDlpPath,
                FFmpegPath = _settingsProvider.GetFfmpegPath(),
                OutputFolder = outputFolder ?? AppDomain.CurrentDomain.BaseDirectory,
                OutputFileTemplate = "%(title)s.%(ext)s"
            };

            return client;
        }

        private OptionSet BuildBaseOptionSet(DownloadWorkerOptions workerOptions)
        {
            var options = new OptionSet
            {
                NoWarnings = true,
                NoPlaylist = true,
                Color = "no_color",
                IgnoreConfig = true,
                RestrictFilenames = false,
                Progress = true,
                Newline = true
            };

            if (!string.IsNullOrWhiteSpace(workerOptions.BandwidthLimit))
            {
                var limitBytes = ParseSizeToBytes(workerOptions.BandwidthLimit);
                if (limitBytes.HasValue)
                {
                    options.LimitRate = limitBytes.Value;
                }
            }

            return options;
        }

        private OptionSet BuildDownloadOptionSet(string outputDirectory, DownloadWorkerOptions workerOptions)
        {
            var options = BuildBaseOptionSet(workerOptions);
            options.Output = Path.Combine(outputDirectory, "%(title)s.%(ext)s");
            options.MergeOutputFormat = DownloadMergeFormat.Mp4;
            options.FfmpegLocation = _settingsProvider.GetFfmpegPath();
            var tempPath = ResolvePath(workerOptions.TempDirectory ?? Path.Combine(workerOptions.OutputDirectory, "tmp"));
            Directory.CreateDirectory(tempPath);
            options.Paths = $"temp:{tempPath}";
            return options;
        }

        private async Task<YtDlpVideoMetadata?> TryGetMetadataAsync(
            string url,
            CancellationToken cancellationToken)
        {
            try
            {
                return await GetVideoMetadataAsync(url, cancellationToken).ConfigureAwait(false);
            }
            catch (Exception ex)
            {
                _logger.LogDebug(ex, "Metadata lookup failed for {Url}", url);
                return null;
            }
        }

        private string? ResolveDownloadedFilePath(string? reportedPath, string outputDirectory, YtDlpVideoMetadata? metadata)
        {
            if (!Directory.Exists(outputDirectory))
            {
                return null;
            }

            if (!string.IsNullOrWhiteSpace(reportedPath))
            {
                var path = Path.IsPathRooted(reportedPath)
                    ? reportedPath
                    : Path.Combine(outputDirectory, reportedPath);

                if (File.Exists(path))
                {
                    return Path.GetFullPath(path);
                }
            }

            if (metadata != null && !string.IsNullOrWhiteSpace(metadata.Title))
            {
                var normalizedTitle = SanitizeFileName(metadata.Title);
                var candidates = Directory.GetFiles(outputDirectory, $"{normalizedTitle}*");
                if (candidates.Length > 0)
                {
                    return candidates
                        .OrderByDescending(File.GetLastWriteTimeUtc)
                        .First();
                }
            }

            var fallback = Directory.GetFiles(outputDirectory)
                .OrderByDescending(File.GetLastWriteTimeUtc)
                .FirstOrDefault();

            return fallback;
        }

        private static string SanitizeFileName(string value)
        {
            var invalidChars = Path.GetInvalidFileNameChars();
            var builder = new StringBuilder(value.Length);
            foreach (var ch in value)
            {
                builder.Append(invalidChars.Contains(ch) ? '_' : ch);
            }

            return builder.ToString();
        }

        private static long? ParseSizeToBytes(string? value)
        {
            if (string.IsNullOrWhiteSpace(value))
            {
                return null;
            }

            value = value.Trim();
            if (long.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var raw))
            {
                return raw;
            }

            try
            {
                var numberPart = new string(value.TakeWhile(c => char.IsDigit(c) || c == '.' || c == ',').ToArray());
                var unitPart = value[numberPart.Length..].Trim().ToUpperInvariant();

                if (!double.TryParse(numberPart, NumberStyles.Float, CultureInfo.InvariantCulture, out var number))
                {
                    return null;
                }

                return unitPart switch
                {
                    "KIB" or "KB" => (long)(number * 1024),
                    "MIB" or "MB" => (long)(number * 1024 * 1024),
                    "GIB" or "GB" => (long)(number * 1024 * 1024 * 1024),
                    _ => (long)number
                };
            }
            catch
            {
                return null;
            }
        }

    private CoreSearchResult MapSearchResult(VideoData data)
    {
        var metadata = MapMetadata(data);
        return new CoreSearchResult
        {
            Id = metadata.Id,
            Title = metadata.Title,
            Channel = metadata.Channel,
            ThumbnailUrl = metadata.ThumbnailUrl,
            Duration = metadata.Duration,
            Url = !string.IsNullOrWhiteSpace(data.WebpageUrl)
                ? data.WebpageUrl
                : $"https://www.youtube.com/watch?v={metadata.Id}",
            UploadDate = metadata.UploadDate,
            ViewCount = metadata.ViewCount
        };
    }

        private YtDlpVideoMetadata MapMetadata(VideoData data)
        {
            var metadata = new YtDlpVideoMetadata
            {
                Id = data.ID ?? string.Empty,
                Title = data.Title ?? string.Empty,
                Artist = data.Artist ?? data.Uploader ?? data.Channel,
                Channel = data.Channel,
                Description = data.Description,
                Duration = data.Duration.HasValue ? TimeSpan.FromSeconds(data.Duration.Value) : (TimeSpan?)null,
                UploadDate = data.UploadDate,
                Tags = data.Tags?.Where(t => !string.IsNullOrWhiteSpace(t)).ToList() ?? new List<string>(),
                ThumbnailUrl = data.Thumbnail,
                ViewCount = data.ViewCount,
                LikeCount = data.LikeCount
            };

            var primaryFormat = data.Formats?
                .Where(f => f != null)
                .OrderByDescending(f => f.Height ?? 0)
                .ThenByDescending(f => f.Width ?? 0)
                .ThenByDescending(f => f.Bitrate ?? 0)
                .FirstOrDefault();

            if (primaryFormat != null)
            {
                metadata.Width = primaryFormat.Width;
                metadata.Height = primaryFormat.Height;
                metadata.Fps = primaryFormat.FrameRate;
                metadata.VideoCodec = primaryFormat.VideoCodec;
                metadata.AudioCodec = primaryFormat.AudioCodec;
                metadata.FileSize = primaryFormat.FileSize ?? primaryFormat.ApproximateFileSize;
            }

            return metadata;
        }

        private static string FormatErrorOutput(string[]? errorOutput)
        {
            if (errorOutput == null || errorOutput.Length == 0)
            {
                return "Unknown error";
            }

            return string.Join(Environment.NewLine, errorOutput);
        }

        private string ResolvePath(string? path)
        {
            if (string.IsNullOrWhiteSpace(path))
            {
                return AppDomain.CurrentDomain.BaseDirectory;
            }

            var resolved = Path.IsPathRooted(path)
                ? path
                : Path.Combine(AppDomain.CurrentDomain.BaseDirectory, path);

            return Path.GetFullPath(resolved);
        }

        private string GetYtDlpPath()
        {
            var lookupPaths = new[]
            {
                "/usr/local/bin/yt-dlp",
                "/usr/bin/yt-dlp",
                Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "yt-dlp"),
                "yt-dlp"
            };

            foreach (var path in lookupPaths)
            {
                if (File.Exists(path))
                {
                    _logger.LogInformation("Using yt-dlp executable at {Path}", path);
                    return path;
                }
            }

            _logger.LogWarning("yt-dlp executable not found in common locations; relying on PATH resolution");
            return "yt-dlp";
        }
    }
}
