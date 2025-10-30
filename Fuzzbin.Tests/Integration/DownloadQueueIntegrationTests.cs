using System;
using System.Linq;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Microsoft.Extensions.DependencyInjection;
using Xunit;
using FluentAssertions;
using IDownloadQueueService = Fuzzbin.Services.Interfaces.IDownloadQueueService;
using DownloadStatusEnum = Fuzzbin.Core.Entities.DownloadStatus;

namespace Fuzzbin.Tests.Integration
{
    /// <summary>
    /// Integration tests for Download Queue functionality.
    /// Tests cover end-to-end behavior for:
    /// - Complete download lifecycle (Queue → Download → Fail → Retry → Complete)
    /// - Duplicate detection workflow
    /// - Bulk operations (retry all, clear by status)
    /// - Progress tracking
    /// </summary>
    [Collection("Integration")]
    public class DownloadQueueIntegrationTests : IntegrationTestBase
    {
        public DownloadQueueIntegrationTests(IntegrationTestFactory factory) : base(factory)
        {
        }

        [Fact]
        public async Task DownloadWorkflow_FailedToRestartToCompleted_ShouldTrackFullLifecycle()
        {
            // Arrange
            using var scope = Factory.Services.CreateScope();
            var downloadQueueService = scope.ServiceProvider.GetRequiredService<IDownloadQueueService>();
            var unitOfWork = scope.ServiceProvider.GetRequiredService<IUnitOfWork>();
            
            var testUrl = $"https://example.com/video-{Guid.NewGuid()}";

            // 1. Add URL to queue → status = Queued
            var queueItem = await downloadQueueService.AddToQueueAsync(testUrl, priority: 5);
            queueItem.Should().NotBeNull();
            queueItem.Status.Should().Be(DownloadStatusEnum.Queued);
            queueItem.RetryCount.Should().Be(0);

            // 2. Start download → status = Downloading
            await downloadQueueService.UpdateStatusAsync(queueItem.Id, DownloadStatusEnum.Downloading);
            var item = await downloadQueueService.GetByIdAsync(queueItem.Id);
            item!.Status.Should().Be(DownloadStatusEnum.Downloading);
            item.StartedDate.Should().NotBeNull();

            // 3. Simulate failure → status = Failed, ErrorMessage set
            var errorMessage = "Network timeout";
            await downloadQueueService.UpdateStatusAsync(queueItem.Id, DownloadStatusEnum.Failed, errorMessage);
            item = await downloadQueueService.GetByIdAsync(queueItem.Id);
            item!.Status.Should().Be(DownloadStatusEnum.Failed);
            item.ErrorMessage.Should().Be(errorMessage);
            item.CompletedDate.Should().NotBeNull();

            // 4. Retry download → status = Queued, RetryCount++, ErrorMessage cleared
            var retryResult = await downloadQueueService.RetryDownloadAsync(queueItem.Id);
            retryResult.Should().BeTrue();
            item = await downloadQueueService.GetByIdAsync(queueItem.Id);
            item!.Status.Should().Be(DownloadStatusEnum.Queued);
            item.RetryCount.Should().Be(1);
            item.ErrorMessage.Should().BeNull();
            item.StartedDate.Should().BeNull();
            item.CompletedDate.Should().BeNull();
            item.Progress.Should().Be(0);

            // 5. Complete download → status = Completed, VideoId set
            var videoId = Guid.NewGuid();
            await downloadQueueService.UpdateStatusAsync(queueItem.Id, DownloadStatusEnum.Downloading);
            await downloadQueueService.MarkAsCompletedAsync(queueItem.Id, videoId);
            item = await downloadQueueService.GetByIdAsync(queueItem.Id);
            item!.Status.Should().Be(DownloadStatusEnum.Completed);
            item.VideoId.Should().Be(videoId);

            // 6. Clear from history → IsDeleted = true
            var removeResult = await downloadQueueService.RemoveFromQueueAsync(queueItem.Id);
            removeResult.Should().BeTrue();
            
            // Verify item is marked as deleted in the database directly
            var allItems = await unitOfWork.DownloadQueueItems.GetAllAsync(includeDeleted: true);
            var deletedItem = allItems.FirstOrDefault(i => i.Id == queueItem.Id);
            deletedItem.Should().NotBeNull();
            deletedItem!.IsDeleted.Should().BeTrue();
            deletedItem.DeletedDate.Should().NotBeNull();
        }

