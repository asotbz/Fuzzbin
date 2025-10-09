using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Fuzzbin.Data.Migrations
{
    /// <inheritdoc />
    public partial class UpdateDownloadQueueItemVideoIdType : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "DownloadQueues");

            migrationBuilder.AddColumn<string>(
                name: "Format",
                table: "Videos",
                type: "TEXT",
                nullable: true);

            migrationBuilder.CreateTable(
                name: "DownloadQueueItems",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    Url = table.Column<string>(type: "TEXT", maxLength: 2000, nullable: false),
                    Title = table.Column<string>(type: "TEXT", maxLength: 500, nullable: true),
                    Status = table.Column<string>(type: "TEXT", maxLength: 50, nullable: false),
                    Priority = table.Column<int>(type: "INTEGER", nullable: false),
                    Progress = table.Column<double>(type: "REAL", nullable: false),
                    ErrorMessage = table.Column<string>(type: "TEXT", maxLength: 1000, nullable: true),
                    RetryCount = table.Column<int>(type: "INTEGER", nullable: false),
                    VideoId = table.Column<Guid>(type: "TEXT", nullable: true),
                    IsDeleted = table.Column<bool>(type: "INTEGER", nullable: false),
                    AddedDate = table.Column<DateTime>(type: "TEXT", nullable: false),
                    StartedDate = table.Column<DateTime>(type: "TEXT", nullable: true),
                    CompletedDate = table.Column<DateTime>(type: "TEXT", nullable: true),
                    DeletedDate = table.Column<DateTime>(type: "TEXT", nullable: true),
                    DownloadSpeed = table.Column<string>(type: "TEXT", nullable: true),
                    ETA = table.Column<string>(type: "TEXT", nullable: true),
                    FilePath = table.Column<string>(type: "TEXT", nullable: true),
                    OutputPath = table.Column<string>(type: "TEXT", nullable: true),
                    Format = table.Column<string>(type: "TEXT", nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_DownloadQueueItems", x => x.Id);
                    table.ForeignKey(
                        name: "FK_DownloadQueueItems_Videos_VideoId",
                        column: x => x.VideoId,
                        principalTable: "Videos",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.SetNull);
                });

            migrationBuilder.CreateIndex(
                name: "IX_DownloadQueueItems_IsDeleted",
                table: "DownloadQueueItems",
                column: "IsDeleted");

            migrationBuilder.CreateIndex(
                name: "IX_DownloadQueueItems_Priority",
                table: "DownloadQueueItems",
                column: "Priority");

            migrationBuilder.CreateIndex(
                name: "IX_DownloadQueueItems_Status",
                table: "DownloadQueueItems",
                column: "Status");

            migrationBuilder.CreateIndex(
                name: "IX_DownloadQueueItems_VideoId",
                table: "DownloadQueueItems",
                column: "VideoId");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "DownloadQueueItems");

            migrationBuilder.DropColumn(
                name: "Format",
                table: "Videos");

            migrationBuilder.CreateTable(
                name: "DownloadQueues",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    AddedDate = table.Column<DateTime>(type: "TEXT", nullable: false),
                    Artist = table.Column<string>(type: "TEXT", maxLength: 500, nullable: true),
                    CompletedDate = table.Column<DateTime>(type: "TEXT", nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    DeletedDate = table.Column<DateTime>(type: "TEXT", nullable: true),
                    DownloadSpeed = table.Column<string>(type: "TEXT", nullable: true),
                    ETA = table.Column<string>(type: "TEXT", nullable: true),
                    ErrorMessage = table.Column<string>(type: "TEXT", maxLength: 1000, nullable: true),
                    FilePath = table.Column<string>(type: "TEXT", maxLength: 1000, nullable: true),
                    FileSize = table.Column<long>(type: "INTEGER", nullable: true),
                    Format = table.Column<string>(type: "TEXT", nullable: true),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false),
                    IsDeleted = table.Column<bool>(type: "INTEGER", nullable: false),
                    MaxRetries = table.Column<int>(type: "INTEGER", nullable: false),
                    OutputPath = table.Column<string>(type: "TEXT", nullable: true),
                    Priority = table.Column<int>(type: "INTEGER", nullable: false),
                    Progress = table.Column<double>(type: "REAL", nullable: false),
                    RetryCount = table.Column<int>(type: "INTEGER", nullable: false),
                    StartedDate = table.Column<DateTime>(type: "TEXT", nullable: true),
                    Status = table.Column<string>(type: "TEXT", maxLength: 50, nullable: false),
                    Title = table.Column<string>(type: "TEXT", maxLength: 500, nullable: true),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    Url = table.Column<string>(type: "TEXT", maxLength: 2000, nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_DownloadQueues", x => x.Id);
                });

            migrationBuilder.CreateIndex(
                name: "IX_DownloadQueues_IsActive",
                table: "DownloadQueues",
                column: "IsActive");

            migrationBuilder.CreateIndex(
                name: "IX_DownloadQueues_Priority",
                table: "DownloadQueues",
                column: "Priority");

            migrationBuilder.CreateIndex(
                name: "IX_DownloadQueues_Status",
                table: "DownloadQueues",
                column: "Status");
        }
    }
}
