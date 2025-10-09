using Fuzzbin.Core.Entities;

namespace Fuzzbin.Services.Interfaces;

public interface IPlaylistService
{
    /// <summary>
    /// Represents a playlist session with current state
    /// </summary>
    public class PlaylistSession
    {
        public Guid SessionId { get; set; }
        public List<Video> Videos { get; set; } = new();
        public int CurrentIndex { get; set; }
        public bool IsPlaying { get; set; }
        public bool IsShuffled { get; set; }
        public bool IsRepeating { get; set; }
        public RepeatMode RepeatMode { get; set; }
        public List<int> ShuffleOrder { get; set; } = new();
        public DateTime CreatedAt { get; set; }
        public DateTime LastAccessedAt { get; set; }
    }

    public enum RepeatMode
    {
        None,
        RepeatOne,
        RepeatAll
    }

    /// <summary>
    /// Create a new playlist session from a collection
    /// </summary>
    Task<PlaylistSession> CreateFromCollectionAsync(Guid collectionId);

    /// <summary>
    /// Create a new playlist session from selected videos
    /// </summary>
    Task<PlaylistSession> CreateFromVideosAsync(List<Guid> videoIds);

    /// <summary>
    /// Create a new playlist session from a saved search
    /// </summary>
    Task<PlaylistSession> CreateFromSearchAsync(Guid savedSearchId);

    /// <summary>
    /// Get an existing playlist session
    /// </summary>
    Task<PlaylistSession?> GetSessionAsync(Guid sessionId);

    /// <summary>
    /// Update playlist session state
    /// </summary>
    Task UpdateSessionAsync(PlaylistSession session);

    /// <summary>
    /// Get the current video in the playlist
    /// </summary>
    Video? GetCurrentVideo(PlaylistSession session);

    /// <summary>
    /// Move to the next video in the playlist
    /// </summary>
    Task<Video?> NextAsync(PlaylistSession session);

    /// <summary>
    /// Move to the previous video in the playlist
    /// </summary>
    Task<Video?> PreviousAsync(PlaylistSession session);

    /// <summary>
    /// Jump to a specific index in the playlist
    /// </summary>
    Task<Video?> JumpToIndexAsync(PlaylistSession session, int index);

    /// <summary>
    /// Add videos to the current playlist
    /// </summary>
    Task AddVideosAsync(PlaylistSession session, List<Guid> videoIds);

    /// <summary>
    /// Remove a video from the playlist
    /// </summary>
    Task RemoveVideoAsync(PlaylistSession session, int index);

    /// <summary>
    /// Reorder videos in the playlist
    /// </summary>
    Task ReorderAsync(PlaylistSession session, int fromIndex, int toIndex);

    /// <summary>
    /// Toggle shuffle mode
    /// </summary>
    Task ToggleShuffleAsync(PlaylistSession session);

    /// <summary>
    /// Set repeat mode
    /// </summary>
    Task SetRepeatModeAsync(PlaylistSession session, RepeatMode mode);

    /// <summary>
    /// Clear the playlist
    /// </summary>
    Task ClearAsync(PlaylistSession session);

    /// <summary>
    /// Clean up old sessions
    /// </summary>
    Task CleanupOldSessionsAsync(TimeSpan maxAge);

    /// <summary>
    /// Export playlist to M3U format
    /// </summary>
    Task<string> ExportToM3uAsync(PlaylistSession session);

    /// <summary>
    /// Get playlist duration
    /// </summary>
    TimeSpan GetTotalDuration(PlaylistSession session);

    /// <summary>
    /// Get remaining duration from current position
    /// </summary>
    TimeSpan GetRemainingDuration(PlaylistSession session);
}