using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.Interfaces;

namespace Fuzzbin.Services
{
    public class BulkOrganizeService : IBulkOrganizeService
    {
        private readonly IUnitOfWork _unitOfWork;
        private readonly ILogger<BulkOrganizeService> _logger;
        
        public BulkOrganizeService(
            IUnitOfWork unitOfWork,
            ILogger<BulkOrganizeService> logger)
        {
            _unitOfWork = unitOfWork;
            _logger = logger;
        }
        
        public class OrganizeOptions
        {
            public string Pattern { get; set; } = "{artist}/{year}/{title}";
            public bool CreateDirectories { get; set; } = true;
            public bool MoveFiles { get; set; } = false; // false = copy, true = move
            public bool RenameOnly { get; set; } = false; // Just rename without moving to different directory
            public bool PreserveExtension { get; set; } = true;
            public bool SkipExisting { get; set; } = true;
            public bool UpdateDatabase { get; set; } = true;
            public Dictionary<string, string> CustomVariables { get; set; } = new();
        }
        
        public class OrganizeResult
        {
            public int TotalVideos { get; set; }
            public int SuccessCount { get; set; }
            public int SkippedCount { get; set; }
            public int ErrorCount { get; set; }
            public List<OrganizeItemResult> Items { get; set; } = new();
            public TimeSpan Duration { get; set; }
        }
        
        public class OrganizeItemResult
        {
            public Guid VideoId { get; set; }
            public string OriginalPath { get; set; } = string.Empty;
            public string NewPath { get; set; } = string.Empty;
            public bool Success { get; set; }
            public string? ErrorMessage { get; set; }
            public OrganizeAction Action { get; set; }
        }
        
        public enum OrganizeAction
        {
            None,
            Copied,
            Moved,
            Renamed,
            Skipped,
            Error
        }
        
        public async Task<OrganizeResult> OrganizeVideosAsync(
            IEnumerable<Guid> videoIds,
            OrganizeOptions options)
        {
            var startTime = DateTime.UtcNow;
            var result = new OrganizeResult();
            
            var videos = await GetVideosAsync(videoIds);
            result.TotalVideos = videos.Count;
            
            // Get base directory from configuration
            var baseDirectory = options.RenameOnly
                ? null
                : await GetBaseDirectoryAsync();
            
            foreach (var video in videos)
            {
                var itemResult = await OrganizeSingleVideoAsync(video, options, baseDirectory);
                result.Items.Add(itemResult);
                
                if (itemResult.Success)
                {
                    result.SuccessCount++;
                }
                else if (itemResult.Action == OrganizeAction.Skipped)
                {
                    result.SkippedCount++;
                }
                else
                {
                    result.ErrorCount++;
                }
            }
            
            result.Duration = DateTime.UtcNow - startTime;
            return result;
        }
        
        private async Task<List<Video>> GetVideosAsync(IEnumerable<Guid> videoIds)
        {
            var videos = new List<Video>();
            foreach (var id in videoIds)
            {
                var video = await _unitOfWork.Videos.GetByIdAsync(id);
                if (video != null)
                {
                    videos.Add(video);
                }
            }
            return videos;
        }
        
        private async Task<string> GetBaseDirectoryAsync()
        {
            // Get the organized directory configuration
            var organizedDirConfig = await _unitOfWork.Configurations
                .FirstOrDefaultAsync(c => c.Key == "OrganizedDirectory" && c.Category == "Library");
            
            if (!string.IsNullOrEmpty(organizedDirConfig?.Value))
            {
                return organizedDirConfig.Value;
            }
            
            // Fall back to library directory
            var libraryDirConfig = await _unitOfWork.Configurations
                .FirstOrDefaultAsync(c => c.Key == "LibraryDirectory" && c.Category == "Library");
            
            return libraryDirConfig?.Value ?? "/videos/organized";
        }
        
