using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;
using Fuzzbin.Core.Entities;
using Fuzzbin.Core.Interfaces;
using Fuzzbin.Data.Context;
using Fuzzbin.Data.Repositories;
using Fuzzbin.Services;
using Fuzzbin.Services.Interfaces;
using Fuzzbin.Services.Models;
using Xunit;

namespace Fuzzbin.Tests.Services;

public class SourceVerificationServiceTests
{
    [Fact]
    public async Task VerifyVideoAsync_ReturnsVerifiedWhenMetricsMatch()
    {
        var (service, unitOfWork, context) = CreateService();
        await using var _ = context;

        var video = new Video
        {
            Title = "Sample",
            Artist = "Artist",
            Duration = 180,
            FrameRate = 29.97,
            Resolution = "1920x1080",
            FileSize = 45_000_000,
            YouTubeId = "abc123"
        };

        await unitOfWork.Videos.AddAsync(video);
        await unitOfWork.SaveChangesAsync();

        var result = await service.VerifyVideoAsync(video, new SourceVerificationRequest { ConfidenceThreshold = 0.7 });

        Assert.Equal(VideoSourceVerificationStatus.Verified, result.Status);
        Assert.True(result.Confidence >= 0.7);
        Assert.NotNull(result.ComparisonSnapshotJson);

        var latest = await service.GetLatestAsync(video.Id);
        Assert.NotNull(latest);
        Assert.Equal(result.Id, latest!.Id);
    }

    [Fact]
    public async Task OverrideAsync_UpdatesManualOverride()
    {
        var (service, unitOfWork, context) = CreateService();
        await using var _ = context;

        var video = new Video
        {
            Title = "Sample",
            Artist = "Artist",
            Duration = 200,
            FrameRate = 30,
            Resolution = "1280x720",
            YouTubeId = "override123"
        };

        await unitOfWork.Videos.AddAsync(video);
        await unitOfWork.SaveChangesAsync();

        var verification = await service.VerifyVideoAsync(video, new SourceVerificationRequest { ConfidenceThreshold = 0.9 });

        var overridden = await service.OverrideAsync(verification.Id, new SourceVerificationOverride
        {
            MarkAsVerified = false,
            Confidence = 0.2,
            Notes = "Audio mismatch"
        });

        Assert.True(overridden.IsManualOverride);
        Assert.Equal(VideoSourceVerificationStatus.Mismatch, overridden.Status);
        Assert.Equal(0.2, overridden.Confidence);
        Assert.Equal("Audio mismatch", overridden.Notes);
    }

    private (SourceVerificationService Service, IUnitOfWork UnitOfWork, ApplicationDbContext Context) CreateService()
    {
        var options = new DbContextOptionsBuilder<ApplicationDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .Options;

        var context = new ApplicationDbContext(options);
        var unitOfWork = new UnitOfWork(context);

        var verificationRepository = new Repository<VideoSourceVerification>(context);
        var videoRepository = new Repository<Video>(context);
        var ytDlpService = new TestYtDlpService();

        var service = new SourceVerificationService(
            NullLogger<SourceVerificationService>.Instance,
            verificationRepository,
            videoRepository,
            ytDlpService,
            unitOfWork);

        return (service, unitOfWork, context);
    }

    private sealed class TestYtDlpService : IYtDlpService
    {
        public Task<DownloadResult> DownloadVideoAsync(string url, string outputPath, IProgress<DownloadProgress>? progress = null, CancellationToken cancellationToken = default) => throw new NotImplementedException();

        public Task<List<Fuzzbin.Core.Interfaces.SearchResult>> SearchVideosAsync(string query, int maxResults = 10, CancellationToken cancellationToken = default) => throw new NotImplementedException();

        public Task<YtDlpVideoMetadata> GetVideoMetadataAsync(string url, CancellationToken cancellationToken = default)
        {
            return Task.FromResult(new YtDlpVideoMetadata
            {
                Duration = TimeSpan.FromSeconds(180),
                Fps = 29.97,
                Width = 1920,
                Height = 1080
            });
        }

        public Task<bool> ValidateInstallationAsync() => Task.FromResult(true);

        public Task<string> GetVersionAsync() => Task.FromResult("test");
    }
}