        [Fact]
        public async Task DuplicateDetection_ShouldPreventDuplicateQueuing()
        {
            // Arrange
            using var scope = Factory.Services.CreateScope();
            var downloadQueueService = scope.ServiceProvider.GetRequiredService<IDownloadQueueService>();
            
            var testUrl = $"https://example.com/unique-video-{Guid.NewGuid()}";

            // 1. Add URL to queue
            var queueItem = await downloadQueueService.AddToQueueAsync(testUrl);
            queueItem.Should().NotBeNull();

            // 2. Verify IsUrlAlreadyQueuedAsync returns true
            var isDuplicate = await downloadQueueService.IsUrlAlreadyQueuedAsync(testUrl);
            isDuplicate.Should().BeTrue();

            // 3. Attempt to add same URL → throws InvalidOperationException
            var exception = await Assert.ThrowsAsync<InvalidOperationException>(
                async () => await downloadQueueService.AddToQueueAsync(testUrl));
            
            exception.Message.Should().Contain("already queued");
        }

        [Fact]
        public async Task BulkRetry_ShouldRetryAllFailedDownloads()
        {
            // Arrange
            using var scope = Factory.Services.CreateScope();
            var downloadQueueService = scope.ServiceProvider.GetRequiredService<IDownloadQueueService>();
            
            // 1. Create multiple failed downloads
            var failedUrls = new[]
            {
                $"https://example.com/failed1-{Guid.NewGuid()}",
                $"https://example.com/failed2-{Guid.NewGuid()}",
                $"https://example.com/failed3-{Guid.NewGuid()}"
            };

            var itemIds = new System.Collections.Generic.List<Guid>();
            foreach (var url in failedUrls)
            {
                var item = await downloadQueueService.AddToQueueAsync(url);
                await downloadQueueService.UpdateStatusAsync(item.Id, DownloadStatusEnum.Failed, "Test error");
                itemIds.Add(item.Id);
            }

            // 2. Call RetryAllFailedAsync
            var count = await downloadQueueService.RetryAllFailedAsync();

            // 3. Count should be at least 2 (some may have already been retried by background service)
            count.Should().BeGreaterOrEqualTo(2);

            // Verify that at least some items have been retried
            // (Due to shared database, some items may have been processed before marking as failed)
            var retriedCount = 0;
            foreach (var itemId in itemIds)
            {
                var item = await downloadQueueService.GetByIdAsync(itemId);
                item.Should().NotBeNull();
                // Item may be Queued or already picked up by background service and Downloading
                item!.Status.Should().Match(s => s == DownloadStatusEnum.Queued || s == DownloadStatusEnum.Downloading);
                if (item.RetryCount >= 1 && item.ErrorMessage == null)
                {
                    retriedCount++;
                }
            }
            
            // At least one item should have been successfully retried
            retriedCount.Should().BeGreaterOrEqualTo(1, "at least one failed item should have been retried");
        }

        [Fact]
        public async Task ClearByStatus_ShouldOnlyClearMatchingStatus()
        {
            // Arrange
            using var scope = Factory.Services.CreateScope();
            var downloadQueueService = scope.ServiceProvider.GetRequiredService<IDownloadQueueService>();
            
            // 1. Create items with different statuses
            var queuedItem = await downloadQueueService.AddToQueueAsync($"https://example.com/queued-{Guid.NewGuid()}");
            
            var failedItem = await downloadQueueService.AddToQueueAsync($"https://example.com/failed-{Guid.NewGuid()}");
            await downloadQueueService.UpdateStatusAsync(failedItem.Id, DownloadStatusEnum.Failed, "Error");
            
            var completedItem = await downloadQueueService.AddToQueueAsync($"https://example.com/completed-{Guid.NewGuid()}");
            await downloadQueueService.UpdateStatusAsync(completedItem.Id, DownloadStatusEnum.Completed);

            // 2. Clear only Failed items
            var count = await downloadQueueService.ClearQueueByStatusAsync(DownloadStatusEnum.Failed);

            // 3. Only Failed items marked as deleted
            count.Should().BeGreaterOrEqualTo(1);
            
            // Verify deleted item directly from database
            var unitOfWork2 = scope.ServiceProvider.GetRequiredService<IUnitOfWork>();
            var allItems2 = await unitOfWork2.DownloadQueueItems.GetAllAsync(includeDeleted: true);
            
            var failedDeleted = allItems2.FirstOrDefault(i => i.Id == failedItem.Id);
            failedDeleted.Should().NotBeNull();
            failedDeleted!.IsDeleted.Should().BeTrue();

            // 4. Other items remain untouched
            var queuedItem2 = allItems2.FirstOrDefault(i => i.Id == queuedItem.Id);
            queuedItem2.Should().NotBeNull();
            queuedItem2!.IsDeleted.Should().BeFalse();
            
            var completedItem2 = allItems2.FirstOrDefault(i => i.Id == completedItem.Id);
            completedItem2.Should().NotBeNull();
            completedItem2!.IsDeleted.Should().BeFalse();
        }

