using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Core.Specifications.Collections;
using Fuzzbin.Core.Specifications.Videos;
using Fuzzbin.Services.Interfaces;

namespace Fuzzbin.Services
{
    public class CollectionService : ICollectionService
    {
        private readonly IUnitOfWork _unitOfWork;
        private readonly ILogger<CollectionService> _logger;

        public CollectionService(IUnitOfWork unitOfWork, ILogger<CollectionService> logger)
        {
            _unitOfWork = unitOfWork;
            _logger = logger;
        }

        public async Task<Collection> CreateCollectionAsync(string name, string? description = null, CollectionType type = CollectionType.Manual)
        {
            try
            {
                var collection = new Collection
                {
                    Name = name,
                    Description = description,
                    Type = type,
                    IsPublic = true,
                    IsFavorite = false,
                    VideoCount = 0,
                    TotalDuration = TimeSpan.Zero,
                    SortOrder = 0
                };

                await _unitOfWork.Collections.AddAsync(collection);
                await _unitOfWork.SaveChangesAsync();

                _logger.LogInformation("Created new collection: {CollectionName} (ID: {CollectionId})", name, collection.Id);
                return collection;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error creating collection: {CollectionName}", name);
                throw;
            }
        }

        public async Task<Collection?> GetCollectionAsync(Guid id)
        {
            return await _unitOfWork.Collections.GetByIdWithVideosAsync(id);
        }

        public async Task<IEnumerable<Collection>> GetAllCollectionsAsync()
        {
            return await _unitOfWork.Collections.GetAllWithVideosAsync();
        }

        public async Task<IEnumerable<Collection>> GetUserCollectionsAsync(bool includePrivate = true)
        {
            IReadOnlyList<Collection> collections;

            if (includePrivate)
            {
                collections = await _unitOfWork.Collections.ListAsync(new CollectionsActiveSpecification());
            }
            else
            {
                collections = await _unitOfWork.Collections.ListAsync(new CollectionsPublicSpecification());
            }

            return collections;
        }

        public async Task<bool> UpdateCollectionAsync(Collection collection)
        {
            try
            {
                await _unitOfWork.Collections.UpdateAsync(collection);
                await _unitOfWork.SaveChangesAsync();
                
                _logger.LogInformation("Updated collection: {CollectionId}", collection.Id);
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error updating collection: {CollectionId}", collection.Id);
                return false;
            }
        }

        public async Task<bool> DeleteCollectionAsync(Guid id)
        {
            try
            {
                var collection = await _unitOfWork.Collections.GetByIdAsync(id);
                if (collection == null)
                {
                    _logger.LogWarning("Collection not found for deletion: {CollectionId}", id);
                    return false;
                }

                await _unitOfWork.Collections.DeleteAsync(collection);
                await _unitOfWork.SaveChangesAsync();
                
                _logger.LogInformation("Deleted collection: {CollectionId}", id);
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error deleting collection: {CollectionId}", id);
                return false;
            }
        }

        public async Task<bool> AddVideoToCollectionAsync(Guid collectionId, Guid videoId)
        {
            try
            {
                var result = await _unitOfWork.Collections.AddVideoToCollectionAsync(collectionId, videoId);
                
                if (result)
                {
                    _logger.LogInformation("Added video {VideoId} to collection {CollectionId}", videoId, collectionId);
                    await UpdateCollectionStatistics(collectionId);
                }
                
                return result;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error adding video {VideoId} to collection {CollectionId}", videoId, collectionId);
                return false;
            }
        }

        public async Task<bool> RemoveVideoFromCollectionAsync(Guid collectionId, Guid videoId)
        {
            try
            {
                var result = await _unitOfWork.Collections.RemoveVideoFromCollectionAsync(collectionId, videoId);
                
                if (result)
                {
                    _logger.LogInformation("Removed video {VideoId} from collection {CollectionId}", videoId, collectionId);
                    await UpdateCollectionStatistics(collectionId);
                }
                
                return result;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error removing video {VideoId} from collection {CollectionId}", videoId, collectionId);
                return false;
            }
        }

        public async Task<bool> ReorderCollectionVideosAsync(Guid collectionId, List<Guid> videoIds)
        {
            try
            {
                var result = await _unitOfWork.Collections.ReorderVideosAsync(collectionId, videoIds);
                
                if (result)
                {
                    _logger.LogInformation("Reordered videos in collection {CollectionId}", collectionId);
                }
                
                return result;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error reordering videos in collection {CollectionId}", collectionId);
                return false;
            }
        }

