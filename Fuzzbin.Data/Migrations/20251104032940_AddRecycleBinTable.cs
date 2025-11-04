using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Fuzzbin.Data.Migrations
{
    /// <inheritdoc />
    public partial class AddRecycleBinTable : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_ImvdbVideoCandidates_Queries_QueryId1",
                table: "ImvdbVideoCandidates");

            migrationBuilder.DropForeignKey(
                name: "FK_MbRecordingCandidates_Queries_QueryId1",
                table: "MbRecordingCandidates");

            migrationBuilder.DropForeignKey(
                name: "FK_YtVideoCandidates_Queries_QueryId1",
                table: "YtVideoCandidates");

            migrationBuilder.DropIndex(
                name: "IX_YtVideoCandidates_QueryId1",
                table: "YtVideoCandidates");

            migrationBuilder.DropIndex(
                name: "IX_MbRecordingCandidates_QueryId1",
                table: "MbRecordingCandidates");

            migrationBuilder.DropIndex(
                name: "IX_ImvdbVideoCandidates_QueryId1",
                table: "ImvdbVideoCandidates");

            migrationBuilder.DropColumn(
                name: "QueryId1",
                table: "YtVideoCandidates");

            migrationBuilder.DropColumn(
                name: "QueryId1",
                table: "MbRecordingCandidates");

            migrationBuilder.DropColumn(
                name: "QueryId1",
                table: "ImvdbVideoCandidates");

            migrationBuilder.CreateTable(
                name: "RecycleBins",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    OriginalFilePath = table.Column<string>(type: "TEXT", maxLength: 2000, nullable: false),
                    RecycleBinPath = table.Column<string>(type: "TEXT", maxLength: 2000, nullable: false),
                    FileSize = table.Column<long>(type: "INTEGER", nullable: true),
                    DeletedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    ExpiresAt = table.Column<DateTime>(type: "TEXT", nullable: true),
                    DownloadQueueItemId = table.Column<Guid>(type: "TEXT", nullable: true),
                    VideoId = table.Column<Guid>(type: "TEXT", nullable: true),
                    DeletionReason = table.Column<string>(type: "TEXT", maxLength: 1000, nullable: true),
                    CanRestore = table.Column<bool>(type: "INTEGER", nullable: false),
                    Notes = table.Column<string>(type: "TEXT", maxLength: 2000, nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_RecycleBins", x => x.Id);
                    table.ForeignKey(
                        name: "FK_RecycleBins_DownloadQueueItems_DownloadQueueItemId",
                        column: x => x.DownloadQueueItemId,
                        principalTable: "DownloadQueueItems",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.SetNull);
                    table.ForeignKey(
                        name: "FK_RecycleBins_Videos_VideoId",
                        column: x => x.VideoId,
                        principalTable: "Videos",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.SetNull);
                });

            migrationBuilder.CreateIndex(
                name: "IX_RecycleBins_DeletedAt",
                table: "RecycleBins",
                column: "DeletedAt");

            migrationBuilder.CreateIndex(
                name: "IX_RecycleBins_DownloadQueueItemId",
                table: "RecycleBins",
                column: "DownloadQueueItemId");

            migrationBuilder.CreateIndex(
                name: "IX_RecycleBins_ExpiresAt",
                table: "RecycleBins",
                column: "ExpiresAt");

            migrationBuilder.CreateIndex(
                name: "IX_RecycleBins_IsActive",
                table: "RecycleBins",
                column: "IsActive");

            migrationBuilder.CreateIndex(
                name: "IX_RecycleBins_VideoId",
                table: "RecycleBins",
                column: "VideoId");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "RecycleBins");

            migrationBuilder.AddColumn<Guid>(
                name: "QueryId1",
                table: "YtVideoCandidates",
                type: "TEXT",
                nullable: true);

            migrationBuilder.AddColumn<Guid>(
                name: "QueryId1",
                table: "MbRecordingCandidates",
                type: "TEXT",
                nullable: true);

            migrationBuilder.AddColumn<Guid>(
                name: "QueryId1",
                table: "ImvdbVideoCandidates",
                type: "TEXT",
                nullable: true);

            migrationBuilder.CreateIndex(
                name: "IX_YtVideoCandidates_QueryId1",
                table: "YtVideoCandidates",
                column: "QueryId1");

            migrationBuilder.CreateIndex(
                name: "IX_MbRecordingCandidates_QueryId1",
                table: "MbRecordingCandidates",
                column: "QueryId1");

            migrationBuilder.CreateIndex(
                name: "IX_ImvdbVideoCandidates_QueryId1",
                table: "ImvdbVideoCandidates",
                column: "QueryId1");

            migrationBuilder.AddForeignKey(
                name: "FK_ImvdbVideoCandidates_Queries_QueryId1",
                table: "ImvdbVideoCandidates",
                column: "QueryId1",
                principalTable: "Queries",
                principalColumn: "Id");

            migrationBuilder.AddForeignKey(
                name: "FK_MbRecordingCandidates_Queries_QueryId1",
                table: "MbRecordingCandidates",
                column: "QueryId1",
                principalTable: "Queries",
                principalColumn: "Id");

            migrationBuilder.AddForeignKey(
                name: "FK_YtVideoCandidates_Queries_QueryId1",
                table: "YtVideoCandidates",
                column: "QueryId1",
                principalTable: "Queries",
                principalColumn: "Id");
        }
    }
}