        private async Task<OrganizeItemResult> OrganizeSingleVideoAsync(
            Video video, 
            OrganizeOptions options,
            string? baseDirectory)
        {
            var result = new OrganizeItemResult
            {
                VideoId = video.Id,
                OriginalPath = video.FilePath ?? string.Empty
            };

            try
            {
                if (string.IsNullOrWhiteSpace(video.FilePath))
                {
                    result.Success = false;
                    result.Action = OrganizeAction.Error;
                    result.ErrorMessage = "Video file path is missing";
                    return result;
                }

                // Generate new path from pattern
                var newPath = GeneratePathFromPattern(video, options.Pattern, options.CustomVariables);

                // Add extension if needed
                if (options.PreserveExtension)
                {
                    var extension = string.IsNullOrWhiteSpace(video.FilePath)
                        ? string.Empty
                        : Path.GetExtension(video.FilePath);
                    if (!string.IsNullOrEmpty(extension) && !newPath.EndsWith(extension, StringComparison.OrdinalIgnoreCase))
                    {
                        newPath += extension;
                    }
                }
                
                // Sanitize path
                newPath = SanitizePath(newPath);
                
                // Determine full path
                string fullNewPath;
                if (options.RenameOnly)
                {
                    var directory = Path.GetDirectoryName(video.FilePath) ?? string.Empty;
                    fullNewPath = Path.Combine(directory, newPath);
                }
                else
                {
                    fullNewPath = Path.Combine(baseDirectory ?? "", newPath);
                }
                
                result.NewPath = fullNewPath;
                
                // Check if source file exists
                    if (!File.Exists(video.FilePath))
                    {
                        result.Success = false;
                        result.Action = OrganizeAction.Error;
                        result.ErrorMessage = "Source file not found";
                        return result;
                }
                
                // Check if target already exists
                if (File.Exists(fullNewPath))
                {
                    if (options.SkipExisting)
                    {
                        result.Success = true;
                        result.Action = OrganizeAction.Skipped;
                        return result;
                    }
                }
                
                // Create directories if needed
                if (options.CreateDirectories)
                {
                    var targetDirectory = Path.GetDirectoryName(fullNewPath);
                    if (!string.IsNullOrEmpty(targetDirectory) && !Directory.Exists(targetDirectory))
                    {
                        Directory.CreateDirectory(targetDirectory);
                    }
                }
                
                // Perform the file operation
                if (options.RenameOnly)
                {
                    File.Move(video.FilePath, fullNewPath);
                    result.Action = OrganizeAction.Renamed;
                }
                else if (options.MoveFiles)
                {
                    File.Move(video.FilePath, fullNewPath);
                    result.Action = OrganizeAction.Moved;
                }
                else
                {
                    File.Copy(video.FilePath, fullNewPath, !options.SkipExisting);
                    result.Action = OrganizeAction.Copied;
                }
                
                // Update database if requested
                if (options.UpdateDatabase && (options.MoveFiles || options.RenameOnly))
                {
                    video.FilePath = fullNewPath;
                    video.UpdatedAt = DateTime.UtcNow;
                    await _unitOfWork.Videos.UpdateAsync(video);
                    await _unitOfWork.SaveChangesAsync();
                }
                
                result.Success = true;
                _logger.LogInformation("Organized video {VideoId} from {OldPath} to {NewPath}", 
                    video.Id, video.FilePath, fullNewPath);
            }
            catch (Exception ex)
            {
                result.Success = false;
                result.Action = OrganizeAction.Error;
                result.ErrorMessage = ex.Message;
                _logger.LogError(ex, "Error organizing video {VideoId}", video.Id);
            }
            
            return result;
        }
        
        private string GeneratePathFromPattern(
            Video video, 
            string pattern,
            Dictionary<string, string> customVariables)
        {
            var result = pattern;
            
            // Replace standard variables
            var replacements = new Dictionary<string, string?>
            {
                { "{title}", video.Title },
                { "{artist}", video.Artist },
                { "{year}", video.Year?.ToString() },
                { "{genre}", string.Join(", ", video.Genres?.Select(g => g.Name) ?? Enumerable.Empty<string>()) },
                { "{album}", video.Album },
                { "{rating}", video.Rating?.ToString() },
                { "{duration}", FormatDuration(video.Duration) },
                { "{resolution}", video.Resolution },
                { "{codec}", video.VideoCodec },
                { "{date}", video.CreatedAt.ToString("yyyy-MM-dd") },
                { "{month}", video.CreatedAt.ToString("MM") },
                { "{day}", video.CreatedAt.ToString("dd") },
                { "{id}", video.Id.ToString() },
                { "{original_name}", Path.GetFileNameWithoutExtension(video.FilePath) }
            };
            
            // Add custom variables
            foreach (var custom in customVariables)
            {
                replacements[$"{{{custom.Key}}}"] = custom.Value;
            }
            
            // Perform replacements
            foreach (var replacement in replacements)
            {
                if (!string.IsNullOrEmpty(replacement.Value))
                {
                    result = result.Replace(replacement.Key, replacement.Value);
                }
                else
                {
                    // Remove empty placeholders
                    result = result.Replace(replacement.Key, "Unknown");
                }
            }
            
            return result;
        }
        
