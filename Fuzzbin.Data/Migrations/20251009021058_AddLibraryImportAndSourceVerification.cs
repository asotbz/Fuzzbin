using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Fuzzbin.Data.Migrations
{
    /// <inheritdoc />
    public partial class AddLibraryImportAndSourceVerification : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "FileHash",
                table: "Videos",
                type: "TEXT",
                maxLength: 128,
                nullable: true);

            migrationBuilder.CreateTable(
                name: "LibraryImportSessions",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    RootPath = table.Column<string>(type: "TEXT", maxLength: 2000, nullable: false),
                    StartedByUserId = table.Column<string>(type: "TEXT", maxLength: 450, nullable: true),
                    StartedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    CompletedAt = table.Column<DateTime>(type: "TEXT", nullable: true),
                    Status = table.Column<string>(type: "TEXT", maxLength: 50, nullable: false),
                    CreatedVideoIdsJson = table.Column<string>(type: "TEXT", nullable: true),
                    Notes = table.Column<string>(type: "TEXT", maxLength: 2000, nullable: true),
                    ErrorMessage = table.Column<string>(type: "TEXT", maxLength: 2000, nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_LibraryImportSessions", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "VideoSourceVerifications",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    VideoId = table.Column<Guid>(type: "TEXT", nullable: false),
                    SourceUrl = table.Column<string>(type: "TEXT", maxLength: 2000, nullable: true),
                    SourceProvider = table.Column<string>(type: "TEXT", maxLength: 100, nullable: true),
                    Status = table.Column<string>(type: "TEXT", maxLength: 50, nullable: false),
                    Confidence = table.Column<double>(type: "REAL", nullable: false),
                    ComparisonSnapshotJson = table.Column<string>(type: "TEXT", nullable: true),
                    IsManualOverride = table.Column<bool>(type: "INTEGER", nullable: false),
                    Notes = table.Column<string>(type: "TEXT", maxLength: 1000, nullable: true),
                    VerifiedAt = table.Column<DateTime>(type: "TEXT", nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_VideoSourceVerifications", x => x.Id);
                    table.ForeignKey(
                        name: "FK_VideoSourceVerifications_Videos_VideoId",
                        column: x => x.VideoId,
                        principalTable: "Videos",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "LibraryImportItems",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    SessionId = table.Column<Guid>(type: "TEXT", nullable: false),
                    FilePath = table.Column<string>(type: "TEXT", maxLength: 2000, nullable: false),
                    RelativePath = table.Column<string>(type: "TEXT", maxLength: 2000, nullable: true),
                    FileName = table.Column<string>(type: "TEXT", maxLength: 500, nullable: false),
                    Extension = table.Column<string>(type: "TEXT", maxLength: 20, nullable: true),
                    FileHash = table.Column<string>(type: "TEXT", maxLength: 128, nullable: true),
                    FileSize = table.Column<long>(type: "INTEGER", nullable: false),
                    DurationSeconds = table.Column<double>(type: "REAL", nullable: true),
                    Resolution = table.Column<string>(type: "TEXT", maxLength: 50, nullable: true),
                    VideoCodec = table.Column<string>(type: "TEXT", maxLength: 100, nullable: true),
                    AudioCodec = table.Column<string>(type: "TEXT", maxLength: 100, nullable: true),
                    BitrateKbps = table.Column<int>(type: "INTEGER", nullable: true),
                    FrameRate = table.Column<double>(type: "REAL", nullable: true),
                    Title = table.Column<string>(type: "TEXT", maxLength: 500, nullable: true),
                    Artist = table.Column<string>(type: "TEXT", maxLength: 500, nullable: true),
                    Album = table.Column<string>(type: "TEXT", maxLength: 500, nullable: true),
                    Year = table.Column<int>(type: "INTEGER", nullable: true),
                    Status = table.Column<string>(type: "TEXT", maxLength: 50, nullable: false),
                    DuplicateStatus = table.Column<string>(type: "TEXT", maxLength: 50, nullable: false),
                    DuplicateVideoId = table.Column<Guid>(type: "TEXT", nullable: true),
                    SuggestedVideoId = table.Column<Guid>(type: "TEXT", nullable: true),
                    ManualVideoId = table.Column<Guid>(type: "TEXT", nullable: true),
                    Confidence = table.Column<double>(type: "REAL", nullable: true),
                    CandidateMatchesJson = table.Column<string>(type: "TEXT", nullable: true),
                    Notes = table.Column<string>(type: "TEXT", maxLength: 1000, nullable: true),
                    IsCommitted = table.Column<bool>(type: "INTEGER", nullable: false),
                    ReviewedAt = table.Column<DateTime>(type: "TEXT", nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_LibraryImportItems", x => x.Id);
                    table.ForeignKey(
                        name: "FK_LibraryImportItems_LibraryImportSessions_SessionId",
                        column: x => x.SessionId,
                        principalTable: "LibraryImportSessions",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "IX_Videos_FileHash",
                table: "Videos",
                column: "FileHash");

            migrationBuilder.CreateIndex(
                name: "IX_LibraryImportItems_DuplicateStatus",
                table: "LibraryImportItems",
                column: "DuplicateStatus");

            migrationBuilder.CreateIndex(
                name: "IX_LibraryImportItems_FileHash",
                table: "LibraryImportItems",
                column: "FileHash");

            migrationBuilder.CreateIndex(
                name: "IX_LibraryImportItems_IsCommitted",
                table: "LibraryImportItems",
                column: "IsCommitted");

            migrationBuilder.CreateIndex(
                name: "IX_LibraryImportItems_SessionId",
                table: "LibraryImportItems",
                column: "SessionId");

            migrationBuilder.CreateIndex(
                name: "IX_LibraryImportItems_Status",
                table: "LibraryImportItems",
                column: "Status");

            migrationBuilder.CreateIndex(
                name: "IX_LibraryImportSessions_StartedAt",
                table: "LibraryImportSessions",
                column: "StartedAt");

            migrationBuilder.CreateIndex(
                name: "IX_LibraryImportSessions_Status",
                table: "LibraryImportSessions",
                column: "Status");

            migrationBuilder.CreateIndex(
                name: "IX_VideoSourceVerifications_Status",
                table: "VideoSourceVerifications",
                column: "Status");

            migrationBuilder.CreateIndex(
                name: "IX_VideoSourceVerifications_VideoId",
                table: "VideoSourceVerifications",
                column: "VideoId");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "LibraryImportItems");

            migrationBuilder.DropTable(
                name: "VideoSourceVerifications");

            migrationBuilder.DropTable(
                name: "LibraryImportSessions");

            migrationBuilder.DropIndex(
                name: "IX_Videos_FileHash",
                table: "Videos");

            migrationBuilder.DropColumn(
                name: "FileHash",
                table: "Videos");
        }
    }
}
