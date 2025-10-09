using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Core.Specifications.Collections;
using Fuzzbin.Data.Context;

namespace Fuzzbin.Data.Repositories
{
    public class CollectionRepository : Repository<Collection>, ICollectionRepository
    {
        private new readonly ApplicationDbContext _context;

        public CollectionRepository(ApplicationDbContext context) : base(context)
        {
            _context = context;
        }

        public async Task<Collection?> GetByIdWithVideosAsync(Guid id)
        {
            var specification = new CollectionWithVideosSpecification(id);
            return await FirstOrDefaultAsync(specification);
        }

        public async Task<IEnumerable<Collection>> GetAllWithVideosAsync()
        {
            var specification = new CollectionsWithVideosSpecification();
            return await ListAsync(specification);
        }

        public async Task<IEnumerable<Collection>> GetByTypeAsync(CollectionType type)
        {
            var specification = new CollectionsByTypeSpecification(type);
            return await ListAsync(specification);
        }

        public async Task<IEnumerable<Collection>> GetFavoritesAsync()
        {
            var specification = new CollectionsFavoritesSpecification();
            return await ListAsync(specification);
        }

        public async Task<IEnumerable<Collection>> GetPublicCollectionsAsync()
        {
            var specification = new CollectionsPublicSpecification();
            return await ListAsync(specification);
        }

        public async Task<bool> AddVideoToCollectionAsync(Guid collectionId, Guid videoId, int position = 0)
        {
            var collection = await _context.Collections
                .Include(c => c.CollectionVideos)
                .FirstOrDefaultAsync(c => c.Id == collectionId && c.IsActive);
            
            if (collection == null)
                return false;

            var video = await _context.Videos.FindAsync(videoId);
            if (video == null || !video.IsActive)
                return false;

            // Check if video is already in collection
            if (collection.CollectionVideos.Any(cv => cv.VideoId == videoId))
                return false;

            var collectionVideo = new CollectionVideo
            {
                CollectionId = collectionId,
                VideoId = videoId,
                Position = position > 0 ? position : collection.CollectionVideos.Count + 1
            };

            collection.CollectionVideos.Add(collectionVideo);
            _context.CollectionVideos.Add(collectionVideo);
            collection.VideoCount = collection.CollectionVideos.Count;
            
            await _context.SaveChangesAsync();
            return true;
        }

        public async Task<bool> RemoveVideoFromCollectionAsync(Guid collectionId, Guid videoId)
        {
            var collectionVideo = await _context.CollectionVideos
                .FirstOrDefaultAsync(cv => cv.CollectionId == collectionId && cv.VideoId == videoId);
            
            if (collectionVideo == null)
                return false;

            _context.CollectionVideos.Remove(collectionVideo);
            
            var collection = await _context.Collections.FindAsync(collectionId);
            if (collection != null)
            {
                collection.VideoCount = Math.Max(0, collection.VideoCount - 1);
            }

            // Reorder remaining videos
            var remainingVideos = await _context.CollectionVideos
                .Where(cv => cv.CollectionId == collectionId && cv.Position > collectionVideo.Position)
                .ToListAsync();
            
            foreach (var video in remainingVideos)
            {
                video.Position--;
            }

            await _context.SaveChangesAsync();
            return true;
        }

        public async Task<bool> UpdateVideoPositionAsync(Guid collectionId, Guid videoId, int newPosition)
        {
            var collectionVideo = await _context.CollectionVideos
                .FirstOrDefaultAsync(cv => cv.CollectionId == collectionId && cv.VideoId == videoId);
            
            if (collectionVideo == null)
                return false;

            var oldPosition = collectionVideo.Position;
            
            if (oldPosition == newPosition)
                return true;

            var otherVideos = await _context.CollectionVideos
                .Where(cv => cv.CollectionId == collectionId && cv.Id != collectionVideo.Id)
                .OrderBy(cv => cv.Position)
                .ToListAsync();

            if (newPosition > oldPosition)
            {
                // Moving down
                foreach (var video in otherVideos.Where(v => v.Position > oldPosition && v.Position <= newPosition))
                {
                    video.Position--;
                }
            }
            else
            {
                // Moving up
                foreach (var video in otherVideos.Where(v => v.Position >= newPosition && v.Position < oldPosition))
                {
                    video.Position++;
                }
            }

            collectionVideo.Position = newPosition;
            await _context.SaveChangesAsync();
            return true;
        }

