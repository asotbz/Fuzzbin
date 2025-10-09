using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Logging;

namespace Fuzzbin.Services
{
    public interface IActivityLogService
    {
        Task<ActivityLog> LogAsync(string category, string action, string? entityType = null, string? entityId = null, string? entityName = null, string? details = null, string? oldValue = null, string? newValue = null);
        Task LogSuccessAsync(string category, string action, string? entityType = null, string? entityId = null, string? entityName = null, string? details = null);
        Task LogErrorAsync(string category, string action, string? error, string? entityType = null, string? entityId = null, string? entityName = null, string? details = null);
        Task<IEnumerable<ActivityLog>> GetRecentLogsAsync(int count = 100);
        Task<IEnumerable<ActivityLog>> GetUserLogsAsync(string userId, DateTime? startDate = null, DateTime? endDate = null);
        Task<IEnumerable<ActivityLog>> SearchLogsAsync(
            string? searchTerm = null,
            string? category = null,
            string? action = null,
            string? userId = null,
            DateTime? startDate = null,
            DateTime? endDate = null,
            bool? isSuccess = null,
            int skip = 0,
            int take = 100);
        Task<Dictionary<string, int>> GetCategorySummaryAsync(DateTime? startDate = null, DateTime? endDate = null);
        Task<Dictionary<string, int>> GetActionSummaryAsync(DateTime? startDate = null, DateTime? endDate = null);
        Task<Dictionary<DateTime, int>> GetDailyActivityAsync(int days = 30);
        Task<int> GetLogCountAsync(
            string? category = null,
            string? action = null,
            string? userId = null,
            DateTime? startDate = null,
            DateTime? endDate = null,
            bool? isSuccess = null);
        Task ClearOldLogsAsync(int daysToKeep = 90);
    }

    public class ActivityLogService : IActivityLogService
    {
        private readonly IActivityLogRepository _repository;
        private readonly IHttpContextAccessor _httpContextAccessor;
        private readonly ILogger<ActivityLogService> _logger;

        public ActivityLogService(
            IActivityLogRepository repository,
            IHttpContextAccessor httpContextAccessor,
            ILogger<ActivityLogService> logger)
        {
            _repository = repository;
            _httpContextAccessor = httpContextAccessor;
            _logger = logger;
        }

        public async Task<ActivityLog> LogAsync(
            string category,
            string action,
            string? entityType = null,
            string? entityId = null,
            string? entityName = null,
            string? details = null,
            string? oldValue = null,
            string? newValue = null)
        {
            try
            {
                var httpContext = _httpContextAccessor.HttpContext;
                var userId = httpContext?.User?.Identity?.Name ?? "System";
                var username = httpContext?.User?.Identity?.Name ?? "System";
                var ipAddress = GetClientIpAddress(httpContext);
                var userAgent = httpContext?.Request?.Headers["User-Agent"].ToString() ?? "Unknown";

                var log = new ActivityLog
                {
                    Timestamp = DateTime.UtcNow,
                    UserId = userId,
                    Username = username,
                    Action = action,
                    Category = category,
                    EntityType = entityType ?? string.Empty,
                    EntityId = entityId,
                    EntityName = entityName,
                    Details = details,
                    OldValue = oldValue,
                    NewValue = newValue,
                    IpAddress = ipAddress,
                    UserAgent = userAgent,
                    IsSuccess = true
                };

                await _repository.AddAsync(log);
                return log;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to log activity: {Action} - {Category}", action, category);
                throw;
            }
        }

        public async Task LogSuccessAsync(
            string category,
            string action,
            string? entityType = null,
            string? entityId = null,
            string? entityName = null,
            string? details = null)
        {
            await LogAsync(category, action, entityType, entityId, entityName, details);
        }

        public async Task LogErrorAsync(
            string category,
            string action,
            string? error,
            string? entityType = null,
            string? entityId = null,
            string? entityName = null,
            string? details = null)
        {
            try
            {
                var httpContext = _httpContextAccessor.HttpContext;
                var userId = httpContext?.User?.Identity?.Name ?? "System";
                var username = httpContext?.User?.Identity?.Name ?? "System";
                var ipAddress = GetClientIpAddress(httpContext);
                var userAgent = httpContext?.Request?.Headers["User-Agent"].ToString() ?? "Unknown";

                var log = new ActivityLog
                {
                    Timestamp = DateTime.UtcNow,
                    UserId = userId,
                    Username = username,
                    Action = action,
                    Category = category,
                    EntityType = entityType ?? string.Empty,
                    EntityId = entityId,
                    EntityName = entityName,
                    IpAddress = ipAddress,
                    UserAgent = userAgent,
                    IsSuccess = false,
                    ErrorMessage = error
                };

                await _repository.AddAsync(log);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to log error activity: {Action} - {Category} - {Error}", action, category, error);
            }
        }

        public async Task<IEnumerable<ActivityLog>> GetRecentLogsAsync(int count = 100)
        {
            return await _repository.GetRecentAsync(count);
        }

        public async Task<IEnumerable<ActivityLog>> GetUserLogsAsync(string userId, DateTime? startDate = null, DateTime? endDate = null)
        {
            return await _repository.GetByUserAsync(userId, startDate, endDate);
        }

        public async Task<IEnumerable<ActivityLog>> SearchLogsAsync(
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
            return await _repository.SearchAsync(
                searchTerm, category, action, userId,
                startDate, endDate, isSuccess, skip, take);
        }

        public async Task<Dictionary<string, int>> GetCategorySummaryAsync(DateTime? startDate = null, DateTime? endDate = null)
        {
            return await _repository.GetCategorySummaryAsync(startDate, endDate);
        }

        public async Task<Dictionary<string, int>> GetActionSummaryAsync(DateTime? startDate = null, DateTime? endDate = null)
        {
            return await _repository.GetActionSummaryAsync(startDate, endDate);
        }

        public async Task<Dictionary<DateTime, int>> GetDailyActivityAsync(int days = 30)
        {
            return await _repository.GetDailyActivityAsync(days);
        }

        public async Task<int> GetLogCountAsync(
            string? category = null,
            string? action = null,
            string? userId = null,
            DateTime? startDate = null,
            DateTime? endDate = null,
            bool? isSuccess = null)
        {
            return await _repository.GetCountAsync(category, action, userId, startDate, endDate, isSuccess);
        }

        public async Task ClearOldLogsAsync(int daysToKeep = 90)
        {
            try
            {
                await _repository.ClearOldLogsAsync(daysToKeep);
                _logger.LogInformation("Cleaned up activity logs older than {Days} days", daysToKeep);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Failed to cleanup old activity logs");
            }
        }

        private string GetClientIpAddress(HttpContext? context)
        {
            if (context == null)
                return "Unknown";

            string? ipAddress = null;

            // Check for forwarded IP (proxy/load balancer)
            if (context.Request.Headers.ContainsKey("X-Forwarded-For"))
            {
                ipAddress = context.Request.Headers["X-Forwarded-For"].ToString().Split(',')[0].Trim();
            }

            // Check for real IP header
            if (string.IsNullOrWhiteSpace(ipAddress) && context.Request.Headers.ContainsKey("X-Real-IP"))
            {
                ipAddress = context.Request.Headers["X-Real-IP"].ToString();
            }

            // Fall back to connection remote IP
            if (string.IsNullOrWhiteSpace(ipAddress))
            {
                ipAddress = context.Connection.RemoteIpAddress?.ToString();
            }

            return ipAddress ?? "Unknown";
        }
    }
}