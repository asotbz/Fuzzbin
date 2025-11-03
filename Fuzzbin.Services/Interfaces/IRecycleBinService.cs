using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Services.Interfaces
{
    /// <summary>
    /// Service for managing the recycle bin functionality
    /// </summary>
    public interface IRecycleBinService
    {
        /// <summary>
        /// Moves a file to the recycle bin instead of permanently deleting it
        /// </summary>
        /// <param name="filePath">The file to move to recycle bin</param>
        /// <param name="downloadQueueItemId">Optional associated download queue item</param>
        /// <param name="videoId">Optional associated video</param>
        /// <param name="reason">Reason for deletion</param>
        /// <returns>The recycle bin record</returns>
        Task<RecycleBin> MoveToRecycleBinAsync(
            string filePath, 
            Guid? downloadQueueItemId = null, 
            Guid? videoId = null, 
            string? reason = null);
        
        /// <summary>
        /// Restores a file from the recycle bin to its original location
        /// </summary>
        /// <param name="recycleBinId">The recycle bin record ID</param>
        /// <returns>True if restored successfully</returns>
        Task<bool> RestoreFromRecycleBinAsync(Guid recycleBinId);
        
        /// <summary>
        /// Permanently deletes a file from the recycle bin
        /// </summary>
        /// <param name="recycleBinId">The recycle bin record ID</param>
        /// <returns>True if deleted successfully</returns>
        Task<bool> PermanentlyDeleteAsync(Guid recycleBinId);
        
        /// <summary>
        /// Gets all items currently in the recycle bin
        /// </summary>
        /// <param name="includeExpired">Whether to include expired items</param>
        /// <returns>List of recycle bin items</returns>
        Task<List<RecycleBin>> GetRecycleBinItemsAsync(bool includeExpired = true);
        
        /// <summary>
        /// Purges expired items from the recycle bin
        /// </summary>
        /// <returns>Number of items purged</returns>
        Task<int> PurgeExpiredItemsAsync();
        
        /// <summary>
        /// Empties the entire recycle bin
        /// </summary>
        /// <returns>Number of items deleted</returns>
        Task<int> EmptyRecycleBinAsync();
        
        /// <summary>
        /// Gets the total size of files in the recycle bin
        /// </summary>
        /// <returns>Total size in bytes</returns>
        Task<long> GetRecycleBinSizeAsync();
        
        /// <summary>
        /// Sets the expiration date for recycle bin items
        /// </summary>
        /// <param name="daysToKeep">Number of days to keep items before auto-purge</param>
        Task SetExpirationPolicyAsync(int daysToKeep);
    }
}