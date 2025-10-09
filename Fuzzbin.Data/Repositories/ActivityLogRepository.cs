using Microsoft.EntityFrameworkCore;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;

namespace Fuzzbin.Data.Repositories
{
    public class ActivityLogRepository : IActivityLogRepository
    {
        private readonly Context.ApplicationDbContext _context;

        public ActivityLogRepository(Context.ApplicationDbContext context)
        {
            _context = context;
        }

        public async Task<ActivityLog> AddAsync(ActivityLog log)
        {
            _context.ActivityLogs.Add(log);
            await _context.SaveChangesAsync();
            return log;
        }

        public async Task<IEnumerable<ActivityLog>> GetRecentAsync(int count = 100)
        {
            return await _context.ActivityLogs
                .OrderByDescending(l => l.Timestamp)
                .Take(count)
                .ToListAsync();
        }

        public async Task<IEnumerable<ActivityLog>> GetByUserAsync(string userId, DateTime? startDate = null, DateTime? endDate = null)
        {
            var query = _context.ActivityLogs.Where(l => l.UserId == userId);

            if (startDate.HasValue)
                query = query.Where(l => l.Timestamp >= startDate.Value);

            if (endDate.HasValue)
                query = query.Where(l => l.Timestamp <= endDate.Value);

            return await query
                .OrderByDescending(l => l.Timestamp)
                .ToListAsync();
        }

        public async Task<IEnumerable<ActivityLog>> GetByCategoryAsync(string category, DateTime? startDate = null, DateTime? endDate = null)
        {
            var query = _context.ActivityLogs.Where(l => l.Category == category);

            if (startDate.HasValue)
                query = query.Where(l => l.Timestamp >= startDate.Value);

            if (endDate.HasValue)
                query = query.Where(l => l.Timestamp <= endDate.Value);

            return await query
                .OrderByDescending(l => l.Timestamp)
                .ToListAsync();
        }

        public async Task<IEnumerable<ActivityLog>> GetByEntityAsync(string entityType, string entityId)
        {
            return await _context.ActivityLogs
                .Where(l => l.EntityType == entityType && l.EntityId == entityId)
                .OrderByDescending(l => l.Timestamp)
                .ToListAsync();
        }

        public async Task<IEnumerable<ActivityLog>> SearchAsync(
            string? searchTerm = null,
            string? category = null,
            string? action = null,
            string? userId = null,
            DateTime? startDate = null,
            DateTime? endDate = null,
            bool? isSuccess = null,
            int skip = 0,
            int take = 100)
        {
            var query = _context.ActivityLogs.AsQueryable();

            if (!string.IsNullOrWhiteSpace(searchTerm))
            {
                query = query.Where(l => 
                    l.Action.Contains(searchTerm) ||
                    l.Details != null && l.Details.Contains(searchTerm) ||
                    l.EntityName != null && l.EntityName.Contains(searchTerm) ||
                    l.Username.Contains(searchTerm));
            }

            if (!string.IsNullOrWhiteSpace(category))
                query = query.Where(l => l.Category == category);

            if (!string.IsNullOrWhiteSpace(action))
                query = query.Where(l => l.Action == action);

            if (!string.IsNullOrWhiteSpace(userId))
                query = query.Where(l => l.UserId == userId);

            if (startDate.HasValue)
                query = query.Where(l => l.Timestamp >= startDate.Value);

            if (endDate.HasValue)
                query = query.Where(l => l.Timestamp <= endDate.Value);

            if (isSuccess.HasValue)
                query = query.Where(l => l.IsSuccess == isSuccess.Value);

            return await query
                .OrderByDescending(l => l.Timestamp)
                .Skip(skip)
                .Take(take)
                .ToListAsync();
        }

        public async Task<int> GetCountAsync(
            string? category = null,
            string? action = null,
            string? userId = null,
            DateTime? startDate = null,
            DateTime? endDate = null,
            bool? isSuccess = null)
        {
            var query = _context.ActivityLogs.AsQueryable();

            if (!string.IsNullOrWhiteSpace(category))
                query = query.Where(l => l.Category == category);

            if (!string.IsNullOrWhiteSpace(action))
                query = query.Where(l => l.Action == action);

            if (!string.IsNullOrWhiteSpace(userId))
                query = query.Where(l => l.UserId == userId);

            if (startDate.HasValue)
                query = query.Where(l => l.Timestamp >= startDate.Value);

            if (endDate.HasValue)
                query = query.Where(l => l.Timestamp <= endDate.Value);

            if (isSuccess.HasValue)
                query = query.Where(l => l.IsSuccess == isSuccess.Value);

            return await query.CountAsync();
        }

        public async Task<Dictionary<string, int>> GetCategorySummaryAsync(DateTime? startDate = null, DateTime? endDate = null)
        {
            var query = _context.ActivityLogs.AsQueryable();

            if (startDate.HasValue)
                query = query.Where(l => l.Timestamp >= startDate.Value);

            if (endDate.HasValue)
                query = query.Where(l => l.Timestamp <= endDate.Value);

            return await query
                .GroupBy(l => l.Category)
                .Select(g => new { Category = g.Key, Count = g.Count() })
                .ToDictionaryAsync(x => x.Category, x => x.Count);
        }

        public async Task<Dictionary<string, int>> GetActionSummaryAsync(DateTime? startDate = null, DateTime? endDate = null)
        {
            var query = _context.ActivityLogs.AsQueryable();

            if (startDate.HasValue)
                query = query.Where(l => l.Timestamp >= startDate.Value);

            if (endDate.HasValue)
                query = query.Where(l => l.Timestamp <= endDate.Value);

            return await query
                .GroupBy(l => l.Action)
                .Select(g => new { Action = g.Key, Count = g.Count() })
                .ToDictionaryAsync(x => x.Action, x => x.Count);
        }

        public async Task<Dictionary<DateTime, int>> GetDailyActivityAsync(int days = 30)
        {
            var startDate = DateTime.UtcNow.Date.AddDays(-days);

            var data = await _context.ActivityLogs
                .Where(l => l.Timestamp >= startDate)
                .GroupBy(l => l.Timestamp.Date)
                .Select(g => new { Date = g.Key, Count = g.Count() })
                .OrderBy(x => x.Date)
                .ToListAsync();

            return data.ToDictionary(x => x.Date, x => x.Count);
        }

        public async Task ClearOldLogsAsync(int daysToKeep = 90)
        {
            var cutoffDate = DateTime.UtcNow.AddDays(-daysToKeep);
            
            await _context.ActivityLogs
                .Where(l => l.Timestamp < cutoffDate)
                .ExecuteDeleteAsync();
        }

        public async Task<ActivityLog?> GetByIdAsync(int id)
        {
            return await _context.ActivityLogs.FindAsync(id);
        }

        public async Task DeleteAsync(int id)
        {
            var log = await GetByIdAsync(id);
            if (log != null)
            {
                _context.ActivityLogs.Remove(log);
                await _context.SaveChangesAsync();
            }
        }
    }
}