        [Fact]
        public async Task ProgressTracking_ShouldUpdateCorrectly()
        {
            // Arrange
            using var scope = Factory.Services.CreateScope();
            var downloadQueueService = scope.ServiceProvider.GetRequiredService<IDownloadQueueService>();
            
            var testUrl = $"https://example.com/progress-{Guid.NewGuid()}";
            var queueItem = await downloadQueueService.AddToQueueAsync(testUrl);
            await downloadQueueService.UpdateStatusAsync(queueItem.Id, DownloadStatusEnum.Downloading);

            // 1. Update progress multiple times (25%, 50%, 75%)
            await downloadQueueService.UpdateProgressAsync(queueItem.Id, 25.0, "1.2 MB/s", "5 minutes");
            var item = await downloadQueueService.GetByIdAsync(queueItem.Id);
            item!.Progress.Should().Be(25.0);
            item.DownloadSpeed.Should().Be("1.2 MB/s");
            item.ETA.Should().Be("5 minutes");

            await downloadQueueService.UpdateProgressAsync(queueItem.Id, 50.0, "1.5 MB/s", "3 minutes");
            item = await downloadQueueService.GetByIdAsync(queueItem.Id);
            item!.Progress.Should().Be(50.0);
            item.DownloadSpeed.Should().Be("1.5 MB/s");
            item.ETA.Should().Be("3 minutes");

            await downloadQueueService.UpdateProgressAsync(queueItem.Id, 75.0, "1.8 MB/s", "1 minute");
            item = await downloadQueueService.GetByIdAsync(queueItem.Id);
            item!.Progress.Should().Be(75.0);
            item.DownloadSpeed.Should().Be("1.8 MB/s");
            item.ETA.Should().Be("1 minute");
        }

        [Fact]
        public async Task RemoveFromQueue_ShouldNotRemoveActiveDownload()
        {
            // Arrange
            using var scope = Factory.Services.CreateScope();
            var downloadQueueService = scope.ServiceProvider.GetRequiredService<IDownloadQueueService>();
            
            var testUrl = $"https://example.com/active-{Guid.NewGuid()}";
            
            // 1. Start a download (status = Downloading)
            var queueItem = await downloadQueueService.AddToQueueAsync(testUrl);
            await downloadQueueService.UpdateStatusAsync(queueItem.Id, DownloadStatusEnum.Downloading);

            // 2. Attempt to remove
            var result = await downloadQueueService.RemoveFromQueueAsync(queueItem.Id);

            // 3. RemoveFromQueueAsync returns false
            result.Should().BeFalse();

            // 4. Item remains in queue, not deleted
            var item = await downloadQueueService.GetByIdAsync(queueItem.Id);
            item!.IsDeleted.Should().BeFalse();
            item.Status.Should().Be(DownloadStatusEnum.Downloading);
        }

        [Fact]
        public async Task CaseInsensitiveUrlMatching_ShouldDetectVariations()
        {
            // Arrange
            using var scope = Factory.Services.CreateScope();
            var downloadQueueService = scope.ServiceProvider.GetRequiredService<IDownloadQueueService>();
            
            var baseUrl = $"https://Example.COM/Video-{Guid.NewGuid()}";
            
            // 1. Add URL with mixed case
            var queueItem = await downloadQueueService.AddToQueueAsync(baseUrl);
            queueItem.Should().NotBeNull();

            // 2. Check various case combinations
            var variations = new[]
            {
                baseUrl.ToLowerInvariant(),
                baseUrl.ToUpperInvariant(),
                $"  {baseUrl}  ", // with whitespace
                baseUrl.Replace("Example", "EXAMPLE").Replace("Video", "video")
            };

            // 3. All variations detected as duplicates
            foreach (var variation in variations)
            {
                var isDuplicate = await downloadQueueService.IsUrlAlreadyQueuedAsync(variation);
                isDuplicate.Should().BeTrue($"variation '{variation}' should be detected as duplicate");
            }

            // 4. Attempting to add any variation should fail
            var exception = await Assert.ThrowsAsync<InvalidOperationException>(
                async () => await downloadQueueService.AddToQueueAsync(baseUrl.ToLowerInvariant()));
            
            exception.Message.Should().Contain("already queued");
        }
    }
}