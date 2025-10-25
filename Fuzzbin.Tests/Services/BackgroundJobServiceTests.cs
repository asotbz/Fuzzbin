using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Data.Context;
using Fuzzbin.Data.Repositories;
using Fuzzbin.Services;
using Xunit;

namespace Fuzzbin.Tests.Services;

public class BackgroundJobServiceTests
{
    private static (ApplicationDbContext Context, IUnitOfWork Uow, BackgroundJobService Service) CreateService()
    {
        var options = new DbContextOptionsBuilder<ApplicationDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .ConfigureWarnings(w => w.Ignore(Microsoft.EntityFrameworkCore.Diagnostics.InMemoryEventId.TransactionIgnoredWarning))
            .Options;

        var context = new ApplicationDbContext(options);
        var uow = new UnitOfWork(context);
        var service = new BackgroundJobService(uow, NullLogger<BackgroundJobService>.Instance);
        return (context, uow, service);
    }

    [Fact]
    public async Task TryEnqueueSingletonJobAsync_PreventsDuplicateActiveJobs()
    {
        var (context, uow, service) = CreateService();
        await using var _ = context;

        // First enqueue should create a new pending job
        var (created1, job1) = await service.TryEnqueueSingletonJobAsync(BackgroundJobType.RefreshMetadata);
        Assert.True(created1);
        Assert.NotNull(job1);
        Assert.Equal(BackgroundJobStatus.Pending, job1.Status);

        // Second enqueue should return existing job (still pending)
        var (created2, job2) = await service.TryEnqueueSingletonJobAsync(BackgroundJobType.RefreshMetadata);
        Assert.False(created2);
        Assert.Equal(job1.Id, job2.Id);

        // Mark first job Running, ensure still blocks another enqueue
        job1.Status = BackgroundJobStatus.Running;
        await uow.BackgroundJobs.UpdateAsync(job1);
        await uow.SaveChangesAsync();

        var (created3, job3) = await service.TryEnqueueSingletonJobAsync(BackgroundJobType.RefreshMetadata);
        Assert.False(created3);
        Assert.Equal(job1.Id, job3.Id);

        // Complete job; subsequent enqueue should create a new one
        job1.Status = BackgroundJobStatus.Completed;
        job1.CompletedAt = DateTime.UtcNow;
        await uow.BackgroundJobs.UpdateAsync(job1);
        await uow.SaveChangesAsync();

        var (created4, job4) = await service.TryEnqueueSingletonJobAsync(BackgroundJobType.RefreshMetadata);
        Assert.True(created4);
        Assert.NotEqual(job1.Id, job4.Id);
    }

    [Fact]
    public async Task CancelJobAsync_SetsCancellationRequested()
    {
        var (context, _, service) = CreateService();
        await using var _ = context;

        var job = await service.CreateJobAsync(BackgroundJobType.OrganizeFiles);
        Assert.False(job.CancellationRequested);

        await service.CancelJobAsync(job.Id);

        var reloaded = await service.GetJobAsync(job.Id);
        Assert.NotNull(reloaded);
        Assert.True(reloaded!.CancellationRequested);
        Assert.Equal(BackgroundJobStatus.Pending, reloaded.Status);
    }

    [Fact]
    public async Task CleanupOldJobsAsync_RetainsMostRecent200TerminalJobs()
    {
        var (context, uow, service) = CreateService();
        await using var _ = context;

        // Create 250 completed jobs with ascending CreatedAt / CompletedAt
        var baseTime = DateTime.UtcNow.AddDays(-5);
        var jobs = new List<BackgroundJob>();
        for (int i = 0; i < 250; i++)
        {
            var job = new BackgroundJob
            {
                Type = BackgroundJobType.RefreshMetadata,
                Status = BackgroundJobStatus.Completed,
                Progress = 100,
                CreatedAt = baseTime.AddMinutes(i),
                StartedAt = baseTime.AddMinutes(i).AddSeconds(5),
                CompletedAt = baseTime.AddMinutes(i).AddSeconds(30),
                ResultJson = "{}"
            };
            await uow.BackgroundJobs.AddAsync(job);
            jobs.Add(job);
        }

        await uow.SaveChangesAsync();

        // Invoke cleanup (olderThan parameter ignored by current retention implementation)
        await service.CleanupOldJobsAsync(TimeSpan.FromDays(30));

        // Query active (IsActive) jobs still present
        var remaining = uow.BackgroundJobs
            .GetQueryable()
            .Where(j => j.Status == BackgroundJobStatus.Completed)
            .ToList();

        Assert.True(remaining.Count <= 200, $"Expected at most 200 retained jobs, found {remaining.Count}");

        // Ensure the newest jobs (latest CompletedAt) are retained
        var newestCompletedTimes = jobs
            .OrderByDescending(j => j.CompletedAt)
            .Take(200)
            .Select(j => j.CompletedAt)
            .ToHashSet();

        var remainingTimes = remaining.Select(r => r.CompletedAt).ToHashSet();
        Assert.True(newestCompletedTimes.SetEquals(remainingTimes),
            "Retention did not preserve the most recent 200 terminal jobs.");
    }
}