        private string SanitizePath(string path)
        {
            // Remove invalid characters
            var invalidChars = Path.GetInvalidFileNameChars()
                .Where(c => c != Path.DirectorySeparatorChar && c != Path.AltDirectorySeparatorChar)
                .ToArray();
            
            var parts = path.Split(new[] { Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar });
            var sanitizedParts = parts.Select(part =>
            {
                foreach (var c in invalidChars)
                {
                    part = part.Replace(c.ToString(), "_");
                }
                // Remove leading/trailing dots and spaces
                part = part.Trim(' ', '.');
                // Replace multiple spaces with single space
                part = Regex.Replace(part, @"\s+", " ");
                return part;
            });
            
            return Path.Combine(sanitizedParts.ToArray());
        }
        
        private string FormatDuration(double? seconds)
        {
            if (!seconds.HasValue) return "Unknown";
            
            var ts = TimeSpan.FromSeconds(seconds.Value);
            if (ts.TotalHours >= 1)
            {
                return $"{(int)ts.TotalHours}h{ts.Minutes}m";
            }
            else
            {
                return $"{(int)ts.TotalMinutes}m{ts.Seconds}s";
            }
        }
        
        public async Task<Dictionary<string, int>> PreviewOrganizeAsync(
            IEnumerable<Guid> videoIds,
            OrganizeOptions options)
        {
            var preview = new Dictionary<string, int>();
            var videos = await GetVideosAsync(videoIds);
            var baseDirectory = options.RenameOnly
                ? null
                : await GetBaseDirectoryAsync();
            
            foreach (var video in videos)
            {
                var currentPath = video.FilePath ?? string.Empty;
                var newPath = GeneratePathFromPattern(video, options.Pattern, options.CustomVariables);
                if (options.PreserveExtension)
                {
                    var extension = string.IsNullOrWhiteSpace(currentPath)
                        ? string.Empty
                        : Path.GetExtension(currentPath);
                    if (!string.IsNullOrEmpty(extension) && !newPath.EndsWith(extension, StringComparison.OrdinalIgnoreCase))
                    {
                        newPath += extension;
                    }
                }

                newPath = SanitizePath(newPath);

                if (options.RenameOnly)
                {
                    var dir = string.IsNullOrEmpty(currentPath)
                        ? string.Empty
                        : Path.GetDirectoryName(currentPath) ?? string.Empty;
                    newPath = Path.Combine(dir, newPath);
                }
                else if (!string.IsNullOrEmpty(baseDirectory))
                {
                    newPath = Path.Combine(baseDirectory, newPath);
                }
                
                var directoryPath = Path.GetDirectoryName(newPath) ?? "Root";
                preview[directoryPath] = preview.GetValueOrDefault(directoryPath, 0) + 1;
            }
            
            return preview;
        }
        
        public List<string> GetAvailableVariables()
        {
            return new List<string>
            {
                "{title}",
                "{artist}",
                "{year}",
                "{genre}",
                "{album}",
                "{rating}",
                "{duration}",
                "{resolution}",
                "{codec}",
                "{date}",
                "{month}",
                "{day}",
                "{id}",
                "{original_name}"
            };
        }
        
        public List<string> GetSamplePatterns()
        {
            return new List<string>
            {
                "{artist}/{year}/{title}",
                "{genre}/{artist}/{title}",
                "{year}/{artist} - {title}",
                "{artist}/{album}/{title}",
                "Organized/{genre}/{artist}/{year} - {title}",
                "{resolution}/{artist} - {title}",
                "{year}/{month}/{artist} - {title}"
            };
        }
    }
}
