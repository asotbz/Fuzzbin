using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Core.Specifications;
using Fuzzbin.Core.Specifications.DownloadQueue;
using Fuzzbin.Services;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;
using Microsoft.Extensions.Logging;
using Moq;
using Xunit;
using FluentAssertions;
using DownloadStatusEnum = Fuzzbin.Core.Entities.DownloadStatus;

namespace Fuzzbin.Tests.Services
{
    /// <summary>
    /// Test suite for Download Queue Reliability features.
    /// Tests cover:
    /// - Delete operations (soft delete with IsDeleted flag)
    /// - Restart logic (status reset and re-queuing)
    /// - Clear queue operations (by status)
    /// - Duplicate URL detection (case-insensitive)
    /// </summary>
    public class DownloadQueueReliabilityTests
    {
        private readonly Mock<IUnitOfWork> _mockUnitOfWork;
        private readonly Mock<ILogger<DownloadQueueService>> _mockLogger;
        private readonly Mock<IDownloadTaskQueue> _mockTaskQueue;
        private readonly Mock<IDownloadSettingsProvider> _mockSettingsProvider;
        private readonly Mock<IActivityLogService> _mockActivityLogService;
        private readonly Mock<IRepository<DownloadQueueItem>> _mockRepository;
        private readonly DownloadQueueService _service;

        public DownloadQueueReliabilityTests()
        {
            _mockUnitOfWork = new Mock<IUnitOfWork>();
            _mockLogger = new Mock<ILogger<DownloadQueueService>>();
            _mockTaskQueue = new Mock<IDownloadTaskQueue>();
            _mockSettingsProvider = new Mock<IDownloadSettingsProvider>();
            _mockActivityLogService = new Mock<IActivityLogService>();
            _mockRepository = new Mock<IRepository<DownloadQueueItem>>();

            _mockUnitOfWork.Setup(x => x.DownloadQueueItems).Returns(_mockRepository.Object);

            _service = new DownloadQueueService(
                _mockUnitOfWork.Object,
                _mockLogger.Object,
                _mockTaskQueue.Object,
                _mockSettingsProvider.Object,
                _mockActivityLogService.Object);
        }

        [Fact]
        public async Task RemoveFromQueueAsync_ShouldMarkItemAsDeleted()
        {
            // Arrange
            var queueId = Guid.NewGuid();
            var queueItem = new DownloadQueueItem
            {
                Id = queueId,
                Url = "https://example.com/video",
                Status = DownloadStatusEnum.Queued,
                IsDeleted = false
            };

            _mockRepository
                .Setup(x => x.FirstOrDefaultAsync(It.IsAny<ISpecification<DownloadQueueItem>>()))
                .ReturnsAsync(queueItem);

            // Act
            var result = await _service.RemoveFromQueueAsync(queueId);

            // Assert
            result.Should().BeTrue();
            queueItem.IsDeleted.Should().BeTrue();
            queueItem.DeletedDate.Should().NotBeNull();
            queueItem.DeletedDate.Should().BeCloseTo(DateTime.UtcNow, TimeSpan.FromSeconds(5));
            
            _mockRepository.Verify(x => x.UpdateAsync(queueItem), Times.Once);
            _mockUnitOfWork.Verify(x => x.SaveChangesAsync(), Times.Once);
        }

        [Fact]
        public async Task RemoveFromQueueAsync_ShouldNotRemoveDownloadingItem()
        {
            // Arrange
            var queueId = Guid.NewGuid();
            var queueItem = new DownloadQueueItem
            {
                Id = queueId,
                Url = "https://example.com/video",
                Status = DownloadStatusEnum.Downloading,
                IsDeleted = false
            };

            _mockRepository
                .Setup(x => x.FirstOrDefaultAsync(It.IsAny<ISpecification<DownloadQueueItem>>()))
                .ReturnsAsync(queueItem);

            // Act
            var result = await _service.RemoveFromQueueAsync(queueId);

            // Assert
            result.Should().BeFalse();
            queueItem.IsDeleted.Should().BeFalse();
            queueItem.DeletedDate.Should().BeNull();
            
            _mockRepository.Verify(x => x.UpdateAsync(It.IsAny<DownloadQueueItem>()), Times.Never);
            _mockUnitOfWork.Verify(x => x.SaveChangesAsync(), Times.Never);
        }

