using Microsoft.Extensions.Caching.Memory;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.Interfaces;
using static Fuzzbin.Services.Interfaces.IPlaylistService;
using static Fuzzbin.Services.Interfaces.ISearchService;

namespace Fuzzbin.Services;

public class PlaylistService : IPlaylistService
{
    private readonly IUnitOfWork _unitOfWork;
    private readonly ILogger<PlaylistService> _logger;
    private readonly IMemoryCache _cache;
    private readonly ISearchService _searchService;
    private readonly TimeSpan _sessionCacheDuration = TimeSpan.FromHours(24);

    public PlaylistService(
        IUnitOfWork unitOfWork,
        ILogger<PlaylistService> logger,
        IMemoryCache cache,
        ISearchService searchService)
    {
        _unitOfWork = unitOfWork;
        _logger = logger;
        _cache = cache;
        _searchService = searchService;
    }

    public async Task<PlaylistSession> CreateFromCollectionAsync(Guid collectionId)
    {
        var collections = await _unitOfWork.Collections.GetAllAsync();
        var collection = collections.FirstOrDefault(c => c.Id == collectionId);
        if (collection == null)
        {
            throw new ArgumentException($"Collection with ID {collectionId} not found");
        }

        var videos = collection.CollectionVideos
            .OrderBy(cv => cv.Position)
            .Select(cv => cv.Video)
            .Where(v => v != null && v.IsActive)
            .ToList();

        var session = new PlaylistSession
        {
            SessionId = Guid.NewGuid(),
            Videos = videos!,
            CurrentIndex = 0,
            IsPlaying = false,
            IsShuffled = false,
            IsRepeating = false,
            RepeatMode = RepeatMode.None,
            CreatedAt = DateTime.UtcNow,
            LastAccessedAt = DateTime.UtcNow
        };

        await CacheSessionAsync(session);
        _logger.LogInformation("Created playlist session {SessionId} from collection {CollectionId} with {VideoCount} videos",
            session.SessionId, collectionId, videos.Count);

        return session;
    }

    public async Task<PlaylistSession> CreateFromVideosAsync(List<Guid> videoIds)
    {
        var allVideos = await _unitOfWork.Videos.GetAllAsync();
        var videos = new List<Video>();
        foreach (var id in videoIds)
        {
            var video = allVideos.FirstOrDefault(v => v.Id == id);
            if (video != null && video.IsActive)
            {
                videos.Add(video);
            }
        }

        var session = new PlaylistSession
        {
            SessionId = Guid.NewGuid(),
            Videos = videos,
            CurrentIndex = 0,
            IsPlaying = false,
            IsShuffled = false,
            IsRepeating = false,
            RepeatMode = RepeatMode.None,
            CreatedAt = DateTime.UtcNow,
            LastAccessedAt = DateTime.UtcNow
        };

        await CacheSessionAsync(session);
        _logger.LogInformation("Created playlist session {SessionId} with {VideoCount} videos",
            session.SessionId, videos.Count);

        return session;
    }

    public async Task<PlaylistSession> CreateFromSearchAsync(Guid savedSearchId)
    {
        var savedSearch = await _searchService.GetSavedSearchAsync(savedSearchId);
        if (savedSearch == null)
        {
            throw new ArgumentException($"Saved search with ID {savedSearchId} not found");
        }

        var searchQuery = System.Text.Json.JsonSerializer.Deserialize<SearchQuery>(savedSearch.Query);
        if (searchQuery == null)
        {
            throw new InvalidOperationException($"Failed to deserialize search query for saved search {savedSearchId}");
        }
        var searchResult = await _searchService.SearchAsync(searchQuery);
        var videos = searchResult.Videos.ToList();

        var session = new PlaylistSession
        {
            SessionId = Guid.NewGuid(),
            Videos = videos,
            CurrentIndex = 0,
            IsPlaying = false,
            IsShuffled = false,
            IsRepeating = false,
            RepeatMode = RepeatMode.None,
            CreatedAt = DateTime.UtcNow,
            LastAccessedAt = DateTime.UtcNow
        };

        await CacheSessionAsync(session);
        _logger.LogInformation("Created playlist session {SessionId} from saved search {SavedSearchId} with {VideoCount} videos", 
            session.SessionId, savedSearchId, videos.Count);

        return session;
    }

    public async Task<PlaylistSession?> GetSessionAsync(Guid sessionId)
    {
        if (_cache.TryGetValue<PlaylistSession>(GetCacheKey(sessionId), out var session))
        {
            session!.LastAccessedAt = DateTime.UtcNow;
            await CacheSessionAsync(session);
            return session;
        }

        _logger.LogWarning("Playlist session {SessionId} not found", sessionId);
        return null;
    }

