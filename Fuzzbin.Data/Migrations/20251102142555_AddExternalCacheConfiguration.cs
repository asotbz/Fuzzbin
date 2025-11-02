using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Fuzzbin.Data.Migrations
{
    /// <inheritdoc />
    public partial class AddExternalCacheConfiguration : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            // Insert ExternalCache configuration settings
            migrationBuilder.InsertData(
                table: "Configurations",
                columns: new[] { "Id", "Category", "Key", "Value", "Description", "IsActive", "IsEncrypted", "IsSystem", "CreatedAt", "UpdatedAt" },
                values: new object[,]
                {
                    {
                        Guid.NewGuid(),
                        "ExternalCache",
                        "CacheTtlHours",
                        "336",
                        "Cache lifetime for external metadata sources in hours (Default: 336, Max: 720, Min: 0)",
                        true,
                        false,
                        false,
                        DateTime.UtcNow,
                        DateTime.UtcNow
                    },
                    {
                        Guid.NewGuid(),
                        "ExternalCache",
                        "MusicBrainzUserAgent",
                        "Fuzzbin/1.0 (https://github.com/fuzzbin)",
                        "User-Agent string for MusicBrainz API requests (required)",
                        true,
                        false,
                        false,
                        DateTime.UtcNow,
                        DateTime.UtcNow
                    },
                    {
                        Guid.NewGuid(),
                        "ExternalCache",
                        "EnableAutomaticPurge",
                        "true",
                        "Enable automatic cache purging during maintenance runs",
                        true,
                        false,
                        false,
                        DateTime.UtcNow,
                        DateTime.UtcNow
                    },
                    {
                        Guid.NewGuid(),
                        "ExternalCache",
                        "MaintenanceIntervalHours",
                        "8",
                        "Interval in hours between automatic maintenance runs (cache purge, cleanup)",
                        true,
                        false,
                        false,
                        DateTime.UtcNow,
                        DateTime.UtcNow
                    }
                });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            // Remove ExternalCache configuration settings
            migrationBuilder.Sql(
                "DELETE FROM Configurations WHERE Category = 'ExternalCache'");
        }
    }
}
