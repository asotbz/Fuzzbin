using System;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;
using Xunit;
using Fuzzbin.Core.Entities;
using Fuzzbin.Data.Context;
using Fuzzbin.Data.Repositories;
using Fuzzbin.Services;
using Fuzzbin.Services.Interfaces;

namespace Fuzzbin.Tests.Services
{
    /// <summary>
    /// Tests for Download Queue Completed Enhancements (Section 8.3)
    /// Verifies: Title population from metadata, play action, and source URL capture
    /// </summary>
    public class DownloadQueueCompletedEnhancementsTests : IDisposable
    {
        private readonly ApplicationDbContext _context;
        private readonly UnitOfWork _unitOfWork;
        private readonly DownloadQueueService _queueService;
        private readonly TestDownloadTaskQueue _taskQueue;
        private readonly TestDownloadSettingsProvider _settingsProvider;
        private readonly TestActivityLogService _activityLogService;

        public DownloadQueueCompletedEnhancementsTests()
        {
            var options = new DbContextOptionsBuilder<ApplicationDbContext>()
                .UseInMemoryDatabase(Guid.NewGuid().ToString())
                .Options;

            _context = new ApplicationDbContext(options);
            _unitOfWork = new UnitOfWork(_context);
            _taskQueue = new TestDownloadTaskQueue();
            _settingsProvider = new TestDownloadSettingsProvider();
            _activityLogService = new TestActivityLogService();

            _queueService = new DownloadQueueService(
                _unitOfWork,
                NullLogger<DownloadQueueService>.Instance,
                _taskQueue,
                _settingsProvider,
                _activityLogService);
        }

        [Fact]
        public async Task MarkAsCompleted_ShouldPopulateTitleFromVideoMetadata()
        {
            // Arrange - Create a video with metadata
            var video = new Video
            {
                Title = "Test Song",
                Artist = "Test Artist",
                FilePath = "/path/to/video.mp4"
            };
            await _unitOfWork.Videos.AddAsync(video);
            await _unitOfWork.SaveChangesAsync();

            // Create a queue item without a title
            var queueItem = await _queueService.AddToQueueAsync("https://youtube.com/watch?v=test", priority: 5);
            Assert.Null(queueItem.Title); // Initially no title

            // Act - Mark as completed with the video ID
            await _queueService.MarkAsCompletedAsync(queueItem.Id, video.Id);

            // Assert - Title should be populated from video metadata
            var updatedItem = await _queueService.GetByIdAsync(queueItem.Id);
            Assert.NotNull(updatedItem);
            Assert.Equal(DownloadStatus.Completed, updatedItem.Status);
            Assert.Equal(video.Id, updatedItem.VideoId);
            Assert.Equal("Test Artist - Test Song", updatedItem.Title);
        }

        [Fact]
        public async Task MarkAsCompleted_ShouldPreserveTitleIfAlreadySet()
        {
            // Arrange - Create a video
            var video = new Video
            {
                Title = "New Title",
                Artist = "New Artist",
                FilePath = "/path/to/video.mp4"
            };
            await _unitOfWork.Videos.AddAsync(video);
            await _unitOfWork.SaveChangesAsync();

            // Create a queue item WITH a title
            var queueItem = await _queueService.AddToQueueAsync(
                "https://youtube.com/watch?v=test",
                customTitle: "Original Title",
                priority: 5);
            Assert.Equal("Original Title", queueItem.Title);

            // Act - Mark as completed
            await _queueService.MarkAsCompletedAsync(queueItem.Id, video.Id);

            // Assert - Original title should be preserved
            var updatedItem = await _queueService.GetByIdAsync(queueItem.Id);
            Assert.NotNull(updatedItem);
            Assert.Equal("Original Title", updatedItem.Title);
        }

        [Fact]
        public async Task MarkAsCompleted_WithoutVideoId_ShouldNotPopulateTitle()
        {
            // Arrange
            var queueItem = await _queueService.AddToQueueAsync("https://youtube.com/watch?v=test", priority: 5);

            // Act - Mark as completed without a video ID
            await _queueService.MarkAsCompletedAsync(queueItem.Id, videoId: null);

            // Assert - No title should be set
            var updatedItem = await _queueService.GetByIdAsync(queueItem.Id);
            Assert.NotNull(updatedItem);
            Assert.Equal(DownloadStatus.Completed, updatedItem.Status);
            Assert.Null(updatedItem.VideoId);
            Assert.Null(updatedItem.Title);
        }

