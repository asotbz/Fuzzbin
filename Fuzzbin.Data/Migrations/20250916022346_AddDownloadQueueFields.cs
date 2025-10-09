using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Fuzzbin.Data.Migrations
{
    /// <inheritdoc />
    public partial class AddDownloadQueueFields : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.RenameColumn(
                name: "StartedAt",
                table: "DownloadQueues",
                newName: "StartedDate");

            migrationBuilder.RenameColumn(
                name: "CompletedAt",
                table: "DownloadQueues",
                newName: "OutputPath");

            migrationBuilder.AlterColumn<double>(
                name: "Progress",
                table: "DownloadQueues",
                type: "REAL",
                nullable: false,
                oldClrType: typeof(int),
                oldType: "INTEGER");

            migrationBuilder.AddColumn<DateTime>(
                name: "AddedDate",
                table: "DownloadQueues",
                type: "TEXT",
                nullable: false,
                defaultValue: new DateTime(1, 1, 1, 0, 0, 0, 0, DateTimeKind.Unspecified));

            migrationBuilder.AddColumn<DateTime>(
                name: "CompletedDate",
                table: "DownloadQueues",
                type: "TEXT",
                nullable: true);

            migrationBuilder.AddColumn<DateTime>(
                name: "DeletedDate",
                table: "DownloadQueues",
                type: "TEXT",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "DownloadSpeed",
                table: "DownloadQueues",
                type: "TEXT",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "ETA",
                table: "DownloadQueues",
                type: "TEXT",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "Format",
                table: "DownloadQueues",
                type: "TEXT",
                nullable: true);

            migrationBuilder.AddColumn<bool>(
                name: "IsDeleted",
                table: "DownloadQueues",
                type: "INTEGER",
                nullable: false,
                defaultValue: false);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "AddedDate",
                table: "DownloadQueues");

            migrationBuilder.DropColumn(
                name: "CompletedDate",
                table: "DownloadQueues");

            migrationBuilder.DropColumn(
                name: "DeletedDate",
                table: "DownloadQueues");

            migrationBuilder.DropColumn(
                name: "DownloadSpeed",
                table: "DownloadQueues");

            migrationBuilder.DropColumn(
                name: "ETA",
                table: "DownloadQueues");

            migrationBuilder.DropColumn(
                name: "Format",
                table: "DownloadQueues");

            migrationBuilder.DropColumn(
                name: "IsDeleted",
                table: "DownloadQueues");

            migrationBuilder.RenameColumn(
                name: "StartedDate",
                table: "DownloadQueues",
                newName: "StartedAt");

            migrationBuilder.RenameColumn(
                name: "OutputPath",
                table: "DownloadQueues",
                newName: "CompletedAt");

            migrationBuilder.AlterColumn<int>(
                name: "Progress",
                table: "DownloadQueues",
                type: "INTEGER",
                nullable: false,
                oldClrType: typeof(double),
                oldType: "REAL");
        }
    }
}
