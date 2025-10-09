using Microsoft.AspNetCore.SignalR;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Web.Hubs;

namespace Fuzzbin.Web.Services;

/// <summary>
/// Pushes video lifecycle events to the SignalR hub so connected UIs can stay in sync.
/// </summary>
public sealed class SignalRVideoUpdateNotifier : IVideoUpdateNotifier
{
    private readonly IHubContext<VideoUpdatesHub> _hubContext;

    public SignalRVideoUpdateNotifier(IHubContext<VideoUpdatesHub> hubContext)
    {
        _hubContext = hubContext;
    }

    public Task VideoCreatedAsync(VideoUpdateNotification video)
    {
        return _hubContext.Clients.All.SendAsync("VideoCreated", video);
    }

    public Task VideoUpdatedAsync(VideoUpdateNotification video)
    {
        return _hubContext.Clients.All.SendAsync("VideoUpdated", video);
    }

    public Task VideoDeletedAsync(Guid videoId)
    {
        return _hubContext.Clients.All.SendAsync("VideoDeleted", videoId);
    }
}