        public async Task<IEnumerable<Video>> GetCollectionVideosAsync(Guid collectionId)
        {
            return await _unitOfWork.Collections.GetCollectionVideosAsync(collectionId);
        }

        public async Task<Collection?> DuplicateCollectionAsync(Guid collectionId, string newName)
        {
            try
            {
                var duplicatedCollection = await _unitOfWork.Collections.DuplicateCollectionAsync(collectionId, newName);
                
                if (duplicatedCollection != null)
                {
                    _logger.LogInformation("Duplicated collection {CollectionId} as {NewCollectionName}", collectionId, newName);
                }
                
                return duplicatedCollection;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error duplicating collection {CollectionId}", collectionId);
                return null;
            }
        }

        public async Task<bool> MergeCollectionsAsync(Guid sourceId, Guid targetId)
        {
            try
            {
                var result = await _unitOfWork.Collections.MergeCollectionsAsync(sourceId, targetId);
                
                if (result)
                {
                    _logger.LogInformation("Merged collection {SourceId} into {TargetId}", sourceId, targetId);
                    await UpdateCollectionStatistics(targetId);
                }
                
                return result;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error merging collections {SourceId} into {TargetId}", sourceId, targetId);
                return false;
            }
        }

        public async Task<bool> ToggleFavoriteAsync(Guid collectionId)
        {
            try
            {
                var collection = await _unitOfWork.Collections.GetByIdAsync(collectionId);
                if (collection == null)
                    return false;

                collection.IsFavorite = !collection.IsFavorite;
                await _unitOfWork.Collections.UpdateAsync(collection);
                await _unitOfWork.SaveChangesAsync();
                
                _logger.LogInformation("Toggled favorite status for collection {CollectionId}: {IsFavorite}", 
                    collectionId, collection.IsFavorite);
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error toggling favorite for collection {CollectionId}", collectionId);
                return false;
            }
        }

        public async Task<bool> SetCollectionVisibilityAsync(Guid collectionId, bool isPublic)
        {
            try
            {
                var collection = await _unitOfWork.Collections.GetByIdAsync(collectionId);
                if (collection == null)
                    return false;

                collection.IsPublic = isPublic;
                await _unitOfWork.Collections.UpdateAsync(collection);
                await _unitOfWork.SaveChangesAsync();
                
                _logger.LogInformation("Set collection {CollectionId} visibility to {IsPublic}", collectionId, isPublic);
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error setting visibility for collection {CollectionId}", collectionId);
                return false;
            }
        }

        public async Task<IEnumerable<Collection>> SearchCollectionsAsync(string searchTerm)
        {
            return await _unitOfWork.Collections.SearchCollectionsAsync(searchTerm);
        }

        public async Task<bool> UpdateSmartCollectionCriteriaAsync(Guid collectionId, string criteria)
        {
            try
            {
                var collection = await _unitOfWork.Collections.GetByIdAsync(collectionId);
                if (collection == null || collection.Type != CollectionType.Smart)
                    return false;

                collection.SmartCriteria = criteria;
                await _unitOfWork.Collections.UpdateAsync(collection);
                await _unitOfWork.SaveChangesAsync();
                
                // Refresh the collection with new criteria
                await RefreshSmartCollectionAsync(collectionId);
                
                _logger.LogInformation("Updated smart collection criteria for {CollectionId}", collectionId);
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error updating smart collection criteria for {CollectionId}", collectionId);
                return false;
            }
        }

        public async Task<bool> RefreshSmartCollectionAsync(Guid collectionId)
        {
            try
            {
                var collection = await _unitOfWork.Collections.GetByIdWithVideosAsync(collectionId);
                if (collection == null || collection.Type != CollectionType.Smart || string.IsNullOrEmpty(collection.SmartCriteria))
                    return false;

                // Parse and apply smart criteria
                // This is a simplified implementation - you'd want to implement a proper criteria parser
                var allVideos = await _unitOfWork.Videos.ListAsync(new VideoActiveSpecification(includeRelations: true));
                var filteredVideos = ApplySmartCriteria(allVideos, collection.SmartCriteria);

                // Clear existing videos
                var existingVideos = collection.CollectionVideos.ToList();
                foreach (var cv in existingVideos)
                {
                    await _unitOfWork.Collections.RemoveVideoFromCollectionAsync(collectionId, cv.VideoId);
                }

                // Add filtered videos
                int position = 1;
                foreach (var video in filteredVideos)
                {
                    await _unitOfWork.Collections.AddVideoToCollectionAsync(collectionId, video.Id, position++);
                }

                await UpdateCollectionStatistics(collectionId);
                
                _logger.LogInformation("Refreshed smart collection {CollectionId}", collectionId);
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error refreshing smart collection {CollectionId}", collectionId);
                return false;
            }
        }