        public async Task<IEnumerable<Video>> GetCollectionVideosAsync(Guid collectionId)
        {
            var specification = new CollectionWithVideosSpecification(collectionId);
            var collection = await FirstOrDefaultAsync(specification);

            if (collection == null)
            {
                return Enumerable.Empty<Video>();
            }

            return collection.CollectionVideos
                .OrderBy(cv => cv.Position)
                .Select(cv => cv.Video)
                .Where(v => v.IsActive)
                .ToList();
        }

        public async Task<int> GetVideoCountAsync(Guid collectionId)
        {
            return await _context.CollectionVideos
                .CountAsync(cv => cv.CollectionId == collectionId);
        }

        public async Task<TimeSpan> GetTotalDurationAsync(Guid collectionId)
        {
            var totalSeconds = await _context.CollectionVideos
                .Where(cv => cv.CollectionId == collectionId)
                .Select(cv => cv.Video.Duration ?? 0)
                .SumAsync();
            
            return TimeSpan.FromSeconds(totalSeconds);
        }

        public async Task<bool> ReorderVideosAsync(Guid collectionId, List<Guid> videoIds)
        {
            var collectionVideos = await _context.CollectionVideos
                .Where(cv => cv.CollectionId == collectionId)
                .ToListAsync();
            
            if (collectionVideos.Count != videoIds.Count)
                return false;

            for (int i = 0; i < videoIds.Count; i++)
            {
                var collectionVideo = collectionVideos.FirstOrDefault(cv => cv.VideoId == videoIds[i]);
                if (collectionVideo == null)
                    return false;
                
                collectionVideo.Position = i + 1;
            }

            await _context.SaveChangesAsync();
            return true;
        }

        public async Task<IEnumerable<Collection>> SearchCollectionsAsync(string searchTerm)
        {
            var specification = new CollectionsSearchSpecification(searchTerm);
            return await ListAsync(specification);
        }

        public async Task<Collection?> DuplicateCollectionAsync(Guid collectionId, string newName)
        {
            var originalCollection = await GetByIdWithVideosAsync(collectionId);
            if (originalCollection == null)
                return null;

            var newCollection = new Collection
            {
                Name = newName,
                Description = originalCollection.Description,
                Type = originalCollection.Type,
                SmartCriteria = originalCollection.SmartCriteria,
                IsPublic = originalCollection.IsPublic,
                IsFavorite = false,
                SortOrder = originalCollection.SortOrder,
                VideoCount = originalCollection.VideoCount,
                TotalDuration = originalCollection.TotalDuration
            };

            _context.Collections.Add(newCollection);
            await _context.SaveChangesAsync();

            // Copy videos to new collection
            foreach (var cv in originalCollection.CollectionVideos.OrderBy(v => v.Position))
            {
                _context.CollectionVideos.Add(new CollectionVideo
                {
                    CollectionId = newCollection.Id,
                    VideoId = cv.VideoId,
                    Position = cv.Position,
                    Notes = cv.Notes
                });
            }

            await _context.SaveChangesAsync();
            return newCollection;
        }

        public async Task<bool> MergeCollectionsAsync(Guid sourceId, Guid targetId)
        {
            if (sourceId == targetId)
                return false;

            var sourceVideos = await _context.CollectionVideos
                .Where(cv => cv.CollectionId == sourceId)
                .ToListAsync();
            
            var targetVideos = await _context.CollectionVideos
                .Where(cv => cv.CollectionId == targetId)
                .ToListAsync();
            
            var maxPosition = targetVideos.Any() ? targetVideos.Max(v => v.Position) : 0;
            var addedCount = 0;

            foreach (var sourceVideo in sourceVideos)
            {
                // Skip if video already exists in target
                if (targetVideos.Any(tv => tv.VideoId == sourceVideo.VideoId))
                    continue;

                addedCount++;
                _context.CollectionVideos.Add(new CollectionVideo
                {
                    CollectionId = targetId,
                    VideoId = sourceVideo.VideoId,
                    Position = ++maxPosition,
                    Notes = sourceVideo.Notes
                });
            }

            // Update target collection video count
            var targetCollection = await _context.Collections.FindAsync(targetId);
            if (targetCollection != null)
            {
                targetCollection.VideoCount = targetVideos.Count + addedCount;
            }

            // Delete source collection
            var sourceCollection = await _context.Collections.FindAsync(sourceId);
            if (sourceCollection != null)
            {
                sourceCollection.IsActive = false;
            }

            await _context.SaveChangesAsync();
            return true;
        }
    }
}