    public async Task UpdateSessionAsync(PlaylistSession session)
    {
        session.LastAccessedAt = DateTime.UtcNow;
        await CacheSessionAsync(session);
        _logger.LogDebug("Updated playlist session {SessionId}", session.SessionId);
    }

    public Video? GetCurrentVideo(PlaylistSession session)
    {
        if (session.Videos.Count == 0 || session.CurrentIndex >= session.Videos.Count)
        {
            return null;
        }

        if (session.IsShuffled && session.ShuffleOrder.Count > 0)
        {
            var shuffledIndex = session.ShuffleOrder[session.CurrentIndex];
            return session.Videos[shuffledIndex];
        }

        return session.Videos[session.CurrentIndex];
    }

    public async Task<Video?> NextAsync(PlaylistSession session)
    {
        if (session.Videos.Count == 0)
        {
            return null;
        }

        session.CurrentIndex++;

        // Handle repeat one mode
        if (session.RepeatMode == RepeatMode.RepeatOne)
        {
            session.CurrentIndex--;
            await UpdateSessionAsync(session);
            return GetCurrentVideo(session);
        }

        // Check if we've reached the end
        if (session.CurrentIndex >= session.Videos.Count)
        {
            if (session.RepeatMode == RepeatMode.RepeatAll)
            {
                session.CurrentIndex = 0;
            }
            else
            {
                session.CurrentIndex = session.Videos.Count - 1;
                session.IsPlaying = false;
                await UpdateSessionAsync(session);
                return null;
            }
        }

        await UpdateSessionAsync(session);
        return GetCurrentVideo(session);
    }

    public async Task<Video?> PreviousAsync(PlaylistSession session)
    {
        if (session.Videos.Count == 0)
        {
            return null;
        }

        session.CurrentIndex--;

        if (session.CurrentIndex < 0)
        {
            if (session.RepeatMode == RepeatMode.RepeatAll)
            {
                session.CurrentIndex = session.Videos.Count - 1;
            }
            else
            {
                session.CurrentIndex = 0;
            }
        }

        await UpdateSessionAsync(session);
        return GetCurrentVideo(session);
    }

    public async Task<Video?> JumpToIndexAsync(PlaylistSession session, int index)
    {
        if (index < 0 || index >= session.Videos.Count)
        {
            throw new ArgumentOutOfRangeException(nameof(index));
        }

        session.CurrentIndex = index;
        await UpdateSessionAsync(session);
        return GetCurrentVideo(session);
    }

    public async Task AddVideosAsync(PlaylistSession session, List<Guid> videoIds)
    {
        var allVideos = await _unitOfWork.Videos.GetAllAsync();
        foreach (var id in videoIds)
        {
            var video = allVideos.FirstOrDefault(v => v.Id == id);
            if (video != null && video.IsActive)
            {
                session.Videos.Add(video);
                if (session.IsShuffled)
                {
                    // Add to shuffle order
                    session.ShuffleOrder.Add(session.Videos.Count - 1);
                }
            }
        }

        await UpdateSessionAsync(session);
        _logger.LogInformation("Added {Count} videos to playlist session {SessionId}",
            videoIds.Count, session.SessionId);
    }

    public async Task RemoveVideoAsync(PlaylistSession session, int index)
    {
        if (index < 0 || index >= session.Videos.Count)
        {
            throw new ArgumentOutOfRangeException(nameof(index));
        }

        session.Videos.RemoveAt(index);

        // Update shuffle order if needed
        if (session.IsShuffled)
        {
            session.ShuffleOrder.Remove(index);
            // Adjust indices in shuffle order
            for (int i = 0; i < session.ShuffleOrder.Count; i++)
            {
                if (session.ShuffleOrder[i] > index)
                {
                    session.ShuffleOrder[i]--;
                }
            }
        }

        // Adjust current index if needed
        if (session.CurrentIndex >= session.Videos.Count && session.Videos.Count > 0)
        {
            session.CurrentIndex = session.Videos.Count - 1;
        }

        await UpdateSessionAsync(session);
        _logger.LogInformation("Removed video at index {Index} from playlist session {SessionId}", 
            index, session.SessionId);
    }

    public async Task ReorderAsync(PlaylistSession session, int fromIndex, int toIndex)
    {
        if (fromIndex < 0 || fromIndex >= session.Videos.Count ||
            toIndex < 0 || toIndex >= session.Videos.Count)
        {
            throw new ArgumentOutOfRangeException();
        }

        var video = session.Videos[fromIndex];
        session.Videos.RemoveAt(fromIndex);
        session.Videos.Insert(toIndex, video);

        // Adjust current index if needed
        if (session.CurrentIndex == fromIndex)
        {
            session.CurrentIndex = toIndex;
        }
        else if (fromIndex < session.CurrentIndex && toIndex >= session.CurrentIndex)
        {
            session.CurrentIndex--;
        }
        else if (fromIndex > session.CurrentIndex && toIndex <= session.CurrentIndex)
        {
            session.CurrentIndex++;
        }

        await UpdateSessionAsync(session);
        _logger.LogInformation("Reordered video from index {FromIndex} to {ToIndex} in playlist session {SessionId}", 
            fromIndex, toIndex, session.SessionId);
    }