        public async Task<Dictionary<string, object>> GetCollectionStatisticsAsync(Guid collectionId)
        {
            var stats = new Dictionary<string, object>();

            try
            {
                var collection = await _unitOfWork.Collections.GetByIdWithVideosAsync(collectionId);
                if (collection == null)
                    return stats;

                var videos = await _unitOfWork.Collections.GetCollectionVideosAsync(collectionId);
                var videosList = videos.ToList();

                stats["VideoCount"] = videosList.Count;
                stats["TotalDuration"] = await _unitOfWork.Collections.GetTotalDurationAsync(collectionId);
                stats["TotalSize"] = videosList.Sum(v => v.FileSize ?? 0);
                stats["AverageRating"] = videosList.Any(v => v.Rating.HasValue) 
                    ? videosList.Where(v => v.Rating.HasValue).Average(v => v.Rating!.Value) 
                    : 0;
                stats["TopArtists"] = videosList.GroupBy(v => v.Artist)
                    .OrderByDescending(g => g.Count())
                    .Take(5)
                    .Select(g => new { Artist = g.Key, Count = g.Count() });
                stats["YearRange"] = videosList.Any(v => v.Year.HasValue) 
                    ? $"{videosList.Where(v => v.Year.HasValue).Min(v => v.Year)}-{videosList.Where(v => v.Year.HasValue).Max(v => v.Year)}"
                    : "N/A";
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting statistics for collection {CollectionId}", collectionId);
            }

            return stats;
        }

        public async Task<bool> ExportCollectionAsync(Guid collectionId, string exportPath, string format = "m3u")
        {
            try
            {
                var collection = await _unitOfWork.Collections.GetByIdWithVideosAsync(collectionId);
                if (collection == null)
                    return false;

                var videos = await _unitOfWork.Collections.GetCollectionVideosAsync(collectionId);

                switch (format.ToLower())
                {
                    case "m3u":
                        await ExportAsM3U(collection, videos, exportPath);
                        break;
                    case "json":
                        await ExportAsJson(collection, videos, exportPath);
                        break;
                    case "csv":
                        await ExportAsCsv(collection, videos, exportPath);
                        break;
                    default:
                        _logger.LogWarning("Unsupported export format: {Format}", format);
                        return false;
                }

                _logger.LogInformation("Exported collection {CollectionId} to {ExportPath} as {Format}", 
                    collectionId, exportPath, format);
                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error exporting collection {CollectionId}", collectionId);
                return false;
            }
        }

        public async Task<Collection?> ImportCollectionAsync(string importPath, string name)
        {
            try
            {
                if (!System.IO.File.Exists(importPath))
                {
                    _logger.LogWarning("Import file not found: {ImportPath}", importPath);
                    return null;
                }

                var extension = System.IO.Path.GetExtension(importPath).ToLower();
                Collection? collection = null;

                switch (extension)
                {
                    case ".m3u":
                    case ".m3u8":
                        collection = await ImportFromM3U(importPath, name);
                        break;
                    case ".json":
                        collection = await ImportFromJson(importPath, name);
                        break;
                    case ".csv":
                        collection = await ImportFromCsv(importPath, name);
                        break;
                    default:
                        _logger.LogWarning("Unsupported import format: {Extension}", extension);
                        return null;
                }

                if (collection != null)
                {
                    _logger.LogInformation("Imported collection {CollectionName} from {ImportPath}", name, importPath);
                }

                return collection;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error importing collection from {ImportPath}", importPath);
                return null;
            }
        }

        private async Task UpdateCollectionStatistics(Guid collectionId)
        {
            try
            {
                var collection = await _unitOfWork.Collections.GetByIdAsync(collectionId);
                if (collection == null)
                    return;

                collection.VideoCount = await _unitOfWork.Collections.GetVideoCountAsync(collectionId);
                collection.TotalDuration = await _unitOfWork.Collections.GetTotalDurationAsync(collectionId);
                
                await _unitOfWork.Collections.UpdateAsync(collection);
                await _unitOfWork.SaveChangesAsync();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error updating statistics for collection {CollectionId}", collectionId);
            }
        }