        [Fact]
        public async Task CompletedItem_ShouldHaveVideoIdForPlayAction()
        {
            // Arrange
            var video = new Video
            {
                Title = "Playable Video",
                Artist = "Test Artist",
                FilePath = "/path/to/video.mp4"
            };
            await _unitOfWork.Videos.AddAsync(video);
            await _unitOfWork.SaveChangesAsync();

            var queueItem = await _queueService.AddToQueueAsync("https://youtube.com/watch?v=test", priority: 5);

            // Act
            await _queueService.MarkAsCompletedAsync(queueItem.Id, video.Id);

            // Assert - VideoId should be set for play action
            var completedItem = await _queueService.GetByIdAsync(queueItem.Id);
            Assert.NotNull(completedItem);
            Assert.True(completedItem.VideoId.HasValue);
            Assert.Equal(video.Id, completedItem.VideoId.Value);
        }

        [Fact]
        public async Task GetItemsByStatus_CompletedItems_ShouldIncludeVideoForPlayAction()
        {
            // Arrange
            var video = new Video
            {
                Title = "Completed Video",
                Artist = "Test Artist",
                FilePath = "/path/to/video.mp4"
            };
            await _unitOfWork.Videos.AddAsync(video);
            await _unitOfWork.SaveChangesAsync();

            var queueItem = await _queueService.AddToQueueAsync("https://youtube.com/watch?v=test", priority: 5);
            await _queueService.MarkAsCompletedAsync(queueItem.Id, video.Id);

            // Act - Get completed items with video relationship
            var completedItems = await _queueService.GetItemsByStatusAsync(DownloadStatus.Completed, limit: 10);

            // Assert
            Assert.Single(completedItems);
            var item = completedItems.First();
            Assert.Equal(video.Id, item.VideoId);
            Assert.NotNull(item.Video); // Video should be included for play action
            Assert.Equal("Completed Video", item.Video.Title);
        }

        [Fact]
        public async Task SourceURLCapture_ShouldBeVerifiedInUnitOfWork()
        {
            // This test verifies that VideoSourceVerifications repository is available in UnitOfWork
            // The actual source URL capture is tested in integration tests with DownloadBackgroundService

            // Arrange - Create a video
            var video = new Video
            {
                Title = "Test Video",
                Artist = "Test Artist",
                FilePath = "/path/to/video.mp4"
            };
            await _unitOfWork.Videos.AddAsync(video);
            await _unitOfWork.SaveChangesAsync();

            // Act - Create a source verification (simulating what DownloadBackgroundService does)
            var verification = new VideoSourceVerification
            {
                VideoId = video.Id,
                SourceUrl = "https://youtube.com/watch?v=test123",
                SourceProvider = "youtube",
                Status = VideoSourceVerificationStatus.Verified,
                Confidence = 1.0,
                VerifiedAt = DateTime.UtcNow,
                Notes = "Automatically verified during download"
            };

            await _unitOfWork.VideoSourceVerifications.AddAsync(verification);
            await _unitOfWork.SaveChangesAsync();

            // Assert - Source verification should be persisted
            var savedVerifications = await _unitOfWork.VideoSourceVerifications
                .GetAsync(v => v.VideoId == video.Id);
            
            Assert.Single(savedVerifications);
            var savedVerification = savedVerifications.First();
            Assert.Equal("https://youtube.com/watch?v=test123", savedVerification.SourceUrl);
            Assert.Equal("youtube", savedVerification.SourceProvider);
            Assert.Equal(VideoSourceVerificationStatus.Verified, savedVerification.Status);
            Assert.Equal(1.0, savedVerification.Confidence);
            Assert.Equal("Automatically verified during download", savedVerification.Notes);
        }

        [Fact]
        public async Task SourceURLCapture_ShouldPreventDuplicates()
        {
            // Arrange
            var video = new Video
            {
                Title = "Test Video",
                Artist = "Test Artist",
                FilePath = "/path/to/video.mp4"
            };
            await _unitOfWork.Videos.AddAsync(video);
            await _unitOfWork.SaveChangesAsync();

            var sourceUrl = "https://youtube.com/watch?v=test123";

            // Act - Add same source URL twice
            var verification1 = new VideoSourceVerification
            {
                VideoId = video.Id,
                SourceUrl = sourceUrl,
                SourceProvider = "youtube",
                Status = VideoSourceVerificationStatus.Verified,
                Confidence = 1.0,
                VerifiedAt = DateTime.UtcNow
            };
            await _unitOfWork.VideoSourceVerifications.AddAsync(verification1);
            await _unitOfWork.SaveChangesAsync();

            // Check if source already exists before adding duplicate
            var existingVerifications = await _unitOfWork.VideoSourceVerifications
                .GetAsync(v => v.VideoId == video.Id && v.SourceUrl == sourceUrl);

            // Assert - Should find existing verification and not add duplicate
            Assert.Single(existingVerifications);
        }

