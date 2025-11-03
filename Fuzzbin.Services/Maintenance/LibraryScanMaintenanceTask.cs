using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.Interfaces;

namespace Fuzzbin.Services.Maintenance;

/// <summary>
/// Scans the library directory for new files and missing videos
/// </summary>
public class LibraryScanMaintenanceTask : IMaintenanceTask
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILibraryPathManager _libraryPathManager;
    private readonly IMetadataService _metadataService;
    private readonly ILogger<LibraryScanMaintenanceTask> _logger;
    
    private static readonly string[] VideoExtensions = 
    {
        ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv"
    };
    
    public string TaskName => "LibraryScan";
    public string Description => "Scan library for new and missing videos";
    
    public bool IsEnabled
    {
        get
        {
            var config = _unitOfWork.Configurations
                .GetQueryable()
                .FirstOrDefault(c => c.Category == "Maintenance" 
                    && c.Key == "LibraryScan.Enabled");
            return config?.Value != "false"; // Enabled by default
        }
    }
    
    public LibraryScanMaintenanceTask(
        IUnitOfWork unitOfWork,
        ILibraryPathManager libraryPathManager,
        IMetadataService metadataService,
        ILogger<LibraryScanMaintenanceTask> logger)
    {
        _unitOfWork = unitOfWork;
        _libraryPathManager = libraryPathManager;
        _metadataService = metadataService;
        _logger = logger;
    }
    
    public async Task<MaintenanceTaskResult> ExecuteAsync(CancellationToken cancellationToken)
    {
        var stopwatch = Stopwatch.StartNew();
        var metrics = new Dictionary<string, object>();
        
        try
        {
            var libraryRoot = await _libraryPathManager.GetLibraryRootAsync(cancellationToken);
            
            if (string.IsNullOrWhiteSpace(libraryRoot) || !Directory.Exists(libraryRoot))
            {
                return new MaintenanceTaskResult
                {
                    Success = false,
                    ErrorMessage = $"Library root not found or not configured: {libraryRoot}",
                    Duration = stopwatch.Elapsed
                };
            }
            
            _logger.LogInformation("Starting library scan in: {LibraryRoot}", libraryRoot);
            
            // Step 1: Discover all video files
            var discoveredFiles = DiscoverVideoFiles(libraryRoot, cancellationToken);
            metrics["filesScanned"] = discoveredFiles.Count;
            
            // Step 2: Get all existing videos from database
            var existingVideos = await _unitOfWork.Videos
                .GetQueryable()
                .Where(v => v.IsActive)
                .ToListAsync(cancellationToken);
            
            // Step 3: Import new files
            var importResult = await ImportNewFilesAsync(
                discoveredFiles, 
                existingVideos, 
                libraryRoot,
                cancellationToken);
            
            metrics["imported"] = importResult.ImportedCount;
            metrics["skipped"] = importResult.SkippedCount;
            metrics["importErrors"] = importResult.ErrorCount;
            
            // Step 4: Mark missing videos
            var missingResult = await UpdateMissingStatusAsync(
                discoveredFiles, 
                existingVideos,
                libraryRoot,
                cancellationToken);
            
            metrics["markedMissing"] = missingResult.MarkedMissingCount;
            metrics["restored"] = missingResult.RestoredCount;
            
            stopwatch.Stop();
            
            var summary = $"Scanned {discoveredFiles.Count} files: " +
                         $"{importResult.ImportedCount} imported, " +
                         $"{missingResult.MarkedMissingCount} marked missing, " +
                         $"{missingResult.RestoredCount} restored, " +
                         $"{importResult.ErrorCount} errors";
            
            return new MaintenanceTaskResult
            {
                Success = true,
                Summary = summary,
                ItemsProcessed = discoveredFiles.Count,
                Duration = stopwatch.Elapsed,
                Metrics = metrics
            };
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error during library scan");
            return new MaintenanceTaskResult
            {
                Success = false,
                ErrorMessage = ex.Message,
                Duration = stopwatch.Elapsed,
                Metrics = metrics
            };
        }
    }
    
    private List<string> DiscoverVideoFiles(string rootPath, CancellationToken cancellationToken)
    {
        var files = new List<string>();
        
        try
        {
            var searchOption = GetRecursiveSearchOption();
            
            foreach (var extension in VideoExtensions)
            {
                if (cancellationToken.IsCancellationRequested)
                    break;
                
                try
                {
                    var matchingFiles = Directory.GetFiles(rootPath, $"*{extension}", searchOption)
                        .Where(f => !IsIgnoredFile(f));
                    
                    files.AddRange(matchingFiles);
                }
                catch (UnauthorizedAccessException ex)
                {
                    _logger.LogWarning(ex, "Access denied to directory during scan");
                }
            }
            
            _logger.LogInformation("Discovered {FileCount} video files", files.Count);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error discovering video files in: {RootPath}", rootPath);
        }
        
        return files;
    }
    
    private bool IsIgnoredFile(string filePath)
    {
        // Ignore hidden files/directories
        var fileName = Path.GetFileName(filePath);
        if (fileName.StartsWith("."))
            return true;
        
        // Ignore files in hidden directories
        var directoryPath = Path.GetDirectoryName(filePath);
        if (directoryPath?.Split(Path.DirectorySeparatorChar).Any(d => d.StartsWith(".")) == true)
            return true;
        
        return false;
    }
    
    private SearchOption GetRecursiveSearchOption()
    {
        var config = _unitOfWork.Configurations
            .GetQueryable()
            .FirstOrDefault(c => c.Category == "Maintenance" 
                && c.Key == "LibraryScan.Recursive");
        
        return config?.Value == "false" 
            ? SearchOption.TopDirectoryOnly 
            : SearchOption.AllDirectories;
    }
    
    private async Task<ImportResult> ImportNewFilesAsync(
        List<string> discoveredFiles,
        List<Video> existingVideos,
        string libraryRoot,
        CancellationToken cancellationToken)
    {
        var result = new ImportResult();
        var enrichOnline = GetEnrichOnlineMetadataOption();
        
        // Build index of existing files for fast lookup
        var existingPaths = new HashSet<string>(
            existingVideos
                .Where(v => !string.IsNullOrWhiteSpace(v.FilePath))
                .Select(v => Path.Combine(libraryRoot, v.FilePath!)),
            StringComparer.OrdinalIgnoreCase);
        
        // Find new files
        var newFiles = discoveredFiles
            .Where(f => !existingPaths.Contains(f))
            .ToList();
        
        _logger.LogInformation("Found {NewFileCount} new files to import", newFiles.Count);
        
        foreach (var filePath in newFiles)
        {
            if (cancellationToken.IsCancellationRequested)
                break;
            
            try
            {
                var relativePath = Path.GetRelativePath(libraryRoot, filePath);
                
                _logger.LogDebug("Importing new file: {RelativePath}", relativePath);
                
                // Extract metadata
                var metadata = await _metadataService.ExtractMetadataAsync(
                    filePath, 
                    cancellationToken);
                
                var video = new Video
                {
                    FilePath = relativePath,
                    Title = metadata.Title ?? Path.GetFileNameWithoutExtension(filePath),
                    Artist = metadata.Artist ?? "Unknown Artist",
                    Album = metadata.Album,
                    Year = metadata.ReleaseDate?.Year,
                    Duration = metadata.Duration.HasValue ? (int)metadata.Duration.Value.TotalSeconds : null,
                    FileSize = metadata.FileSize,
                    VideoCodec = metadata.VideoCodec,
                    AudioCodec = metadata.AudioCodec,
                    Resolution = metadata.Width.HasValue && metadata.Height.HasValue ? $"{metadata.Width}x{metadata.Height}" : null,
                    Format = metadata.Container,
                    FrameRate = metadata.FrameRate,
                    Bitrate = metadata.VideoBitrate.HasValue ? (int)(metadata.VideoBitrate.Value / 1000) : null,
                    ImportedAt = DateTime.UtcNow,
                    IsActive = true
                };
                
                // Optionally enrich with online metadata
                if (enrichOnline && 
                    !string.IsNullOrWhiteSpace(video.Artist) && 
                    !string.IsNullOrWhiteSpace(video.Title))
                {
                    try
                    {
                        await _metadataService.EnrichVideoMetadataAsync(
                            video,
                            fetchOnlineMetadata: true,
                            cancellationToken: cancellationToken);
                    }
                    catch (Exception ex)
                    {
                        _logger.LogWarning(ex, 
                            "Failed to enrich online metadata for: {RelativePath}", 
                            relativePath);
                        // Continue with local metadata only
                    }
                }
                
                await _unitOfWork.Videos.AddAsync(video);
                await _unitOfWork.SaveChangesAsync();
                
                result.ImportedCount++;
                
                _logger.LogInformation("Imported: {Artist} - {Title}", 
                    video.Artist, video.Title);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to import file: {FilePath}", filePath);
                result.ErrorCount++;
            }
        }
        
        return result;
    }
    
    private bool GetEnrichOnlineMetadataOption()
    {
        var config = _unitOfWork.Configurations
            .GetQueryable()
            .FirstOrDefault(c => c.Category == "Maintenance" 
                && c.Key == "LibraryScan.EnrichOnline");
        
        return config?.Value == "true"; // Disabled by default (can be slow)
    }
    
    private async Task<MissingResult> UpdateMissingStatusAsync(
        List<string> discoveredFiles,
        List<Video> existingVideos,
        string libraryRoot,
        CancellationToken cancellationToken)
    {
        var result = new MissingResult();
        
        // Build set of discovered files for fast lookup
        var discoveredSet = new HashSet<string>(discoveredFiles, StringComparer.OrdinalIgnoreCase);
        
        foreach (var video in existingVideos)
        {
            if (cancellationToken.IsCancellationRequested)
                break;
            
            if (string.IsNullOrWhiteSpace(video.FilePath))
                continue;
            
            var fullPath = Path.Combine(libraryRoot, video.FilePath);
            var fileExists = discoveredSet.Contains(fullPath);
            
            // Mark as missing
            if (!fileExists && !video.IsMissing)
            {
                video.IsMissing = true;
                video.MissingDetectedAt = DateTime.UtcNow;
                result.MarkedMissingCount++;
                
                _logger.LogWarning("Video file missing: {FilePath} ({Artist} - {Title})",
                    video.FilePath, video.Artist, video.Title);
            }
            // Restore (file returned)
            else if (fileExists && video.IsMissing)
            {
                video.IsMissing = false;
                video.MissingDetectedAt = null;
                result.RestoredCount++;
                
                _logger.LogInformation("Video file restored: {FilePath} ({Artist} - {Title})",
                    video.FilePath, video.Artist, video.Title);
            }
        }
        
        if (result.MarkedMissingCount > 0 || result.RestoredCount > 0)
        {
            await _unitOfWork.SaveChangesAsync();
        }
        
        return result;
    }
    
    private class ImportResult
    {
        public int ImportedCount { get; set; }
        public int SkippedCount { get; set; }
        public int ErrorCount { get; set; }
    }
    
    private class MissingResult
    {
        public int MarkedMissingCount { get; set; }
        public int RestoredCount { get; set; }
    }
}
