using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Fuzzbin.Data.Migrations
{
    /// <inheritdoc />
    public partial class AddMetadataCacheSchema : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "ImvdbArtists",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    ImvdbId = table.Column<int>(type: "INTEGER", nullable: false),
                    Name = table.Column<string>(type: "TEXT", maxLength: 500, nullable: false),
                    LastSeenAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_ImvdbArtists", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "ImvdbVideos",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    ImvdbId = table.Column<int>(type: "INTEGER", nullable: false),
                    SongTitle = table.Column<string>(type: "TEXT", maxLength: 500, nullable: true),
                    VideoTitle = table.Column<string>(type: "TEXT", maxLength: 500, nullable: true),
                    ReleaseDate = table.Column<string>(type: "TEXT", maxLength: 10, nullable: true),
                    DirectorCredit = table.Column<string>(type: "TEXT", maxLength: 500, nullable: true),
                    HasSources = table.Column<bool>(type: "INTEGER", nullable: false),
                    LastSeenAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_ImvdbVideos", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "MbArtists",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    Mbid = table.Column<string>(type: "TEXT", maxLength: 36, nullable: false),
                    Name = table.Column<string>(type: "TEXT", maxLength: 500, nullable: false),
                    SortName = table.Column<string>(type: "TEXT", maxLength: 500, nullable: true),
                    Disambiguation = table.Column<string>(type: "TEXT", maxLength: 500, nullable: true),
                    Country = table.Column<string>(type: "TEXT", maxLength: 2, nullable: true),
                    LastSeenAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_MbArtists", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "MbRecordings",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    Mbid = table.Column<string>(type: "TEXT", maxLength: 36, nullable: false),
                    Title = table.Column<string>(type: "TEXT", maxLength: 500, nullable: false),
                    LengthMs = table.Column<int>(type: "INTEGER", nullable: true),
                    LastSeenAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_MbRecordings", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "MbReleaseGroups",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    Mbid = table.Column<string>(type: "TEXT", maxLength: 36, nullable: false),
                    Title = table.Column<string>(type: "TEXT", maxLength: 500, nullable: false),
                    PrimaryType = table.Column<string>(type: "TEXT", maxLength: 50, nullable: true),
                    FirstReleaseDate = table.Column<string>(type: "TEXT", maxLength: 10, nullable: true),
                    LastSeenAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_MbReleaseGroups", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "MbReleases",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    Mbid = table.Column<string>(type: "TEXT", maxLength: 36, nullable: false),
                    Title = table.Column<string>(type: "TEXT", maxLength: 500, nullable: false),
                    Date = table.Column<string>(type: "TEXT", maxLength: 10, nullable: true),
                    Country = table.Column<string>(type: "TEXT", maxLength: 2, nullable: true),
                    Barcode = table.Column<string>(type: "TEXT", maxLength: 50, nullable: true),
                    RecordLabel = table.Column<string>(type: "TEXT", maxLength: 500, nullable: true),
                    LastSeenAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_MbReleases", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "Queries",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    RawTitle = table.Column<string>(type: "TEXT", maxLength: 500, nullable: false),
                    RawArtist = table.Column<string>(type: "TEXT", maxLength: 500, nullable: false),
                    NormTitle = table.Column<string>(type: "TEXT", maxLength: 500, nullable: false),
                    NormArtist = table.Column<string>(type: "TEXT", maxLength: 500, nullable: false),
                    NormComboKey = table.Column<string>(type: "TEXT", maxLength: 1000, nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Queries", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "YtVideos",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    VideoId = table.Column<string>(type: "TEXT", maxLength: 50, nullable: false),
                    Title = table.Column<string>(type: "TEXT", maxLength: 500, nullable: false),
                    ChannelId = table.Column<string>(type: "TEXT", maxLength: 100, nullable: true),
                    ChannelName = table.Column<string>(type: "TEXT", maxLength: 500, nullable: true),
                    DurationSeconds = table.Column<int>(type: "INTEGER", nullable: true),
                    Width = table.Column<int>(type: "INTEGER", nullable: true),
                    Height = table.Column<int>(type: "INTEGER", nullable: true),
                    ViewCount = table.Column<long>(type: "INTEGER", nullable: true),
                    PublishedAt = table.Column<string>(type: "TEXT", maxLength: 30, nullable: true),
                    ThumbnailUrl = table.Column<string>(type: "TEXT", maxLength: 1000, nullable: true),
                    ThumbnailPath = table.Column<string>(type: "TEXT", maxLength: 1000, nullable: true),
                    IsOfficialChannel = table.Column<bool>(type: "INTEGER", nullable: true),
                    LastSeenAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_YtVideos", x => x.Id);
                    table.UniqueConstraint("AK_YtVideos_VideoId", x => x.VideoId);
                });

            migrationBuilder.CreateTable(
                name: "ImvdbVideoArtist",
                columns: table => new
                {
                    VideoId = table.Column<Guid>(type: "TEXT", nullable: false),
                    ArtistId = table.Column<Guid>(type: "TEXT", nullable: false),
                    Role = table.Column<string>(type: "TEXT", maxLength: 50, nullable: false),
                    ArtistOrder = table.Column<int>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_ImvdbVideoArtist", x => new { x.VideoId, x.ArtistId });
                    table.ForeignKey(
                        name: "FK_ImvdbVideoArtist_ImvdbArtists_ArtistId",
                        column: x => x.ArtistId,
                        principalTable: "ImvdbArtists",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_ImvdbVideoArtist_ImvdbVideos_VideoId",
                        column: x => x.VideoId,
                        principalTable: "ImvdbVideos",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "ImvdbVideoSource",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    VideoId = table.Column<Guid>(type: "TEXT", nullable: false),
                    Source = table.Column<string>(type: "TEXT", maxLength: 50, nullable: false),
                    ExternalId = table.Column<string>(type: "TEXT", maxLength: 200, nullable: false),
                    IsOfficial = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_ImvdbVideoSource", x => x.Id);
                    table.ForeignKey(
                        name: "FK_ImvdbVideoSource_ImvdbVideos_VideoId",
                        column: x => x.VideoId,
                        principalTable: "ImvdbVideos",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "MbRecordingArtist",
                columns: table => new
                {
                    RecordingId = table.Column<Guid>(type: "TEXT", nullable: false),
                    ArtistId = table.Column<Guid>(type: "TEXT", nullable: false),
                    ArtistOrder = table.Column<int>(type: "INTEGER", nullable: false),
                    IsJoinPhraseFeat = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_MbRecordingArtist", x => new { x.RecordingId, x.ArtistId });
                    table.ForeignKey(
                        name: "FK_MbRecordingArtist_MbArtists_ArtistId",
                        column: x => x.ArtistId,
                        principalTable: "MbArtists",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_MbRecordingArtist_MbRecordings_RecordingId",
                        column: x => x.RecordingId,
                        principalTable: "MbRecordings",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "MbTags",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    EntityType = table.Column<string>(type: "TEXT", maxLength: 50, nullable: false),
                    EntityId = table.Column<Guid>(type: "TEXT", nullable: false),
                    Tag = table.Column<string>(type: "TEXT", maxLength: 200, nullable: false),
                    Count = table.Column<int>(type: "INTEGER", nullable: true),
                    MbRecordingId = table.Column<Guid>(type: "TEXT", nullable: true),
                    MbReleaseGroupId = table.Column<Guid>(type: "TEXT", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_MbTags", x => x.Id);
                    table.ForeignKey(
                        name: "FK_MbTags_MbRecordings_MbRecordingId",
                        column: x => x.MbRecordingId,
                        principalTable: "MbRecordings",
                        principalColumn: "Id");
                    table.ForeignKey(
                        name: "FK_MbTags_MbReleaseGroups_MbReleaseGroupId",
                        column: x => x.MbReleaseGroupId,
                        principalTable: "MbReleaseGroups",
                        principalColumn: "Id");
                });

            migrationBuilder.CreateTable(
                name: "MbRecordingRelease",
                columns: table => new
                {
                    RecordingId = table.Column<Guid>(type: "TEXT", nullable: false),
                    ReleaseId = table.Column<Guid>(type: "TEXT", nullable: false),
                    TrackNumber = table.Column<int>(type: "INTEGER", nullable: true),
                    DiscNumber = table.Column<int>(type: "INTEGER", nullable: true)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_MbRecordingRelease", x => new { x.RecordingId, x.ReleaseId });
                    table.ForeignKey(
                        name: "FK_MbRecordingRelease_MbRecordings_RecordingId",
                        column: x => x.RecordingId,
                        principalTable: "MbRecordings",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_MbRecordingRelease_MbReleases_ReleaseId",
                        column: x => x.ReleaseId,
                        principalTable: "MbReleases",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "MbReleaseToGroup",
                columns: table => new
                {
                    ReleaseId = table.Column<Guid>(type: "TEXT", nullable: false),
                    ReleaseGroupId = table.Column<Guid>(type: "TEXT", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_MbReleaseToGroup", x => new { x.ReleaseId, x.ReleaseGroupId });
                    table.ForeignKey(
                        name: "FK_MbReleaseToGroup_MbReleaseGroups_ReleaseGroupId",
                        column: x => x.ReleaseGroupId,
                        principalTable: "MbReleaseGroups",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_MbReleaseToGroup_MbReleases_ReleaseId",
                        column: x => x.ReleaseId,
                        principalTable: "MbReleases",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "ImvdbVideoCandidates",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    QueryId = table.Column<Guid>(type: "TEXT", nullable: false),
                    VideoId = table.Column<Guid>(type: "TEXT", nullable: false),
                    TitleNorm = table.Column<string>(type: "TEXT", maxLength: 500, nullable: false),
                    ArtistNorm = table.Column<string>(type: "TEXT", maxLength: 500, nullable: false),
                    TextScore = table.Column<double>(type: "REAL", nullable: false),
                    SourceBonus = table.Column<double>(type: "REAL", nullable: false),
                    OverallScore = table.Column<double>(type: "REAL", nullable: false),
                    Rank = table.Column<int>(type: "INTEGER", nullable: false),
                    Selected = table.Column<bool>(type: "INTEGER", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_ImvdbVideoCandidates", x => x.Id);
                    table.ForeignKey(
                        name: "FK_ImvdbVideoCandidates_ImvdbVideos_VideoId",
                        column: x => x.VideoId,
                        principalTable: "ImvdbVideos",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_ImvdbVideoCandidates_Queries_QueryId",
                        column: x => x.QueryId,
                        principalTable: "Queries",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "MbRecordingCandidates",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    QueryId = table.Column<Guid>(type: "TEXT", nullable: false),
                    RecordingId = table.Column<Guid>(type: "TEXT", nullable: false),
                    TitleNorm = table.Column<string>(type: "TEXT", maxLength: 500, nullable: false),
                    ArtistNorm = table.Column<string>(type: "TEXT", maxLength: 500, nullable: false),
                    TextScore = table.Column<double>(type: "REAL", nullable: false),
                    YearScore = table.Column<double>(type: "REAL", nullable: true),
                    DurationScore = table.Column<double>(type: "REAL", nullable: true),
                    OverallScore = table.Column<double>(type: "REAL", nullable: false),
                    Rank = table.Column<int>(type: "INTEGER", nullable: false),
                    Selected = table.Column<bool>(type: "INTEGER", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_MbRecordingCandidates", x => x.Id);
                    table.ForeignKey(
                        name: "FK_MbRecordingCandidates_MbRecordings_RecordingId",
                        column: x => x.RecordingId,
                        principalTable: "MbRecordings",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_MbRecordingCandidates_Queries_QueryId",
                        column: x => x.QueryId,
                        principalTable: "Queries",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "QuerySourceCaches",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    QueryId = table.Column<Guid>(type: "TEXT", nullable: false),
                    Source = table.Column<string>(type: "TEXT", maxLength: 50, nullable: false),
                    LastCheckedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    ResultEtag = table.Column<string>(type: "TEXT", maxLength: 200, nullable: true),
                    HttpStatus = table.Column<int>(type: "INTEGER", nullable: true),
                    Notes = table.Column<string>(type: "TEXT", maxLength: 1000, nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_QuerySourceCaches", x => x.Id);
                    table.ForeignKey(
                        name: "FK_QuerySourceCaches_Queries_QueryId",
                        column: x => x.QueryId,
                        principalTable: "Queries",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "MvLinks",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    ImvdbVideoId = table.Column<Guid>(type: "TEXT", nullable: true),
                    MbRecordingId = table.Column<Guid>(type: "TEXT", nullable: true),
                    YtVideoId = table.Column<string>(type: "TEXT", maxLength: 50, nullable: true),
                    LinkType = table.Column<string>(type: "TEXT", maxLength: 50, nullable: false),
                    Confidence = table.Column<double>(type: "REAL", nullable: false),
                    Notes = table.Column<string>(type: "TEXT", maxLength: 1000, nullable: true),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_MvLinks", x => x.Id);
                    table.ForeignKey(
                        name: "FK_MvLinks_ImvdbVideos_ImvdbVideoId",
                        column: x => x.ImvdbVideoId,
                        principalTable: "ImvdbVideos",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.SetNull);
                    table.ForeignKey(
                        name: "FK_MvLinks_MbRecordings_MbRecordingId",
                        column: x => x.MbRecordingId,
                        principalTable: "MbRecordings",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.SetNull);
                    table.ForeignKey(
                        name: "FK_MvLinks_YtVideos_YtVideoId",
                        column: x => x.YtVideoId,
                        principalTable: "YtVideos",
                        principalColumn: "VideoId",
                        onDelete: ReferentialAction.SetNull);
                });

            migrationBuilder.CreateTable(
                name: "YtVideoCandidates",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    QueryId = table.Column<Guid>(type: "TEXT", nullable: false),
                    VideoId = table.Column<string>(type: "TEXT", maxLength: 50, nullable: false),
                    TitleNorm = table.Column<string>(type: "TEXT", maxLength: 500, nullable: false),
                    ArtistNorm = table.Column<string>(type: "TEXT", maxLength: 500, nullable: false),
                    TextScore = table.Column<double>(type: "REAL", nullable: false),
                    ChannelBonus = table.Column<double>(type: "REAL", nullable: true),
                    DurationScore = table.Column<double>(type: "REAL", nullable: true),
                    OverallScore = table.Column<double>(type: "REAL", nullable: false),
                    Rank = table.Column<int>(type: "INTEGER", nullable: false),
                    Selected = table.Column<bool>(type: "INTEGER", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_YtVideoCandidates", x => x.Id);
                    table.ForeignKey(
                        name: "FK_YtVideoCandidates_Queries_QueryId",
                        column: x => x.QueryId,
                        principalTable: "Queries",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_YtVideoCandidates_YtVideos_VideoId",
                        column: x => x.VideoId,
                        principalTable: "YtVideos",
                        principalColumn: "VideoId",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "QueryResolutions",
                columns: table => new
                {
                    Id = table.Column<Guid>(type: "TEXT", nullable: false),
                    QueryId = table.Column<Guid>(type: "TEXT", nullable: false),
                    MvExists = table.Column<bool>(type: "INTEGER", nullable: false),
                    ChosenSource = table.Column<string>(type: "TEXT", maxLength: 50, nullable: false),
                    MvLinkId = table.Column<Guid>(type: "TEXT", nullable: true),
                    ResolvedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    UpdatedAt = table.Column<DateTime>(type: "TEXT", nullable: false),
                    IsActive = table.Column<bool>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_QueryResolutions", x => x.Id);
                    table.ForeignKey(
                        name: "FK_QueryResolutions_MvLinks_MvLinkId",
                        column: x => x.MvLinkId,
                        principalTable: "MvLinks",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.SetNull);
                    table.ForeignKey(
                        name: "FK_QueryResolutions_Queries_QueryId",
                        column: x => x.QueryId,
                        principalTable: "Queries",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "IX_ImvdbArtists_ImvdbId",
                table: "ImvdbArtists",
                column: "ImvdbId",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_ImvdbArtists_IsActive",
                table: "ImvdbArtists",
                column: "IsActive");

            migrationBuilder.CreateIndex(
                name: "IX_ImvdbArtists_Name",
                table: "ImvdbArtists",
                column: "Name");

            migrationBuilder.CreateIndex(
                name: "IX_ImvdbVideoArtist_ArtistId",
                table: "ImvdbVideoArtist",
                column: "ArtistId");

            migrationBuilder.CreateIndex(
                name: "IX_ImvdbVideoArtist_VideoId",
                table: "ImvdbVideoArtist",
                column: "VideoId");

            migrationBuilder.CreateIndex(
                name: "IX_ImvdbVideoCandidates_IsActive",
                table: "ImvdbVideoCandidates",
                column: "IsActive");

            migrationBuilder.CreateIndex(
                name: "IX_ImvdbVideoCandidates_QueryId",
                table: "ImvdbVideoCandidates",
                column: "QueryId");

            migrationBuilder.CreateIndex(
                name: "IX_ImvdbVideoCandidates_QueryId_Rank",
                table: "ImvdbVideoCandidates",
                columns: new[] { "QueryId", "Rank" });

            migrationBuilder.CreateIndex(
                name: "IX_ImvdbVideoCandidates_VideoId",
                table: "ImvdbVideoCandidates",
                column: "VideoId");

            migrationBuilder.CreateIndex(
                name: "IX_ImvdbVideos_ImvdbId",
                table: "ImvdbVideos",
                column: "ImvdbId",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_ImvdbVideos_IsActive",
                table: "ImvdbVideos",
                column: "IsActive");

            migrationBuilder.CreateIndex(
                name: "IX_ImvdbVideos_SongTitle",
                table: "ImvdbVideos",
                column: "SongTitle");

            migrationBuilder.CreateIndex(
                name: "IX_ImvdbVideoSource_Source_ExternalId",
                table: "ImvdbVideoSource",
                columns: new[] { "Source", "ExternalId" });

            migrationBuilder.CreateIndex(
                name: "IX_ImvdbVideoSource_VideoId",
                table: "ImvdbVideoSource",
                column: "VideoId");

            migrationBuilder.CreateIndex(
                name: "IX_MbArtists_IsActive",
                table: "MbArtists",
                column: "IsActive");

            migrationBuilder.CreateIndex(
                name: "IX_MbArtists_Mbid",
                table: "MbArtists",
                column: "Mbid",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_MbArtists_Name",
                table: "MbArtists",
                column: "Name");

            migrationBuilder.CreateIndex(
                name: "IX_MbRecordingArtist_ArtistId",
                table: "MbRecordingArtist",
                column: "ArtistId");

            migrationBuilder.CreateIndex(
                name: "IX_MbRecordingArtist_RecordingId",
                table: "MbRecordingArtist",
                column: "RecordingId");

            migrationBuilder.CreateIndex(
                name: "IX_MbRecordingCandidates_IsActive",
                table: "MbRecordingCandidates",
                column: "IsActive");

            migrationBuilder.CreateIndex(
                name: "IX_MbRecordingCandidates_QueryId",
                table: "MbRecordingCandidates",
                column: "QueryId");

            migrationBuilder.CreateIndex(
                name: "IX_MbRecordingCandidates_QueryId_Rank",
                table: "MbRecordingCandidates",
                columns: new[] { "QueryId", "Rank" });

            migrationBuilder.CreateIndex(
                name: "IX_MbRecordingCandidates_RecordingId",
                table: "MbRecordingCandidates",
                column: "RecordingId");

            migrationBuilder.CreateIndex(
                name: "IX_MbRecordingRelease_RecordingId",
                table: "MbRecordingRelease",
                column: "RecordingId");

            migrationBuilder.CreateIndex(
                name: "IX_MbRecordingRelease_ReleaseId",
                table: "MbRecordingRelease",
                column: "ReleaseId");

            migrationBuilder.CreateIndex(
                name: "IX_MbRecordings_IsActive",
                table: "MbRecordings",
                column: "IsActive");

            migrationBuilder.CreateIndex(
                name: "IX_MbRecordings_Mbid",
                table: "MbRecordings",
                column: "Mbid",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_MbRecordings_Title",
                table: "MbRecordings",
                column: "Title");

            migrationBuilder.CreateIndex(
                name: "IX_MbReleaseGroups_IsActive",
                table: "MbReleaseGroups",
                column: "IsActive");

            migrationBuilder.CreateIndex(
                name: "IX_MbReleaseGroups_Mbid",
                table: "MbReleaseGroups",
                column: "Mbid",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_MbReleases_IsActive",
                table: "MbReleases",
                column: "IsActive");

            migrationBuilder.CreateIndex(
                name: "IX_MbReleases_Mbid",
                table: "MbReleases",
                column: "Mbid",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_MbReleaseToGroup_ReleaseGroupId",
                table: "MbReleaseToGroup",
                column: "ReleaseGroupId");

            migrationBuilder.CreateIndex(
                name: "IX_MbReleaseToGroup_ReleaseId",
                table: "MbReleaseToGroup",
                column: "ReleaseId");

            migrationBuilder.CreateIndex(
                name: "IX_MbTags_EntityType_EntityId",
                table: "MbTags",
                columns: new[] { "EntityType", "EntityId" });

            migrationBuilder.CreateIndex(
                name: "IX_MbTags_MbRecordingId",
                table: "MbTags",
                column: "MbRecordingId");

            migrationBuilder.CreateIndex(
                name: "IX_MbTags_MbReleaseGroupId",
                table: "MbTags",
                column: "MbReleaseGroupId");

            migrationBuilder.CreateIndex(
                name: "IX_MbTags_Tag",
                table: "MbTags",
                column: "Tag");

            migrationBuilder.CreateIndex(
                name: "IX_MvLinks_ImvdbVideoId",
                table: "MvLinks",
                column: "ImvdbVideoId");

            migrationBuilder.CreateIndex(
                name: "IX_MvLinks_IsActive",
                table: "MvLinks",
                column: "IsActive");

            migrationBuilder.CreateIndex(
                name: "IX_MvLinks_LinkType",
                table: "MvLinks",
                column: "LinkType");

            migrationBuilder.CreateIndex(
                name: "IX_MvLinks_MbRecordingId",
                table: "MvLinks",
                column: "MbRecordingId");

            migrationBuilder.CreateIndex(
                name: "IX_MvLinks_YtVideoId",
                table: "MvLinks",
                column: "YtVideoId");

            migrationBuilder.CreateIndex(
                name: "IX_Queries_IsActive",
                table: "Queries",
                column: "IsActive");

            migrationBuilder.CreateIndex(
                name: "IX_Queries_NormArtist",
                table: "Queries",
                column: "NormArtist");

            migrationBuilder.CreateIndex(
                name: "IX_Queries_NormComboKey",
                table: "Queries",
                column: "NormComboKey",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_Queries_NormTitle",
                table: "Queries",
                column: "NormTitle");

            migrationBuilder.CreateIndex(
                name: "IX_QueryResolutions_ChosenSource",
                table: "QueryResolutions",
                column: "ChosenSource");

            migrationBuilder.CreateIndex(
                name: "IX_QueryResolutions_IsActive",
                table: "QueryResolutions",
                column: "IsActive");

            migrationBuilder.CreateIndex(
                name: "IX_QueryResolutions_MvLinkId",
                table: "QueryResolutions",
                column: "MvLinkId");

            migrationBuilder.CreateIndex(
                name: "IX_QueryResolutions_QueryId",
                table: "QueryResolutions",
                column: "QueryId",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_QuerySourceCaches_LastCheckedAt",
                table: "QuerySourceCaches",
                column: "LastCheckedAt");

            migrationBuilder.CreateIndex(
                name: "IX_QuerySourceCaches_QueryId",
                table: "QuerySourceCaches",
                column: "QueryId");

            migrationBuilder.CreateIndex(
                name: "IX_QuerySourceCaches_Source",
                table: "QuerySourceCaches",
                column: "Source");

            migrationBuilder.CreateIndex(
                name: "IX_YtVideoCandidates_IsActive",
                table: "YtVideoCandidates",
                column: "IsActive");

            migrationBuilder.CreateIndex(
                name: "IX_YtVideoCandidates_QueryId",
                table: "YtVideoCandidates",
                column: "QueryId");

            migrationBuilder.CreateIndex(
                name: "IX_YtVideoCandidates_QueryId_Rank",
                table: "YtVideoCandidates",
                columns: new[] { "QueryId", "Rank" });

            migrationBuilder.CreateIndex(
                name: "IX_YtVideoCandidates_VideoId",
                table: "YtVideoCandidates",
                column: "VideoId");

            migrationBuilder.CreateIndex(
                name: "IX_YtVideos_ChannelId",
                table: "YtVideos",
                column: "ChannelId");

            migrationBuilder.CreateIndex(
                name: "IX_YtVideos_IsActive",
                table: "YtVideos",
                column: "IsActive");

            migrationBuilder.CreateIndex(
                name: "IX_YtVideos_VideoId",
                table: "YtVideos",
                column: "VideoId",
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "ImvdbVideoArtist");

            migrationBuilder.DropTable(
                name: "ImvdbVideoCandidates");

            migrationBuilder.DropTable(
                name: "ImvdbVideoSource");

            migrationBuilder.DropTable(
                name: "MbRecordingArtist");

            migrationBuilder.DropTable(
                name: "MbRecordingCandidates");

            migrationBuilder.DropTable(
                name: "MbRecordingRelease");

            migrationBuilder.DropTable(
                name: "MbReleaseToGroup");

            migrationBuilder.DropTable(
                name: "MbTags");

            migrationBuilder.DropTable(
                name: "QueryResolutions");

            migrationBuilder.DropTable(
                name: "QuerySourceCaches");

            migrationBuilder.DropTable(
                name: "YtVideoCandidates");

            migrationBuilder.DropTable(
                name: "ImvdbArtists");

            migrationBuilder.DropTable(
                name: "MbArtists");

            migrationBuilder.DropTable(
                name: "MbReleases");

            migrationBuilder.DropTable(
                name: "MbReleaseGroups");

            migrationBuilder.DropTable(
                name: "MvLinks");

            migrationBuilder.DropTable(
                name: "Queries");

            migrationBuilder.DropTable(
                name: "ImvdbVideos");

            migrationBuilder.DropTable(
                name: "MbRecordings");

            migrationBuilder.DropTable(
                name: "YtVideos");
        }
    }
}
