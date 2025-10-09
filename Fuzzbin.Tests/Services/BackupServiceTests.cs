using System;
using System.IO.Compression;
using System.Linq;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging.Abstractions;
using Fuzzbin.Core.Entities;
using Fuzzbin.Data.Context;
using Fuzzbin.Data.Repositories;
using Fuzzbin.Services;
using Fuzzbin.Services.Interfaces;
using Xunit;

namespace Fuzzbin.Tests.Services;

public sealed class BackupServiceTests : IDisposable
{
    private readonly string _workspace;
    private readonly DbContextOptions<ApplicationDbContext> _options;
    private readonly ApplicationDbContext _context;
    private readonly UnitOfWork _unitOfWork;
    private readonly IBackupService _backupService;
    private readonly string _databasePath;

    public BackupServiceTests()
    {
        _workspace = Path.Combine(Path.GetTempPath(), "Fuzzbin_BackupTests", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_workspace);

        _databasePath = Path.Combine(_workspace, "fuzzbin.db");
        _options = new DbContextOptionsBuilder<ApplicationDbContext>()
            .UseSqlite($"Data Source={_databasePath}")
            .Options;

        _context = new ApplicationDbContext(_options);
        _context.Database.EnsureDeleted();
        _context.Database.EnsureCreated();

        _unitOfWork = new UnitOfWork(_context);
        _backupService = new BackupService(_context, _unitOfWork, NullLogger<BackupService>.Instance);

        _context.Configurations.Add(new Configuration
        {
            Key = "TestKey",
            Value = "OriginalValue",
            Category = "Test"
        });
        _context.SaveChanges();
    }

    [Fact]
    public async Task CreateBackupAsync_CreatesArchiveWithExpectedEntries()
    {
        var result = await _backupService.CreateBackupAsync();

        Assert.True(File.Exists(result.FilePath));
        Assert.EndsWith(".zip", result.FilePath);

        await using var stream = File.OpenRead(result.FilePath);
        using var archive = new ZipArchive(stream, ZipArchiveMode.Read);

        Assert.NotNull(archive.GetEntry("database.db"));
        Assert.NotNull(archive.GetEntry("configurations.json"));
        Assert.NotNull(archive.GetEntry("manifest.json"));
    }

    [Fact]
    public async Task RestoreBackupAsync_RevertsDatabaseToBackupState()
    {
        var backup = await _backupService.CreateBackupAsync();

        var configuration = (await _unitOfWork.Configurations.GetAllAsync())
            .Single(c => c.Key == "TestKey");
        configuration.Value = "Modified";
        await _unitOfWork.Configurations.UpdateAsync(configuration);
        await _unitOfWork.SaveChangesAsync();

        using (var verificationContext = new ApplicationDbContext(_options))
        {
            var modifiedValue = verificationContext.Configurations
                .AsNoTracking()
                .Single(c => c.Key == "TestKey").Value;
            Assert.Equal("Modified", modifiedValue);
        }

        await using var stream = File.OpenRead(backup.FilePath);
        await _backupService.RestoreBackupAsync(stream);

        using (var verificationContext = new ApplicationDbContext(_options))
        {
            var restoredValue = verificationContext.Configurations
                .AsNoTracking()
                .Single(c => c.Key == "TestKey").Value;

            Assert.Equal("OriginalValue", restoredValue);
        }

        using var rawConnection = new SqliteConnection($"Data Source={_databasePath}");
        rawConnection.Open();
        using var command = rawConnection.CreateCommand();
        command.CommandText = "SELECT Value FROM Configurations WHERE Key = 'TestKey'";
        var rawValue = command.ExecuteScalar()?.ToString();

        Assert.Equal("OriginalValue", rawValue);
    }

    public void Dispose()
    {
        _unitOfWork.Dispose();
        _context.Dispose();

        try
        {
            if (Directory.Exists(_workspace))
            {
                Directory.Delete(_workspace, recursive: true);
            }
        }
        catch
        {
            // Ignore cleanup errors in tests
        }
    }
}