        [Fact]
        public async Task RetryDownloadAsync_ShouldResetFailedItemAndRequeue()
        {
            // Arrange
            var queueId = Guid.NewGuid();
            var queueItem = new DownloadQueueItem
            {
                Id = queueId,
                Url = "https://example.com/video",
                Status = DownloadStatusEnum.Failed,
                RetryCount = 0,
                ErrorMessage = "Download failed",
                StartedDate = DateTime.UtcNow.AddMinutes(-10),
                CompletedDate = DateTime.UtcNow.AddMinutes(-5),
                Progress = 50,
                DownloadSpeed = "1 MB/s",
                ETA = "5 minutes"
            };

            _mockRepository
                .Setup(x => x.FirstOrDefaultAsync(It.IsAny<ISpecification<DownloadQueueItem>>()))
                .ReturnsAsync(queueItem);

            // Act
            var result = await _service.RetryDownloadAsync(queueId);

            // Assert
            result.Should().BeTrue();
            queueItem.Status.Should().Be(DownloadStatusEnum.Queued);
            queueItem.RetryCount.Should().Be(1);
            queueItem.ErrorMessage.Should().BeNull();
            queueItem.StartedDate.Should().BeNull();
            queueItem.CompletedDate.Should().BeNull();
            queueItem.Progress.Should().Be(0);
            queueItem.DownloadSpeed.Should().BeNull();
            queueItem.ETA.Should().BeNull();
            
            _mockRepository.Verify(x => x.UpdateAsync(queueItem), Times.Once);
            _mockUnitOfWork.Verify(x => x.SaveChangesAsync(), Times.Once);
            _mockTaskQueue.Verify(x => x.QueueAsync(queueId, It.IsAny<CancellationToken>()), Times.Once);
        }

        [Fact]
        public async Task RetryAllFailedAsync_ShouldRetryMultipleFailedItems()
        {
            // Arrange
            var failedItems = new List<DownloadQueueItem>
            {
                new DownloadQueueItem
                {
                    Id = Guid.NewGuid(),
                    Url = "https://example.com/video1",
                    Status = DownloadStatusEnum.Failed,
                    RetryCount = 0,
                    ErrorMessage = "Error 1"
                },
                new DownloadQueueItem
                {
                    Id = Guid.NewGuid(),
                    Url = "https://example.com/video2",
                    Status = DownloadStatusEnum.Failed,
                    RetryCount = 1,
                    ErrorMessage = "Error 2"
                },
                new DownloadQueueItem
                {
                    Id = Guid.NewGuid(),
                    Url = "https://example.com/video3",
                    Status = DownloadStatusEnum.Failed,
                    RetryCount = 2,
                    ErrorMessage = "Error 3"
                }
            };

            _mockRepository
                .Setup(x => x.ListAsync(It.IsAny<ISpecification<DownloadQueueItem>>()))
                .ReturnsAsync(failedItems);

            // Act
            var count = await _service.RetryAllFailedAsync();

            // Assert
            count.Should().Be(3);
            
            foreach (var item in failedItems)
            {
                item.Status.Should().Be(DownloadStatusEnum.Queued);
                item.ErrorMessage.Should().BeNull();
                item.StartedDate.Should().BeNull();
                item.CompletedDate.Should().BeNull();
                item.Progress.Should().Be(0);
                item.DownloadSpeed.Should().BeNull();
                item.ETA.Should().BeNull();
            }
            
            failedItems[0].RetryCount.Should().Be(1);
            failedItems[1].RetryCount.Should().Be(2);
            failedItems[2].RetryCount.Should().Be(3);
            
            _mockRepository.Verify(x => x.UpdateAsync(It.IsAny<DownloadQueueItem>()), Times.Exactly(3));
            _mockUnitOfWork.Verify(x => x.SaveChangesAsync(), Times.Once);
            _mockTaskQueue.Verify(x => x.QueueAsync(It.IsAny<Guid>(), It.IsAny<CancellationToken>()), Times.Exactly(3));
        }

