using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;

namespace Fuzzbin.Core.Interfaces
{
    public interface IActivityLogRepository
    {
        Task<ActivityLog> AddAsync(ActivityLog log);
        Task<ActivityLog?> GetByIdAsync(int id);
        Task<IEnumerable<ActivityLog>> GetRecentAsync(int count = 100);
        Task<IEnumerable<ActivityLog>> GetByUserAsync(string userId, DateTime? startDate = null, DateTime? endDate = null);
        Task<IEnumerable<ActivityLog>> GetByCategoryAsync(string category, DateTime? startDate = null, DateTime? endDate = null);
        Task<IEnumerable<ActivityLog>> GetByEntityAsync(string entityType, string entityId);
        Task<IEnumerable<ActivityLog>> SearchAsync(
            string? searchTerm = null,
            string? category = null,
            string? action = null,
            string? userId = null,
            DateTime? startDate = null,
            DateTime? endDate = null,
            bool? isSuccess = null,
            int skip = 0,
            int take = 100);
        Task<int> GetCountAsync(
            string? category = null,
            string? action = null,
            string? userId = null,
            DateTime? startDate = null,
            DateTime? endDate = null,
            bool? isSuccess = null);
        Task<Dictionary<string, int>> GetCategorySummaryAsync(DateTime? startDate = null, DateTime? endDate = null);
        Task<Dictionary<string, int>> GetActionSummaryAsync(DateTime? startDate = null, DateTime? endDate = null);
        Task<Dictionary<DateTime, int>> GetDailyActivityAsync(int days = 30);
        Task ClearOldLogsAsync(int daysToKeep = 90);
        Task DeleteAsync(int id);
    }
}