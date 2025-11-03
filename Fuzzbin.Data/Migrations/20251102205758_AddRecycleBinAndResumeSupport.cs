using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Fuzzbin.Data.Migrations
{
    /// <inheritdoc />
    public partial class AddRecycleBinAndResumeSupport : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<long>(
                name: "BytesDownloaded",
                table: "DownloadQueueItems",
                type: "INTEGER",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "PartialFilePath",
                table: "DownloadQueueItems",
                type: "TEXT",
                nullable: true);

            migrationBuilder.AddColumn<long>(
                name: "ResumePosition",
                table: "DownloadQueueItems",
                type: "INTEGER",
                nullable: true);

            migrationBuilder.AddColumn<bool>(
                name: "SupportsResume",
                table: "DownloadQueueItems",
                type: "INTEGER",
                nullable: false,
                defaultValue: false);

            migrationBuilder.AddColumn<long>(
                name: "TotalBytes",
                table: "DownloadQueueItems",
                type: "INTEGER",
                nullable: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "BytesDownloaded",
                table: "DownloadQueueItems");

            migrationBuilder.DropColumn(
                name: "PartialFilePath",
                table: "DownloadQueueItems");

            migrationBuilder.DropColumn(
                name: "ResumePosition",
                table: "DownloadQueueItems");

            migrationBuilder.DropColumn(
                name: "SupportsResume",
                table: "DownloadQueueItems");

            migrationBuilder.DropColumn(
                name: "TotalBytes",
                table: "DownloadQueueItems");
        }
    }
}