        [Fact]
        public async Task ClearQueueByStatusAsync_ShouldClearItemsByStatus()
        {
            // Arrange
            var completedItems = new List<DownloadQueueItem>
            {
                new DownloadQueueItem
                {
                    Id = Guid.NewGuid(),
                    Url = "https://example.com/video1",
                    Status = DownloadStatusEnum.Completed,
                    IsDeleted = false
                },
                new DownloadQueueItem
                {
                    Id = Guid.NewGuid(),
                    Url = "https://example.com/video2",
                    Status = DownloadStatusEnum.Completed,
                    IsDeleted = false
                }
            };

            _mockRepository
                .Setup(x => x.ListAsync(It.IsAny<ISpecification<DownloadQueueItem>>()))
                .ReturnsAsync(completedItems);

            // Act
            var count = await _service.ClearQueueByStatusAsync(DownloadStatusEnum.Completed);

            // Assert
            count.Should().Be(2);
            
            foreach (var item in completedItems)
            {
                item.IsDeleted.Should().BeTrue();
                item.DeletedDate.Should().NotBeNull();
                item.DeletedDate.Should().BeCloseTo(DateTime.UtcNow, TimeSpan.FromSeconds(5));
            }
            
            _mockRepository.Verify(x => x.UpdateAsync(It.IsAny<DownloadQueueItem>()), Times.Exactly(2));
            _mockUnitOfWork.Verify(x => x.SaveChangesAsync(), Times.Once);
        }

        [Fact]
        public async Task IsUrlAlreadyQueuedAsync_ShouldDetectDuplicates()
        {
            // Arrange
            var existingItems = new List<DownloadQueueItem>
            {
                new DownloadQueueItem
                {
                    Id = Guid.NewGuid(),
                    Url = "https://example.com/VIDEO",
                    Status = DownloadStatusEnum.Queued,
                    IsDeleted = false
                }
            };

            _mockRepository
                .Setup(x => x.GetAllAsync(It.IsAny<bool>()))
                .ReturnsAsync(existingItems);

            // Act - test with different case variations
            var result1 = await _service.IsUrlAlreadyQueuedAsync("https://example.com/video");
            var result2 = await _service.IsUrlAlreadyQueuedAsync("  https://example.com/VIDEO  ");
            var result3 = await _service.IsUrlAlreadyQueuedAsync("HTTPS://EXAMPLE.COM/VIDEO");
            var result4 = await _service.IsUrlAlreadyQueuedAsync("https://different.com/video");

            // Assert
            result1.Should().BeTrue("lowercase URL should match");
            result2.Should().BeTrue("trimmed URL should match");
            result3.Should().BeTrue("uppercase URL should match");
            result4.Should().BeFalse("different URL should not match");
        }

        [Fact]
        public async Task AddToQueueAsync_ShouldPreventDuplicates()
        {
            // Arrange
            var existingItems = new List<DownloadQueueItem>
            {
                new DownloadQueueItem
                {
                    Id = Guid.NewGuid(),
                    Url = "https://example.com/video",
                    Status = DownloadStatusEnum.Queued,
                    IsDeleted = false
                }
            };

            _mockRepository
                .Setup(x => x.GetAllAsync(It.IsAny<bool>()))
                .ReturnsAsync(existingItems);

            _mockSettingsProvider
                .Setup(x => x.GetOptions())
                .Returns(new DownloadWorkerOptions
                {
                    OutputDirectory = "/downloads",
                    Format = "mp4"
                });

            // Act & Assert
            var exception = await Assert.ThrowsAsync<InvalidOperationException>(
                async () => await _service.AddToQueueAsync("https://example.com/VIDEO", "/downloads", "mp4", 5));

            exception.Message.Should().Contain("already queued");
            
            _mockRepository.Verify(x => x.AddAsync(It.IsAny<DownloadQueueItem>()), Times.Never);
            _mockUnitOfWork.Verify(x => x.SaveChangesAsync(), Times.Never);
        }
    }
}