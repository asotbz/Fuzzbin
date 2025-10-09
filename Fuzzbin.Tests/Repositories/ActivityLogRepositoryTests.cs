using System;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Fuzzbin.Core.Entities;
using Fuzzbin.Data.Context;
using Fuzzbin.Data.Repositories;
using Xunit;

namespace Fuzzbin.Tests.Repositories;

public class ActivityLogRepositoryTests
{
    [Fact]
    public async Task AddAsync_PersistsLog()
    {
        await using var context = CreateContext();
        var repository = new ActivityLogRepository(context);

        var log = await repository.AddAsync(CreateLog());

        Assert.True(log.Id > 0);
        Assert.Equal(1, await context.ActivityLogs.CountAsync());
    }

    [Fact]
    public async Task GetRecentAsync_ReturnsMostRecentFirst()
    {
        await using var context = CreateContext();
        var repository = new ActivityLogRepository(context);

        var now = DateTime.UtcNow;
        await repository.AddAsync(CreateLog(timestamp: now.AddMinutes(-10), action: ActivityActions.Read));
        await repository.AddAsync(CreateLog(timestamp: now.AddMinutes(-5), action: ActivityActions.Update));
        await repository.AddAsync(CreateLog(timestamp: now, action: ActivityActions.Create));

        var recent = (await repository.GetRecentAsync(2)).ToList();

        Assert.Equal(2, recent.Count);
        Assert.True(recent[0].Timestamp > recent[1].Timestamp);
        Assert.Equal(ActivityActions.Create, recent[0].Action);
    }

    [Fact]
    public async Task GetByUserAsync_HonorsDateRange()
    {
        await using var context = CreateContext();
        var repository = new ActivityLogRepository(context);

        var now = DateTime.UtcNow;
        await repository.AddAsync(CreateLog(userId: "user", timestamp: now.AddDays(-2)));
        await repository.AddAsync(CreateLog(userId: "user", timestamp: now.AddDays(-1)));
        await repository.AddAsync(CreateLog(userId: "user", timestamp: now));
        await repository.AddAsync(CreateLog(userId: "other", timestamp: now));

        var results = (await repository.GetByUserAsync("user", now.AddDays(-1.5), now.AddHours(-12))).ToList();

        Assert.Single(results);
        Assert.True(results[0].Timestamp >= now.AddDays(-1.5));
        Assert.True(results[0].Timestamp <= now.AddHours(-12));
    }

    [Fact]
    public async Task SearchAsync_AppliesAllFilters()
    {
        await using var context = CreateContext();
        var repository = new ActivityLogRepository(context);
        var now = DateTime.UtcNow;

        await repository.AddAsync(CreateLog(
            userId: "alpha",
            category: ActivityCategories.Video,
            action: ActivityActions.Update,
            searchTerm: "queued",
            timestamp: now.AddHours(-2),
            isSuccess: true));

        await repository.AddAsync(CreateLog(
            userId: "alpha",
            category: ActivityCategories.Video,
            action: ActivityActions.Update,
            searchTerm: "queued",
            timestamp: now.AddHours(-1),
            isSuccess: false));

        await repository.AddAsync(CreateLog(
            userId: "beta",
            category: ActivityCategories.System,
            action: ActivityActions.Login,
            searchTerm: "other",
            timestamp: now,
            isSuccess: true));

        var results = (await repository.SearchAsync(
            searchTerm: "queued",
            category: ActivityCategories.Video,
            action: ActivityActions.Update,
            userId: "alpha",
            startDate: now.AddHours(-1.5),
            endDate: now,
            isSuccess: false,
            skip: 0,
            take: 10)).ToList();

        Assert.Single(results);
        Assert.False(results[0].IsSuccess);
        Assert.Equal("alpha", results[0].UserId);
    }

    [Fact]
    public async Task GetCountAsync_UsesSameFiltersAsSearch()
    {
        await using var context = CreateContext();
        var repository = new ActivityLogRepository(context);
        var now = DateTime.UtcNow;

        await repository.AddAsync(CreateLog(userId: "user", category: ActivityCategories.Video, action: ActivityActions.Update, timestamp: now));
        await repository.AddAsync(CreateLog(userId: "user", category: ActivityCategories.Video, action: ActivityActions.Update, timestamp: now.AddDays(-1)));
        await repository.AddAsync(CreateLog(userId: "user", category: ActivityCategories.System, action: ActivityActions.Update, timestamp: now));

        var count = await repository.GetCountAsync(
            category: ActivityCategories.Video,
            action: ActivityActions.Update,
            userId: "user",
            startDate: now.AddHours(-12),
            endDate: now.AddHours(1));

        Assert.Equal(1, count);
    }

