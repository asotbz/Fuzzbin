using System;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace Fuzzbin.Services.Interfaces;

/// <summary>
/// Broadcasts video lifecycle events to interested listeners (e.g., SignalR hubs).
/// </summary>
public interface IVideoUpdateNotifier
{
    Task VideoCreatedAsync(VideoUpdateNotification video);
    Task VideoUpdatedAsync(VideoUpdateNotification video);
    Task VideoDeletedAsync(Guid videoId);
}

public sealed record VideoUpdateNotification(
    Guid Id,
    string Title,
    string Artist,
    string? Album,
    int? Year,
    int? Duration,
    string? Format,
    string? ThumbnailPath,
    DateTime? ImportedAt,
    DateTime? UpdatedAt,
    IReadOnlyList<string> Genres,
    IReadOnlyList<string> Tags
);
