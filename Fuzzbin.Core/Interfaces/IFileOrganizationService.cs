using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Interfaces;

public interface IFileOrganizationService
{
    /// <summary>
    /// Organizes a video file based on the configured naming pattern
    /// </summary>
    Task<string> OrganizeVideoFileAsync(Video video, string sourceFilePath, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Generates a file path based on the configured naming pattern
    /// </summary>
    string GenerateFilePath(Video video, string pattern);
    
    /// <summary>
    /// Validates if a naming pattern is valid
    /// </summary>
    bool ValidatePattern(string pattern);
    
    /// <summary>
    /// Gets available pattern variables for the UI
    /// </summary>
    Dictionary<string, string> GetAvailablePatternVariables();
    
    /// <summary>
    /// Previews what the organized path would be without moving the file
    /// </summary>
    string PreviewOrganizedPath(Video video, string pattern);
    
    /// <summary>
    /// Reorganizes all videos in the library based on new pattern
    /// </summary>
    Task<ReorganizeResult> ReorganizeLibraryAsync(string newPattern, IProgress<ReorganizeProgress>? progress = null, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Moves a video file to a new location
    /// </summary>
    Task<bool> MoveVideoFileAsync(Video video, string newPath, CancellationToken cancellationToken = default);
    
    /// <summary>
    /// Ensures directory structure exists for a given path
    /// </summary>
    void EnsureDirectoryExists(string filePath);
}

public class ReorganizeResult
{
    public int TotalVideos { get; set; }
    public int SuccessfulMoves { get; set; }
    public int FailedMoves { get; set; }
    public List<string> Errors { get; set; } = new();
    public TimeSpan Duration { get; set; }
}

public class ReorganizeProgress
{
    public int Current { get; set; }
    public int Total { get; set; }
    public string CurrentFile { get; set; } = string.Empty;
    public double PercentComplete => Total > 0 ? (double)Current / Total * 100 : 0;
}

public static class FileOrganizationPatternVariables
{
    public static readonly Dictionary<string, string> Variables = new()
    {
        // Artist variables
        { "{artist}", "Artist name" },
        { "{artist_safe}", "Artist name (filesystem safe)" },
        { "{artist_sort}", "Artist sort name" },
        
        // Title variables  
        { "{title}", "Video title" },
        { "{title_safe}", "Video title (filesystem safe)" },
        
        // Date variables
        { "{year}", "Release year (4 digits)" },
        { "{year2}", "Release year (2 digits)" },
        { "{month}", "Release month (2 digits)" },
        { "{month_name}", "Release month name" },
        { "{day}", "Release day (2 digits)" },
        { "{date}", "Release date (YYYY-MM-DD)" },
        
        // Genre variables
        { "{genre}", "Primary genre" },
        { "{genres}", "All genres (comma separated)" },
        
        // Label variables
        { "{label}", "Record label" },
        { "{label_safe}", "Record label (filesystem safe)" },
        
        // Technical variables
        { "{resolution}", "Video resolution (e.g., 1080p)" },
        { "{width}", "Video width in pixels" },
        { "{height}", "Video height in pixels" },
        { "{codec}", "Video codec" },
        { "{format}", "File format/extension" },
        { "{bitrate}", "Video bitrate" },
        { "{fps}", "Frames per second" },
        
        // IMVDb variables
        { "{imvdb_id}", "IMVDb ID" },
        { "{director}", "Director name" },
        { "{production}", "Production company" },
        { "{featured_artists}", "Featured artists" },
        
        // MusicBrainz variables
        { "{mb_artist_id}", "MusicBrainz artist ID" },
        { "{mb_recording_id}", "MusicBrainz recording ID" },
        { "{album}", "Album name" },
        { "{track_number}", "Track number" },
        
        // Custom variables
        { "{tags}", "All tags (comma separated)" },
        { "{collection}", "Collection name" },
        { "{custom1}", "Custom field 1" },
        { "{custom2}", "Custom field 2" },
        { "{custom3}", "Custom field 3" }
    };
    
    public static string MakeFileSystemSafe(string input)
    {
        if (string.IsNullOrWhiteSpace(input))
            return "Unknown";
            
        var invalidChars = Path.GetInvalidFileNameChars()
            .Concat(new[] { ':', '*', '?', '"', '<', '>', '|', '\\', '/' })
            .Distinct();
            
        foreach (var c in invalidChars)
        {
            input = input.Replace(c.ToString(), "_");
        }
        
        // Remove multiple consecutive underscores
        while (input.Contains("__"))
        {
            input = input.Replace("__", "_");
        }
        
        return input.Trim('_', ' ', '.');
    }
}