    public async Task ToggleShuffleAsync(PlaylistSession session)
    {
        session.IsShuffled = !session.IsShuffled;

        if (session.IsShuffled)
        {
            // Create shuffle order
            session.ShuffleOrder = Enumerable.Range(0, session.Videos.Count).ToList();
            
            // Fisher-Yates shuffle
            var random = new Random();
            for (int i = session.ShuffleOrder.Count - 1; i > 0; i--)
            {
                int j = random.Next(i + 1);
                (session.ShuffleOrder[i], session.ShuffleOrder[j]) = (session.ShuffleOrder[j], session.ShuffleOrder[i]);
            }

            // Make sure current video stays current
            if (session.Videos.Count > 0 && session.CurrentIndex < session.Videos.Count)
            {
                var currentVideoIndex = session.CurrentIndex;
                var shufflePosition = session.ShuffleOrder.IndexOf(currentVideoIndex);
                if (shufflePosition != 0)
                {
                    (session.ShuffleOrder[0], session.ShuffleOrder[shufflePosition]) = 
                        (session.ShuffleOrder[shufflePosition], session.ShuffleOrder[0]);
                }
                session.CurrentIndex = 0;
            }
        }
        else
        {
            // Return to original order
            if (session.Videos.Count > 0 && session.CurrentIndex < session.ShuffleOrder.Count)
            {
                session.CurrentIndex = session.ShuffleOrder[session.CurrentIndex];
            }
            session.ShuffleOrder.Clear();
        }

        await UpdateSessionAsync(session);
        _logger.LogInformation("Toggled shuffle to {IsShuffled} for playlist session {SessionId}", 
            session.IsShuffled, session.SessionId);
    }

    public async Task SetRepeatModeAsync(PlaylistSession session, RepeatMode mode)
    {
        session.RepeatMode = mode;
        session.IsRepeating = mode != RepeatMode.None;
        await UpdateSessionAsync(session);
        _logger.LogInformation("Set repeat mode to {RepeatMode} for playlist session {SessionId}", 
            mode, session.SessionId);
    }

    public async Task ClearAsync(PlaylistSession session)
    {
        session.Videos.Clear();
        session.ShuffleOrder.Clear();
        session.CurrentIndex = 0;
        session.IsPlaying = false;
        await UpdateSessionAsync(session);
        _logger.LogInformation("Cleared playlist session {SessionId}", session.SessionId);
    }

    public Task CleanupOldSessionsAsync(TimeSpan maxAge)
    {
        // Note: This is a simple implementation using in-memory cache
        // In a production system, you might want to persist sessions to database
        _logger.LogInformation("Cleaning up playlist sessions older than {MaxAge}", maxAge);
        return Task.CompletedTask;
    }

    public Task<string> ExportToM3uAsync(PlaylistSession session)
    {
        var m3u = new System.Text.StringBuilder();
        m3u.AppendLine("#EXTM3U");
        
        foreach (var video in session.Videos)
        {
            var duration = video.Duration ?? 0;
            m3u.AppendLine($"#EXTINF:{duration},{video.Artist} - {video.Title}");
            if (!string.IsNullOrEmpty(video.FilePath))
            {
                m3u.AppendLine(video.FilePath);
            }
        }

        return Task.FromResult(m3u.ToString());
    }

    public TimeSpan GetTotalDuration(PlaylistSession session)
    {
        var totalSeconds = session.Videos.Sum(v => v.Duration ?? 0);
        return TimeSpan.FromSeconds(totalSeconds);
    }

    public TimeSpan GetRemainingDuration(PlaylistSession session)
    {
        if (session.CurrentIndex >= session.Videos.Count)
        {
            return TimeSpan.Zero;
        }

        var remainingVideos = session.IsShuffled && session.ShuffleOrder.Count > 0
            ? session.ShuffleOrder.Skip(session.CurrentIndex).Select(i => session.Videos[i])
            : session.Videos.Skip(session.CurrentIndex);

        var totalSeconds = remainingVideos.Sum(v => v.Duration ?? 0);
        return TimeSpan.FromSeconds(totalSeconds);
    }

    private string GetCacheKey(Guid sessionId) => $"playlist_session_{sessionId}";

    private Task CacheSessionAsync(PlaylistSession session)
    {
        _cache.Set(GetCacheKey(session.SessionId), session, _sessionCacheDuration);
        return Task.CompletedTask;
    }
}