        private IEnumerable<Video> ApplySmartCriteria(IEnumerable<Video> videos, string criteria)
        {
            // This is a simplified implementation
            // In a real application, you'd want to implement a proper query language parser
            // For now, we'll just do basic string matching
            
            var criteriaLower = criteria.ToLower();
            
            if (criteriaLower.Contains("year:"))
            {
                // Extract year criteria
                var yearMatch = System.Text.RegularExpressions.Regex.Match(criteriaLower, @"year:(\d{4})");
                if (yearMatch.Success && int.TryParse(yearMatch.Groups[1].Value, out int year))
                {
                    videos = videos.Where(v => v.Year == year);
                }
            }

            if (criteriaLower.Contains("artist:"))
            {
                // Extract artist criteria
                var artistMatch = System.Text.RegularExpressions.Regex.Match(criteriaLower, @"artist:([^\s]+)");
                if (artistMatch.Success)
                {
                    var artist = artistMatch.Groups[1].Value;
                    videos = videos.Where(v => v.Artist.ToLower().Contains(artist));
                }
            }

            if (criteriaLower.Contains("rating:"))
            {
                // Extract rating criteria
                var ratingMatch = System.Text.RegularExpressions.Regex.Match(criteriaLower, @"rating:(\d+)");
                if (ratingMatch.Success && int.TryParse(ratingMatch.Groups[1].Value, out int rating))
                {
                    videos = videos.Where(v => v.Rating >= rating);
                }
            }

            return videos;
        }

        private async Task ExportAsM3U(Collection collection, IEnumerable<Video> videos, string exportPath)
        {
            var lines = new List<string> { "#EXTM3U" };
            
            foreach (var video in videos)
            {
                if (!string.IsNullOrEmpty(video.FilePath))
                {
                    lines.Add($"#EXTINF:{video.Duration ?? -1},{video.Artist} - {video.Title}");
                    lines.Add(video.FilePath);
                }
            }

            await System.IO.File.WriteAllLinesAsync(exportPath, lines);
        }

        private async Task ExportAsJson(Collection collection, IEnumerable<Video> videos, string exportPath)
        {
            var exportData = new
            {
                Collection = new
                {
                    collection.Name,
                    collection.Description,
                    collection.Type,
                    ExportDate = DateTime.UtcNow
                },
                Videos = videos.Select(v => new
                {
                    v.Title,
                    v.Artist,
                    v.Album,
                    v.Year,
                    v.Duration,
                    v.FilePath
                })
            };

            var json = System.Text.Json.JsonSerializer.Serialize(exportData, new System.Text.Json.JsonSerializerOptions 
            { 
                WriteIndented = true 
            });
            
            await System.IO.File.WriteAllTextAsync(exportPath, json);
        }

        private async Task ExportAsCsv(Collection collection, IEnumerable<Video> videos, string exportPath)
        {
            var lines = new List<string>
            {
                "Title,Artist,Album,Year,Duration,FilePath"
            };

            foreach (var video in videos)
            {
                lines.Add($"\"{video.Title}\",\"{video.Artist}\",\"{video.Album ?? ""}\",{video.Year ?? 0},{video.Duration ?? 0},\"{video.FilePath ?? ""}\"");
            }

            await System.IO.File.WriteAllLinesAsync(exportPath, lines);
        }

        private async Task<Collection?> ImportFromM3U(string importPath, string name)
        {
            var lines = await System.IO.File.ReadAllLinesAsync(importPath);
            var collection = await CreateCollectionAsync(name, $"Imported from {System.IO.Path.GetFileName(importPath)}");

            var videos = await _unitOfWork.Videos.ListAsync(new VideoActiveSpecification(includeRelations: false));
            var videoLookup = videos
                .Where(v => !string.IsNullOrEmpty(v.FilePath))
                .ToDictionary(v => v.FilePath!, StringComparer.OrdinalIgnoreCase);

            foreach (var line in lines)
            {
                if (string.IsNullOrWhiteSpace(line) || line.StartsWith("#"))
                    continue;

                if (!videoLookup.TryGetValue(line, out var video))
                {
                    continue;
                }
                
                await AddVideoToCollectionAsync(collection.Id, video.Id);
            }

            return collection;
        }

        private async Task<Collection?> ImportFromJson(string importPath, string name)
        {
            var json = await System.IO.File.ReadAllTextAsync(importPath);
            // Implement JSON deserialization and import logic
            // This would be similar to ImportFromM3U but parsing JSON structure
            return await CreateCollectionAsync(name, $"Imported from {System.IO.Path.GetFileName(importPath)}");
        }

        private async Task<Collection?> ImportFromCsv(string importPath, string name)
        {
            var lines = await System.IO.File.ReadAllLinesAsync(importPath);
            // Implement CSV parsing and import logic
            // This would be similar to ImportFromM3U but parsing CSV structure
            return await CreateCollectionAsync(name, $"Imported from {System.IO.Path.GetFileName(importPath)}");
        }
    }
}
