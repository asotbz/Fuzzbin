namespace Fuzzbin.Services;

/// <summary>
/// Defines available pattern variables for file organization
/// </summary>
public static class FileOrganizationPatternVariables
{
    public static readonly Dictionary<string, string> Variables = new()
    {
        { "artist", "Artist name" },
        { "artist_safe", "Artist name (filesystem safe)" },
        { "artist_sort", "Artist sort name" },
        { "primary_artist", "Primary artist without featured collaborators" },
        
        { "title", "Video title" },
        { "title_safe", "Video title (filesystem safe)" },
        
        { "year", "Release year (4 digits)" },
        { "year2", "Release year (2 digits)" },
        { "month", "Release month (2 digits)" },
        { "month_name", "Release month name" },
        { "day", "Release day (2 digits)" },
        { "date", "Release date (YYYY-MM-DD)" },
        
        { "genre", "Primary genre" },
        { "genres", "All genres (comma separated)" },
        
        { "label", "Record label" },
        { "label_safe", "Record label (filesystem safe)" },
        
        { "resolution", "Video resolution (e.g., 1080p)" },
        { "width", "Video width in pixels" },
        { "height", "Video height in pixels" },
        { "codec", "Video codec" },
        { "format", "File format/extension" },
        { "bitrate", "Video bitrate" },
        { "fps", "Frames per second" },
        
        { "imvdb_id", "IMVDb ID" },
        { "director", "Director name" },
        { "production", "Production company" },
        { "featured_artists", "Featured artists" },
        
        { "mb_artist_id", "MusicBrainz artist ID" },
        { "mb_recording_id", "MusicBrainz recording ID" },
        { "album", "Album name" },
        { "track_number", "Track number" },
        
        { "tags", "All tags (comma separated)" },
        { "collection", "Collection name" },
        { "custom1", "Custom field 1" },
        { "custom2", "Custom field 2" },
        { "custom3", "Custom field 3" }
    };
}