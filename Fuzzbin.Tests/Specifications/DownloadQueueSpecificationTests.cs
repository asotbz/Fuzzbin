using System;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Specifications.DownloadQueue;
using Fuzzbin.Data.Context;
using Fuzzbin.Data.Repositories;
using Xunit;

namespace Fuzzbin.Tests.Specifications;

public class DownloadQueueSpecificationTests
{
    [Fact]
    public async Task DownloadQueueRetrySpecification_FiltersAndOrders()
    {
        var options = new DbContextOptionsBuilder<ApplicationDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .Options;

        await using var context = new ApplicationDbContext(options);

        var eligible = new DownloadQueueItem
        {
            Title = "Eligible",
            Status = DownloadStatus.Failed,
            RetryCount = 1,
            UpdatedAt = DateTime.UtcNow.AddMinutes(-30),
            Priority = 2
        };

        var tooRecent = new DownloadQueueItem
        {
            Title = "TooRecent",
            Status = DownloadStatus.Downloading,
            RetryCount = 1,
            UpdatedAt = DateTime.UtcNow.AddMinutes(-2),
            Priority = 1
        };

        var tooManyRetries = new DownloadQueueItem
        {
            Title = "TooManyRetries",
            Status = DownloadStatus.Failed,
            RetryCount = 5,
            UpdatedAt = DateTime.UtcNow.AddMinutes(-40),
            Priority = 1
        };

        var wrongStatus = new DownloadQueueItem
        {
            Title = "Completed",
            Status = DownloadStatus.Completed,
            RetryCount = 0,
            UpdatedAt = DateTime.UtcNow.AddMinutes(-50),
            Priority = 0
        };

        context.DownloadQueueItems.AddRange(eligible, tooRecent, tooManyRetries, wrongStatus);
        await context.SaveChangesAsync();
        context.ChangeTracker.Clear();

        var repository = new Repository<DownloadQueueItem>(context);
        // Advance the reference time to bypass the automatic UpdatedAt timestamp applied during SaveChanges.
        var referenceTime = DateTime.UtcNow.AddMinutes(11);
        var specification = new DownloadQueueRetrySpecification(TimeSpan.FromMinutes(10), maxRetries: 3, currentUtc: referenceTime);

        var results = await repository.ListAsync(specification);

        Assert.Single(results);
        Assert.Equal(eligible.Id, results[0].Id);
        Assert.Equal(EntityState.Unchanged, context.Entry(results[0]).State); // tracking enabled
        Assert.True(results[0].UpdatedAt <= referenceTime.Subtract(TimeSpan.FromMinutes(10)) + TimeSpan.FromMinutes(1));
    }
}
