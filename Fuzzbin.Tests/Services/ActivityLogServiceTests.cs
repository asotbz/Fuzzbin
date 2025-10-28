using System;
using System.Security.Claims;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;
using Fuzzbin.Data.Context;
using Fuzzbin.Data.Repositories;
using Fuzzbin.Services;
using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;
using Xunit;

namespace Fuzzbin.Tests.Services;

public class ActivityLogServiceTests
{
    [Fact]
    public async Task LogAsync_WithHttpContext_PersistsEntry()
    {
        var options = new DbContextOptionsBuilder<ApplicationDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .Options;

        await using var context = new ApplicationDbContext(options);
        var repository = new ActivityLogRepository(context);
        var httpContextAccessor = new HttpContextAccessor();
        var httpContext = new DefaultHttpContext();
        httpContext.User = new ClaimsPrincipal(new ClaimsIdentity(
            new[] { new Claim(ClaimTypes.Name, "qa.tester") },
            "TestAuth"));
        httpContextAccessor.HttpContext = httpContext;

        var service = new ActivityLogService(
            repository,
            httpContextAccessor,
            NullLogger<ActivityLogService>.Instance);

        await service.LogAsync(
            ActivityCategories.Video,
            ActivityActions.Create,
            entityType: nameof(Video),
            entityId: "video-123",
            entityName: "Sample Video",
            details: "Created sample video");

        var log = await context.ActivityLogs.SingleAsync();

        Assert.Equal(ActivityCategories.Video, log.Category);
        Assert.Equal(ActivityActions.Create, log.Action);
        Assert.Equal("video-123", log.EntityId);
        Assert.Equal("Sample Video", log.EntityName);
        Assert.Equal("qa.tester", log.UserId);
        Assert.True(log.IsSuccess);
        Assert.Null(log.ErrorMessage);
    }

    [Fact]
    public async Task LogErrorAsync_PersistsFailureEntry()
    {
        var options = new DbContextOptionsBuilder<ApplicationDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .Options;

        await using var context = new ApplicationDbContext(options);
        var repository = new ActivityLogRepository(context);
        var httpContextAccessor = new HttpContextAccessor();

        var service = new ActivityLogService(
            repository,
            httpContextAccessor,
            NullLogger<ActivityLogService>.Instance);

        await service.LogErrorAsync(
            ActivityCategories.Video,
            ActivityActions.Delete,
            error: "Unexpected failure",
            entityType: nameof(Video),
            entityId: "video-456",
            entityName: "Failing Video",
            details: "Deletion threw an exception");

        var log = await context.ActivityLogs.SingleAsync();

        Assert.Equal(ActivityCategories.Video, log.Category);
        Assert.Equal(ActivityActions.Delete, log.Action);
        Assert.Equal("video-456", log.EntityId);
        Assert.Equal("Failing Video", log.EntityName);
        Assert.False(log.IsSuccess);
        Assert.Equal("Unexpected failure", log.ErrorMessage);
        Assert.Equal("System", log.UserId);
    }
}
