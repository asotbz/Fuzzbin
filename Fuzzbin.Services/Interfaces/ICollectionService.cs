using Fuzzbin.Core.Entities;

namespace Fuzzbin.Services.Interfaces;

public interface ICollectionService
{
    // Core CRUD operations
    Task<Collection> CreateCollectionAsync(string name, string? description = null, CollectionType type = CollectionType.Manual);
    Task<Collection?> GetCollectionAsync(Guid id);
    Task<IEnumerable<Collection>> GetAllCollectionsAsync();
    Task<IEnumerable<Collection>> GetUserCollectionsAsync(bool includePrivate = true);
    Task<bool> UpdateCollectionAsync(Collection collection);
    Task<bool> DeleteCollectionAsync(Guid id);
    
    // Video management
    Task<bool> AddVideoToCollectionAsync(Guid collectionId, Guid videoId);
    Task<bool> RemoveVideoFromCollectionAsync(Guid collectionId, Guid videoId);
    Task<bool> ReorderCollectionVideosAsync(Guid collectionId, List<Guid> videoIds);
    Task<IEnumerable<Video>> GetCollectionVideosAsync(Guid collectionId);
    
    // Collection operations
    Task<Collection?> DuplicateCollectionAsync(Guid collectionId, string newName);
    Task<bool> MergeCollectionsAsync(Guid sourceId, Guid targetId);
    Task<bool> ToggleFavoriteAsync(Guid collectionId);
    Task<bool> SetCollectionVisibilityAsync(Guid collectionId, bool isPublic);
    Task<IEnumerable<Collection>> SearchCollectionsAsync(string searchTerm);
    
    // Smart collections
    Task<bool> UpdateSmartCollectionCriteriaAsync(Guid collectionId, string criteria);
    Task<bool> RefreshSmartCollectionAsync(Guid collectionId);
    
    // Statistics and export/import
    Task<Dictionary<string, object>> GetCollectionStatisticsAsync(Guid collectionId);
    Task<bool> ExportCollectionAsync(Guid collectionId, string exportPath, string format = "m3u");
    Task<Collection?> ImportCollectionAsync(string importPath, string name);
}