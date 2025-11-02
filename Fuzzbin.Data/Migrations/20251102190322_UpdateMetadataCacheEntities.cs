using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Fuzzbin.Data.Migrations
{
    /// <inheritdoc />
    public partial class UpdateMetadataCacheEntities : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.RenameColumn(
                name: "Tag",
                table: "MbTags",
                newName: "Name");

            migrationBuilder.RenameIndex(
                name: "IX_MbTags_Tag",
                table: "MbTags",
                newName: "IX_MbTags_Name");

            migrationBuilder.RenameColumn(
                name: "Date",
                table: "MbReleases",
                newName: "ReleaseDate");

            migrationBuilder.RenameColumn(
                name: "LengthMs",
                table: "MbRecordings",
                newName: "DurationMs");

            migrationBuilder.AddColumn<Guid>(
                name: "QueryId1",
                table: "YtVideoCandidates",
                type: "TEXT",
                nullable: true);

            migrationBuilder.AlterColumn<int>(
                name: "Count",
                table: "MbTags",
                type: "INTEGER",
                nullable: false,
                defaultValue: 0,
                oldClrType: typeof(int),
                oldType: "INTEGER",
                oldNullable: true);

            migrationBuilder.AddColumn<DateTime>(
                name: "CreatedAt",
                table: "MbTags",
                type: "TEXT",
                nullable: false,
                defaultValue: new DateTime(1, 1, 1, 0, 0, 0, 0, DateTimeKind.Unspecified));

            migrationBuilder.AddColumn<bool>(
                name: "IsActive",
                table: "MbTags",
                type: "INTEGER",
                nullable: false,
                defaultValue: false);

            migrationBuilder.AddColumn<DateTime>(
                name: "UpdatedAt",
                table: "MbTags",
                type: "TEXT",
                nullable: false,
                defaultValue: new DateTime(1, 1, 1, 0, 0, 0, 0, DateTimeKind.Unspecified));

            migrationBuilder.AddColumn<DateTime>(
                name: "CreatedAt",
                table: "MbReleaseToGroup",
                type: "TEXT",
                nullable: false,
                defaultValue: new DateTime(1, 1, 1, 0, 0, 0, 0, DateTimeKind.Unspecified));

            migrationBuilder.AddColumn<Guid>(
                name: "Id",
                table: "MbReleaseToGroup",
                type: "TEXT",
                nullable: false,
                defaultValue: new Guid("00000000-0000-0000-0000-000000000000"));

            migrationBuilder.AddColumn<bool>(
                name: "IsActive",
                table: "MbReleaseToGroup",
                type: "INTEGER",
                nullable: false,
                defaultValue: false);

            migrationBuilder.AddColumn<DateTime>(
                name: "UpdatedAt",
                table: "MbReleaseToGroup",
                type: "TEXT",
                nullable: false,
                defaultValue: new DateTime(1, 1, 1, 0, 0, 0, 0, DateTimeKind.Unspecified));

            migrationBuilder.AddColumn<int>(
                name: "TrackCount",
                table: "MbReleases",
                type: "INTEGER",
                nullable: true);

            migrationBuilder.AddColumn<DateTime>(
                name: "CreatedAt",
                table: "MbRecordingRelease",
                type: "TEXT",
                nullable: false,
                defaultValue: new DateTime(1, 1, 1, 0, 0, 0, 0, DateTimeKind.Unspecified));

            migrationBuilder.AddColumn<Guid>(
                name: "Id",
                table: "MbRecordingRelease",
                type: "TEXT",
                nullable: false,
                defaultValue: new Guid("00000000-0000-0000-0000-000000000000"));

            migrationBuilder.AddColumn<bool>(
                name: "IsActive",
                table: "MbRecordingRelease",
                type: "INTEGER",
                nullable: false,
                defaultValue: false);

            migrationBuilder.AddColumn<DateTime>(
                name: "UpdatedAt",
                table: "MbRecordingRelease",
                type: "TEXT",
                nullable: false,
                defaultValue: new DateTime(1, 1, 1, 0, 0, 0, 0, DateTimeKind.Unspecified));

            migrationBuilder.AddColumn<Guid>(
                name: "QueryId1",
                table: "MbRecordingCandidates",
                type: "TEXT",
                nullable: true);

            migrationBuilder.AddColumn<DateTime>(
                name: "CreatedAt",
                table: "MbRecordingArtist",
                type: "TEXT",
                nullable: false,
                defaultValue: new DateTime(1, 1, 1, 0, 0, 0, 0, DateTimeKind.Unspecified));

            migrationBuilder.AddColumn<string>(
                name: "CreditedName",
                table: "MbRecordingArtist",
                type: "TEXT",
                nullable: true);

            migrationBuilder.AddColumn<Guid>(
                name: "Id",
                table: "MbRecordingArtist",
                type: "TEXT",
                nullable: false,
                defaultValue: new Guid("00000000-0000-0000-0000-000000000000"));

            migrationBuilder.AddColumn<bool>(
                name: "IsActive",
                table: "MbRecordingArtist",
                type: "INTEGER",
                nullable: false,
                defaultValue: false);

            migrationBuilder.AddColumn<string>(
                name: "JoinPhrase",
                table: "MbRecordingArtist",
                type: "TEXT",
                nullable: true);

            migrationBuilder.AddColumn<DateTime>(
                name: "UpdatedAt",
                table: "MbRecordingArtist",
                type: "TEXT",
                nullable: false,
                defaultValue: new DateTime(1, 1, 1, 0, 0, 0, 0, DateTimeKind.Unspecified));

            migrationBuilder.AddColumn<DateTime>(
                name: "CreatedAt",
                table: "ImvdbVideoSource",
                type: "TEXT",
                nullable: false,
                defaultValue: new DateTime(1, 1, 1, 0, 0, 0, 0, DateTimeKind.Unspecified));

            migrationBuilder.AddColumn<bool>(
                name: "IsActive",
                table: "ImvdbVideoSource",
                type: "INTEGER",
                nullable: false,
                defaultValue: false);

            migrationBuilder.AddColumn<DateTime>(
                name: "UpdatedAt",
                table: "ImvdbVideoSource",
                type: "TEXT",
                nullable: false,
                defaultValue: new DateTime(1, 1, 1, 0, 0, 0, 0, DateTimeKind.Unspecified));

            migrationBuilder.AddColumn<int>(
                name: "RuntimeSeconds",
                table: "ImvdbVideos",
                type: "INTEGER",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "ThumbnailUrl",
                table: "ImvdbVideos",
                type: "TEXT",
                nullable: true);

            migrationBuilder.AddColumn<Guid>(
                name: "QueryId1",
                table: "ImvdbVideoCandidates",
                type: "TEXT",
                nullable: true);

            migrationBuilder.AddColumn<DateTime>(
                name: "CreatedAt",
                table: "ImvdbVideoArtist",
                type: "TEXT",
                nullable: false,
                defaultValue: new DateTime(1, 1, 1, 0, 0, 0, 0, DateTimeKind.Unspecified));

            migrationBuilder.AddColumn<Guid>(
                name: "Id",
                table: "ImvdbVideoArtist",
                type: "TEXT",
                nullable: false,
                defaultValue: new Guid("00000000-0000-0000-0000-000000000000"));

            migrationBuilder.AddColumn<bool>(
                name: "IsActive",
                table: "ImvdbVideoArtist",
                type: "INTEGER",
                nullable: false,
                defaultValue: false);

            migrationBuilder.AddColumn<DateTime>(
                name: "UpdatedAt",
                table: "ImvdbVideoArtist",
                type: "TEXT",
                nullable: false,
                defaultValue: new DateTime(1, 1, 1, 0, 0, 0, 0, DateTimeKind.Unspecified));

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

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
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
                name: "CreatedAt",
                table: "MbTags");

            migrationBuilder.DropColumn(
                name: "IsActive",
                table: "MbTags");

            migrationBuilder.DropColumn(
                name: "UpdatedAt",
                table: "MbTags");

            migrationBuilder.DropColumn(
                name: "CreatedAt",
                table: "MbReleaseToGroup");

            migrationBuilder.DropColumn(
                name: "Id",
                table: "MbReleaseToGroup");

            migrationBuilder.DropColumn(
                name: "IsActive",
                table: "MbReleaseToGroup");

            migrationBuilder.DropColumn(
                name: "UpdatedAt",
                table: "MbReleaseToGroup");

            migrationBuilder.DropColumn(
                name: "TrackCount",
                table: "MbReleases");

            migrationBuilder.DropColumn(
                name: "CreatedAt",
                table: "MbRecordingRelease");

            migrationBuilder.DropColumn(
                name: "Id",
                table: "MbRecordingRelease");

            migrationBuilder.DropColumn(
                name: "IsActive",
                table: "MbRecordingRelease");

            migrationBuilder.DropColumn(
                name: "UpdatedAt",
                table: "MbRecordingRelease");

            migrationBuilder.DropColumn(
                name: "QueryId1",
                table: "MbRecordingCandidates");

            migrationBuilder.DropColumn(
                name: "CreatedAt",
                table: "MbRecordingArtist");

            migrationBuilder.DropColumn(
                name: "CreditedName",
                table: "MbRecordingArtist");

            migrationBuilder.DropColumn(
                name: "Id",
                table: "MbRecordingArtist");

            migrationBuilder.DropColumn(
                name: "IsActive",
                table: "MbRecordingArtist");

            migrationBuilder.DropColumn(
                name: "JoinPhrase",
                table: "MbRecordingArtist");

            migrationBuilder.DropColumn(
                name: "UpdatedAt",
                table: "MbRecordingArtist");

            migrationBuilder.DropColumn(
                name: "CreatedAt",
                table: "ImvdbVideoSource");

            migrationBuilder.DropColumn(
                name: "IsActive",
                table: "ImvdbVideoSource");

            migrationBuilder.DropColumn(
                name: "UpdatedAt",
                table: "ImvdbVideoSource");

            migrationBuilder.DropColumn(
                name: "RuntimeSeconds",
                table: "ImvdbVideos");

            migrationBuilder.DropColumn(
                name: "ThumbnailUrl",
                table: "ImvdbVideos");

            migrationBuilder.DropColumn(
                name: "QueryId1",
                table: "ImvdbVideoCandidates");

            migrationBuilder.DropColumn(
                name: "CreatedAt",
                table: "ImvdbVideoArtist");

            migrationBuilder.DropColumn(
                name: "Id",
                table: "ImvdbVideoArtist");

            migrationBuilder.DropColumn(
                name: "IsActive",
                table: "ImvdbVideoArtist");

            migrationBuilder.DropColumn(
                name: "UpdatedAt",
                table: "ImvdbVideoArtist");

            migrationBuilder.RenameColumn(
                name: "Name",
                table: "MbTags",
                newName: "Tag");

            migrationBuilder.RenameIndex(
                name: "IX_MbTags_Name",
                table: "MbTags",
                newName: "IX_MbTags_Tag");

            migrationBuilder.RenameColumn(
                name: "ReleaseDate",
                table: "MbReleases",
                newName: "Date");

            migrationBuilder.RenameColumn(
                name: "DurationMs",
                table: "MbRecordings",
                newName: "LengthMs");

            migrationBuilder.AlterColumn<int>(
                name: "Count",
                table: "MbTags",
                type: "INTEGER",
                nullable: true,
                oldClrType: typeof(int),
                oldType: "INTEGER");
        }
    }
}
