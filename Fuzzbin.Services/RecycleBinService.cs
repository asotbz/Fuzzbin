using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Services.Interfaces;

namespace Fuzzbin.Services
{
    public class RecycleBinService : IRecycleBinService
    {
        private readonly IUnitOfWork _unitOfWork;
        private readonly ILogger<RecycleBinService> _logger;
        private readonly IConfigurationPathService _configService;

        public RecycleBinService(
            IUnitOfWork unitOfWork,
            ILogger<RecycleBinService> logger,
            IConfigurationPathService configService)
        {
            _unitOfWork = unitOfWork;
            _logger = logger;
            _configService = configService;
        }

        public async Task<RecycleBin> MoveToRecycleBinAsync(
            string filePath,
            Guid? downloadQueueItemId = null,
            Guid? videoId = null,
            string? reason = null)
        {
            try
            {
                if (string.IsNullOrWhiteSpace(filePath) || !File.Exists(filePath))
                {
                    throw new FileNotFoundException($"File not found: {filePath}");
                }

                var recycleBinPath = await GetRecycleBinPathAsync();
                Directory.CreateDirectory(recycleBinPath);

                var fileInfo = new FileInfo(filePath);
                var fileName = fileInfo.Name;
                var timestamp = DateTime.UtcNow.ToString("yyyyMMdd_HHmmss");
                var uniqueFileName = $"{timestamp}_{Guid.NewGuid():N}_{fileName}";
                var recycleBinFilePath = Path.Combine(recycleBinPath, uniqueFileName);

                // Move the file to recycle bin
                File.Move(filePath, recycleBinFilePath);

                // Create recycle bin record
                var recycleBinItem = new RecycleBin
                {
                    OriginalFilePath = filePath,
                    RecycleBinPath = recycleBinFilePath,
                    FileSize = fileInfo.Length,
                    DeletedAt = DateTime.UtcNow,
                    ExpiresAt = DateTime.UtcNow.AddDays(30), // Default 30 days retention
                    DownloadQueueItemId = downloadQueueItemId,
                    VideoId = videoId,
                    DeletionReason = reason,
                    CanRestore = true
                };

                await _unitOfWork.RecycleBins.AddAsync(recycleBinItem);
                await _unitOfWork.SaveChangesAsync();

                _logger.LogInformation(
                    "Moved file to recycle bin: {OriginalPath} -> {RecycleBinPath}",
                    filePath, recycleBinFilePath);

                return recycleBinItem;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error moving file to recycle bin: {FilePath}", filePath);
                throw;
            }
        }

        public async Task<bool> RestoreFromRecycleBinAsync(Guid recycleBinId)
        {
            try
            {
                var item = await _unitOfWork.RecycleBins
                    .FirstOrDefaultAsync(r => r.Id == recycleBinId);
                
                if (item == null)
                {
                    _logger.LogWarning("Recycle bin item not found: {Id}", recycleBinId);
                    return false;
                }

                if (!item.CanRestore)
                {
                    _logger.LogWarning("Item cannot be restored: {Id}", recycleBinId);
                    return false;
                }

                if (!File.Exists(item.RecycleBinPath))
                {
                    _logger.LogWarning("File not found in recycle bin: {Path}", item.RecycleBinPath);
                    item.CanRestore = false;
                    await _unitOfWork.RecycleBins.UpdateAsync(item);
                    await _unitOfWork.SaveChangesAsync();
                    return false;
                }

                // Ensure the original directory exists
                var originalDir = Path.GetDirectoryName(item.OriginalFilePath);
                if (!string.IsNullOrWhiteSpace(originalDir))
                {
                    Directory.CreateDirectory(originalDir);
                }

                // Handle duplicate files at original location
                var restorePath = item.OriginalFilePath;
                if (File.Exists(restorePath))
                {
                    var dir = Path.GetDirectoryName(restorePath) ?? "";
                    var fileName = Path.GetFileNameWithoutExtension(restorePath);
                    var extension = Path.GetExtension(restorePath);
                    var counter = 1;
                    
                    do
                    {
                        restorePath = Path.Combine(dir, $"{fileName}_restored_{counter}{extension}");
                        counter++;
                    }
                    while (File.Exists(restorePath));

                    _logger.LogInformation(
                        "Original file exists, restoring to: {NewPath}",
                        restorePath);
                }

                // Move file back from recycle bin
                File.Move(item.RecycleBinPath, restorePath);

                // Remove from recycle bin database
                await _unitOfWork.RecycleBins.DeleteAsync(item);
                await _unitOfWork.SaveChangesAsync();

                _logger.LogInformation(
                    "Restored file from recycle bin: {RecycleBinPath} -> {RestoredPath}",
                    item.RecycleBinPath, restorePath);

                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error restoring file from recycle bin: {Id}", recycleBinId);
                throw;
            }
        }

