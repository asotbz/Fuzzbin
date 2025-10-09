using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Interfaces
{
    public interface ICollectionRepository : IRepository<Collection>
    {
        Task<Collection?> GetByIdWithVideosAsync(Guid id);
        Task<IEnumerable<Collection>> GetAllWithVideosAsync();
        Task<IEnumerable<Collection>> GetByTypeAsync(CollectionType type);
        Task<IEnumerable<Collection>> GetFavoritesAsync();
        Task<IEnumerable<Collection>> GetPublicCollectionsAsync();
        Task<bool> AddVideoToCollectionAsync(Guid collectionId, Guid videoId, int position = 0);
        Task<bool> RemoveVideoFromCollectionAsync(Guid collectionId, Guid videoId);
        Task<bool> UpdateVideoPositionAsync(Guid collectionId, Guid videoId, int newPosition);
        Task<IEnumerable<Video>> GetCollectionVideosAsync(Guid collectionId);
        Task<int> GetVideoCountAsync(Guid collectionId);
        Task<TimeSpan> GetTotalDurationAsync(Guid collectionId);
        Task<bool> ReorderVideosAsync(Guid collectionId, List<Guid> videoIds);
        Task<IEnumerable<Collection>> SearchCollectionsAsync(string searchTerm);
        Task<Collection?> DuplicateCollectionAsync(Guid collectionId, string newName);
        Task<bool> MergeCollectionsAsync(Guid sourceId, Guid targetId);
    }
}