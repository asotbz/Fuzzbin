using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
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

public class MetadataExportServiceTests : IAsyncLifetime
{
    private readonly string _tempRoot = Path.Combine(Path.GetTempPath(), $"fz-tests-{Guid.NewGuid():N}");

    public Task InitializeAsync()
    {
        Directory.CreateDirectory(_tempRoot);
        return Task.CompletedTask;
    }

    public Task DisposeAsync()
    {
        TryDeleteDirectory(_tempRoot);
        return Task.CompletedTask;
    }

    [Fact]
    public async Task ExportVideoAsync_CreatesNfoAndArtwork()
    {
        var (service, context, unitOfWork, video, exportRoot) = await CreateServiceAsync();
        await using var _ = context;

        var options = new MetadataExportOptions
        {
            OutputDirectory = exportRoot,
            IncludeArtwork = true,
            IncludeVideoFile = false,
            CreateArchive = false
        };

        var result = await service.ExportVideoAsync(video, options);

        Assert.True(result.Success);
        Assert.Contains(result.Files, path => path.EndsWith(".nfo", StringComparison.OrdinalIgnoreCase));
        Assert.Contains(result.Files, path => path.EndsWith(".jpg", StringComparison.OrdinalIgnoreCase));

        foreach (var file in result.Files)
        {
            Assert.True(File.Exists(file), $"Expected file not found: {file}");
        }

        var reloaded = await unitOfWork.Videos.GetByIdAsync(video.Id);
        Assert.NotNull(reloaded);
        Assert.False(string.IsNullOrWhiteSpace(reloaded!.NfoPath));
    }

    [Fact]
    public async Task ImportAsync_UpdatesVideoFromNfo()
    {
        var (service, context, unitOfWork, video, exportRoot) = await CreateServiceAsync();
        await using var _ = context;

        var exportOptions = new MetadataExportOptions
        {
            OutputDirectory = exportRoot,
            IncludeArtwork = false,
            IncludeVideoFile = false
        };

        var exportResult = await service.ExportVideoAsync(video, exportOptions);
        var nfoPath = Assert.Single(exportResult.Files, path => path.EndsWith(".nfo", StringComparison.OrdinalIgnoreCase));

        var xml = await File.ReadAllTextAsync(nfoPath);
        var document = System.Xml.Linq.XDocument.Parse(xml);
        document.Root?.Element("title")?.SetValue("Updated Title");
        document.Save(nfoPath);

        var importResult = await service.ImportAsync(exportRoot);

        Assert.Equal(1, importResult.VideosUpdated);
        Assert.Empty(importResult.Errors);

        var updated = await unitOfWork.Videos.GetByIdAsync(video.Id);
        Assert.Equal("Updated Title", updated!.Title);
    }

    private async Task<(IMetadataExportService Service, ApplicationDbContext Context, IUnitOfWork UnitOfWork, Video Video, string ExportRoot)> CreateServiceAsync()
    {
        var options = new DbContextOptionsBuilder<ApplicationDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .Options;

        var context = new ApplicationDbContext(options);
        var unitOfWork = new UnitOfWork(context);

        var libraryPath = Path.Combine(_tempRoot, "library");
        Directory.CreateDirectory(libraryPath);

        await unitOfWork.Configurations.AddAsync(new Configuration
        {
            Key = "LibraryPath",
            Category = "Storage",
            Value = libraryPath
        });
        await unitOfWork.SaveChangesAsync();

        var pathManager = new LibraryPathManager(unitOfWork, NullLogger<LibraryPathManager>.Instance);
        var nfoService = new NfoExportService();

        var webRoot = Path.Combine(_tempRoot, "wwwroot");
        Directory.CreateDirectory(Path.Combine(webRoot, "thumbnails"));

        var configuration = new ConfigurationBuilder()
            .AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["WebRootPath"] = webRoot
            })
            .Build();

        var metadataService = new MetadataExportService(
            unitOfWork,
            pathManager,
            nfoService,
            configuration,
            NullLogger<MetadataExportService>.Instance);

        var sourceDirectory = Path.Combine(_tempRoot, "source");
        Directory.CreateDirectory(sourceDirectory);

        var videoFilePath = Path.Combine(sourceDirectory, "sample.mp4");
        await File.WriteAllTextAsync(videoFilePath, "sample");

        var video = new Video
        {
            Id = Guid.NewGuid(),
            Title = "Sample Video",
            Artist = "Sample Artist",
            FilePath = videoFilePath,
            Duration = 180,
            Year = 2020,
            Description = "Original description",
            ImvdbId = "test-imvdb-id"
        };

        await unitOfWork.Videos.AddAsync(video);
        await unitOfWork.SaveChangesAsync();

        var thumbnailPath = Path.Combine(webRoot, "thumbnails", $"{video.Id}.jpg");
        await File.WriteAllTextAsync(thumbnailPath, "thumbnail");

        var exportRoot = Path.Combine(_tempRoot, "exports");
        Directory.CreateDirectory(exportRoot);

        return (metadataService, context, unitOfWork, video, exportRoot);
    }

    private static void TryDeleteDirectory(string path)
    {
        try
        {
            if (Directory.Exists(path))
            {
                Directory.Delete(path, recursive: true);
            }
        }
        catch
        {
            // ignore cleanup failures
        }
    }
}