        public async Task<bool> PermanentlyDeleteAsync(Guid recycleBinId)
        {
            try
            {
                var item = await _unitOfWork.RecycleBins
                    .FirstOrDefaultAsync(r => r.Id == recycleBinId);
                
                if (item == null)
                {
                    _logger.LogWarning("Recycle bin item not found: {Id}", recycleBinId);
                    return false;
                }

                // Delete the physical file
                if (File.Exists(item.RecycleBinPath))
                {
                    File.Delete(item.RecycleBinPath);
                }

                // Remove from database
                await _unitOfWork.RecycleBins.DeleteAsync(item);
                await _unitOfWork.SaveChangesAsync();

                _logger.LogInformation(
                    "Permanently deleted file from recycle bin: {Path}",
                    item.RecycleBinPath);

                return true;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error permanently deleting file: {Id}", recycleBinId);
                throw;
            }
        }

        public async Task<List<RecycleBin>> GetRecycleBinItemsAsync(bool includeExpired = true)
        {
            try
            {
                var allItems = await _unitOfWork.RecycleBins.GetAllAsync();
                
                if (!includeExpired)
                {
                    var now = DateTime.UtcNow;
                    allItems = allItems.Where(i => !i.ExpiresAt.HasValue || i.ExpiresAt.Value > now).ToList();
                }

                return allItems
                    .OrderByDescending(i => i.DeletedAt)
                    .ToList();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error getting recycle bin items");
                throw;
            }
        }

        public async Task<int> PurgeExpiredItemsAsync()
        {
            try
            {
                var now = DateTime.UtcNow;
                var allItems = await _unitOfWork.RecycleBins.GetAllAsync();
                var expiredItems = allItems
                    .Where(i => i.ExpiresAt.HasValue && i.ExpiresAt.Value <= now)
                    .ToList();

                var count = 0;
                foreach (var item in expiredItems)
                {
                    if (await PermanentlyDeleteAsync(item.Id))
                    {
                        count++;
                    }
                }

                _logger.LogInformation("Purged {Count} expired items from recycle bin", count);
                return count;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error purging expired items");
                throw;
            }
        }

        public async Task<int> EmptyRecycleBinAsync()
        {
            try
            {
                var allItems = await _unitOfWork.RecycleBins.GetAllAsync();
                var count = 0;

                foreach (var item in allItems)
                {
                    if (await PermanentlyDeleteAsync(item.Id))
                    {
                        count++;
                    }
                }

                _logger.LogInformation("Emptied recycle bin, deleted {Count} items", count);
                return count;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error emptying recycle bin");
                throw;
            }
        }

        public async Task<long> GetRecycleBinSizeAsync()
        {
            try
            {
                var items = await _unitOfWork.RecycleBins.GetAllAsync();
                return items.Sum(i => i.FileSize ?? 0);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error calculating recycle bin size");
                throw;
            }
        }

        public async Task SetExpirationPolicyAsync(int daysToKeep)
        {
            try
            {
                if (daysToKeep < 1)
                {
                    throw new ArgumentException("Days to keep must be at least 1", nameof(daysToKeep));
                }

                var allItems = await _unitOfWork.RecycleBins.GetAllAsync();
                var cutoffDate = DateTime.UtcNow.AddDays(daysToKeep);

                foreach (var item in allItems)
                {
                    if (!item.ExpiresAt.HasValue || item.ExpiresAt.Value > cutoffDate)
                    {
                        item.ExpiresAt = item.DeletedAt.AddDays(daysToKeep);
                        await _unitOfWork.RecycleBins.UpdateAsync(item);
                    }
                }

                await _unitOfWork.SaveChangesAsync();
                
                _logger.LogInformation(
                    "Updated recycle bin expiration policy to {Days} days",
                    daysToKeep);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error setting expiration policy");
                throw;
            }
        }

        private async Task<string> GetRecycleBinPathAsync()
        {
            try
            {
                // Try to get from configuration
                var config = await _unitOfWork.Configurations
                    .FirstOrDefaultAsync(c => c.Category == "Storage" && c.Key == "RecycleBinPath");

                if (config != null && !string.IsNullOrWhiteSpace(config.Value))
                {
                    return config.Value;
                }

                // Default: /recycleBin under top-level Fuzzbin configuration directory
                var configDir = _configService.GetConfigDirectory();
                var defaultPath = Path.Combine(configDir, "recycleBin");

                // Create the configuration entry
                var newConfig = new Configuration
                {
                    Category = "Storage",
                    Key = "RecycleBinPath",
                    Value = defaultPath,
                    Description = "Path where deleted files are temporarily stored before permanent deletion",
                    IsSystem = false
                };

                await _unitOfWork.Configurations.AddAsync(newConfig);
                await _unitOfWork.SaveChangesAsync();

                _logger.LogInformation("Created RecycleBin configuration with default path: {Path}", defaultPath);
                return defaultPath;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to get RecycleBin path from configuration, using temporary fallback");
                // Fallback to config directory + recycleBin
                var configDir = _configService.GetConfigDirectory();
                return Path.Combine(configDir, "recycleBin");
            }
        }
    }
}