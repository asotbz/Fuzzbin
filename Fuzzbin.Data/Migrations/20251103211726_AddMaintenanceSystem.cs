using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Fuzzbin.Data.Migrations
{
    /// <inheritdoc />
    public partial class AddMaintenanceSystem : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<bool>(
                name: "IsMissing",
                table: "Videos",
                type: "INTEGER",
                nullable: false,
                defaultValue: false);

            migrationBuilder.AddColumn<DateTime>(
                name: "MissingDetectedAt",
                table: "Videos",
                type: "TEXT",
                nullable: true);

            migrationBuilder.CreateTable(
                name: "CacheStatSnapshots",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    SnapshotAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    TotalQueries = table.Column<int>(type: "INTEGER", nullable: false),
                    MbSourceCaches = table.Column<int>(type: "INTEGER", nullable: false),
                    ImvdbSourceCaches = table.Column<int>(type: "INTEGER", nullable: false),
                    YtSourceCaches = table.Column<int>(type: "INTEGER", nullable: false),
                    TotalResolutions = table.Column<int>(type: "INTEGER", nullable: false),
                    MbCandidates = table.Column<int>(type: "INTEGER", nullable: false),
                    ImvdbCandidates = table.Column<int>(type: "INTEGER", nullable: false),
                    YtCandidates = table.Column<int>(type: "INTEGER", nullable: false),
                    HitRatePercent = table.Column<double>(type: "REAL", nullable: false),
                    AvgCandidatesPerQuery = table.Column<double>(type: "REAL", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_CacheStatSnapshots", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "MaintenanceExecutions",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    TaskName = table.Column<string>(type: "TEXT", maxLength: 200, nullable: false),
                    StartedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    CompletedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    Success = table.Column<bool>(type: "INTEGER", nullable: false),
                    Summary = table.Column<string>(type: "TEXT", maxLength: 2000, nullable: false),
                    ItemsProcessed = table.Column<int>(type: "INTEGER", nullable: false),
                    ErrorMessage = table.Column<string>(type: "TEXT", maxLength: 2000, nullable: true),
                    DurationMs = table.Column<int>(type: "INTEGER", nullable: false),
                    MetricsJson = table.Column<string>(type: "TEXT", nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_MaintenanceExecutions", x => x.Id);
                });

            migrationBuilder.CreateIndex(
                name: "IX_Videos_IsMissing",
                table: "Videos",
                column: "IsMissing");

            migrationBuilder.CreateIndex(
                name: "IX_Videos_MissingDetectedAt",
                table: "Videos",
                column: "MissingDetectedAt");

            migrationBuilder.CreateIndex(
                name: "IX_CacheStatSnapshots_IsActive",
                table: "CacheStatSnapshots",
                column: "IsActive");

            migrationBuilder.CreateIndex(
                name: "IX_CacheStatSnapshots_SnapshotAt",
                table: "CacheStatSnapshots",
                column: "SnapshotAt");

            migrationBuilder.CreateIndex(
                name: "IX_MaintenanceExecutions_IsActive",
                table: "MaintenanceExecutions",
                column: "IsActive");

            migrationBuilder.CreateIndex(
                name: "IX_MaintenanceExecutions_StartedAt",
                table: "MaintenanceExecutions",
                column: "StartedAt");

            migrationBuilder.CreateIndex(
                name: "IX_MaintenanceExecutions_Success",
                table: "MaintenanceExecutions",
                column: "Success");

            migrationBuilder.CreateIndex(
                name: "IX_MaintenanceExecutions_TaskName",
                table: "MaintenanceExecutions",
                column: "TaskName");

            // Insert default maintenance configuration
            var seedDate = new DateTime(2024, 1, 1, 0, 0, 0, DateTimeKind.Utc);
            
            migrationBuilder.InsertData(
                table: "Configurations",
                columns: new[] { "Id", "Category", "Key", "Value", "Description", "IsSystem", "IsEncrypted", "IsActive", "CreatedAt", "UpdatedAt" },
                values: new object[,]
                {
                    { Guid.Parse("10000000-0000-0000-0000-000000000001"), "Maintenance", "IntervalHours", "8", "How often to run maintenance tasks (in hours). Default: 8", false, false, true, seedDate, seedDate },
                    { Guid.Parse("10000000-0000-0000-0000-000000000002"), "Maintenance", "LibraryScan.Enabled", "true", "Enable automatic library scanning for new and missing videos", false, false, true, seedDate, seedDate },
                    { Guid.Parse("10000000-0000-0000-0000-000000000003"), "Maintenance", "LibraryScan.Recursive", "true", "Scan subdirectories recursively", false, false, true, seedDate, seedDate },
                    { Guid.Parse("10000000-0000-0000-0000-000000000004"), "Maintenance", "LibraryScan.EnrichOnline", "false", "Enrich imported videos with online metadata (IMVDb, MusicBrainz)", false, false, true, seedDate, seedDate },
                    { Guid.Parse("10000000-0000-0000-0000-000000000005"), "Maintenance", "ThumbnailCleanup.Enabled", "true", "Enable automatic cleanup of orphaned thumbnails", false, false, true, seedDate, seedDate },
                    { Guid.Parse("10000000-0000-0000-0000-000000000006"), "Maintenance", "ThumbnailCleanup.GracePeriodDays", "7", "Days to wait before deleting thumbnails of deleted videos (0 for immediate)", false, false, true, seedDate, seedDate },
                    { Guid.Parse("10000000-0000-0000-0000-000000000007"), "Maintenance", "CacheStats.Enabled", "true", "Enable cache statistics collection", false, false, true, seedDate, seedDate },
                    { Guid.Parse("10000000-0000-0000-0000-000000000008"), "Maintenance", "CacheStats.RetentionDays", "14", "Days to retain cache statistics (older stats are purged)", false, false, true, seedDate, seedDate },
                    { Guid.Parse("10000000-0000-0000-0000-000000000009"), "Maintenance", "RecycleBinPurge.Enabled", "true", "Enable automatic purging of old recycle bin files", false, false, true, seedDate, seedDate },
                    { Guid.Parse("10000000-0000-0000-0000-00000000000a"), "Maintenance", "RecycleBinPurge.RetentionDays", "7", "Days to keep files in recycle bin before permanent deletion", false, false, true, seedDate, seedDate },
                    { Guid.Parse("10000000-0000-0000-0000-00000000000b"), "Maintenance", "RecycleBinPurge.HardDelete", "false", "Permanently delete database records (true) or soft delete (false)", false, false, true, seedDate, seedDate },
                    { Guid.Parse("10000000-0000-0000-0000-00000000000c"), "Maintenance", "AutoBackup.Enabled", "true", "Enable automated database backups", false, false, true, seedDate, seedDate },
                    { Guid.Parse("10000000-0000-0000-0000-00000000000d"), "Maintenance", "AutoBackup.IntervalHours", "24", "Hours between automated backups", false, false, true, seedDate, seedDate },
                    { Guid.Parse("10000000-0000-0000-0000-00000000000e"), "Maintenance", "AutoBackup.MaxBackups", "7", "Maximum number of backups to keep (oldest are deleted)", false, false, true, seedDate, seedDate }
                });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            // Remove maintenance configuration
            migrationBuilder.DeleteData(
                table: "Configurations",
                keyColumn: "Id",
                keyValues: new object[]
                {
                    Guid.Parse("10000000-0000-0000-0000-000000000001"),
                    Guid.Parse("10000000-0000-0000-0000-000000000002"),
                    Guid.Parse("10000000-0000-0000-0000-000000000003"),
                    Guid.Parse("10000000-0000-0000-0000-000000000004"),
                    Guid.Parse("10000000-0000-0000-0000-000000000005"),
                    Guid.Parse("10000000-0000-0000-0000-000000000006"),
                    Guid.Parse("10000000-0000-0000-0000-000000000007"),
                    Guid.Parse("10000000-0000-0000-0000-000000000008"),
                    Guid.Parse("10000000-0000-0000-0000-000000000009"),
                    Guid.Parse("10000000-0000-0000-0000-00000000000a"),
                    Guid.Parse("10000000-0000-0000-0000-00000000000b"),
                    Guid.Parse("10000000-0000-0000-0000-00000000000c"),
                    Guid.Parse("10000000-0000-0000-0000-00000000000d"),
                    Guid.Parse("10000000-0000-0000-0000-00000000000e")
                });

            migrationBuilder.DropTable(
                name: "CacheStatSnapshots");

            migrationBuilder.DropTable(
                name: "MaintenanceExecutions");

            migrationBuilder.DropIndex(
                name: "IX_Videos_IsMissing",
                table: "Videos");

            migrationBuilder.DropIndex(
                name: "IX_Videos_MissingDetectedAt",
                table: "Videos");

            migrationBuilder.DropColumn(
                name: "IsMissing",
                table: "Videos");

            migrationBuilder.DropColumn(
                name: "MissingDetectedAt",
                table: "Videos");
        }
    }
}