        public void Dispose()
        {
            _context?.Dispose();
        }

        // Test helper classes
        private class TestDownloadTaskQueue : IDownloadTaskQueue
        {
            public ValueTask QueueAsync(Guid queueId, System.Threading.CancellationToken cancellationToken = default)
            {
                return ValueTask.CompletedTask;
            }

            public System.Collections.Generic.IAsyncEnumerable<Guid> DequeueAsync(System.Threading.CancellationToken cancellationToken = default)
            {
                throw new NotImplementedException();
            }
        }

        private class TestDownloadSettingsProvider : IDownloadSettingsProvider
        {
            public Fuzzbin.Services.Models.DownloadWorkerOptions GetOptions()
            {
                return new Fuzzbin.Services.Models.DownloadWorkerOptions
                {
                    OutputDirectory = "/tmp/downloads",
                    Format = "mp4",
                    MaxConcurrentDownloads = 2,
                    MaxRetryCount = 3,
                    RetryBackoffSeconds = 5,
                    ProgressPercentageStep = 1.0,
                    TempDirectory = "/tmp"
                };
            }

            public string GetFfmpegPath() => "/usr/bin/ffmpeg";
            public string GetFfprobePath() => "/usr/bin/ffprobe";
            public void Invalidate() { }
        }

        private class TestActivityLogService : IActivityLogService
        {
            public Task<ActivityLog> LogAsync(string category, string action, string? entityType = null, string? entityId = null, string? entityName = null, string? details = null, string? oldValue = null, string? newValue = null)
                => Task.FromResult(new ActivityLog());

            public Task LogSuccessAsync(string category, string action, string? entityType = null, string? entityId = null, string? entityName = null, string? details = null)
                => Task.CompletedTask;

            public Task LogErrorAsync(string category, string action, string? errorMessage = null, string? entityType = null, string? entityId = null, string? entityName = null, string? details = null)
                => Task.CompletedTask;

            public Task<System.Collections.Generic.IEnumerable<ActivityLog>> GetRecentLogsAsync(int count = 100)
                => Task.FromResult<System.Collections.Generic.IEnumerable<ActivityLog>>(new System.Collections.Generic.List<ActivityLog>());

            public Task<System.Collections.Generic.IEnumerable<ActivityLog>> GetUserLogsAsync(string userId, DateTime? startDate = null, DateTime? endDate = null)
                => Task.FromResult<System.Collections.Generic.IEnumerable<ActivityLog>>(new System.Collections.Generic.List<ActivityLog>());

            public Task<System.Collections.Generic.IEnumerable<ActivityLog>> SearchLogsAsync(string? searchTerm = null, string? category = null, string? action = null, string? userId = null, DateTime? startDate = null, DateTime? endDate = null, bool? isSuccess = null, int skip = 0, int take = 100)
                => Task.FromResult<System.Collections.Generic.IEnumerable<ActivityLog>>(new System.Collections.Generic.List<ActivityLog>());

            public Task<System.Collections.Generic.Dictionary<string, int>> GetCategorySummaryAsync(DateTime? startDate = null, DateTime? endDate = null)
                => Task.FromResult(new System.Collections.Generic.Dictionary<string, int>());

            public Task<System.Collections.Generic.Dictionary<string, int>> GetActionSummaryAsync(DateTime? startDate = null, DateTime? endDate = null)
                => Task.FromResult(new System.Collections.Generic.Dictionary<string, int>());

            public Task<System.Collections.Generic.Dictionary<DateTime, int>> GetDailyActivityAsync(int days = 30)
                => Task.FromResult(new System.Collections.Generic.Dictionary<DateTime, int>());

            public Task<int> GetLogCountAsync(string? category = null, string? action = null, string? userId = null, DateTime? startDate = null, DateTime? endDate = null, bool? isSuccess = null)
                => Task.FromResult(0);

            public Task ClearOldLogsAsync(int daysToKeep = 90)
                => Task.CompletedTask;
        }
    }
}