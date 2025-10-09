using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

#pragma warning disable CA1814 // Prefer jagged arrays over multidimensional

namespace Fuzzbin.Data.Migrations
{
    /// <inheritdoc />
    public partial class InitialCreate : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "Configurations",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    Key = table.Column<string>(type: "TEXT", maxLength: 200, nullable: false),
                    Value = table.Column<string>(type: "TEXT", nullable: false),
                    Category = table.Column<string>(type: "TEXT", maxLength: 100, nullable: false),
                    Description = table.Column<string>(type: "TEXT", maxLength: 500, nullable: true),
                    IsEncrypted = table.Column<bool>(type: "INTEGER", nullable: false),
                    IsSystem = table.Column<bool>(type: "INTEGER", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Configurations", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "DownloadQueues",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    Url = table.Column<string>(type: "TEXT", maxLength: 2000, nullable: false),
                    Title = table.Column<string>(type: "TEXT", maxLength: 500, nullable: true),
                    Artist = table.Column<string>(type: "TEXT", maxLength: 500, nullable: true),
                    Status = table.Column<string>(type: "TEXT", maxLength: 50, nullable: false),
                    Progress = table.Column<int>(type: "INTEGER", nullable: false),
                    ErrorMessage = table.Column<string>(type: "TEXT", maxLength: 1000, nullable: true),
                    StartedAt = table.Column<DateTime>(type: "TEXT", nullable: true),
                    CompletedAt = table.Column<DateTime>(type: "TEXT", nullable: true),
                    FileSize = table.Column<long>(type: "INTEGER", nullable: true),
                    FilePath = table.Column<string>(type: "TEXT", maxLength: 1000, nullable: true),
                    Priority = table.Column<int>(type: "INTEGER", nullable: false),
                    RetryCount = table.Column<int>(type: "INTEGER", nullable: false),
                    MaxRetries = table.Column<int>(type: "INTEGER", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_DownloadQueues", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "FeaturedArtists",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    Name = table.Column<string>(type: "TEXT", maxLength: 500, nullable: false),
                    ImvdbArtistId = table.Column<string>(type: "TEXT", maxLength: 100, nullable: true),
                    MusicBrainzArtistId = table.Column<string>(type: "TEXT", maxLength: 100, nullable: true),
                    Biography = table.Column<string>(type: "TEXT", maxLength: 5000, nullable: true),
                    ImagePath = table.Column<string>(type: "TEXT", maxLength: 1000, nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_FeaturedArtists", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "Genres",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    Name = table.Column<string>(type: "TEXT", maxLength: 100, nullable: false),
                    Description = table.Column<string>(type: "TEXT", maxLength: 500, nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Genres", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "Tags",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    Name = table.Column<string>(type: "TEXT", maxLength: 100, nullable: false),
                    Color = table.Column<string>(type: "TEXT", maxLength: 7, nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Tags", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "Videos",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    Title = table.Column<string>(type: "TEXT", maxLength: 500, nullable: false),
                    Artist = table.Column<string>(type: "TEXT", maxLength: 500, nullable: false),
                    Album = table.Column<string>(type: "TEXT", maxLength: 500, nullable: true),
                    Year = table.Column<int>(type: "INTEGER", nullable: true),
                    Duration = table.Column<int>(type: "INTEGER", nullable: true),
                    FilePath = table.Column<string>(type: "TEXT", maxLength: 1000, nullable: true),
                    FileSize = table.Column<long>(type: "INTEGER", nullable: true),
                    VideoCodec = table.Column<string>(type: "TEXT", nullable: true),
                    AudioCodec = table.Column<string>(type: "TEXT", nullable: true),
                    Resolution = table.Column<string>(type: "TEXT", nullable: true),
                    FrameRate = table.Column<double>(type: "REAL", nullable: true),
                    Bitrate = table.Column<int>(type: "INTEGER", nullable: true),
                    ImvdbId = table.Column<string>(type: "TEXT", maxLength: 100, nullable: true),
                    MusicBrainzRecordingId = table.Column<string>(type: "TEXT", maxLength: 100, nullable: true),
                    YouTubeId = table.Column<string>(type: "TEXT", maxLength: 50, nullable: true),
                    Description = table.Column<string>(type: "TEXT", maxLength: 5000, nullable: true),
                    Director = table.Column<string>(type: "TEXT", nullable: true),
                    ProductionCompany = table.Column<string>(type: "TEXT", nullable: true),
                    Publisher = table.Column<string>(type: "TEXT", nullable: true),
                    ThumbnailPath = table.Column<string>(type: "TEXT", maxLength: 1000, nullable: true),
                    NfoPath = table.Column<string>(type: "TEXT", maxLength: 1000, nullable: true),
                    ImportedAt = table.Column<DateTime>(type: "TEXT", nullable: true),
                    LastPlayedAt = table.Column<DateTime>(type: "TEXT", nullable: true),
                    PlayCount = table.Column<int>(type: "INTEGER", nullable: false),
                    Rating = table.Column<int>(type: "INTEGER", nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Videos", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "VideoFeaturedArtist",
                columns: table => new
                {
                    FeaturedArtistId = table.Column<Guid>(type: "TEXT", nullable: false),
                    VideoId = table.Column<Guid>(type: "TEXT", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_VideoFeaturedArtist", x => new { x.FeaturedArtistId, x.VideoId });
                    table.ForeignKey(
                        name: "FK_VideoFeaturedArtist_FeaturedArtists_FeaturedArtistId",
                        column: x => x.FeaturedArtistId,
                        principalTable: "FeaturedArtists",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_VideoFeaturedArtist_Videos_VideoId",
                        column: x => x.VideoId,
                        principalTable: "Videos",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "VideoGenre",
                columns: table => new
                {
                    GenreId = table.Column<Guid>(type: "TEXT", nullable: false),
                    VideoId = table.Column<Guid>(type: "TEXT", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_VideoGenre", x => new { x.GenreId, x.VideoId });
                    table.ForeignKey(
                        name: "FK_VideoGenre_Genres_GenreId",
                        column: x => x.GenreId,
                        principalTable: "Genres",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_VideoGenre_Videos_VideoId",
                        column: x => x.VideoId,
                        principalTable: "Videos",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "VideoTag",
                columns: table => new
                {
                    TagId = table.Column<Guid>(type: "TEXT", nullable: false),
                    VideoId = table.Column<Guid>(type: "TEXT", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_VideoTag", x => new { x.TagId, x.VideoId });
                    table.ForeignKey(
                        name: "FK_VideoTag_Tags_TagId",
                        column: x => x.TagId,
                        principalTable: "Tags",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_VideoTag_Videos_VideoId",
                        column: x => x.VideoId,
                        principalTable: "Videos",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.InsertData(
                table: "Configurations",
                columns: new[] { "Id", "Category", "CreatedAt", "Description", "IsActive", "IsEncrypted", "IsSystem", "Key", "UpdatedAt", "Value" },
                values: new object[,]
                {
                    { new Guid("00000000-0000-0000-0000-000000000001"), "System", new DateTime(2024, 1, 1, 0, 0, 0, 0, DateTimeKind.Utc), "Application version", true, false, true, "AppVersion", new DateTime(2024, 1, 1, 0, 0, 0, 0, DateTimeKind.Utc), "1.0.0" },
                    { new Guid("00000000-0000-0000-0000-000000000002"), "Paths", new DateTime(2024, 1, 1, 0, 0, 0, 0, DateTimeKind.Utc), "Default media storage path", true, false, false, "MediaPath", new DateTime(2024, 1, 1, 0, 0, 0, 0, DateTimeKind.Utc), "/media/videos" },
                    { new Guid("00000000-0000-0000-0000-000000000003"), "Paths", new DateTime(2024, 1, 1, 0, 0, 0, 0, DateTimeKind.Utc), "Thumbnail storage path", true, false, false, "ThumbnailPath", new DateTime(2024, 1, 1, 0, 0, 0, 0, DateTimeKind.Utc), "/media/thumbnails" },
                    { new Guid("00000000-0000-0000-0000-000000000004"), "Downloads", new DateTime(2024, 1, 1, 0, 0, 0, 0, DateTimeKind.Utc), "Maximum number of concurrent downloads", true, false, false, "MaxConcurrentDownloads", new DateTime(2024, 1, 1, 0, 0, 0, 0, DateTimeKind.Utc), "2" },
                    { new Guid("00000000-0000-0000-0000-000000000005"), "System", new DateTime(2024, 1, 1, 0, 0, 0, 0, DateTimeKind.Utc), "Indicates if this is the first run", true, false, true, "IsFirstRun", new DateTime(2024, 1, 1, 0, 0, 0, 0, DateTimeKind.Utc), "true" }
                });

            migrationBuilder.CreateIndex(
                name: "IX_Configurations_Category_Key",
                table: "Configurations",
                columns: new[] { "Category", "Key" },
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_Configurations_IsActive",
                table: "Configurations",
                column: "IsActive");

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

            migrationBuilder.CreateIndex(
                name: "IX_FeaturedArtists_ImvdbArtistId",
                table: "FeaturedArtists",
                column: "ImvdbArtistId");

            migrationBuilder.CreateIndex(
                name: "IX_FeaturedArtists_IsActive",
                table: "FeaturedArtists",
                column: "IsActive");

            migrationBuilder.CreateIndex(
                name: "IX_FeaturedArtists_MusicBrainzArtistId",
                table: "FeaturedArtists",
                column: "MusicBrainzArtistId");

            migrationBuilder.CreateIndex(
                name: "IX_FeaturedArtists_Name",
                table: "FeaturedArtists",
                column: "Name");

            migrationBuilder.CreateIndex(
                name: "IX_Genres_IsActive",
                table: "Genres",
                column: "IsActive");

            migrationBuilder.CreateIndex(
                name: "IX_Genres_Name",
                table: "Genres",
                column: "Name",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_Tags_IsActive",
                table: "Tags",
                column: "IsActive");

            migrationBuilder.CreateIndex(
                name: "IX_Tags_Name",
                table: "Tags",
                column: "Name",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_VideoFeaturedArtist_VideoId",
                table: "VideoFeaturedArtist",
                column: "VideoId");

            migrationBuilder.CreateIndex(
                name: "IX_VideoGenre_VideoId",
                table: "VideoGenre",
                column: "VideoId");

            migrationBuilder.CreateIndex(
                name: "IX_Videos_Artist",
                table: "Videos",
                column: "Artist");

            migrationBuilder.CreateIndex(
                name: "IX_Videos_ImvdbId",
                table: "Videos",
                column: "ImvdbId");

            migrationBuilder.CreateIndex(
                name: "IX_Videos_IsActive",
                table: "Videos",
                column: "IsActive");

            migrationBuilder.CreateIndex(
                name: "IX_Videos_Title",
                table: "Videos",
                column: "Title");

            migrationBuilder.CreateIndex(
                name: "IX_Videos_YouTubeId",
                table: "Videos",
                column: "YouTubeId");

            migrationBuilder.CreateIndex(
                name: "IX_VideoTag_VideoId",
                table: "VideoTag",
                column: "VideoId");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "Configurations");

            migrationBuilder.DropTable(
                name: "DownloadQueues");

            migrationBuilder.DropTable(
                name: "VideoFeaturedArtist");

            migrationBuilder.DropTable(
                name: "VideoGenre");

            migrationBuilder.DropTable(
                name: "VideoTag");

            migrationBuilder.DropTable(
                name: "FeaturedArtists");

            migrationBuilder.DropTable(
                name: "Genres");

            migrationBuilder.DropTable(
                name: "Tags");

            migrationBuilder.DropTable(
                name: "Videos");
        }
    }
}