    [Fact]
    public async Task Summaries_GroupByCategoryAndAction()
    {
        await using var context = CreateContext();
        var repository = new ActivityLogRepository(context);

        await repository.AddAsync(CreateLog(category: ActivityCategories.Video, action: ActivityActions.Update));
        await repository.AddAsync(CreateLog(category: ActivityCategories.Video, action: ActivityActions.Update));
        await repository.AddAsync(CreateLog(category: ActivityCategories.Video, action: ActivityActions.Play));
        await repository.AddAsync(CreateLog(category: ActivityCategories.System, action: ActivityActions.Login));

        var categorySummary = await repository.GetCategorySummaryAsync();
        var actionSummary = await repository.GetActionSummaryAsync();

        Assert.Equal(3, categorySummary[ActivityCategories.Video]);
        Assert.Equal(1, categorySummary[ActivityCategories.System]);
        Assert.Equal(2, actionSummary[ActivityActions.Update]);
        Assert.True(actionSummary.ContainsKey(ActivityActions.Play));
    }

    [Fact]
    public async Task GetDailyActivityAsync_AggregatesRecentDays()
    {
        await using var context = CreateContext();
        var repository = new ActivityLogRepository(context);
        var today = DateTime.UtcNow.Date;

        await repository.AddAsync(CreateLog(timestamp: today.AddDays(-1)));
        await repository.AddAsync(CreateLog(timestamp: today.AddDays(-1).AddHours(1)));
        await repository.AddAsync(CreateLog(timestamp: today));

        var daily = await repository.GetDailyActivityAsync(days: 2);

        Assert.Equal(2, daily.Count);
        Assert.Equal(2, daily[today.AddDays(-1)]);
        Assert.Equal(1, daily[today]);
    }

    [Fact]
    public async Task ClearOldLogsAsync_RemovesEntriesBeforeCutoff()
    {
        await using var connection = new SqliteConnection("Filename=:memory:");
        await connection.OpenAsync();

        var options = new DbContextOptionsBuilder<ApplicationDbContext>()
            .UseSqlite(connection)
            .Options;

        await using var context = new ApplicationDbContext(options);
        await context.Database.EnsureCreatedAsync();

        var repository = new ActivityLogRepository(context);
        var now = DateTime.UtcNow;

        await repository.AddAsync(CreateLog(timestamp: now.AddDays(-10)));
        await repository.AddAsync(CreateLog(timestamp: now.AddDays(-5)));
        await repository.AddAsync(CreateLog(timestamp: now));

        await repository.ClearOldLogsAsync(daysToKeep: 7);

        var remaining = await context.ActivityLogs.OrderBy(l => l.Timestamp).ToListAsync();
        Assert.Equal(2, remaining.Count);
        Assert.True(remaining[0].Timestamp >= now.AddDays(-7));
    }

    [Fact]
    public async Task DeleteAsync_RemovesLog()
    {
        await using var context = CreateContext();
        var repository = new ActivityLogRepository(context);

        var log = await repository.AddAsync(CreateLog());
        await repository.DeleteAsync(log.Id);

        Assert.Empty(await context.ActivityLogs.ToListAsync());
    }

    private static ActivityLog CreateLog(
        string userId = "user",
        string category = ActivityCategories.System,
        string action = ActivityActions.Update,
        string searchTerm = "detail",
        DateTime? timestamp = null,
        bool? isSuccess = null)
    {
        return new ActivityLog
        {
            Timestamp = timestamp ?? DateTime.UtcNow,
            UserId = userId,
            Username = userId,
            Action = action,
            Category = category,
            EntityType = "Entity",
            EntityId = "1",
            EntityName = "Name",
            Details = searchTerm,
            IsSuccess = isSuccess ?? true,
            IpAddress = "127.0.0.1",
            UserAgent = "Test",
            Duration = TimeSpan.FromMilliseconds(10)
        };
    }

    private static ApplicationDbContext CreateContext()
    {
        var options = new DbContextOptionsBuilder<ApplicationDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .Options;

        return new ApplicationDbContext(options);
    }
}
