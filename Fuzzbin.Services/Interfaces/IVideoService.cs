using System.Collections.Generic;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Specifications.Queries;

namespace Fuzzbin.Services.Interfaces;

public interface IVideoService
{
    Task<List<Video>> GetAllVideosAsync(CancellationToken cancellationToken = default);
    Task<Video?> GetVideoByIdAsync(Guid id, CancellationToken cancellationToken = default);
    Task<Video> CreateVideoAsync(Video video, CancellationToken cancellationToken = default);
    Task<Video> UpdateVideoAsync(Video video, CancellationToken cancellationToken = default);
    Task DeleteVideoAsync(Guid id, CancellationToken cancellationToken = default);
    Task<List<Video>> GetVideosByArtistAsync(string artist, CancellationToken cancellationToken = default);
    Task<List<Video>> GetVideosByGenreAsync(Guid genreId, CancellationToken cancellationToken = default);
    Task<List<Video>> GetRecentVideosAsync(int count = 10, CancellationToken cancellationToken = default);
    Task<PagedResult<Video>> GetVideosAsync(VideoQuery query, CancellationToken cancellationToken = default);
    Task<IReadOnlyList<Video>> GetVideosUnpagedAsync(VideoQuery query, CancellationToken cancellationToken = default);
}
